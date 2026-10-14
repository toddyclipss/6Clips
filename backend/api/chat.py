# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""WebSocket /ws/chat endpoint — planner agent."""
import json
import asyncio
import logging
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from backend.database import AsyncSessionLocal
from backend.models.user_settings import UserSettings
from backend.models.chat_session import ChatSession, ChatMessage as ChatMessageModel
from backend.core.ws_manager import ws_manager
from backend.core.chat_history import CHAT_SESSION
from backend.core.user_intelligence import UserIntelligence
from backend.agents.planner import PlannerAgent

logger = logging.getLogger(__name__)
router = APIRouter()

planner = PlannerAgent()
intelligence = UserIntelligence()


async def _persist_message(session_id: str, role: str, content: str = None,
                           msg_type: str = None, data_json: str = None, user_id: str = "local"):
    """Save a message to the DB and update session metadata."""
    async with AsyncSessionLocal() as db:
        msg = ChatMessageModel(
            session_id=session_id,
            user_id=user_id,
            role=role,
            content=content,
            msg_type=msg_type,
            data_json=data_json,
        )
        db.add(msg)

        # Update session
        result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
        session = result.scalar_one_or_none()
        if session:
            session.message_count = (session.message_count or 0) + 1
            session.updated_at = datetime.utcnow()
            # Auto-title from first user message
            if session.title == "New chat" and role == "user" and content:
                session.title = content[:80] + ("..." if len(content) > 80 else "")

        await db.commit()


async def _load_session_history(session_id: str) -> list[dict]:
    """Load chat history from DB for a session (for AI context)."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ChatMessageModel)
            .where(ChatMessageModel.session_id == session_id)
            .where(ChatMessageModel.role.in_(["user", "assistant"]))
            .order_by(ChatMessageModel.created_at.asc())
        )
        messages = result.scalars().all()
    return [{"role": m.role, "content": m.content or ""} for m in messages if m.content]


async def _load_previous_session_context(user_id: str, current_session_id: str | None) -> list[dict]:
    """
    Load the last few messages from the most recent *previous* session.
    This gives the planner continuity across sessions — it knows what the user
    was doing last time even if they started a new chat.
    Returns up to 4 messages (2 user + 2 assistant turns).
    """
    async with AsyncSessionLocal() as db:
        # Find the most recent session that is NOT the current one
        query = (
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
            .limit(2)
        )
        result = await db.execute(query)
        sessions = result.scalars().all()

        prev_session = None
        for s in sessions:
            if s.id != current_session_id:
                prev_session = s
                break

        if not prev_session:
            return []

        # Load last 4 messages from that session
        result = await db.execute(
            select(ChatMessageModel)
            .where(ChatMessageModel.session_id == prev_session.id)
            .where(ChatMessageModel.role.in_(["user", "assistant"]))
            .where(ChatMessageModel.content.isnot(None))
            .order_by(ChatMessageModel.created_at.desc())
            .limit(4)
        )
        messages = result.scalars().all()

    if not messages:
        return []

    # Reverse to chronological order, truncate long messages
    msgs = []
    for m in reversed(messages):
        content = (m.content or "")[:300]
        if len(m.content or "") > 300:
            content += "..."
        msgs.append({"role": m.role, "content": content})
    return msgs


async def _maybe_update_profile(user_id: str):
    """Check if user profile needs updating and trigger AI generation if so."""
    try:
        if await intelligence.should_update_profile(user_id):
            logger.info(f"Triggering AI profile update for {user_id}")
            await intelligence.update_profile_with_ai(user_id)
    except Exception as e:
        logger.warning(f"Profile auto-update failed (non-critical): {e}")


@router.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket):
    user_id = "local"
    # The HTTP CSRF middleware never sees a websocket scope, so any page the
    # user happens to have open could connect here, drive the planner (real
    # dispatched jobs, `job_cancel` on the user's own work) and read every
    # event the app streams. Same allowlist, same rule as the middleware: a
    # PRESENT Origin must be ours; no Origin is a non-browser client
    # (messaging bridge, tests, CLI) and still passes. Closing before accept
    # answers the handshake with a refusal rather than an open socket.
    from backend.core.origins import lan_mode, origin_ok
    origin = websocket.headers.get("origin")
    if origin and not lan_mode() and not origin_ok(origin):
        logger.warning("Rejected /ws/chat handshake from foreign origin %r", origin[:120])
        await websocket.close(code=1008)
        return
    await ws_manager.connect(websocket, user_id)
    try:
        # Load user settings
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(UserSettings)
                .where(UserSettings.user_id == user_id)
                .order_by(UserSettings.updated_at.desc(), UserSettings.id.desc())
                .limit(1)
            )
            user_settings = result.scalars().first()

        # Send smart suggestions on connect (for returning users)
        # Explicit handshake cleanup: NEVER invoke any generative AI path on connect;
        # Use deterministic/cached rule-based suggestions only.
        # Send directly to THIS connecting websocket to avoid broadcasting to other/diagnostic sessions.
        try:
            ctx = await intelligence.get_context_summary(user_id)
            if not ctx.get("is_first_session"):
                profile = await intelligence.get_user_profile(user_id)
                suggestions = None
                from backend.models.user_profile import UserProfile
                async with AsyncSessionLocal() as db:
                    p_res = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
                    up = p_res.scalar_one_or_none()
                    if up and up.suggestions_json:
                        try:
                            cached = json.loads(up.suggestions_json)
                            cache_age = (datetime.utcnow() - (up.suggestions_updated_at or datetime.min)).total_seconds()
                            if cache_age < 3600:
                                suggestions = cached
                        except (json.JSONDecodeError, TypeError):
                            pass
                if not suggestions:
                    suggestions = await intelligence._get_rule_based_suggestions(user_id, ctx, profile)
                if suggestions:
                    await websocket.send_text(json.dumps({
                        "type": "smart_suggestions",
                        "suggestions": suggestions,
                    }))
        except Exception as e:
            logger.debug("Non-critical onconnect suggestions failed: %s", e)

        # Current session ID — set by frontend via set_session message
        current_session_id = None

        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")
            logger.debug("WS recv | type=%s | user=%s", msg_type, user_id)

            if msg_type == "set_session":
                # Frontend tells us which session to use
                current_session_id = msg.get("session_id")
                # Attribute backend-persisted rich cards / job rows to this
                # session (rides asyncio context into dispatched jobs).
                CHAT_SESSION.set(current_session_id)
                logger.info(f"Session set to: {current_session_id}")

            elif msg_type == "chat_message":
                content = msg.get("content", "").strip()
                if not content:
                    continue
                logger.info("WS chat_message | user=%s | content=%s", user_id, content[:100])

                # Auto-create session if none set
                if not current_session_id:
                    async with AsyncSessionLocal() as db:
                        session = ChatSession(user_id=user_id, title="New chat")
                        db.add(session)
                        await db.commit()
                        await db.refresh(session)
                    current_session_id = session.id
                    await ws_manager.send({
                        "type": "session_created",
                        "session_id": session.id,
                        "title": session.title,
                    }, user_id)

                # Attribute everything this turn emits (planner rich cards,
                # jobs it dispatches) to the active session. Dispatched jobs
                # snapshot this context, so results that land after the turn
                # returns still persist into the right session.
                CHAT_SESSION.set(current_session_id)

                # Persist user message
                await _persist_message(current_session_id, "user", content=content, user_id=user_id)

                # Reload user settings (may have changed via Settings page)
                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        select(UserSettings)
                        .where(UserSettings.user_id == user_id)
                        .order_by(UserSettings.updated_at.desc(), UserSettings.id.desc())
                        .limit(1)
                    )
                    user_settings = result.scalars().first()

                # Load full session history from DB
                history = await _load_session_history(current_session_id)
                # Remove the last message (current user message) since planner appends it
                if history and history[-1]["role"] == "user" and history[-1]["content"] == content:
                    history = history[:-1]

                # Session isolation: A new conversation starts completely fresh and must NOT
                # inherit old user-message history or language from prior sessions.
                prev_context = []

                # Extract project, provider, and model from payload or fallback to active project
                project_id = msg.get("project_id")
                pinned_provider = msg.get("provider")
                pinned_model = msg.get("model")
                pinned_think = msg.get("think")
                reasoning_level = msg.get("reasoning_level") or msg.get("reasoning")

                # Strict Explicit Selection — reject before calling inference if unselected
                eff_prov = pinned_provider or (getattr(user_settings, "ai_provider", None) if user_settings else None)
                eff_model = pinned_model or (getattr(user_settings, "ai_model", None) if user_settings else None)
                if not eff_prov or not eff_model:
                    await ws_manager.send({
                        "type": "chat_error",
                        "error": "No AI model selected. Choose a model in Global Chat to continue.",
                        "session_id": current_session_id,
                    }, user_id)
                    continue

                eff_reasoning = reasoning_level or (getattr(user_settings, "ai_reasoning_level", None) if user_settings else None)
                if not eff_reasoning:
                    await ws_manager.send({
                        "type": "chat_error",
                        "error": "No reasoning effort selected. Choose Low, Medium, or High in Global Chat to continue.",
                        "session_id": current_session_id,
                    }, user_id)
                    continue
                raw_norm = str(eff_reasoning).strip().lower()
                reasoning_level = "high" if raw_norm in ("hard", "high") else raw_norm

                if not project_id:
                    async with AsyncSessionLocal() as db:
                        from backend.models.project import Project
                        p_res = await db.execute(
                            select(Project.id)
                            .where(Project.user_id == user_id)
                            .order_by(Project.updated_at.desc())
                            .limit(1)
                        )
                        project_id = p_res.scalar_one_or_none()

                # Run planner and capture response via return value (concurrency-safe)
                assistant_response = None
                try:
                    assistant_response = await planner.handle_message(
                        message=content,
                        history=history,
                        user_settings=user_settings,
                        user_id=user_id,
                        previous_session_context=prev_context,
                        pinned_provider=pinned_provider,
                        pinned_model=pinned_model,
                        project_id=project_id,
                        pinned_think=pinned_think,
                        reasoning_level=reasoning_level,
                    )
                except Exception as e:
                    logger.error(f"Planner error: {e}", exc_info=True)
                    await ws_manager.send({
                        "type": "chat_error",
                        "error": str(e),
                        "session_id": current_session_id,
                    }, user_id)

                # Persist assistant response
                if assistant_response:
                    if isinstance(assistant_response, dict):
                        resp_content = assistant_response.get("content", "")
                        resp_timeline = assistant_response.get("execution_timeline")
                    else:
                        resp_content = str(assistant_response)
                        resp_timeline = None

                    if resp_content or resp_timeline:
                        data_payload = json.dumps({"execution_timeline": resp_timeline}) if resp_timeline else None
                        await _persist_message(
                            current_session_id, "assistant",
                            content=resp_content or "Operations completed.", user_id=user_id,
                            data_json=data_payload,
                        )

                # Auto-update user profile in background if enough events accumulated
                asyncio.create_task(
                    _maybe_update_profile(user_id)
                )

                # Send updated session title (in case it changed from "New chat")
                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        select(ChatSession).where(ChatSession.id == current_session_id)
                    )
                    sess = result.scalar_one_or_none()
                    if sess:
                        await ws_manager.send({
                            "type": "session_updated",
                            "session_id": sess.id,
                            "title": sess.title,
                            "message_count": sess.message_count,
                        }, user_id)

            elif msg_type == "wizard_step_complete":
                await _handle_wizard_step(msg, user_id)

            elif msg_type == "wizard_cancel":
                pass  # Frontend handles UI dismiss

            elif msg_type == "job_cancel":
                job_id = msg.get("job_id")
                if job_id:
                    # Conditional: only a job that is still live is cancelled.
                    # update_job_status allows terminal→terminal writes (the
                    # boot sweep self-heals through them), so a late cancel
                    # used to rewrite an already-finished job as "cancelled".
                    from backend.agents.job_helper import cancel_if_live
                    await cancel_if_live(job_id)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WS error: {e}", exc_info=True)
    finally:
        ws_manager.disconnect(websocket, user_id)


async def _handle_wizard_step(msg: dict, user_id: str):
    """Process a wizard step completion — save the value to user settings."""
    from backend.core.crypto import encrypt
    from datetime import datetime

    wizard_id = msg.get("wizard_id", "")
    value = msg.get("value", "")

    if not value:
        return

    # Map wizard fields to user_settings columns
    encrypted_field_map = {
        "douyin_cookie": ("douyin_cookie_encrypted", "douyin_cookie_set_at"),
        "tiktok_cookie": ("tiktok_cookie_encrypted", "tiktok_cookie_set_at"),
    }

    plain_field_map = {}

    field = msg.get("field", "")
    is_encrypted = field in encrypted_field_map
    is_plain = field in plain_field_map

    if not is_encrypted and not is_plain:
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        settings = result.scalar_one_or_none()
        if not settings:
            settings = UserSettings(user_id=user_id)
            db.add(settings)

        if is_encrypted:
            col_name, timestamp_col = encrypted_field_map[field]
            setattr(settings, col_name, encrypt(value))
            if timestamp_col:
                setattr(settings, timestamp_col, datetime.utcnow())
        elif is_plain:
            setattr(settings, plain_field_map[field], value)

        await db.commit()

    await ws_manager.send({
        "type": "wizard_step_result",
        "step": msg.get("step"),
        "status": "success",
        "message": "Saved successfully!",
    }, user_id)
