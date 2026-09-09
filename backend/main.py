import asyncio
# D-001-1: Windows is the only supported platform; no sys.platform branches anywhere.
asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

import os

from routers import chat, settings, debug, memories, conversations, webhooks, skills, events, auth, push, documents, heartbeat, custom_mcp
from services.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # D-001-3: Tier 2 background jobs (memory extraction, search tags, reflection,
    # WhatsApp triage) run on Claude Haiku and have no fallback — fail loudly at
    # boot rather than let them silently no-op later.
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Tier 2 background jobs (memory extraction, "
            "search tags, reflection, WhatsApp triage) run on Claude Haiku and need it. "
            "Add ANTHROPIC_API_KEY to .env."
        )

    await init_db()

    # D-001-2: chat is GPT via Codex OAuth only. Verify OAuth connectivity and
    # pin settings.model to a model the Codex endpoint currently serves.
    from services.codex_oauth_service import ensure_chat_model_at_startup
    await ensure_chat_model_at_startup()

    # Initialize skills service (manages MCP and other integrations)
    try:
        from services.skills_service import init_skills
        await init_skills()
    except Exception as e:
        print(f"Skills initialization error: {e}")

    # Initialize WhatsApp bridge (optional, won't fail if unavailable)
    try:
        from services.whatsapp_bridge_client import initialize_bridge
        await initialize_bridge()
    except Exception as e:
        print(f"WhatsApp bridge initialization skipped: {e}")

    # Initialize custom MCP servers (Edward-added servers from DB)
    try:
        from services.custom_mcp_service import initialize_custom_servers
        await initialize_custom_servers()
    except Exception as e:
        print(f"Custom MCP servers initialization skipped: {e}")

    # Initialize tool registry (must be after skills and MCP)
    try:
        from services.tool_registry import initialize_registry
        await initialize_registry()
    except Exception as e:
        print(f"Tool registry initialization error: {e}")

    # Start the scheduled events scheduler
    try:
        from services.scheduler_service import start_scheduler
        await start_scheduler()
    except Exception as e:
        print(f"Scheduler initialization error: {e}")

    # Start the heartbeat system (WhatsApp listener + triage loop)
    try:
        from services.heartbeat import start_heartbeat
        await start_heartbeat()
    except Exception as e:
        print(f"Heartbeat initialization error: {e}")

    yield

    # Shutdown
    try:
        from services.heartbeat import stop_heartbeat
        await stop_heartbeat()
    except Exception as e:
        print(f"Heartbeat shutdown error: {e}")

    try:
        from services.scheduler_service import stop_scheduler
        await stop_scheduler()
    except Exception as e:
        print(f"Scheduler shutdown error: {e}")

    try:
        from services.custom_mcp_service import shutdown_custom_servers
        await shutdown_custom_servers()
    except Exception as e:
        print(f"Custom MCP servers shutdown error: {e}")

    try:
        from services.whatsapp_bridge_client import shutdown_bridge
        await shutdown_bridge()
    except Exception as e:
        print(f"WhatsApp bridge shutdown error: {e}")


app = FastAPI(
    title="Edward API",
    description="Backend API for Edward AI Assistant",
    version="0.1.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:3003",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:3002",
        "http://127.0.0.1:3003",
    ],
    allow_origin_regex=r"^http://192\.168\.\d+\.\d+:(3000|3001|3002|3003|8000)$|^http://10\.\d+\.\d+\.\d+:(3000|3001|3002|3003|8000)$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add authentication middleware (after CORS so preflight requests work)
from middleware.auth import AuthMiddleware
app.add_middleware(AuthMiddleware)

# Include routers
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(settings.router, prefix="/api", tags=["settings"])
app.include_router(debug.router, prefix="/api", tags=["debug"])
app.include_router(memories.router, prefix="/api", tags=["memories"])
app.include_router(conversations.router, prefix="/api", tags=["conversations"])
app.include_router(webhooks.router, prefix="/api", tags=["webhooks"])
app.include_router(skills.router, prefix="/api", tags=["skills"])
app.include_router(events.router, prefix="/api", tags=["events"])
app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(push.router, prefix="/api", tags=["push"])
app.include_router(documents.router, prefix="/api", tags=["documents"])
app.include_router(heartbeat.router, prefix="/api", tags=["heartbeat"])
app.include_router(custom_mcp.router, prefix="/api", tags=["custom-mcp"])

@app.get("/")
async def root():
    return {"message": "Edward API is running"}

@app.get("/health")
async def health():
    return {"status": "healthy"}
