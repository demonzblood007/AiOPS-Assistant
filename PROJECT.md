# AI Operations Assistant - Project Documentation

## What We Built

A production-grade AI assistant that accepts natural language tasks related to AIOps/DevOps/MLOps, plans execution steps using LLM with Chain-of-Thought reasoning, executes them via GitHub API tools with automatic verification and replanning, and logs every decision for full transparency.

---

## Final Architecture

```
User Request
     │
     ▼
┌─────────────────┐
│   GUARDRAILS    │  → Validates input, blocks unsafe operations
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    PLANNER      │  → LLM generates JSON plan (CoT + Few-shot)
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│                    EXECUTOR                          │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐         │
│  │Execute  │───▶│ Verify  │───▶│ Replan? │         │
│  │ Step    │    │ (LLM)   │    │         │         │
│  └─────────┘    └─────────┘    └─────────┘         │
│       ▲                              │              │
│       └──────────────────────────────┘              │
└────────┬────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│    VERIFIER     │  → Calculates confidence, aggregates results
└────────┬────────┘
         │
         ▼
    Final Result + Execution Logs
```

---

## Key Features Implemented

### 1. Input Guardrails
- Blocks dangerous operations (rm -rf, drop database, etc.)
- Detects prompt injection attempts
- Validates sensitive data requests
- Length validation (3-4000 chars)

### 2. Chain-of-Thought Planner
- 5-step reasoning framework
- 3 few-shot examples for consistent output
- JSON plan with step dependencies
- LLM thinking captured and logged

### 3. Smart Executor
- Step-by-step execution with result injection
- LLM-based verification after each step
- Automatic retry (2x per step)
- Automatic replanning (2x per task)
- Actions: retry, alternative, skip, abort

### 4. Execution Logging (Full Transparency)
Every event logged to PostgreSQL:
- Guardrails decisions
- Plan generation with LLM thinking
- Step start/complete
- Verification results
- Replan decisions
- Final completion

### 5. Multi-Provider LLM Factory
Switch providers via `.env`:
- OpenAI (GPT-4o, GPT-4o-mini)
- Anthropic (Claude 3.5 Sonnet)
- Google (Gemini Pro)
- Ollama (Local models)
- Groq (Fast inference)

### 6. Task Queue with Isolation
- Redis RQ with priority queues (high, default, low)
- Composite key: `user_id:task_id`
- Full multi-tenant isolation
- Persistent storage in PostgreSQL

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/tasks/` | POST | Submit new task |
| `/tasks/{task_id}` | GET | Get task status/result |
| `/tasks/stream` | POST | Real-time streaming execution |
| `/tasks/logs/{task_id}` | GET | Detailed execution logs |
| `/tasks/history/{user_id}` | GET | User's task history |
| `/tasks/stats/{user_id}` | GET | User's statistics |

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| API | FastAPI |
| UI | Streamlit |
| Agent Orchestration | LangGraph |
| LLM Framework | LangChain |
| Task Queue | Redis + RQ |
| Database | PostgreSQL (async) |
| Observability | Langfuse (optional) |
| Tools | GitHub API |
| Containerization | Docker |

---

## Demo Scenarios

1. **Get Repo Info**: "Get details about facebook/react repository"
2. **Search Repos**: "Find top 5 Python machine learning repos"
3. **Analyze Repo**: "Get README and list issues in langchain-ai/langchain"
4. **Create Issue**: "Create issue 'Bug report' in owner/repo"

---

## What Makes This Production-Grade

1. **Error Handling**: Retry with exponential backoff, rate limit handling
2. **Observability**: Every decision logged for debugging
3. **Scalability**: Redis queue for horizontal scaling
4. **Security**: Input guardrails, prompt injection detection
5. **Flexibility**: LLM provider agnostic via factory pattern
6. **Maintainability**: Clean architecture, type hints, Pydantic models

---

## Future Enhancements (Out of Scope)

- Parallel step execution
- More tool integrations (K8s, AWS, etc.)
- WebSocket real-time updates
- User authentication
- Cost tracking per request
- RL-based plan improvement
