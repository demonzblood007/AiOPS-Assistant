"""Database repository - CRUD operations for tasks."""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Task


async def create_task(
    db: AsyncSession,
    user_id: str,
    task_id: str,
    prompt: str,
    context: dict = None,
) -> Task:
    """Create a new task record."""
    task = Task(
        user_id=user_id,
        task_id=task_id,
        prompt=prompt,
        context=context or {},
        status="pending",
        created_at=datetime.utcnow(),
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def get_task(
    db: AsyncSession,
    user_id: str,
    task_id: str,
) -> Optional[Task]:
    """Get a task by user_id and task_id."""
    result = await db.execute(
        select(Task).where(
            Task.user_id == user_id,
            Task.task_id == task_id,
        )
    )
    return result.scalar_one_or_none()


async def update_task(
    db: AsyncSession,
    user_id: str,
    task_id: str,
    **kwargs,
) -> Optional[Task]:
    """Update task fields."""
    task = await get_task(db, user_id, task_id)
    if task:
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)
        await db.commit()
        await db.refresh(task)
    return task


async def get_user_tasks(
    db: AsyncSession,
    user_id: str,
    limit: int = 20,
) -> List[Task]:
    """Get recent tasks for a user."""
    result = await db.execute(
        select(Task)
        .where(Task.user_id == user_id)
        .order_by(desc(Task.created_at))
        .limit(limit)
    )
    return result.scalars().all()


async def get_task_stats(
    db: AsyncSession,
    user_id: str,
) -> dict:
    """Get task statistics for a user."""
    tasks = await get_user_tasks(db, user_id, limit=100)
    
    if not tasks:
        return {"total": 0, "completed": 0, "failed": 0, "avg_confidence": 0}
    
    completed = sum(1 for t in tasks if t.status == "completed")
    failed = sum(1 for t in tasks if t.status == "failed")
    confidences = [t.confidence for t in tasks if t.confidence > 0]
    
    return {
        "total": len(tasks),
        "completed": completed,
        "failed": failed,
        "avg_confidence": sum(confidences) / len(confidences) if confidences else 0,
    }
