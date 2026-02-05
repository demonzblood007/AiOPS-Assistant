"""Task schemas - Input, Status, Result with user isolation."""

import hashlib
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskInput(BaseModel):
    """What user submits."""
    user_id: str
    prompt: str = Field(..., min_length=1, max_length=4000)
    context: Optional[Dict[str, Any]] = None  # repo, branch, etc.
    priority: str = Field(default="default", pattern="^(low|default|high)$")
    
    def generate_task_id(self) -> str:
        """Generate unique task_id scoped to user."""
        payload = f"{self.user_id}:{self.prompt}:{datetime.utcnow().isoformat()}"
        return hashlib.sha256(payload.encode()).hexdigest()[:12]


class TaskResult(BaseModel):
    """What user receives."""
    user_id: str
    task_id: str
    status: TaskStatus
    result: Optional[Dict[str, Any]] = None
    artifacts: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    @property
    def redis_key(self) -> str:
        """Isolated Redis key per user."""
        return f"task:{self.user_id}:{self.task_id}"
