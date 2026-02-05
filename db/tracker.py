"""Execution Tracker - Logs every step and decision to database."""

import time
from datetime import datetime
from typing import Any, Dict, Optional
from contextlib import asynccontextmanager

from db.database import async_session
from db.models import ExecutionLog


class ExecutionTracker:
    """
    Tracks execution progress with granular logging.
    
    Usage:
        tracker = ExecutionTracker(user_id, task_id)
        await tracker.log_event("guardrails", "Input Validation", input_data={...})
        
        # Or use context manager for timing:
        async with tracker.track_step("s1", "get_repo") as step:
            result = await execute_tool(...)
            step.set_output(result)
    """
    
    def __init__(self, user_id: str, task_id: str):
        self.user_id = user_id
        self.task_id = task_id
        self._sequence = 0
    
    async def log_event(
        self,
        event_type: str,
        event_name: str,
        step_id: str = None,
        input_data: Dict[str, Any] = None,
        output_data: Dict[str, Any] = None,
        llm_prompt: str = None,
        llm_response: str = None,
        llm_thinking: str = None,
        tokens_used: int = 0,
        decision: str = None,
        decision_reason: str = None,
        latency_ms: int = 0,
        success: bool = True,
        error_message: str = None,
    ) -> int:
        """Log an execution event to database."""
        self._sequence += 1
        
        async with async_session() as db:
            log = ExecutionLog(
                user_id=self.user_id,
                task_id=self.task_id,
                event_type=event_type,
                event_name=event_name,
                sequence=self._sequence,
                step_id=step_id,
                input_data=input_data or {},
                output_data=output_data or {},
                llm_prompt=llm_prompt,
                llm_response=llm_response,
                llm_thinking=llm_thinking,
                tokens_used=tokens_used,
                decision=decision,
                decision_reason=decision_reason,
                latency_ms=latency_ms,
                success=1 if success else 0,
                error_message=error_message,
                created_at=datetime.utcnow(),
            )
            db.add(log)
            await db.commit()
            return log.id
    
    async def log_guardrails(
        self,
        prompt: str,
        passed: bool,
        issues: list = None,
        latency_ms: int = 0,
    ):
        """Log guardrails validation result."""
        await self.log_event(
            event_type="guardrails",
            event_name="Input Validation",
            input_data={"prompt": prompt[:500]},  # Truncate for storage
            output_data={"passed": passed, "issues": issues or []},
            decision="pass" if passed else "block",
            decision_reason="; ".join(issues) if issues else "Input validated",
            latency_ms=latency_ms,
            success=passed,
            error_message="; ".join(issues) if not passed else None,
        )
    
    async def log_planning(
        self,
        prompt: str,
        plan: dict,
        thinking: str = None,
        llm_prompt: str = None,
        llm_response: str = None,
        tokens_used: int = 0,
        latency_ms: int = 0,
        success: bool = True,
        error: str = None,
    ):
        """Log plan generation."""
        await self.log_event(
            event_type="planning",
            event_name="Plan Generation",
            input_data={"user_goal": prompt[:500]},
            output_data={"plan": plan, "step_count": len(plan.get("steps", []))},
            llm_prompt=llm_prompt,
            llm_response=llm_response,
            llm_thinking=thinking,
            tokens_used=tokens_used,
            decision="generated" if success else "failed",
            latency_ms=latency_ms,
            success=success,
            error_message=error,
        )
    
    async def log_step_start(
        self,
        step_id: str,
        tool_name: str,
        params: dict,
    ):
        """Log step execution start."""
        await self.log_event(
            event_type="step_start",
            event_name=f"Execute {tool_name}",
            step_id=step_id,
            input_data={"tool": tool_name, "params": params},
            decision="started",
        )
    
    async def log_step_complete(
        self,
        step_id: str,
        tool_name: str,
        output: Any,
        latency_ms: int,
        success: bool = True,
        error: str = None,
    ):
        """Log step execution completion."""
        await self.log_event(
            event_type="step_complete",
            event_name=f"Completed {tool_name}",
            step_id=step_id,
            output_data={"result": output} if success else {"error": error},
            decision="success" if success else "failed",
            latency_ms=latency_ms,
            success=success,
            error_message=error,
        )
    
    async def log_verification(
        self,
        step_id: str,
        is_valid: bool,
        reason: str,
        can_continue: bool,
        llm_response: str = None,
        latency_ms: int = 0,
    ):
        """Log step verification result."""
        await self.log_event(
            event_type="verify",
            event_name=f"Verify Step {step_id}",
            step_id=step_id,
            output_data={
                "is_valid": is_valid,
                "can_continue": can_continue,
            },
            llm_response=llm_response,
            decision="valid" if is_valid else "invalid",
            decision_reason=reason,
            latency_ms=latency_ms,
            success=is_valid,
        )
    
    async def log_replan(
        self,
        failed_step_id: str,
        action: str,
        reason: str,
        new_steps: list = None,
        llm_response: str = None,
        latency_ms: int = 0,
    ):
        """Log replanning decision."""
        await self.log_event(
            event_type="replan",
            event_name=f"Replan after {failed_step_id}",
            step_id=failed_step_id,
            output_data={
                "action": action,
                "new_steps": new_steps or [],
            },
            llm_response=llm_response,
            decision=action,
            decision_reason=reason,
            latency_ms=latency_ms,
            success=action != "abort",
        )
    
    async def log_completion(
        self,
        final_output: dict,
        confidence: float,
        total_steps: int,
        successful_steps: int,
        replan_count: int,
        total_latency_ms: int,
    ):
        """Log task completion."""
        await self.log_event(
            event_type="completion",
            event_name="Task Completed",
            output_data={
                "final_output": final_output,
                "confidence": confidence,
                "total_steps": total_steps,
                "successful_steps": successful_steps,
                "replan_count": replan_count,
            },
            decision="completed" if confidence > 0 else "failed",
            decision_reason=f"Confidence: {confidence:.0%}",
            latency_ms=total_latency_ms,
            success=confidence > 0,
        )
    
    @asynccontextmanager
    async def track_step(self, step_id: str, tool_name: str, params: dict):
        """
        Context manager for tracking a step's execution.
        
        Usage:
            async with tracker.track_step("s1", "get_repo", params) as step:
                result = await execute(...)
                step.set_output(result)
        """
        step_context = StepTrackingContext(self, step_id, tool_name, params)
        await self.log_step_start(step_id, tool_name, params)
        
        try:
            yield step_context
        finally:
            await self.log_step_complete(
                step_id=step_id,
                tool_name=tool_name,
                output=step_context.output,
                latency_ms=step_context.latency_ms,
                success=step_context.success,
                error=step_context.error,
            )


class StepTrackingContext:
    """Context for tracking step execution."""
    
    def __init__(self, tracker: ExecutionTracker, step_id: str, tool_name: str, params: dict):
        self.tracker = tracker
        self.step_id = step_id
        self.tool_name = tool_name
        self.params = params
        self.output = None
        self.error = None
        self.success = True
        self._start_time = time.time()
    
    @property
    def latency_ms(self) -> int:
        return int((time.time() - self._start_time) * 1000)
    
    def set_output(self, output: Any):
        self.output = output
        self.success = True
    
    def set_error(self, error: str):
        self.error = error
        self.success = False


async def get_execution_logs(user_id: str, task_id: str) -> list:
    """Retrieve all execution logs for a task."""
    async with async_session() as db:
        from sqlalchemy import select
        result = await db.execute(
            select(ExecutionLog)
            .where(ExecutionLog.user_id == user_id, ExecutionLog.task_id == task_id)
            .order_by(ExecutionLog.sequence)
        )
        logs = result.scalars().all()
        return [log.to_dict() for log in logs]
