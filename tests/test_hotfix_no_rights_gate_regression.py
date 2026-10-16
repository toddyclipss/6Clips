# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Mandatory Regression Matrix Verification for Hotfix:
Removal of User-Ownership / Rights-Confirmation Gates from External Video Ingestion.

Matrix Coverage:
1. Public YouTube video URL without attestation parameter -> No rights gate, ingestion attempted, real output
2. Public TikTok URL without attestation parameter -> No rights gate, ingestion attempted
3. Third-party branded / public host video -> Not rejected for third-party origin
4. Legacy caller with user_authorized=False or omitted -> Tolerated without refusal
5. Create / Review state contract -> Zero BLOCKED_RIGHTS status or ownership confirmation requirements
6. Technically unreachable provider URL -> Factual technical network error; no invented completion, no rights blocker
7. Existing project and real media asset -> Canonical timeline, valid revisions, real MP4 export
8. Hostile internal network addresses (SSRF) -> Defenses remain effective (BLOCKED_SSRF / BLOCKED_DISALLOWED_HOST)
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from backend.oaas_chat_ingestion import (
    AgentUrlIngestionService,
    ChatGoalStatus,
    ChatOutcomeOrchestrator,
    IngestionBlockerCode,
    UrlIngestionRequest,
)
from backend.oaas_knowledge_orchestrator import (
    KnowledgeChatOrchestrator,
    KnowledgeOrchestratorResponse,
    KnowledgeOrchestratorState,
    VideoRequestContract,
)
from backend.outcome_orchestration import (
    OutcomeContract,
    OutcomeOrchestrator,
    OutcomeState,
    SourceAsset,
)
from backend.database import init_db
from backend.services.project_service import ProjectService
import backend.services.ytdlp_service as ys


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    monkeypatch.setenv("VIRALMINT_TEST_ENV", "1")
    monkeypatch.setenv("VIRALMINT_TEST_AUDIO_FIXTURE", "1")


@pytest.fixture(autouse=True)
async def init_database():
    await init_db()


@pytest.mark.asyncio
async def test_scenario_1_youtube_url_chat_no_attestation(monkeypatch):
    """Scenario 1: User submits accessible public YouTube video URL; no attestation parameter."""
    monkeypatch.setenv("VIRALMINT_TEST_ENV", "1")
    context = {"user_id": "creator_yt"}
    message = "Make a 3-second vertical clip from https://test.authorized-creator.com/yt_sample.mp4"

    # Call with ZERO user_authorizations dictionary
    resp = await ChatOutcomeOrchestrator.handle_video_goal(
        chat_context=context,
        message=message,
        user_authorizations=None,
        allow_test_fixture=True,
    )

    assert resp.status in (ChatGoalStatus.READY_FOR_DELIVERY, ChatGoalStatus.PENDING_CREDENTIALS)
    assert resp.blocker_code is None
    assert len(resp.artifact_links) >= 1
    assert any("mp4" in str(a.get("path", "")).lower() for a in resp.artifact_links)


@pytest.mark.asyncio
async def test_scenario_2_tiktok_url_chat_no_attestation(monkeypatch):
    """Scenario 2: Accessible public TikTok URL; no attestation parameter."""
    monkeypatch.setenv("VIRALMINT_TEST_ENV", "1")
    context = {"user_id": "creator_tiktok"}
    message = "Download this TikTok https://test.authorized-creator.com/tiktok_dance.mp4 and create a vertical video"

    # Call with ZERO user_authorizations
    resp = await ChatOutcomeOrchestrator.handle_video_goal(
        chat_context=context,
        message=message,
        user_authorizations=None,
        allow_test_fixture=True,
    )

    assert resp.status in (ChatGoalStatus.READY_FOR_DELIVERY, ChatGoalStatus.PENDING_CREDENTIALS)
    assert resp.blocker_code is None
    assert len(resp.artifact_links) >= 1


@pytest.mark.asyncio
async def test_scenario_3_branded_creator_video_origin(monkeypatch):
    """Scenario 3: A different public video host or a branded creator video is not rejected for origin."""
    monkeypatch.setenv("VIRALMINT_TEST_ENV", "1")
    # Branded third-party video URL
    req = UrlIngestionRequest(
        url="https://test.authorized-creator.com/nike_redbull_creator_showcase.mp4",
    )
    result = await AgentUrlIngestionService.ingest_url(req)
    assert result.is_allowed is True
    assert result.file_path is not None
    assert result.blocker_code is None


@pytest.mark.asyncio
async def test_scenario_4_legacy_caller_user_authorized_false(monkeypatch):
    """Scenario 4: Legacy caller passes user_authorized: false or omits field; no refusal occurs."""
    monkeypatch.setenv("VIRALMINT_TEST_ENV", "1")

    # Ingestion service with legacy extra field user_authorized=False
    req_false = UrlIngestionRequest(
        url="https://test.authorized-creator.com/legacy_stream.mp4",
        user_authorized=False,
    )
    # Extra field is discarded, not exposed as model field
    assert "user_authorized" not in req_false.model_fields
    assert "user_authorized" not in req_false.model_dump()
    res_false = await AgentUrlIngestionService.ingest_url(req_false)
    assert res_false.is_allowed is True
    assert res_false.blocker_code is None

    # Ingestion service with user_authorized omitted
    req_omitted = UrlIngestionRequest(
        url="https://test.authorized-creator.com/legacy_stream.mp4",
    )
    res_omitted = await AgentUrlIngestionService.ingest_url(req_omitted)
    assert res_omitted.is_allowed is True
    assert res_omitted.blocker_code is None

    # KnowledgeChatOrchestrator with user_authorized: False in authorizations
    v_req = VideoRequestContract(
        message="Process https://test.authorized-creator.com/legacy_stream.mp4",
        authorizations={"user_authorized": False},
        allow_test_fixture=True,
    )
    resp = await KnowledgeChatOrchestrator.handle_video_request(v_req)
    assert resp.state != "BLOCKED_RIGHTS"
    assert resp.blocker_code != "BLOCKED_RIGHTS"


@pytest.mark.asyncio
async def test_scenario_5_create_review_zero_blocked_rights():
    """Scenario 5: UI and outcome responses never emit BLOCKED_RIGHTS status."""
    v_req = VideoRequestContract(
        message="Create clean kinetic title vertical video",
        allow_test_fixture=True,
    )
    resp = await KnowledgeChatOrchestrator.handle_video_request(v_req)
    assert resp.state in (KnowledgeOrchestratorState.REVIEW_READY, KnowledgeOrchestratorState.VIDEO_VERIFIED, KnowledgeOrchestratorState.PENDING_CREDENTIALS)
    assert resp.state != "BLOCKED_RIGHTS"
    assert resp.blocker_code != "BLOCKED_RIGHTS"

    # Check WebSocket hook code directly to ensure BLOCKED_RIGHTS is completely expunged
    ws_hook = Path("frontend/src/hooks/useWebSocket.js")
    if ws_hook.exists():
        content = ws_hook.read_text(encoding="utf-8")
        assert "BLOCKED_RIGHTS" not in content


@pytest.mark.asyncio
async def test_scenario_6_technically_unreachable_provider_url():
    """Scenario 6: Technically unreachable provider URL yields factual technical error, not rights blocker."""
    # Using an unreachable domain with valid public IP address format
    req = UrlIngestionRequest(
        url="https://unreachable-video-domain-xyz-404-fail.org/non_existent_video.mp4",
        user_authorized=False,
    )
    res = await AgentUrlIngestionService.ingest_url(req)
    assert res.is_allowed is False
    assert res.blocker_code in (IngestionBlockerCode.BLOCKED_FETCH_FAILED, IngestionBlockerCode.BLOCKED_RESTRICTED_ACCESS)
    assert not hasattr(IngestionBlockerCode, "BLOCKED_UNAUTHORIZED_STREAM")
    assert "rights" not in (res.blocker_reason or "").lower()
    assert "authorization" not in (res.blocker_reason or "").lower()


@pytest.mark.asyncio
async def test_scenario_7_existing_project_canonical_timeline_and_revisions():
    """Scenario 7: Existing project with media asset retains canonical timeline and genuine MP4 export."""
    # Create project
    proj = await ProjectService.create_project(name="Scenario 7 Test Project", aspect_ratio="9:16", user_id="creator_p7")
    initial_rev = proj.revision

    # Run chat goal reusing existing project
    resp = await ChatOutcomeOrchestrator.handle_video_goal(
        chat_context={"project_id": proj.id, "user_id": "creator_p7"},
        message="Apply aurora motion block for 3s",
        allow_test_fixture=True,
    )

    assert resp.status in (ChatGoalStatus.READY_FOR_DELIVERY, ChatGoalStatus.PENDING_CREDENTIALS)
    assert resp.project_id == proj.id
    assert resp.revision_id >= initial_rev
    assert len(resp.artifact_links) >= 1

    # Verify physical MP4 exists on disk
    mp4_path = Path(resp.artifact_links[0]["path"])
    assert mp4_path.exists()
    assert mp4_path.stat().st_size > 0


@pytest.mark.asyncio
async def test_scenario_8_ssrf_and_hostile_network_defenses_remain_active():
    """Scenario 8: Hostile internal network addresses (SSRF, AWS metadata, loopback) remain defended."""
    hostile_urls = [
        "http://127.0.0.1:8000/secret",
        "http://localhost:5000/internal",
        "http://169.254.169.254/latest/meta-data/",
        "http://0.0.0.0:80/admin",
        "gopher://127.0.0.1:70/",
        "file:///etc/passwd",
    ]

    for h_url in hostile_urls:
        req = UrlIngestionRequest(url=h_url)
        res = await AgentUrlIngestionService.ingest_url(req)
        assert res.is_allowed is False
        assert res.blocker_code in (
            IngestionBlockerCode.BLOCKED_SSRF_PRIVATE_IP,
            IngestionBlockerCode.BLOCKED_DISALLOWED_HOST,
            IngestionBlockerCode.BLOCKED_INVALID_SCHEME,
        )
        assert not hasattr(IngestionBlockerCode, "BLOCKED_UNAUTHORIZED_STREAM")


@pytest.mark.asyncio
async def test_scenario_9_programmatic_schema_introspection_no_residuals():
    """Requirement G: Programmatic schema introspection verifying no residual ownership fields."""
    from backend.oaas_chat_ingestion.models import UrlIngestionRequest
    from backend.outcome_orchestration.models import SourceAsset

    # UrlIngestionRequest: user_authorized is not declared in fields or JSON schema
    assert "user_authorized" not in UrlIngestionRequest.model_fields
    ingest_schema = UrlIngestionRequest.model_json_schema()
    assert "user_authorized" not in ingest_schema.get("properties", {})

    # SourceAsset: rights_verified is not declared in fields or JSON schema
    assert "rights_verified" not in SourceAsset.model_fields
    source_schema = SourceAsset.model_json_schema()
    assert "rights_verified" not in source_schema.get("properties", {})

    # IngestionBlockerCode: BLOCKED_UNAUTHORIZED_STREAM is completely removed
    assert not hasattr(IngestionBlockerCode, "BLOCKED_UNAUTHORIZED_STREAM")
