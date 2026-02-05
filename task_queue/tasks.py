"""RQ task definitions with database persistence."""

import asyncio
from datetime import datetime
from redis import Redis
from rq import Queue
from config import settings
from schemas import TaskInput, TaskResult, TaskStatus
from agents import agent_workflow
from db.database import async_session
from db.models import Task


# Single persistent loop for the worker to avoid "event loop is closed" on Windows
_worker_loop = asyncio.new_event_loop()


def _run_async(coro):
    """Run an async coroutine on the worker loop (Windows-safe, no per-call close)."""
    global _worker_loop
    if _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
    try:
        return _worker_loop.run_until_complete(coro)
    except RuntimeError:
        # If loop is already running, create a new one just for this call
        temp_loop = asyncio.new_event_loop()
        try:
            return temp_loop.run_until_complete(coro)
        finally:
            temp_loop.close()


# Redis connection
redis_conn = Redis.from_url(settings.redis_url)

# Task queues
high_queue = Queue("high", connection=redis_conn)
default_queue = Queue("default", connection=redis_conn)
low_queue = Queue("low", connection=redis_conn)


def get_queue(priority: str) -> Queue:
    queues = {"high": high_queue, "default": default_queue, "low": low_queue}
    return queues.get(priority, default_queue)


async def _save_to_db(user_id: str, task_id: str, prompt: str, context: dict, status: str, **kwargs):
    """Save task to database."""
    async with async_session() as db:
        # Check if exists
        from sqlalchemy import select
        result = await db.execute(
            select(Task).where(Task.user_id == user_id, Task.task_id == task_id)
        )
        task = result.scalar_one_or_none()
        
        if task:
            # Update existing
            for key, value in kwargs.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            task.status = status
        else:
            # Create new
            task = Task(
                user_id=user_id,
                task_id=task_id,
                prompt=prompt,
                context=context or {},
                status=status,
                created_at=datetime.utcnow(),
                **kwargs,
            )
            db.add(task)
        
        await db.commit()


def process_task(user_id: str, task_id: str, prompt: str, context: dict = None) -> dict:
    """Process a task through the agent workflow."""
    
    # Save to DB as started
    _run_async(_save_to_db(user_id, task_id, prompt, context, "planning", started_at=datetime.utcnow()))
    
    # Build initial state
    initial_state = {
        "user_id": user_id,
        "task_id": task_id,
        "prompt": prompt,
        "context": context or {},
        "guardrails_passed": False,
        "plan": None,
        "plan_valid": False,
        "results": [],
        "final_output": None,
        "confidence": 0.0,
        "errors": [],
    }
    
    # Run workflow
    final_state = _run_async(agent_workflow.ainvoke(initial_state))
    
    # Determine status
    status = TaskStatus.COMPLETED if final_state.get("confidence", 0) > 0 else TaskStatus.FAILED
    
    # Build result
    result = TaskResult(
        user_id=user_id,
        task_id=task_id,
        status=status,
        result=final_state.get("final_output"),
        errors=final_state.get("errors", []),
        completed_at=datetime.utcnow(),
    )
    
    # Save to Redis (cache)
    redis_conn.setex(result.redis_key, settings.task_timeout, result.model_dump_json())
    
    # Save to DB (permanent)
    _run_async(_save_to_db(
        user_id, task_id, prompt, context,
        status.value,
        plan=final_state.get("plan"),
        results=final_state.get("results"),
        final_output=final_state.get("final_output"),
        confidence=final_state.get("confidence", 0),
        errors=final_state.get("errors", []),
        completed_at=datetime.utcnow(),
    ))
    
    return result.model_dump()


async def enqueue_task(task_input: TaskInput) -> str:
    """Enqueue a task for processing (async-friendly, no nested asyncio.run)."""
    task_id = task_input.generate_task_id()
    queue = get_queue(task_input.priority)
    
    # Store initial status in Redis
    initial = TaskResult(user_id=task_input.user_id, task_id=task_id, status=TaskStatus.PENDING)
    redis_conn.setex(initial.redis_key, settings.task_timeout, initial.model_dump_json())
    
    # Save to DB (schedule in current loop)
    asyncio.create_task(_save_to_db(task_input.user_id, task_id, task_input.prompt, task_input.context, "pending"))
    
    # Enqueue job (RQ is sync)
    queue.enqueue(
        process_task,
        task_input.user_id,
        task_id,
        task_input.prompt,
        task_input.context,
        # RQ job ids cannot contain ":" — use a safe separator
        job_id=f"{task_input.user_id}-{task_id}",
    )
    
    return task_id


async def get_task_result(user_id: str, task_id: str) -> TaskResult | None:
    """Get task result from Redis (fast) or DB (fallback)."""
    key = f"task:{user_id}:{task_id}"
    data = redis_conn.get(key)
    
    if data:
        return TaskResult.model_validate_json(data)
    
    # Fallback to DB
    async with async_session() as db:
        from sqlalchemy import select
        result = await db.execute(
            select(Task).where(Task.user_id == user_id, Task.task_id == task_id)
        )
        task = result.scalar_one_or_none()
        if task:
            return TaskResult(
                user_id=task.user_id,
                task_id=task.task_id,
                status=TaskStatus(task.status),
                result=task.final_output,
                errors=task.errors or [],
                completed_at=task.completed_at,
            )
        return None
