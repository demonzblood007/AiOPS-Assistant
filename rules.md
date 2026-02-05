# Agentic AI Project Rules (Compact)

---

## 1) Learning-first, but agent-focused
- **Rule**: Every agent behavior change must include a short explanation of **what/why/how/when** (pattern + trade-offs).
- **Why**: Agentic systems are hard to reason about; understanding prevents “prompt magic” and brittle behavior.

## 2) Small, reviewable changes
- **Rule**: Implement in small steps (one capability/flow at a time). Avoid broad refactors unless explicitly required.
- **Why**: Agent loops create hidden coupling (tools, memory, policy); small diffs keep failures diagnosable.

## 3) Explicit decision points (human-in-the-loop)
- **Rule**: Pause and present options (pros/cons) before deciding on:
  - Agent architecture (planner/worker, ReAct, graph, multi-agent)
  - Tooling (retrieval store, queue, orchestration framework)
  - Memory strategy (scratchpad vs persisted memory, summarization)
  - Safety/policy boundaries (allowed tools, data access, sandboxing)
  - Evaluation approach (offline metrics, golden sets, online checks)
- **Why**: These choices lock in constraints and failure modes.

## 4) Tool contracts are APIs
- **Rule**: Every tool must have a clear contract:
  - Inputs/outputs schema, error cases, retries/timeouts, idempotency notes
  - Logging/telemetry fields (trace id, tool name, latency, status)
- **Why**: Agents fail at the tool boundary more than in “core logic”.

## 5) Observability is mandatory
- **Rule**: Every agent run should be traceable:
  - Correlation id per run
  - Structured logs for decisions, tool calls, and final outcomes
  - Save minimal artifacts needed for debugging (no sensitive data)
- **Why**: If you can’t replay/inspect, you can’t improve reliability.

## 6) Evaluation before optimization
- **Rule**: Add/extend evals whenever behavior changes:
  - A small “golden” test set for critical workflows
  - Regression checks for known failures
  - Clear success criteria (accuracy, cost, latency, safety)
- **Why**: Agent performance is non-linear; evals prevent silent regressions.

## 7) Transparent debugging
- **Rule**: When something breaks, document:
  - Repro steps + inputs (sanitized)
  - Hypothesis → experiment → result
  - Fix + why it works + remaining risks
- **Why**: Debugging is where most agentic learning and stabilization happens.

## 8) Simplicity first, correctness always
- **Rule**: Prefer the simplest reliable approach (deterministic logic where possible), then add model-driven flexibility.
- **Why**: Over-agentic designs are expensive and fragile without strong evals.

## 9) Documentation as we build
- **Rule**: Keep these always current:
  - `README`: how to run, env vars, tool setup
  - `docs/decisions.md`: key decisions + rationale
  - `docs/evals.md`: datasets, metrics, how to run evals
- **Why**: Agentic systems need shared context to stay maintainable.

---

## Collaboration Checklist (per capability)
- [ ] Explain concept + trade-offs (what/why/how/when)
- [ ] Define/confirm tool contracts (schemas, errors, retries)
- [ ] Implement in a small diff
- [ ] Add/extend evals and sanity tests
- [ ] Add tracing/logging for the new path
- [ ] Update docs + decision log