"""FastAPI application: multi-tenant auth, OAuth, chat, and static UI."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from clario.agent.runner import get_runner
from clario.api.deps import AuthContext, require_tenant
from clario.api.tenancy_routes import router as tenancy_router
from clario.config import PROJECT_ROOT, get_settings
from clario.db.session import get_db, init_db
from clario.logging import configure_logging, get_logger
from clario.tenancy.context import bind_tenant_client, clear_tenant_client
from clario.tenancy.service import (
    add_message,
    archive_conversation,
    ensure_conversation,
    get_conversation,
    list_conversations,
    write_audit,
)
from clario.zoho.errors import ZohoError

FRONTEND_DIR = PROJECT_ROOT / "frontend"
logger = get_logger("clario.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.clario_log_level)
    if settings.groq_api_key:
        os.environ.setdefault("GROQ_API_KEY", settings.groq_api_key)
    if settings.google_api_key:
        os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)
    await init_db()
    logger.info(
        "Clario API starting multi_tenant=%s db=%s llm=%s model=%s",
        settings.multi_tenant_enabled,
        settings.resolved_database_url.split("://")[0],
        settings.llm_provider,
        settings.llm_label(),
    )
    yield


app = FastAPI(title="Clario", version="0.2.0", lifespan=lifespan)
app.include_router(tenancy_router)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    session_id: str | None = None
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    conversation_id: str
    answer: str
    tool_calls: list[dict] = Field(default_factory=list)


@app.get("/health")
async def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "multi_tenant": settings.multi_tenant_enabled,
        "database": settings.resolved_database_url.split("://")[0],
        "zoho_oauth_app_configured": bool(settings.zoho_client_id and settings.zoho_client_secret),
        "llm_provider": settings.llm_provider,
        "llm_configured": settings.llm_ready(),
        "model": settings.llm_label(),
    }


@app.get("/api/status")
async def status(
    auth: AuthContext = Depends(require_tenant),
) -> dict:
    settings = get_settings()
    assert auth.tenant is not None
    conn = auth.tenant.zoho_connection
    return {
        "tenant_id": auth.tenant.id,
        "tenant_name": auth.tenant.name,
        "zoho_ready": bool(conn and conn.is_connected),
        "organization_id_configured": bool(conn and conn.organization_id),
        "llm_provider": settings.llm_provider,
        "llm_configured": settings.llm_ready(),
        "organization": {
            "organization_id": conn.organization_id,
            "name": conn.organization_name,
            "currency_code": conn.currency_code,
        }
        if conn and conn.is_connected
        else None,
    }


@app.get("/api/analytics/overview")
async def analytics_overview(
    auth: AuthContext = Depends(require_tenant),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
) -> dict:
    """Month-to-date business summary for the current workspace (deterministic analytics)."""
    assert auth.tenant is not None
    conn = auth.tenant.zoho_connection
    if conn is None or not conn.is_connected:
        raise HTTPException(
            status_code=503,
            detail="Zoho Books is not connected for this workspace. Connect it from the UI.",
        )
    try:
        service = bind_tenant_client(auth.tenant)
        return await service.get_business_summary(start_date=start_date, end_date=end_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ZohoError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.warning("Analytics overview failed tenant=%s: %s", auth.tenant.id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        clear_tenant_client()


@app.get("/oauth/zoho/callback", response_model=None)
async def oauth_callback_alias(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Zoho Developer Console redirect URI points here by default."""
    from clario.api.tenancy_routes import oauth_callback

    return await oauth_callback(request, code=code, state=state, error=error, db=db)


@app.get("/oauth/zoho/start", response_model=None)
async def legacy_oauth_start() -> HTMLResponse:
    return HTMLResponse(
        """
        <html><body style="font-family: system-ui; max-width: 40rem; margin: 3rem auto;">
          <h1>Multi-tenant OAuth</h1>
          <p>Sign in, select a workspace, then call
          <code>GET /api/oauth/zoho/start</code> with your Bearer token and
          <code>X-Tenant-Id</code> header.</p>
          <p><a href="/">Open Clario</a></p>
        </body></html>
        """,
        status_code=400,
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    request: Request,
    auth: AuthContext = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    settings = get_settings()
    if not settings.llm_ready():
        provider = settings.llm_provider.strip().lower()
        detail = (
            "GROQ_API_KEY is not configured."
            if provider == "groq"
            else "GOOGLE_API_KEY is not configured."
        )
        raise HTTPException(status_code=503, detail=detail)
    assert auth.tenant is not None
    conn = auth.tenant.zoho_connection
    if conn is None or not conn.is_connected:
        raise HTTPException(
            status_code=503,
            detail="Zoho Books is not connected for this workspace. Connect it from the UI.",
        )

    conversation = await ensure_conversation(
        db,
        tenant_id=auth.tenant.id,
        user_id=auth.user.id,
        conversation_id=payload.conversation_id,
        adk_session_id=payload.session_id,
    )
    await add_message(db, conversation=conversation, role="user", content=payload.message)

    try:
        bind_tenant_client(auth.tenant)
        result = await get_runner().ask(
            payload.message,
            session_id=conversation.adk_session_id,
            user_id=f"{auth.tenant.id}:{auth.user.id}",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Chat failed tenant=%s: %s", auth.tenant.id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        clear_tenant_client()

    await add_message(
        db,
        conversation=conversation,
        role="assistant",
        content=result["answer"],
        tool_calls=result.get("tool_calls"),
    )
    await write_audit(
        db,
        tenant_id=auth.tenant.id,
        user_id=auth.user.id,
        action="chat.message",
        resource_type="conversation",
        resource_id=conversation.id,
        metadata={"tool_count": len(result.get("tool_calls") or [])},
        ip_address=request.client.host if request.client else "",
    )
    return ChatResponse(
        session_id=conversation.adk_session_id,
        conversation_id=conversation.id,
        answer=result["answer"],
        tool_calls=result.get("tool_calls") or [],
    )


def _conversation_summary(convo) -> dict:
    return {
        "id": convo.id,
        "title": convo.title or "New chat",
        "session_id": convo.adk_session_id,
        "updated_at": convo.updated_at.isoformat() if convo.updated_at else None,
        "created_at": convo.created_at.isoformat() if convo.created_at else None,
    }


@app.get("/api/conversations")
async def conversations_list(
    auth: AuthContext = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
) -> dict:
    assert auth.tenant is not None
    rows = await list_conversations(
        db, tenant_id=auth.tenant.id, user_id=auth.user.id, limit=limit
    )
    return {"conversations": [_conversation_summary(c) for c in rows]}


@app.get("/api/conversations/{conversation_id}")
async def conversations_get(
    conversation_id: str,
    auth: AuthContext = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
) -> dict:
    assert auth.tenant is not None
    convo = await get_conversation(
        db,
        tenant_id=auth.tenant.id,
        user_id=auth.user.id,
        conversation_id=conversation_id,
    )
    if convo is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {
        **_conversation_summary(convo),
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in (convo.messages or [])
        ],
    }


@app.delete("/api/conversations/{conversation_id}")
async def conversations_delete(
    conversation_id: str,
    auth: AuthContext = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
) -> dict:
    assert auth.tenant is not None
    convo = await archive_conversation(
        db,
        tenant_id=auth.tenant.id,
        user_id=auth.user.id,
        conversation_id=conversation_id,
    )
    if convo is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    try:
        await get_runner().clear(
            convo.adk_session_id, user_id=f"{auth.tenant.id}:{auth.user.id}"
        )
    except Exception:  # noqa: BLE001
        pass
    return {"status": "archived", "id": conversation_id}


@app.post("/api/chat/clear")
async def clear_chat(
    session_id: str = Query(...),
    auth: AuthContext = Depends(require_tenant),
) -> dict:
    assert auth.tenant is not None
    await get_runner().clear(session_id, user_id=f"{auth.tenant.id}:{auth.user.id}")
    return {"status": "cleared", "session_id": session_id}


@app.exception_handler(ZohoError)
async def zoho_error_handler(_: Request, exc: ZohoError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc)})


if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


def create_app() -> FastAPI:
    return app
