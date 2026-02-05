"""Executor - Execute plan steps with verification and replanning."""

import asyncio
import json
import re
import time
from typing import List, Dict, Any, Optional, Tuple
from langchain_core.prompts import ChatPromptTemplate

from llm import get_llm
from schemas import ToolCall, StepResult, StepStatus
from tools import execute_tool, get_tools_description
from observability import get_langfuse_handler
from db.tracker import ExecutionTracker

# Maximum retries per step
MAX_STEP_RETRIES = 2
# Maximum replans allowed
MAX_REPLANS = 2


VERIFY_STEP_PROMPT = """You are verifying the output of a tool execution in an AI Operations workflow.

Step executed:
- Tool: {tool_name}
- Params: {params}
- Output: {output}
- Error: {error}

Original user goal: {user_goal}

Analyze this result:
1. Did the tool execute successfully?
2. Is the output useful for the user's goal?
3. Are there any issues that need addressing?

Respond with JSON only:
{{
  "is_valid": true/false,
  "reason": "brief explanation",
  "can_continue": true/false,
  "suggestion": "what to do if invalid (optional)"
}}
"""

REPLAN_PROMPT = """You are replanning an AI Operations workflow after a step failed or returned invalid results.

Original user goal: {user_goal}
Original plan: {original_plan}

Execution so far:
{execution_history}

Failed/Invalid step:
- Step ID: {failed_step_id}
- Tool: {failed_tool}
- Error/Issue: {issue}

Available tools:
{tools}

Create a NEW plan for the remaining work. Consider:
1. Can we retry with different parameters?
2. Is there an alternative approach?
3. Should we skip this step and continue?

Respond with JSON only:
{{
  "action": "retry" | "alternative" | "skip" | "abort",
  "reason": "why this action",
  "new_steps": [
    {{"step_id": "r1", "tool": "tool_name", "params": {{}}}}
  ]
}}
"""


class StepVerifier:
    """Verifies step outputs using LLM."""
    
    def __init__(self, user_id: str = None, task_id: str = None):
        self.user_id = user_id
        self.task_id = task_id
        self._llm = None
    
    def _get_llm(self):
        if self._llm is None:
            callbacks = []
            handler = get_langfuse_handler(self.user_id, self.task_id)
            if handler:
                callbacks.append(handler)
            
            # Use LLM Factory - provider configured via .env
            self._llm = get_llm(callbacks=callbacks)
        return self._llm
    
    async def verify(
        self, 
        step: dict, 
        result: StepResult, 
        user_goal: str
    ) -> Tuple[bool, str, bool]:
        """
        Verify step output.
        Returns: (is_valid, reason, can_continue)
        """
        # Quick check: if tool completely failed, no need for LLM
        if result.status == StepStatus.FAILED and not result.output:
            return False, f"Tool failed: {result.error}", False
        
        template = ChatPromptTemplate.from_template(VERIFY_STEP_PROMPT)
        chain = template | self._get_llm()
        
        try:
            response = await chain.ainvoke({
                "tool_name": step["tool"],
                "params": json.dumps(step.get("params", {})),
                "output": json.dumps(result.output) if result.output else "None",
                "error": result.error or "None",
                "user_goal": user_goal,
            })
            
            verdict = json.loads(response.content)
            return (
                verdict.get("is_valid", False),
                verdict.get("reason", ""),
                verdict.get("can_continue", False),
            )
        except Exception as e:
            # On verification error, assume valid if step succeeded
            return result.status == StepStatus.SUCCESS, str(e), True


class Replanner:
    """Replans workflow when steps fail."""
    
    def __init__(self, user_id: str = None, task_id: str = None):
        self.user_id = user_id
        self.task_id = task_id
        self._llm = None
    
    def _get_llm(self):
        if self._llm is None:
            callbacks = []
            handler = get_langfuse_handler(self.user_id, self.task_id)
            if handler:
                callbacks.append(handler)
            
            # Use LLM Factory - provider configured via .env
            self._llm = get_llm(callbacks=callbacks)
        return self._llm
    
    async def replan(
        self,
        user_goal: str,
        original_plan: dict,
        execution_history: List[dict],
        failed_step: dict,
        issue: str,
    ) -> Optional[dict]:
        """
        Generate a new plan after failure.
        Returns: {action, reason, new_steps} or None on error
        """
        template = ChatPromptTemplate.from_template(REPLAN_PROMPT)
        chain = template | self._get_llm()
        
        # Format execution history
        history_str = "\n".join([
            f"- {h['step_id']}: {h['status']} - {h.get('summary', '')}"
            for h in execution_history
        ])
        
        try:
            response = await chain.ainvoke({
                "user_goal": user_goal,
                "original_plan": json.dumps(original_plan, indent=2),
                "execution_history": history_str or "No steps executed yet",
                "failed_step_id": failed_step.get("step_id", "unknown"),
                "failed_tool": failed_step.get("tool", "unknown"),
                "issue": issue,
                "tools": get_tools_description(),
            })
            
            return json.loads(response.content)
        except Exception as e:
            return {"action": "abort", "reason": str(e), "new_steps": []}


def inject_results(step: dict, previous_results: Dict[str, Any]) -> dict:
    """
    Replace RESULT_FROM_sX placeholders with actual values.
    Example: RESULT_FROM_s1.owner -> actual owner value from s1 result
    """
    step_copy = json.loads(json.dumps(step))  # Deep copy
    params = step_copy.get("params", {})
    
    for key, value in params.items():
        if isinstance(value, str) and "RESULT_FROM_" in value:
            # Parse: RESULT_FROM_s1.field or RESULT_FROM_s1[0].field
            match = re.match(r"RESULT_FROM_(\w+)(?:\[(\d+)\])?\.?(.+)?", value)
            if match:
                step_id, index, field_path = match.groups()
                
                if step_id in previous_results:
                    result_data = previous_results[step_id]
                    
                    # Handle array index
                    if index is not None and isinstance(result_data, list):
                        idx = int(index)
                        if idx < len(result_data):
                            result_data = result_data[idx]
                    
                    # Handle field path (e.g., "owner" or "repo.name")
                    if field_path:
                        for part in field_path.split("."):
                            if isinstance(result_data, dict):
                                result_data = result_data.get(part)
                            else:
                                break
                    
                    params[key] = result_data
    
    step_copy["params"] = params
    return step_copy


async def execute_step(step: dict, previous_results: Dict[str, Any]) -> StepResult:
    """Execute a single plan step with result injection."""
    start = time.time()
    
    # Inject results from previous steps
    resolved_step = inject_results(step, previous_results)
    
    tool_call = ToolCall(
        tool_name=resolved_step["tool"],
        params=resolved_step.get("params", {}),
    )
    
    result = await execute_tool(tool_call)
    latency = int((time.time() - start) * 1000)
    
    if result.success:
        return StepResult(
            step_id=step["step_id"],
            status=StepStatus.SUCCESS,
            output=result.data,
            latency_ms=latency,
        )
    else:
        return StepResult(
            step_id=step["step_id"],
            status=StepStatus.FAILED,
            error=result.error,
            latency_ms=latency,
        )


async def execute_plan_with_verification(
    steps: List[dict],
    user_goal: str,
    original_plan: dict,
    user_id: str = None,
    task_id: str = None,
    tracker: ExecutionTracker = None,
) -> Tuple[List[StepResult], Dict[str, Any]]:
    """
    Execute plan with step verification and replanning.
    Returns: (results, execution_metadata)
    """
    verifier = StepVerifier(user_id, task_id)
    replanner = Replanner(user_id, task_id)
    
    # Create tracker if not provided
    if tracker is None and user_id and task_id:
        tracker = ExecutionTracker(user_id, task_id)
    
    results: List[StepResult] = []
    previous_results: Dict[str, Any] = {}
    execution_history: List[dict] = []
    replan_count = 0
    total_start = time.time()
    
    current_steps = list(steps)
    step_index = 0
    
    while step_index < len(current_steps):
        step = current_steps[step_index]
        step_retries = 0
        step_success = False
        
        while step_retries <= MAX_STEP_RETRIES and not step_success:
            # Log step start
            if tracker:
                await tracker.log_step_start(
                    step["step_id"], 
                    step["tool"], 
                    step.get("params", {})
                )
            
            step_start = time.time()
            
            # Execute step
            result = await execute_step(step, previous_results)
            
            step_latency = int((time.time() - step_start) * 1000)
            
            # Log step completion
            if tracker:
                await tracker.log_step_complete(
                    step_id=step["step_id"],
                    tool_name=step["tool"],
                    output=result.output,
                    latency_ms=step_latency,
                    success=result.status == StepStatus.SUCCESS,
                    error=result.error,
                )
            
            # Verify step output
            verify_start = time.time()
            is_valid, reason, can_continue = await verifier.verify(
                step, result, user_goal
            )
            verify_latency = int((time.time() - verify_start) * 1000)
            
            # Log verification
            if tracker:
                await tracker.log_verification(
                    step_id=step["step_id"],
                    is_valid=is_valid,
                    reason=reason,
                    can_continue=can_continue,
                    latency_ms=verify_latency,
                )
            
            if is_valid:
                step_success = True
                results.append(result)
                
                # Store result for dependent steps
                if result.output:
                    previous_results[step["step_id"]] = result.output
                
                execution_history.append({
                    "step_id": step["step_id"],
                    "status": "success",
                    "summary": f"Completed {step['tool']}",
                })
            else:
                step_retries += 1
                
                if step_retries <= MAX_STEP_RETRIES:
                    # Simple retry
                    await asyncio.sleep(1)  # Brief pause before retry
                    continue
                
                # Max retries exhausted - try replanning
                if replan_count < MAX_REPLANS:
                    replan_start = time.time()
                    replan_result = await replanner.replan(
                        user_goal=user_goal,
                        original_plan=original_plan,
                        execution_history=execution_history,
                        failed_step=step,
                        issue=reason,
                    )
                    replan_latency = int((time.time() - replan_start) * 1000)
                    
                    if replan_result:
                        action = replan_result.get("action", "abort")
                        
                        # Log replan decision
                        if tracker:
                            await tracker.log_replan(
                                failed_step_id=step["step_id"],
                                action=action,
                                reason=replan_result.get("reason", ""),
                                new_steps=replan_result.get("new_steps", []),
                                latency_ms=replan_latency,
                            )
                        
                        if action == "retry" and replan_result.get("new_steps"):
                            # Replace current step with new approach
                            new_steps = replan_result["new_steps"]
                            current_steps = (
                                current_steps[:step_index] + 
                                new_steps + 
                                current_steps[step_index + 1:]
                            )
                            replan_count += 1
                            step_retries = 0  # Reset for new step
                            step = current_steps[step_index]
                            continue
                        
                        elif action == "skip":
                            # Skip this step and continue
                            execution_history.append({
                                "step_id": step["step_id"],
                                "status": "skipped",
                                "summary": replan_result.get("reason", "Skipped"),
                            })
                            results.append(StepResult(
                                step_id=step["step_id"],
                                status=StepStatus.SKIPPED,
                                error=f"Skipped: {replan_result.get('reason', '')}",
                            ))
                            step_success = True  # Move to next
                            continue
                        
                        elif action == "alternative" and replan_result.get("new_steps"):
                            # Use alternative steps
                            new_steps = replan_result["new_steps"]
                            current_steps = (
                                current_steps[:step_index] + 
                                new_steps + 
                                current_steps[step_index + 1:]
                            )
                            replan_count += 1
                            step_retries = 0
                            step = current_steps[step_index]
                            continue
                
                # Abort - record failure and stop
                results.append(result)
                execution_history.append({
                    "step_id": step["step_id"],
                    "status": "failed",
                    "summary": reason,
                })
                
                total_latency = int((time.time() - total_start) * 1000)
                successful = sum(1 for r in results if r.status == StepStatus.SUCCESS)
                
                # Log completion (failed)
                if tracker:
                    await tracker.log_completion(
                        final_output={},
                        confidence=0.0,
                        total_steps=len(results),
                        successful_steps=successful,
                        replan_count=replan_count,
                        total_latency_ms=total_latency,
                    )
                
                return results, {
                    "completed": False,
                    "failed_at": step["step_id"],
                    "replan_count": replan_count,
                    "reason": reason,
                    "total_latency_ms": total_latency,
                }
        
        step_index += 1
    
    total_latency = int((time.time() - total_start) * 1000)
    successful = sum(1 for r in results if r.status == StepStatus.SUCCESS)
    confidence = successful / len(results) if results else 0.0
    
    # Log completion (success)
    if tracker:
        await tracker.log_completion(
            final_output={r.step_id: r.output for r in results if r.output},
            confidence=confidence,
            total_steps=len(results),
            successful_steps=successful,
            replan_count=replan_count,
            total_latency_ms=total_latency,
        )
    
    return results, {
        "completed": True,
        "steps_executed": len(results),
        "successful_steps": successful,
        "replan_count": replan_count,
        "total_latency_ms": total_latency,
    }


async def executor_node(state: dict) -> dict:
    """LangGraph node for execution with verification and replanning."""
    if not state.get("plan_valid"):
        return state
    
    plan = state.get("plan", {})
    steps = plan.get("steps", [])
    user_goal = state.get("prompt", "")
    
    results, metadata = await execute_plan_with_verification(
        steps=steps,
        user_goal=user_goal,
        original_plan=plan,
        user_id=state.get("user_id"),
        task_id=state.get("task_id"),
    )
    
    return {
        **state,
        "results": [r.model_dump() for r in results],
        "execution_metadata": metadata,
    }
