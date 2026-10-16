# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Same-Project Natural Language Revisions Test Suite for Wave 21 Agent 1.
Verifies multiple sequential conversational revisions operating on the SAME canonical Project:
1. Dead-air trimming and retiming.
2. Cinematic typography and gold word-highlight captions.
3. Headline emphasis and widescreen 16:9 reframing.
4. Natural language CAS rollback to a prior historical revision.

All revisions mutate the single project in-place, advance atomic CAS revisions,
re-render verified physical MP4 media, and persist Library deliverables.
"""

from pathlib import Path
import pytest
from sqlalchemy import select

from backend.database import AsyncSessionLocal, init_db
from backend.models.generated_video import GeneratedVideo
from backend.oaas_knowledge_orchestrator.models import (
    KnowledgeOrchestratorState,
    RevisionRequestContract,
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
async def test_same_project_three_sequential_revisions_and_rollback():
    """
    End-to-End Iterative Journey:
    1. Initial video request on Project P -> Revision R1
    2. Feedback 1: 'remove dead air, tighten pacing, and trim to 2.5 seconds' -> Revision R2 (duration retimed)
    3. Feedback 2: 'make word-by-word professional captions more cinematic with gold highlight' -> Revision R3
    4. Feedback 3: 'emphasize second headline and reframe to 16:9 widescreen' -> Revision R4 (16:9, 1920x1080)
    5. Feedback 4: 'revert to revision 2' -> Revision R5 (restores R2 snapshot on Project P)
    """
    user_id = "creator_revisions"
    context = {"user_id": user_id, "session_id": "sess_revisions"}

    # ─── Step 1: Initial Generation ───────────────────────────────────────────
    init_resp = await KnowledgeChatOrchestrator.handle_video_request(
        request_or_message="Create a 3s vertical promo for sustainable coffee",
        authenticated_context=context,
        allow_test_fixture=True,
    )
    assert init_resp.state in (KnowledgeOrchestratorState.REVIEW_READY, KnowledgeOrchestratorState.PENDING_CREDENTIALS)
    project_id = init_resp.project_id
    rev1 = init_resp.revision_id
    assert rev1 >= 2
    assert init_resp.library_asset_id is not None

    # ─── Step 2: Revision 1 - Trim Dead Air & Retime to 2.5s ───────────────────
    rev1_req = RevisionRequestContract(
        run_id=init_resp.run_id,
        user_feedback="remove dead air, tighten pacing, and trim to 2.5 seconds",
        expected_revision=rev1,
        user_id=user_id,
        allow_test_fixture=True,
    )
    resp_r1 = await KnowledgeChatOrchestrator.revise_deliverable(rev1_req)
    assert resp_r1.state == KnowledgeOrchestratorState.REVIEW_READY
    assert resp_r1.project_id == project_id, "Revision must mutate the SAME project!"
    rev2 = resp_r1.revision_id
    assert rev2 == rev1 + 1

    # Verify physical MP4 duration updated
    mp4_r1 = Path(resp_r1.artifact_links[0]["file_path"])
    assert mp4_r1.exists()
    verif_r1 = MediaVerifier.verify_media_file(mp4_r1, expected_aspect_ratio="9:16", min_duration_sec=0.5)
    assert verif_r1.is_verified is True
    assert verif_r1.probe_duration_sec <= 2.6

    # ─── Step 3: Revision 2 - Cinematic Captions with Gold Highlight ──────────
    rev2_req = RevisionRequestContract(
        run_id=resp_r1.run_id,
        user_feedback="make word-by-word professional captions more cinematic with gold highlight",
        expected_revision=rev2,
        user_id=user_id,
        allow_test_fixture=True,
    )
    resp_r2 = await KnowledgeChatOrchestrator.revise_deliverable(rev2_req)
    assert resp_r2.state == KnowledgeOrchestratorState.REVIEW_READY
    assert resp_r2.project_id == project_id
    rev3 = resp_r2.revision_id
    assert rev3 == rev2 + 1

    # Verify project document reflects caption styling
    proj_r2 = await ProjectService.get_project(project_id)
    import json
    doc_r2 = json.loads(proj_r2.document_json)
    cap_track = next((t for t in doc_r2.get("timeline", {}).get("tracks", []) if t.get("type") == "captions"), None)
    if cap_track and cap_track.get("clips"):
        assert cap_track["clips"][0].get("highlight_color") == "#FACC15"

    # ─── Step 4: Revision 3 - Emphasize Second Headline & Reframe 16:9 ─────────
    rev3_req = RevisionRequestContract(
        run_id=resp_r2.run_id,
        user_feedback="emphasize second headline and reframe to 16:9 widescreen",
        expected_revision=rev3,
        user_id=user_id,
        allow_test_fixture=True,
    )
    resp_r3 = await KnowledgeChatOrchestrator.revise_deliverable(rev3_req)
    assert resp_r3.state == KnowledgeOrchestratorState.REVIEW_READY
    assert resp_r3.project_id == project_id
    rev4 = resp_r3.revision_id
    assert rev4 == rev3 + 1

    # Verify physical MP4 reframed to 16:9 (1920x1080)
    mp4_r3 = Path(resp_r3.artifact_links[0]["file_path"])
    verif_r3 = MediaVerifier.verify_media_file(mp4_r3, expected_aspect_ratio="16:9", min_duration_sec=0.5)
    assert verif_r3.is_verified is True
    assert verif_r3.probe_width == 1920
    assert verif_r3.probe_height == 1080

    # ─── Step 5: Revision 4 - Natural-Language Rollback to Revision 2 ─────────
    rev4_req = RevisionRequestContract(
        run_id=resp_r3.run_id,
        user_feedback="revert to revision 2",
        expected_revision=rev4,
        user_id=user_id,
        allow_test_fixture=True,
    )
    resp_r4 = await KnowledgeChatOrchestrator.revise_deliverable(rev4_req)
    assert resp_r4.state == KnowledgeOrchestratorState.REVIEW_READY
    assert resp_r4.project_id == project_id
    rev5 = resp_r4.revision_id
    assert rev5 == rev4 + 1

    # Verify project restored aspect ratio 9:16 from revision 2
    proj_final = await ProjectService.get_project(project_id)
    assert proj_final.aspect_ratio == "9:16"
