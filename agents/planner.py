"""Planner - LLM generates JSON execution plan with streaming."""

import json
import logging
import re
from typing import AsyncGenerator
from langchain_core.prompts import ChatPromptTemplate

from llm import get_llm
from tools import get_tools_description
from observability import get_langfuse_handler
from db.tracker import ExecutionTracker

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> str:
    """Strip markdown fences like ```json ... ``` or ``` ... ``` and return raw JSON string."""
    if not text:
        return ""
    stripped = text.strip()
    # Match ```json or ``` then capture until closing ``` (no $ so trailing whitespace is ok)
    m = re.search(r"```(?:json)?\s*\n?(.*?)```", stripped, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return stripped


PLANNER_PROMPT = """You are an expert AI Operations planner for an assistant that acts on the user's GitHub account via an access token. Your job is to decompose user requests into executable tool-based plans.

**Context**: Tasks are performed against repositories available to the connected GitHub account. Use `github_list_my_repos` when the user asks about "my repos", "my repositories", or to discover which repos they can work with. For repo-specific tasks, use owner/repo from that list or from the user's message.

## Available Tools
{tools}

## Chain-of-Thought Planning Process

Follow this reasoning framework EXACTLY:

**Step 1 - Intent Analysis**: What is the user trying to achieve? What is the end goal?
**Step 2 - Information Mapping**: What data/information is needed? Which tools provide this?
**Step 3 - Dependency Analysis**: Which steps need outputs from previous steps? What can run in parallel?
**Step 4 - Risk Assessment**: What could go wrong? Are there any missing parameters?
**Step 5 - Plan Construction**: Build the minimal, ordered sequence of tool calls.

## Few-Shot Examples

### Example 1: Simple Single-Step Task
User: "How many stars does the fastapi repository have?"

Reasoning:
- Intent: User wants star count for a specific repository
- Information needed: Repository metadata (stars)
- Tools required: github_get_repo (provides stars, description, language)
- Dependencies: None - single step task
- Risk: Need to identify owner. FastAPI is owned by "tiangolo"

Output:
```json
{{
  "thinking": "User wants star count for FastAPI repo. FastAPI is owned by tiangolo. Single call to github_get_repo will return stars in the response.",
  "steps": [
    {{"step_id": "s1", "tool": "github_get_repo", "params": {{"owner": "tiangolo", "repo": "fastapi"}}}}
  ]
}}
```

### Example 2: Multi-Step with Dependencies
User: "Find the top 3 Python ML repos and check if they have open issues"

Reasoning:
- Intent: Discover popular ML repos, then analyze their issue status
- Information needed: (1) Search results for ML repos, (2) Issues for each repo
- Tools required: github_search_repos → github_list_issues (for each result)
- Dependencies: Issue listing depends on search results (need owner/repo)
- Risk: Search might return repos with different owners; must handle each

Output:
```json
{{
  "thinking": "First search for Python ML repositories with limit 3. Then for each result, list their open issues. The issue queries depend on search completing first to get repo names.",
  "steps": [
    {{"step_id": "s1", "tool": "github_search_repos", "params": {{"query": "machine learning language:python", "limit": 3}}}},
    {{"step_id": "s2", "tool": "github_list_issues", "params": {{"owner": "RESULT_FROM_s1[0].owner", "repo": "RESULT_FROM_s1[0].name", "state": "open", "limit": 5}}, "depends_on": ["s1"]}},
    {{"step_id": "s3", "tool": "github_list_issues", "params": {{"owner": "RESULT_FROM_s1[1].owner", "repo": "RESULT_FROM_s1[1].name", "state": "open", "limit": 5}}, "depends_on": ["s1"]}},
    {{"step_id": "s4", "tool": "github_list_issues", "params": {{"owner": "RESULT_FROM_s1[2].owner", "repo": "RESULT_FROM_s1[2].name", "state": "open", "limit": 5}}, "depends_on": ["s1"]}}
  ]
}}
```

### Example 3: Complex Analysis Task
User: "Analyze the langchain repo - get its README, check recent issues, and list the main source files"

Reasoning:
- Intent: Comprehensive repo analysis covering docs, issues, and structure
- Information needed: (1) README content, (2) Issue list, (3) Directory listing
- Tools required: github_get_file, github_list_issues, github_list_files
- Dependencies: None between tasks - all can reference langchain-ai/langchain directly
- Risk: README might be README.md or readme.rst; use standard README.md

Output:
```json
{{
  "thinking": "User wants comprehensive analysis of langchain repo. Three independent data points needed: README for docs, issues for activity, and file listing for structure. All steps can run in parallel since they don't depend on each other - just need the known owner (langchain-ai) and repo (langchain).",
  "steps": [
    {{"step_id": "s1", "tool": "github_get_file", "params": {{"owner": "langchain-ai", "repo": "langchain", "path": "README.md"}}}},
    {{"step_id": "s2", "tool": "github_list_issues", "params": {{"owner": "langchain-ai", "repo": "langchain", "state": "open", "limit": 10}}}},
    {{"step_id": "s3", "tool": "github_list_files", "params": {{"owner": "langchain-ai", "repo": "langchain", "path": "libs/langchain"}}}}
  ]
}}
```

---

## Your Task

User request: {prompt}
Additional context: {context}

Now apply the Chain-of-Thought process and generate your plan. Respond with ONLY valid JSON in this exact format:
```json
{{
  "thinking": "Your detailed reasoning following the 5-step framework above",
  "steps": [
    {{"step_id": "s1", "tool": "tool_name", "params": {{"param": "value"}}}},
    {{"step_id": "s2", "tool": "tool_name", "params": {{}}, "depends_on": ["s1"]}}
  ]
}}
```
"""


async def generate_plan_stream(
    prompt: str, 
    context: dict = None,
    user_id: str = None,
    task_id: str = None,
) -> AsyncGenerator[str, None]:
    """Generate plan with streaming output."""
    
    callbacks = []
    handler = get_langfuse_handler(user_id, task_id) if user_id else None
    if handler:
        callbacks.append(handler)
    
    # Use LLM Factory - provider configured via .env
    llm = get_llm(streaming=True, callbacks=callbacks)
    
    template = ChatPromptTemplate.from_template(PLANNER_PROMPT)
    chain = template | llm
    
    full_response = ""
    async for chunk in chain.astream({
        "tools": get_tools_description(),
        "prompt": prompt,
        "context": json.dumps(context or {}),
    }):
        content = chunk.content if hasattr(chunk, 'content') else str(chunk)
        full_response += content
        yield content
    
    clean = _extract_json(full_response)
    yield f"\n__DONE__{clean}"


async def generate_plan(prompt: str, context: dict = None, user_id: str = None, task_id: str = None) -> dict:
    """Generate execution plan (non-streaming)."""
    
    callbacks = []
    handler = get_langfuse_handler(user_id, task_id) if user_id else None
    if handler:
        callbacks.append(handler)
    
    # Use LLM Factory - provider configured via .env
    llm = get_llm(callbacks=callbacks)
    
    template = ChatPromptTemplate.from_template(PLANNER_PROMPT)
    chain = template | llm
    
    response = await chain.ainvoke({
        "tools": get_tools_description(),
        "prompt": prompt,
        "context": json.dumps(context or {}),
    })
    
    try:
        clean = _extract_json(response.content)
        plan = json.loads(clean)
        return {"success": True, "plan": plan}
    except json.JSONDecodeError:
        logger.error("Planner returned invalid JSON. Raw response: %s", response.content)
        return {"success": False, "error": "Invalid JSON from LLM", "raw": response.content}


async def planner_node(state: dict) -> dict:
    """LangGraph node for planning."""
    if not state.get("guardrails_passed"):
        return state
    
    result = await generate_plan(
        state["prompt"], 
        state.get("context"),
        state.get("user_id"),
        state.get("task_id"),
    )
    
    if result["success"]:
        return {
            **state,
            "plan": result["plan"],
            "plan_valid": True,
            "thinking": result["plan"].get("thinking", ""),
        }
    else:
        # Log the planning failure so it appears in execution logs
        user_id = state.get("user_id")
        task_id = state.get("task_id")
        if user_id and task_id:
            try:
                tracker = ExecutionTracker(user_id, task_id)
                await tracker.log_event(
                    event_type="planning",
                    event_name="plan_failed",
                    success=False,
                    error_message=result.get("error"),
                    llm_response=result.get("raw"),
                )
            except Exception as e:
                logger.error("Failed to log planning error: %s", e)
        return {
            **state,
            "plan_valid": False,
            "errors": state.get("errors", []) + [result["error"]],
        }
