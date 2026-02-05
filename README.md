# AI Operations Assistant

A production-grade AI assistant that automates AIOps/DevOps/MLOps tasks using natural language. Built with LangGraph, FastAPI, and Redis for scalable task processing.

## Key Features

- **Natural Language Interface** - Describe tasks in plain English
- **Intelligent Planning** - LLM generates executable step-by-step plans with Chain-of-Thought reasoning
- **Automatic Verification** - Each step is verified before proceeding, with automatic replanning on failure
- **Full Observability** - Every decision logged to database for transparency and debugging
- **Multi-Provider LLM** - Switch between OpenAI, Anthropic, Google, Ollama, or Groq via `.env`
- **Scalable Architecture** - Redis task queue with priority support for concurrent users

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           USER REQUEST                                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  GUARDRAILS                                                             │
│  • Block dangerous operations (rm -rf, drop database, etc.)             │
│  • Detect prompt injection attempts                                     │
│  • Validate input length and format                                     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  PLANNER (LLM)                                                          │
│  • Chain-of-Thought reasoning with 5-step framework                     │
│  • Few-shot examples for consistent output                              │
│  • Generates JSON plan with dependencies                                │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  EXECUTOR                                                               │
│  • Executes steps via GitHub API tools                                  │
│  • Verifies each step output with LLM                                   │
│  • Automatic retry (2x) and replanning (2x) on failure                  │
│  • Injects results from previous steps into dependent steps             │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  VERIFIER                                                               │
│  • Calculates confidence score                                          │
│  • Aggregates results and errors                                        │
│  • Produces final output                                                │
└─────────────────────────────────────────────────────────────────────────┘
```

## Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **API** | FastAPI | REST endpoints, streaming SSE |
| **UI** | Streamlit | Interactive dashboard |
| **Orchestration** | LangGraph | Agent workflow management |
| **LLM** | LangChain + Multi-provider | OpenAI/Anthropic/Google/Ollama/Groq |
| **Task Queue** | Redis + RQ | Async processing, priority queues |
| **Database** | PostgreSQL | Persistent storage, execution logs |
| **Observability** | Langfuse (optional) | LLM tracing and monitoring |

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository>
cd ai-ops-assistant

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

**Minimum required:**
```env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-your-key
GITHUB_TOKEN=ghp_your-token
```

### 3. Start Services

**Option A: Docker Compose (Recommended)**
```bash
# Start all services (Postgres, Redis, Langfuse, API, Worker, UI)
docker-compose up

# Access:
# - API: http://localhost:8000
# - UI: http://localhost:8501
# - Langfuse: http://localhost:3000
```

**Option B: Manual Start**
```bash
# Terminal 1: Start Redis
docker run -d -p 6379:6379 redis

# Terminal 2: Start PostgreSQL
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=aiops postgres

# Terminal 3: Start Langfuse (optional)
docker-compose up langfuse langfuse-db

# Terminal 4: Start API
uvicorn main:app --reload

# Terminal 5: Start Worker
python -m task_queue.worker

# Terminal 6: Start UI
streamlit run ui/app.py
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/tasks/` | POST | Submit a new task |
| `/tasks/{task_id}` | GET | Get task status and result |
| `/tasks/stream` | POST | Execute with real-time streaming |
| `/tasks/logs/{task_id}` | GET | Get detailed execution logs |
| `/tasks/history/{user_id}` | GET | Get user's task history |
| `/tasks/stats/{user_id}` | GET | Get user's statistics |
| `/health` | GET | API health check |

## Project Structure

```
├── agents/                 # LangGraph agent nodes
│   ├── guardrails.py      # Input validation
│   ├── planner.py         # LLM plan generation
│   ├── executor.py        # Step execution with verification
│   ├── verifier.py        # Output verification
│   └── graph.py           # Workflow orchestration
├── api/
│   └── routes.py          # FastAPI endpoints
├── db/
│   ├── database.py        # SQLAlchemy async setup
│   ├── models.py          # Task and ExecutionLog models
│   ├── repository.py      # CRUD operations
│   └── tracker.py         # Execution logging
├── llm/
│   └── factory.py         # Multi-provider LLM factory
├── task_queue/
│   ├── tasks.py           # RQ task definitions
│   └── worker.py          # Worker process
├── schemas/               # Pydantic models
├── tools/
│   ├── github_tools.py    # GitHub API with retry
│   └── tool_registry.py   # Tool definitions
├── ui/
│   └── app.py             # Streamlit dashboard
├── observability/
│   └── tracer.py          # Langfuse integration
├── config/
│   └── settings.py        # Pydantic settings
└── main.py                # FastAPI app entry point
```

## Demo Scenarios

### 1. Get Repository Info
```
"Get details about facebook/react repository"
```
→ Returns stars, description, language, forks

### 2. Search Repositories
```
"Find top 5 Python machine learning repositories"
```
→ Returns list of repos with stars and URLs

### 3. Analyze Repository
```
"Get the README and list open issues for langchain-ai/langchain"
```
→ Returns README content and recent issues

## Key Design Decisions

### 1. LLM Factory Pattern
Switch providers without code changes - just update `.env`:
```python
from llm import get_llm
llm = get_llm()  # Uses LLM_PROVIDER from settings
```

### 2. Execution Logging
Every decision is logged to PostgreSQL:
- Guardrails decisions
- Plan generation with LLM thinking
- Step execution (start/complete)
- Verification results
- Replan decisions

### 3. Graceful Failure Handling
```
Step fails → Retry (2x) → Replan (2x) → Skip/Abort
```

### 4. Task Isolation
Composite key `user_id:task_id` ensures multi-tenant safety.



## License

MIT
