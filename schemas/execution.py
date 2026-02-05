"""Execution schemas - Step results and overall state."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class StepResult(BaseModel):
    """Result of one executed step."""
    step_id: str
    status: StepStatus
    output: Optional[Any] = None
    error: Optional[str] = None
    latency_ms: int = 0


class ExecutionState(BaseModel):
    """Full state passed through LangGraph."""
    user_id: str
    task_id: str
    prompt: str
    context: Dict[str, Any] = Field(default_factory=dict)
    
    # Pipeline stages
    guardrails_passed: bool = False
    plan: Optional[Dict[str, Any]] = None
    plan_valid: bool = False
    
    # Execution
    current_step: Optional[str] = None
    results: List[StepResult] = Field(default_factory=list)
    
    # Output
    final_output: Optional[Dict[str, Any]] = None
    confidence: float = 0.0
    errors: List[str] = Field(default_factory=list)
