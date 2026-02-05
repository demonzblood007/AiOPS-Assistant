"""Guardrails - Input validation for AI Ops Assistant."""

from typing import List, Tuple

# Blocked keywords - dangerous operations
BLOCKED_KEYWORDS = [
    "delete all", "drop database", "rm -rf", "force push main",
    "truncate", "delete repository", "remove repo", "format disk",
    "sudo rm", "drop table", "delete branch main", "force push"
]

# Prompt injection patterns
INJECTION_PATTERNS = [
    "ignore previous", "forget your", "you are now",
    "act as if", "pretend you", "ignore all",
    "disregard", "bypass", "override instructions"
]

# Sensitive data patterns
SENSITIVE_PATTERNS = [
    "api key", "password", "secret", "token",
    "credential", "private key", "ssh key"
]


def validate_input(prompt: str) -> Tuple[bool, List[str]]:
    """
    Validate user prompt for safety.
    
    Returns:
        Tuple of (passed: bool, issues: List[str])
    """
    issues = []
    prompt_lower = prompt.lower()
    
    # Check blocked keywords
    for keyword in BLOCKED_KEYWORDS:
        if keyword in prompt_lower:
            issues.append(f"Blocked operation detected: '{keyword}'")
    
    # Check prompt injection patterns
    for pattern in INJECTION_PATTERNS:
        if pattern in prompt_lower:
            issues.append(f"Potential prompt injection: '{pattern}'")
    
    # Check for sensitive data requests
    for pattern in SENSITIVE_PATTERNS:
        if pattern in prompt_lower and ("show" in prompt_lower or "get" in prompt_lower or "list" in prompt_lower):
            issues.append(f"Sensitive data request detected: '{pattern}'")
    
    # Check empty prompt
    if not prompt.strip():
        issues.append("Empty prompt not allowed")
    
    # Check length
    if len(prompt) > 4000:
        issues.append("Prompt too long (max 4000 characters)")
    
    # Check minimum length
    if len(prompt.strip()) < 3:
        issues.append("Prompt too short (min 3 characters)")
    
    return len(issues) == 0, issues


def guardrails_node(state: dict) -> dict:
    """LangGraph node for guardrails validation."""
    prompt = state.get("prompt", "")
    passed, issues = validate_input(prompt)
    
    return {
        **state,
        "guardrails_passed": passed,
        "errors": state.get("errors", []) + issues,
    }
