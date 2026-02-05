"""Langfuse integration for observability."""

from typing import Optional, Any
from contextlib import contextmanager
from langfuse import Langfuse
from langfuse.callback import CallbackHandler
from config import settings


# Initialize Langfuse client
langfuse: Optional[Langfuse] = None
if settings.langfuse_enabled:
    langfuse = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )


def get_langfuse_handler(user_id: str, task_id: str) -> Optional[CallbackHandler]:
    """Get Langfuse callback handler for LangChain."""
    if not settings.langfuse_enabled:
        return None
    
    return CallbackHandler(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
        user_id=user_id,
        session_id=task_id,
    )


@contextmanager
def trace_span(name: str, user_id: str, task_id: str, metadata: dict = None):
    """Context manager for tracing a span."""
    if not langfuse:
        yield None
        return
    
    trace = langfuse.trace(
        name=name,
        user_id=user_id,
        session_id=task_id,
        metadata=metadata or {},
    )
    
    try:
        yield trace
    finally:
        trace.update(status_message="completed")


def log_event(trace, name: str, data: Any):
    """Log an event to a trace."""
    if trace:
        trace.event(name=name, metadata={"data": data})


def get_trace_url(task_id: str) -> Optional[str]:
    """Get URL to view trace in Langfuse dashboard."""
    if not settings.langfuse_enabled:
        return None
    return f"{settings.langfuse_host}/sessions/{task_id}"
