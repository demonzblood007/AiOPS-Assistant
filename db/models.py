"""SQLAlchemy models for persistent storage."""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Float, Integer, JSON, Text, Index, ForeignKeyConstraint
from db.database import Base
from schemas.task import TaskStatus


class Task(Base):
    """Task history and audit trail."""
    
    __tablename__ = "tasks"
    
    # Primary key (composite)
    user_id = Column(String, primary_key=True)
    task_id = Column(String, primary_key=True)
    
    # Task data
    prompt = Column(String, nullable=False)
    context = Column(JSON, default={})
    status = Column(String, default=TaskStatus.PENDING.value)
    
    # Plan and execution
    plan = Column(JSON, nullable=True)
    results = Column(JSON, default=[])
    final_output = Column(JSON, nullable=True)
    execution_metadata = Column(JSON, default={})
    
    # Metrics
    confidence = Column(Float, default=0.0)
    total_tokens = Column(Integer, default=0)
    total_api_calls = Column(Integer, default=0)
    total_latency_ms = Column(Integer, default=0)
    
    # Errors
    errors = Column(JSON, default=[])
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Indexes for common queries
    __table_args__ = (
        Index("ix_tasks_user_created", "user_id", "created_at"),
        Index("ix_tasks_status", "status"),
    )
    
    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "task_id": self.task_id,
            "prompt": self.prompt,
            "status": self.status,
            "plan": self.plan,
            "final_output": self.final_output,
            "confidence": self.confidence,
            "errors": self.errors,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class ExecutionLog(Base):
    """Granular execution log - captures every step, decision, and event."""
    
    __tablename__ = "execution_logs"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to task
    user_id = Column(String, nullable=False)
    task_id = Column(String, nullable=False)
    
    # Event identification
    event_type = Column(String, nullable=False)  # guardrails, planning, step_start, step_complete, verify, replan, error
    event_name = Column(String, nullable=False)  # Human readable name
    sequence = Column(Integer, nullable=False)   # Order of events
    
    # Event data
    step_id = Column(String, nullable=True)      # For step-related events
    input_data = Column(JSON, default={})        # What went into this event
    output_data = Column(JSON, default={})       # What came out
    
    # LLM specific
    llm_prompt = Column(Text, nullable=True)     # The prompt sent to LLM
    llm_response = Column(Text, nullable=True)   # Raw LLM response
    llm_thinking = Column(Text, nullable=True)   # Chain-of-thought reasoning
    tokens_used = Column(Integer, default=0)
    
    # Decision tracking
    decision = Column(String, nullable=True)     # pass/fail/retry/replan/skip
    decision_reason = Column(Text, nullable=True)
    
    # Performance
    latency_ms = Column(Integer, default=0)
    
    # Status
    success = Column(Integer, default=1)  # 1=success, 0=failure
    error_message = Column(Text, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Foreign key constraint
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "task_id"],
            ["tasks.user_id", "tasks.task_id"],
            ondelete="CASCADE"
        ),
        Index("ix_logs_task", "user_id", "task_id"),
        Index("ix_logs_type", "event_type"),
        Index("ix_logs_sequence", "user_id", "task_id", "sequence"),
    )
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "event_name": self.event_name,
            "sequence": self.sequence,
            "step_id": self.step_id,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "llm_thinking": self.llm_thinking,
            "decision": self.decision,
            "decision_reason": self.decision_reason,
            "latency_ms": self.latency_ms,
            "success": bool(self.success),
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
