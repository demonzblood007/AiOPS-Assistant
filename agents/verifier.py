"""Verifier - Validate outputs and calculate confidence."""

from typing import List
from schemas import StepStatus


def calculate_confidence(results: List[dict]) -> float:
    """Calculate confidence score based on step results."""
    if not results:
        return 0.0
    
    successful = sum(1 for r in results if r.get("status") == StepStatus.SUCCESS.value)
    return successful / len(results)


def build_final_output(results: List[dict]) -> dict:
    """Build final output from step results."""
    output = {}
    
    for r in results:
        if r.get("status") == StepStatus.SUCCESS.value and r.get("output"):
            step_id = r.get("step_id", "unknown")
            output[step_id] = r["output"]
    
    return output


def verifier_node(state: dict) -> dict:
    """LangGraph node for verification."""
    results = state.get("results", [])
    
    confidence = calculate_confidence(results)
    final_output = build_final_output(results)
    
    # Collect any errors from failed steps
    errors = state.get("errors", [])
    for r in results:
        if r.get("status") == StepStatus.FAILED.value and r.get("error"):
            errors.append(f"Step {r.get('step_id')}: {r['error']}")
    
    return {
        **state,
        "final_output": final_output,
        "confidence": confidence,
        "errors": errors,
    }
