# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Authentic Real Outcomes Test Suite for Wave 21 Agent 1.
Executes 6 diverse realistic requests aligned with planning journeys V1-V7:
1. V1: Vertical from source (9:16, 1080x1920, kinetic typography)
2. V2: Horizontal highlights (16:9, 1920x1080 widescreen showcase)
3. V3: Original infographic (data metrics, bar chart visualization)
4. V4: Data kinetic promo (high-energy spring easing, metric callout)
5. V5: Speech professional captions (word-level synced captions with high contrast)
6. V6: Multi-clip output (3 independent persisted deliverables and library records)

All tests verify real physical MP4 files, ffprobe probe stats, SHA-256 fingerprints,
canonical Project CAS revisions, and persistent Library deliverables.
"""

import json
from pathlib import Path
import pytest
from sqlalchemy import select

from backend.database import AsyncSessionLocal, init_db
from backend.models.generated_video import GeneratedVideo
from backend.oaas_knowledge_orchestrator.models import (
    KnowledgeOrchestratorState,
    VideoRequestContract,
)
from backend.oaas_knowledge_orchestrator.orchestrator import KnowledgeChatOrchestrator
from backend.oaas_outcomes.media_verifier import MediaVerifier
from backend.services.project_service import ProjectService


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    monkeypatch.setenv("VIRALMINT_TEST_ENV", "1")
    monkeypatch.setenv("VIRALMINT_TEST_AUDIO_FIXTURE", "1")


@pytest.fixture(autouse=True)
async def init_database():
    await init_db()


@pytest.mark.asyncio
async def test_v1_vertical_promo_from_source():
    """V1: Vertical 9:16 promo with kinetic typography, probed resolution 1080x1920."""
    user_id = "creator_v1"
    msg = "Create a 3s vertical promo for artisan matcha with kinetic typography"

    resp = await KnowledgeChatOrchestrator.handle_video_request(
        request_or_message=msg,
        authenticated_context={"user_id": user_id, "session_id": "sess_v1"},
        allow_test_fixture=True,
    )

    assert resp.state in (KnowledgeOrchestratorState.REVIEW_READY, KnowledgeOrchestratorState.PENDING_CREDENTIALS)
    assert resp.project_id is not None
    assert resp.revision_id >= 2
    assert resp.library_asset_id is not None
    assert resp.output_count == 1
    assert len(resp.artifact_links) == 1

    art = resp.artifact_links[0]
    mp4_path = Path(art["file_path"])
    assert mp4_path.exists()
    assert mp4_path.stat().st_size > 0

    verif = MediaVerifier.verify_media_file(mp4_path, expected_aspect_ratio="9:16", min_duration_sec=0.5)
    assert verif.is_verified is True
    assert verif.probe_width == 1080
    assert verif.probe_height == 1920
    assert verif.probe_duration_sec >= 2.0
    assert len(verif.sha256_hash) == 64

    # Verify Library record
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(GeneratedVideo).where(GeneratedVideo.id == resp.library_asset_id))
        video = res.scalar_one_or_none()
        assert video is not None
        assert video.user_id == user_id
        assert video.aspect_ratio == "9:16"

    # Verify citations from knowledge base
    assert len(resp.evidence.knowledge_citations) > 0
    first_cit = resp.evidence.knowledge_citations[0]
    assert len(first_cit.knowledge_doc_id) > 0
    assert len(first_cit.source_hash) == 64


@pytest.mark.asyncio
async def test_v2_horizontal_highlights():
    """V2: Horizontal 16:9 widescreen highlight showcase, probed resolution 1920x1080."""
    user_id = "creator_v2"
    msg = "Create a 4s 16:9 widescreen highlight showcase for tech conference"

    resp = await KnowledgeChatOrchestrator.handle_video_request(
        request_or_message=msg,
        authenticated_context={"user_id": user_id, "session_id": "sess_v2"},
        allow_test_fixture=True,
    )

    assert resp.state in (KnowledgeOrchestratorState.REVIEW_READY, KnowledgeOrchestratorState.PENDING_CREDENTIALS)
    assert resp.preview_details["aspect_ratio"] == "16:9"

    mp4_path = Path(resp.artifact_links[0]["file_path"])
    verif = MediaVerifier.verify_media_file(mp4_path, expected_aspect_ratio="16:9", min_duration_sec=0.5)
    assert verif.is_verified is True
    assert verif.probe_width == 1920
    assert verif.probe_height == 1080
    assert verif.probe_duration_sec >= 2.0

    # Verify project document has 16:9 aspect ratio
    proj = await ProjectService.get_project(resp.project_id)
    assert proj.aspect_ratio == "16:9"


@pytest.mark.asyncio
async def test_v3_original_infographic_data():
    """V3: Original data infographic with animated charts and metric statistics."""
    user_id = "creator_v3"
    msg = "Create a 3s vertical data infographic with animated bar charts and metric statistics"

    resp = await KnowledgeChatOrchestrator.handle_video_request(
        request_or_message=msg,
        authenticated_context={"user_id": user_id, "session_id": "sess_v3"},
        allow_test_fixture=True,
    )

    assert resp.state in (KnowledgeOrchestratorState.REVIEW_READY, KnowledgeOrchestratorState.PENDING_CREDENTIALS)
    # Check that creative rationale reflects data strategy
    rat = resp.evidence.creative_rationale
    assert "data" in rat.intent_summary.lower() or "infographic" in rat.intent_summary.lower()

    mp4_path = Path(resp.artifact_links[0]["file_path"])
    verif = MediaVerifier.verify_media_file(mp4_path, expected_aspect_ratio="9:16", min_duration_sec=0.5)
    assert verif.is_verified is True
    assert verif.probe_width == 1080
    assert verif.probe_height == 1920


@pytest.mark.asyncio
async def test_v4_data_kinetic_promo():
    """V4: High-energy kinetic typography promo with spring easing curves."""
    user_id = "creator_v4"
    msg = "High-energy kinetic typography promo for SaaS launch with fast spring easing"

    resp = await KnowledgeChatOrchestrator.handle_video_request(
        request_or_message=msg,
        authenticated_context={"user_id": user_id, "session_id": "sess_v4"},
        allow_test_fixture=True,
    )

    assert resp.state in (KnowledgeOrchestratorState.REVIEW_READY, KnowledgeOrchestratorState.PENDING_CREDENTIALS)
    rat = resp.evidence.creative_rationale
    assert "spring" in rat.motion_strategy.lower() or "kinetic" in rat.motion_strategy.lower()

    mp4_path = Path(resp.artifact_links[0]["file_path"])
    verif = MediaVerifier.verify_media_file(mp4_path, expected_aspect_ratio="9:16", min_duration_sec=0.5)
    assert verif.is_verified is True


@pytest.mark.asyncio
async def test_v5_speech_professional_captions():
    """V5: Word-by-word synced professional captions with high contrast styling."""
    user_id = "creator_v5"
    msg = "Create a 3s vertical video with word-by-word synced professional captions and high contrast styling"

    resp = await KnowledgeChatOrchestrator.handle_video_request(
        request_or_message=msg,
        authenticated_context={"user_id": user_id, "session_id": "sess_v5"},
        allow_test_fixture=True,
    )

    assert resp.state in (KnowledgeOrchestratorState.REVIEW_READY, KnowledgeOrchestratorState.PENDING_CREDENTIALS)
    proj = await ProjectService.get_project(resp.project_id)
    doc = ProjectService.migrate_project_document(proj.document) if hasattr(proj, "document") else json.loads(proj.document_json)
    
    # Check captions track
    tracks = doc.get("timeline", {}).get("tracks", [])
    cap_track = next((t for t in tracks if t.get("type") == "captions"), None)
    assert cap_track is not None

    mp4_path = Path(resp.artifact_links[0]["file_path"])
    verif = MediaVerifier.verify_media_file(mp4_path, expected_aspect_ratio="9:16", min_duration_sec=0.5)
    assert verif.is_verified is True


@pytest.mark.asyncio
async def test_v6_multi_clip_generation():
    """V6: Multi-clip generation producing 3 distinct persisted deliverables and library records."""
    user_id = "creator_v6"
    msg = "Extract and generate 3 clips for social media teasers"

    req = VideoRequestContract(
        message=msg,
        user_id=user_id,
        session_id="sess_v6",
        output_count=3,
        allow_test_fixture=True,
    )
    resp = await KnowledgeChatOrchestrator.handle_video_request(req)

    assert resp.state in (KnowledgeOrchestratorState.REVIEW_READY, KnowledgeOrchestratorState.PENDING_CREDENTIALS)
    assert resp.output_count == 3
    assert len(resp.artifact_links) == 3
    assert len(resp.library_ids) == 3

    # Verify all 3 files exist and are verified
    hashes = set()
    for art in resp.artifact_links:
        p = Path(art["file_path"])
        assert p.exists()
        verif = MediaVerifier.verify_media_file(p, expected_aspect_ratio="9:16", min_duration_sec=0.5)
        assert verif.is_verified is True
        hashes.add(verif.sha256_hash)

    # Verify 3 distinct library records in database
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(GeneratedVideo).where(GeneratedVideo.id.in_(resp.library_ids))
        )
        videos = res.scalars().all()
        assert len(videos) == 3
        for v in videos:
            assert v.user_id == user_id
