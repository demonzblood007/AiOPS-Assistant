# AI Operations Assistant

## What We're Building

A production-grade AI assistant that accepts natural language tasks related to AIOps/DevOps/MLOps, plans execution steps, executes them via tools, and verifies outputs.

---

## Finalized Architecture

```
User Request
     ↓
┌─────────────────┐
│   GUARDRAILS    │  → Validate input, block unsafe prompts
└────────┬────────┘
         ↓
┌─────────────────┐
│    PLANNER      │  → LLM generates JSON plan with steps
└────────┬────────┘
         ↓
┌─────────────────┐
│   PLAN VALIDATOR│  → Check plan before execution
└────────┬────────┘
         ↓
┌─────────────────┐
│    EXECUTOR     │  → Execute steps via GitHub MCP/API
└────────┬────────┘
         ↓
┌─────────────────┐
│    VERIFIER     │  → Validate outputs, calculate confidence
└────────┬────────┘
         ↓
    Final Result
```

---

## Finalized Decisions

### 1. Task Isolation
- Composite key: `user_id` + `task_id`
- Redis key format: `task:{user_id}:{task_id}`
- Full multi-tenant isolation

### 2. Task Queue
- Redis RQ for parallel task processing
- Each task hashed uniquely
- Multiple workers can process different users simultaneously

### 3. Tool Integration
- GitHub MCP Server for repository operations
- Direct GitHub API as fallback
- Extensible tool registry for future tools

### 4. Agent Framework
- LangGraph for workflow orchestration
- LangChain for LLM interactions
- Langfuse for observability (optional)

### 5. API Design
- FastAPI backend
- `POST /tasks` - Submit new task
- `GET /tasks/{task_id}` - Get task status/result
- User ID passed in headers or query params

### 6. UI
- Streamlit for demo interface

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| API | FastAPI |
| UI | Streamlit |
| Agent Orchestration | LangGraph |
| LLM Framework | LangChain |
| Task Queue | Redis + RQ |
| Observability | Langfuse |
| Primary Tool | GitHub MCP/API |
| Containerization | Docker |

---

## Scope (What We're Delivering)

### Must Have
- Working API (POST /task, GET /task/{id})
- Planner that generates JSON plans
- Executor that calls GitHub tools
- Basic verification of outputs
- 2-3 working demo scenarios
- Redis RQ task queuing

### Included
- Input guardrails
- Plan validation before execution
- Confidence scores
- Basic cost tracking

---

## Out of Scope (Future Work)
- Kubernetes MCP integration
- Database operations
- Custom docs verifier tool
- RL-based plan improvement
- Parallel step execution within a plan

---

## Demo Scenarios

1. **Get Repo Info**: "Get details about facebook/react repository"
2. **Create Issue**: "Create an issue titled 'Bug fix needed' in owner/repo"
3. **Check File**: "Show me the contents of README.md in owner/repo"
