"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router as tasks_router
from db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup."""
    try:
        await init_db()
    except Exception as e:
        import sys
        msg = str(e).lower()
        if "password" in msg or "connection" in msg or "refused" in msg:
            print("\n*** Database connection failed ***", file=sys.stderr)
            print("Start Postgres (and Redis if needed) with:", file=sys.stderr)
            print("  docker compose up -d postgres redis", file=sys.stderr)
            print("Then ensure .env has: DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/aiops", file=sys.stderr)
        raise
    yield


app = FastAPI(
    title="AI Operations Assistant",
    description="Natural language task execution for AIOps/DevOps/MLOps",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(tasks_router)


@app.get("/")
async def root():
    return {"status": "running", "service": "AI Operations Assistant"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
