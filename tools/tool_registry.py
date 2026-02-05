"""Tool registry - Available tools for planner."""

from typing import Dict, List
from tools.github_tools import github_tools
from schemas import ToolCall, ToolResult


# Tool definitions for LLM planner
AVAILABLE_TOOLS: List[Dict] = [
    {
        "name": "github_list_my_repos",
        "description": "List repositories for the connected GitHub account (use when user asks about 'my repos', 'my repositories', or which repos they have access to)",
        "params": ["limit?", "sort?"],
    },
    {
        "name": "github_get_repo",
        "description": "Get repository information (stars, description, language)",
        "params": ["owner", "repo"],
    },
    {
        "name": "github_search_repos",
        "description": "Search repositories by query",
        "params": ["query", "limit?"],
    },
    {
        "name": "github_get_file",
        "description": "Get file content from repository",
        "params": ["owner", "repo", "path"],
    },
    {
        "name": "github_list_files",
        "description": "List files in repository directory",
        "params": ["owner", "repo", "path?"],
    },
    {
        "name": "github_create_issue",
        "description": "Create a new issue in repository",
        "params": ["owner", "repo", "title", "body?"],
    },
    {
        "name": "github_list_issues",
        "description": "List issues in repository",
        "params": ["owner", "repo", "state?", "limit?"],
    },
]


def get_tools_description() -> str:
    """Format tools for LLM prompt."""
    lines = ["Available tools:"]
    for t in AVAILABLE_TOOLS:
        params = ", ".join(t["params"])
        lines.append(f"- {t['name']}({params}): {t['description']}")
    return "\n".join(lines)


async def execute_tool(tool_call: ToolCall) -> ToolResult:
    """Execute a tool call."""
    return await github_tools.execute(tool_call.tool_name, tool_call.params)
