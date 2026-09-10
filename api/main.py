from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from core.db import init_db
from core.registry import discover_workflows
from api.routes import workflows, history, knowledge_base, architect, settings, clients, automation_projects, agents, files, rag
from api.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    discover_workflows()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="AI-OS API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"http://localhost:{p}" for p in range(3000, 3010)],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"name": "AI-OS API", "version": "2.0.0", "docs": "/docs"}


app.include_router(workflows.router, prefix="/api")
app.include_router(history.router, prefix="/api")
app.include_router(knowledge_base.router, prefix="/api")
app.include_router(architect.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(clients.router, prefix="/api")
app.include_router(automation_projects.router, prefix="/api")
app.include_router(agents.router, prefix="/api")
app.include_router(files.router, prefix="/api")
app.include_router(rag.router, prefix="/api")
