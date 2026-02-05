"""LangGraph workflow - Orchestrates the agent pipeline."""

from langgraph.graph import StateGraph, END
from agents.guardrails import guardrails_node
from agents.planner import planner_node
from agents.executor import executor_node
from agents.verifier import verifier_node


def should_continue_after_guardrails(state: dict) -> str:
    """Route after guardrails."""
    if state.get("guardrails_passed"):
        return "planner"
    return END


def should_continue_after_planner(state: dict) -> str:
    """Route after planner."""
    if state.get("plan_valid"):
        return "executor"
    return END


def create_workflow():
    """Create the LangGraph workflow."""
    
    # Define state schema
    workflow = StateGraph(dict)
    
    # Add nodes
    workflow.add_node("guardrails", guardrails_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("verifier", verifier_node)
    
    # Set entry point
    workflow.set_entry_point("guardrails")
    
    # Add edges with conditions
    workflow.add_conditional_edges(
        "guardrails",
        should_continue_after_guardrails,
        {"planner": "planner", END: END}
    )
    
    workflow.add_conditional_edges(
        "planner",
        should_continue_after_planner,
        {"executor": "executor", END: END}
    )
    
    workflow.add_edge("executor", "verifier")
    workflow.add_edge("verifier", END)
    
    return workflow.compile()


# Compiled workflow
agent_workflow = create_workflow()
