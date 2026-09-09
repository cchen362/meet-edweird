from fastapi import APIRouter, HTTPException

from models import Settings, SettingsUpdate
from services.settings_service import get_settings, update_settings

router = APIRouter()


@router.get("/settings", response_model=Settings)
async def read_settings():
    """Get the current Edward settings."""
    try:
        settings = await get_settings()
        return settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/settings", response_model=Settings)
async def save_settings(settings_update: SettingsUpdate):
    """Update Edward's settings."""
    try:
        settings = await update_settings(settings_update)
        return settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/settings/models")
async def get_available_models():
    """Get the chat models the Codex endpoint currently serves."""
    from services.codex_oauth_service import has_valid_tokens, list_served_models

    if not await has_valid_tokens():
        return {"models": [], "codex_connected": False}

    try:
        served = await list_served_models()
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))

    models = [
        {"id": m["id"], "name": m["name"], "description": m["description"]}
        for m in served
    ]
    return {"models": models, "codex_connected": True}

@router.get("/settings/openai/status")
async def get_openai_status():
    """Check Codex OAuth authentication status."""
    from services.codex_oauth_service import has_valid_tokens, get_account_email

    codex_connected = await has_valid_tokens()
    codex_email = await get_account_email() if codex_connected else None

    return {
        "codex_connected": codex_connected,
        "codex_email": codex_email,
    }

@router.post("/settings/openai/login")
async def start_openai_login():
    """Start Codex OAuth flow. Returns auth URL to open in browser."""
    try:
        from services.codex_oauth_service import start_auth_flow
        auth_url = await start_auth_flow()
        return {"auth_url": auth_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/settings/openai/logout")
async def openai_logout():
    """Disconnect Codex OAuth (clear stored tokens)."""
    try:
        from services.codex_oauth_service import clear_tokens
        await clear_tokens()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
