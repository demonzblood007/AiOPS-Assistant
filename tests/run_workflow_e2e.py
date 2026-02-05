"""
End-to-end workflow test: runs the full pipeline and prints logs to the terminal.

Usage (from project root):
  python -m tests.run_workflow_e2e

Ensure .env has LLM and DB/Redis configured. Postgres and Redis must be running.
"""

import asyncio
import json
import logging
import os
import sys

# Project root on path and load .env
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

# Configure logging so pipeline steps are visible in terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
# Reduce noise from libs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

log = logging.getLogger("e2e")


def _safe_summary(state: dict) -> dict:
    """Build a small summary of state for logging (avoid huge payloads)."""
    out = {}
    if "guardrails_passed" in state:
        out["guardrails_passed"] = state["guardrails_passed"]
    if "plan_valid" in state:
        out["plan_valid"] = state["plan_valid"]
    if "plan" in state and state["plan"]:
        plan = state["plan"]
        steps = plan.get("steps", [])
        out["plan_steps"] = len(steps)
        if plan.get("thinking"):
            out["thinking"] = (plan["thinking"][:200] + "…") if len(plan.get("thinking", "")) > 200 else plan.get("thinking")
    if "results" in state and state["results"]:
        out["results_count"] = len(state["results"])
        out["results"] = [
            {"step_id": r.get("step_id"), "status": r.get("status"), "has_output": bool(r.get("output"))}
            for r in state["results"]
        ]
    if "final_output" in state and state["final_output"]:
        out["final_output_keys"] = list(state["final_output"].keys())
    if "confidence" in state:
        out["confidence"] = state["confidence"]
    if "errors" in state and state["errors"]:
        out["errors"] = state["errors"]
    return out


async def run():
    from agents.graph import agent_workflow
    from db.database import async_session
    from db.repository import get_task, create_task

    user_id = "e2e_test"
    task_id = "e2e_run_001"
    prompt = "List my repositories"

    # Ensure Task row exists so execution_logs FK is satisfied
    async with async_session() as db:
        existing = await get_task(db, user_id, task_id)
        if not existing:
            await create_task(db, user_id, task_id, prompt, context={})
            log.info("Created task row for e2e run")

    initial_state = {
        "user_id": user_id,
        "task_id": task_id,
        "prompt": prompt,
        "context": {},
        "guardrails_passed": False,
        "plan": None,
        "plan_valid": False,
        "results": [],
        "final_output": None,
        "confidence": 0.0,
        "errors": [],
    }

    log.info("=" * 60)
    log.info("E2E WORKFLOW START")
    log.info("  user_id=%s task_id=%s prompt=%s", user_id, task_id, repr(prompt))
    log.info("=" * 60)

    try:
        # Stream state updates so we see each node's output
        step = 0
        final = initial_state
        try:
            async for state in agent_workflow.astream(initial_state, stream_mode="values"):
                step += 1
                final = state
                summary = _safe_summary(state)
                log.info("--- Step %s (state update) --- %s", step, json.dumps(summary, default=str))
        except TypeError:
            # Older LangGraph: astream may not support stream_mode; run once and log final state
            log.info("Running workflow (single ainvoke)...")
            final = await agent_workflow.ainvoke(initial_state)
            summary = _safe_summary(final)
            log.info("--- Final state --- %s", json.dumps(summary, default=str))
        log.info("=" * 60)
        log.info("E2E WORKFLOW END")
        log.info("  guardrails_passed=%s plan_valid=%s", final.get("guardrails_passed"), final.get("plan_valid"))
        log.info("  confidence=%s errors=%s", final.get("confidence"), final.get("errors"))
        if final.get("final_output"):
            log.info("  final_output: %s", json.dumps(final["final_output"], default=str, indent=2)[:500])
        log.info("=" * 60)
        return final
    except Exception as e:
        log.exception("E2E workflow failed: %s", e)
        raise


def main():
    try:
        final = asyncio.run(run())
        sys.exit(0 if (final.get("confidence", 0) > 0 and not final.get("errors")) else 1)
    except Exception as e:
        log.error("Exit with error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
