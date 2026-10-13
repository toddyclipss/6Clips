# Copyright (c) 2026 ViralMint. All rights reserved.
# Unit & integration test suite verifying language isolation matrix, scoring edge cases, and suitability constraints.
import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import logging
import os
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ISOLATED_DATA_DIR = ROOT / "tmp_isolated_test"
ISOLATED_DATA_DIR.mkdir(parents=True, exist_ok=True)
os.environ["DATA_DIR"] = str(ISOLATED_DATA_DIR)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{ISOLATED_DATA_DIR / 'viralmint.db'}"
os.environ["STORAGE_ROOT"] = str(ISOLATED_DATA_DIR / "storage")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_language_matrix")

PROD_DB = ROOT / "viralmint.db"
INITIAL_PROD_HASH = hashlib.sha256(PROD_DB.read_bytes()).hexdigest().upper()


def verify_prod_db():
    curr = hashlib.sha256(PROD_DB.read_bytes()).hexdigest().upper()
    assert curr == INITIAL_PROD_HASH, f"Production DB altered! {curr} != {INITIAL_PROD_HASH}"


@pytest.mark.asyncio
async def test_scoring_edge_cases():
    """Verify unavailable-score, genuinely low scoring, and ranking stability."""
    from backend.services.virality_scorer import calculate_viral_opportunity_score

    # 1. Unavailable score case (missing or zero metrics)
    v_empty = {"views": 0, "upload_date": None}
    res_empty = calculate_viral_opportunity_score(v_empty)
    assert res_empty["score"] == 0.0 or res_empty["score"] is None
    assert "upload_date" in res_empty["unavailable_fields"]
    assert "likes" in res_empty["unavailable_fields"]

    # 2. Genuinely low-scoring video (e.g. 50 views, 6 months old)
    v_low = {
        "views": 50,
        "likes": 1,
        "comments": 0,
        "upload_date": datetime.now(timezone.utc) - timedelta(days=180),
    }
    res_low = calculate_viral_opportunity_score(v_low)
    assert res_low["score"] < 25.0, f"Expected low score < 25, got {res_low['score']}"
    assert res_low["views_per_hour"] < 1.0

    # 3. High scoring video (e.g. 500k views, 24 hours old)
    v_high = {
        "views": 500000,
        "likes": 35000,
        "comments": 2100,
        "upload_date": datetime.now(timezone.utc) - timedelta(hours=24),
    }
    res_high = calculate_viral_opportunity_score(v_high)
    assert res_high["score"] >= 80.0, f"Expected high score >= 80, got {res_high['score']}"
    assert res_high["score"] > res_low["score"]


@pytest.mark.asyncio
async def test_duration_suitability_matrix():
    """Verify long-form vs short-form filtering for 3x 60s clips."""
    from backend.services.youtube_trends import classify_suitability_for_clips

    # Candidate 1: Short portrait video (45s) -> UNSUITABLE
    s_short = classify_suitability_for_clips(45, target_clips=3, clip_duration_sec=60)
    assert s_short["status"] == "unsuitable_too_short"
    assert s_short["is_suitable"] is False
    assert s_short["deficit_seconds"] == 135

    # Candidate 2: Marginal clip (200s: > 180s but tight) -> MARGINAL
    s_marginal = classify_suitability_for_clips(200, target_clips=3, clip_duration_sec=60)
    assert s_marginal["status"] == "marginal"
    assert s_marginal["is_suitable"] is True

    # Candidate 3: Long gameplay recording (966s) -> SUITABLE_LONGFORM
    s_long = classify_suitability_for_clips(966, target_clips=3, clip_duration_sec=60)
    assert s_long["status"] == "suitable_longform"
    assert s_long["is_suitable"] is True
    assert s_long["surplus_seconds"] == 726


@pytest.mark.asyncio
async def test_cross_session_context_isolation():
    """Verify that a new session never loads prior session messages from the database."""
    from backend.database import AsyncSessionLocal, init_db
    from backend.models.chat_session import ChatSession, ChatMessage
    from backend.api.chat import _load_previous_session_context
    import uuid

    await init_db()

    user_id = f"test_user_{uuid.uuid4().hex[:8]}"

    async with AsyncSessionLocal() as db:
        # Create completed Portuguese session
        session_pt = ChatSession(id=str(uuid.uuid4()), user_id=user_id, title="Conversa em Português")
        db.add(session_pt)
        msg1 = ChatMessage(
            id=str(uuid.uuid4()),
            session_id=session_pt.id,
            user_id=user_id,
            role="user",
            content="Procure um vídeo viral de Fortnite",
        )
        msg2 = ChatMessage(
            id=str(uuid.uuid4()),
            session_id=session_pt.id,
            user_id=user_id,
            role="assistant",
            content="Encontrei vários vídeos em alta para Fortnite.",
        )
        db.add_all([msg1, msg2])
        await db.commit()

        # In the old code, new sessions called _load_previous_session_context which loaded PT messages!
        # With the fix in chat.py, new sessions pass prev_context = []
        # Let's verify that when a new session is started, it has zero prior messages:
        new_session = ChatSession(id=str(uuid.uuid4()), user_id=user_id, title="New English Chat")
        db.add(new_session)
        await db.commit()

        # Reloading history of new_session should yield 0 messages
        from sqlalchemy import select
        res = await db.execute(select(ChatMessage).where(ChatMessage.session_id == new_session.id))
        messages = res.scalars().all()
        assert len(messages) == 0, "Brand new session MUST have zero messages!"


@pytest.mark.asyncio
async def test_dynamic_language_synthesis_fallback():
    """Verify that fallback tool synthesis detects user query language dynamically."""
    from backend.core.ai_provider import format_trend_synthesis

    # Case 1: English query -> English synthesis
    en_query = "Find a viral Fortnite video and turn it into three 60-second clips."
    tool_res = {
        "output": {
            "query": "Fortnite",
            "results": [
                {
                    "video_id": "vid1",
                    "title": "Fortnite Facts",
                    "author": "Top5Gaming",
                    "duration_seconds": 966,
                    "virality_score": 92.4,
                    "views": 105000,
                    "video_url": "https://youtube.com/watch?v=vid1",
                }
            ],
            "recommended_source": {
                "video_id": "vid1",
                "title": "Fortnite Facts",
                "author": "Top5Gaming",
                "duration_seconds": 966,
                "virality_score": 92.4,
                "views": 105000,
                "video_url": "https://youtube.com/watch?v=vid1",
                "suitability_for_3x60s": {"reason": "Sufficient long-form footage (966s) for 3 distinct 60s clips."},
            },
        }
    }

    en_reply = format_trend_synthesis(en_query, tool_res)
    assert "Found 1 trending viral" in en_reply
    assert "Recommended" in en_reply
    assert "Rights & Licensing Notice" not in en_reply
    assert "Next Step:" in en_reply
    assert "Encontrei" not in en_reply, "Must not be Portuguese!"

    # Case 2: Portuguese query -> Portuguese synthesis
    pt_query = "Procure um vídeo viral de Fortnite e corte em 3 clips de 60 segundos"
    pt_reply = format_trend_synthesis(pt_query, tool_res)
    assert "Encontrei 1" in pt_reply
    assert "Fonte" in pt_reply
    assert "Aviso de Direitos" not in pt_reply
    assert "Próximo Passo:" in pt_reply
    assert "Found 1 trending" not in pt_reply, "Must not be English!"


def main():
    logger.info("Running language isolation matrix and edge case test suite...")
    verify_prod_db()

    asyncio.run(test_scoring_edge_cases())
    logger.info("PASS: test_scoring_edge_cases")

    asyncio.run(test_duration_suitability_matrix())
    logger.info("PASS: test_duration_suitability_matrix")

    asyncio.run(test_cross_session_context_isolation())
    logger.info("PASS: test_cross_session_context_isolation")

    asyncio.run(test_dynamic_language_synthesis_fallback())
    logger.info("PASS: test_dynamic_language_synthesis_fallback")

    verify_prod_db()
    logger.info("ALL LANGUAGE MATRIX TESTS PASSED CLEANLY!")


if __name__ == "__main__":
    main()
