"""Tool schemas - Definitions and results."""

from typing import Any, Dict, Optional
from pydantic import BaseModel


class ToolCall(BaseModel):
    """Request to execute a tool."""
    tool_name: str
    params: Dict[str, Any] = {}


class ToolResult(BaseModel):
    """Response from tool execution."""
    tool_name: str
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    latency_ms: int = 0
