"""FastAPI routes for task management."""

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse

from schemas import TaskInput, TaskResult
from task_queue.tasks import enqueue_task, get_task_result
from agents.planner import generate_plan_stream
from agents.guardrails import validate_input
from observability import get_trace_url
from db import get_db, get_user_tasks, get_task_stats, get_execution_logs, AsyncSession


router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("/", response_model=dict)
async def create_task(task: TaskInput):
    """Submit a new task for async processing."""
    task_id = enqueue_task(task)
    
    return {
        "user_id": task.user_id,
        "task_id": task_id,
        "status": "pending",
        "message": "Task queued for processing",
        "trace_url": get_trace_url(task_id),
    }


@router.get("/{task_id}", response_model=TaskResult)
async def get_task(
    task_id: str,
    user_id: str = Query(..., description="User ID for task isolation"),
):
    """Get task status and result."""
    result = get_task_result(user_id, task_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return result


@router.get("/history/{user_id}")
async def get_history(
    user_id: str,
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get task history for a user."""
    tasks = await get_user_tasks(db, user_id, limit)
    return {"tasks": [t.to_dict() for t in tasks]}


@router.get("/stats/{user_id}")
async def get_stats(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get task statistics for a user."""
    stats = await get_task_stats(db, user_id)
    return stats


@router.get("/logs/{task_id}")
async def get_task_logs(
    task_id: str,
    user_id: str = Query(..., description="User ID for task isolation"),
):
    """
    Get detailed execution logs for a task.
    Shows every step, decision, and event that occurred.
    """
    logs = await get_execution_logs(user_id, task_id)
    
    if not logs:
        raise HTTPException(status_code=404, detail="No logs found for this task")
    
    # Group logs by event type for better visualization
    summary = {
        "total_events": len(logs),
        "event_types": {},
        "timeline": logs,
    }
    
    for log in logs:
        event_type = log["event_type"]
        if event_type not in summary["event_types"]:
            summary["event_types"][event_type] = 0
        summary["event_types"][event_type] += 1
    
    return summary


@router.post("/stream")
async def stream_task(task: TaskInput):
    """Execute task with streaming response."""
    passed, issues = validate_input(task.prompt)
    if not passed:
        raise HTTPException(status_code=400, detail={"errors": issues})
    
    task_id = task.generate_task_id()
    
    async def event_stream():
        yield f"data: {{'event': 'start', 'task_id': '{task_id}'}}\n\n"
        yield f"data: {{'event': 'planning', 'status': 'LLM is thinking...'}}\n\n"
        
        async for chunk in generate_plan_stream(
            task.prompt, 
            task.context,
            task.user_id,
            task_id,
        ):
            if chunk.startswith("__DONE__"):
                full = chunk.replace("__DONE__", "")
                yield f"data: {{'event': 'plan_complete', 'plan': {full}}}\n\n"
            else:
                safe = chunk.replace('"', '\\"').replace('\n', '\\n')
                yield f"data: {{'event': 'chunk', 'content': \"{safe}\"}}\n\n"
        
        trace_url = get_trace_url(task_id)
        yield f"data: {{'event': 'done', 'trace_url': '{trace_url or ''}'}}\n\n"
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")
