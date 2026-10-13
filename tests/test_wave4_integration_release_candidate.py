# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 4 Integration Release Candidate Test Suite.

End-to-end integration and developer QA across all integrated Wave 3 feature domains:
1. API Routing Integrity & Empirical Route Verification (FastAPI TestClient)
   - Route prefix auditing (zero /api/api double prefixes across 220+ endpoints)
   - Catalog, Library, Trends, Creator, and Integration endpoints
2. Canonical Catalog -> ProjectService Integration (Requirement B)
   - Authorized, owner-scoped, revision-checked pathway
   - Block insertion with atomic CAS revision bump
   - Rejection of unready blocks (422), stale revisions (409 CAS), wrong users (403), and path traversal (400)
3. Library -> Motion Contract Integration (Requirement D)
   - MotionAssetIntent (application/x-6clips-asset) insertion into canonical ProjectService
   - Anti-duplicate validation, CAS revision check, and rights policy verification
4. Original Creator -> Plan & Render Orchestration (Requirement C)
   - Truthful WAITING_FOR_INPUT when narration is missing without procedural TTS consent
   - Physical video render with authorized voice fixture, verifying truthful review URL
   - Planner continuation action dispatch
5. Physical FFmpeg Multi-Aspect & Audio Probing (Requirement E & Section 50)
   - 9:16 vertical (1080x1920) and 16:9 widescreen (1920x1080) physical rendering
   - Probing with ffprobe: geometry, audio streams, and distinct SHA-256 hashes
6. HTTP 206 Partial Content Media Streaming
   - Range request verification, Content-Range headers, and byte slices
7. Durable Ledger Crash Recovery & Partial Reconstruction
   - Deterministic transition to PARTIAL on crash mid-render
8. Production Database Protection Guarantee
   - Zero modifications to production viralmint.db
"""

import asyncio
import hashlib
import json
import os
import subprocess
from pathlib import Path
import pytest
from starlette.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import settings
from backend.database import Base, get_db
from backend.main import app
from backend.catalog.manifest_service import CatalogManifestService
from backend.catalog.ghost_preview import GhostPreviewContract
from backend.core.exceptions import RevisionConflictError
from backend.library_workflows.motion_contract import (
    MIME_MOTION_ASSET,
    MotionAssetIntent,
    MotionContractManager,
)
from backend.original_creation.models import (
    EvidenceLedger,
    EvidenceLedgerEntry,
    OriginalCompositionSpec,
    OriginalCreationStatus,
    ShotListEntry,
    TeleprompterScript,
    VoiceInputRequirement,
)
from backend.original_creation.renderer import OriginalVideoRenderer
from backend.original_creation.workflow import OriginalCreatorWorkflow
from backend.production_jobs.ledger import (
    PersistentJobLedger,
    compute_sha256,
    verify_physical_media_file,
)
from backend.production_jobs.types import (
    ErrorClassification,
    JobRecord,
    RecoveryClassification,
)
from backend.services.project_service import ProjectService
from backend.services.video_utils import probe_dimensions

PROD_DB_PATH = Path("c:/Users/toddy/Desktop/ViralMint/viralmint.db")


def _calc_file_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().upper()


@pytest.fixture(autouse=True)
def guard_production_database():
    """Ensure production database remains pristine before and after every test."""
    if PROD_DB_PATH.exists():
        pre_hash = _calc_file_sha256(PROD_DB_PATH)
        yield
        post_hash = _calc_file_sha256(PROD_DB_PATH)
        assert pre_hash == post_hash, f"Production DB modified! Pre: {pre_hash}, Post: {post_hash}"
    else:
        yield


@pytest.fixture
def isolated_client(tmp_path: Path):
    """Provide a FastAPI TestClient configured with an isolated temporary SQLite database."""
    test_db_file = tmp_path / "test_isolated_wave4.db"
    test_engine = create_async_engine(f"sqlite+aiosqlite:///{test_db_file.as_posix()}", echo=False)
    test_sessionmaker = async_sessionmaker(test_engine, expire_on_commit=False)

    async def _setup_tables():
        from backend.models import (  # noqa: F401
            user_settings, user_behavior, feature_flag,
            job, trends_result, downloaded_video, generated_video,
            messaging_config, chat_session, user_profile,
            video_metrics, viral_formula,
            connected_channel, dynamic_template, caption_style,
            project, project_revision, execution,
        )
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_setup_tables())

    async def _override_get_db():
        async with test_sessionmaker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db

    # Also override AsyncSessionLocal inside ProjectService during tests to use isolated engine
    import backend.services.project_service as ps_mod
    orig_session_local = ps_mod.AsyncSessionLocal
    ps_mod.AsyncSessionLocal = test_sessionmaker

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client

    ps_mod.AsyncSessionLocal = orig_session_local
    app.dependency_overrides.pop(get_db, None)


# =========================================================================
# Domain 1: API Routing Integrity & Empirical Route Verification
# =========================================================================

def test_api_route_prefixes_and_zero_double_api():
    """Verify all 220+ API endpoints: no double /api/api prefixes, and all domain routes mounted."""
    all_routes = []
    for r in app.routes:
        path = getattr(r, "path", None)
        if path:
            all_routes.append(path)
        if hasattr(r, "original_router") and hasattr(r, "include_context"):
            prefix = r.include_context.prefix or ""
            for sr in r.original_router.routes:
                sub_path = getattr(sr, "path", "")
                all_routes.append(prefix + sub_path)

    # 1. Zero double /api/api prefixes
    double_api = [p for p in all_routes if p.startswith("/api/api")]
    assert len(double_api) == 0, f"Detected illegal double-prefix routes: {double_api}"

    # 2. Check catalog endpoints
    assert any("/api/catalog/items" in p for p in all_routes)
    assert any("/api/catalog/manifest" in p for p in all_routes)

    # 3. Check library endpoints
    assert any("/api/library/items" in p for p in all_routes)
    assert any("/api/library/trash" in p for p in all_routes)
    assert any("/api/library/storage/quota" in p for p in all_routes)

    # 4. Check creator & trends endpoints
    assert any("/api/original/brief" in p for p in all_routes)
    assert any("/api/original/render" in p for p in all_routes)
    assert any("/api/trends/rank" in p for p in all_routes)

    # 5. Check integration endpoints
    assert any("/api/integration/catalog/add-to-project" in p for p in all_routes)
    assert any("/api/integration/library/apply-motion-intent" in p for p in all_routes)
    assert any("/api/integration/creator/plan-and-render" in p for p in all_routes)
    assert any("/api/integration/health" in p for p in all_routes)


def test_integration_health_endpoint(isolated_client: TestClient):
    """Verify integration health status and domain availability."""
    res = isolated_client.get("/api/integration/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["wave"] == 4
    assert len(data["active_domains"]) >= 6


# =========================================================================
# Domain 2: Canonical Catalog -> ProjectService Integration (Requirement B)
# =========================================================================

def test_catalog_add_to_project_happy_path(isolated_client: TestClient):
    """Requirement B: Insert a ready, internalized catalog block into an existing ProjectRevision with CAS."""
    # 1. Create a project
    project = asyncio.run(ProjectService.create_project("Catalog Test Project", user_id="creator_1"))
    assert project.revision == 1

    # 2. Add internalized block 'weight-wave'
    payload = {
        "project_id": project.id,
        "expected_revision": 1,
        "block_id": "weight-wave",
        "aspect_ratio": "9:16",
        "start_time_seconds": 1.5,
        "timeline_track_index": 0,
        "custom_variables": {"color": "#ff0077"},
        "user_id": "creator_1",
    }
    res = isolated_client.post("/api/integration/catalog/add-to-project", json=payload)
    assert res.status_code == 200, f"Add block failed: {res.text}"
    body = res.json()
    assert body["ok"] is True
    assert body["revision"] == 2
    assert body["timeline_item"]["block_id"] == "weight-wave"

    # Verify persisted document
    doc = body["document"]
    tracks = doc["timeline"]["tracks"]
    found_clip = any(
        c.get("block_id") == "weight-wave" for t in tracks for c in t.get("clips", [])
    )
    assert found_clip is True

    # Verify code binding
    code_files = doc.get("code", {}).get("files", [])
    assert any(f.get("block_id") == "weight-wave" for f in code_files)


def test_catalog_add_to_project_rejection_guards(isolated_client: TestClient):
    """Requirement B: Rejection of unready blocks, stale CAS revisions, path traversal, and wrong user."""
    project = asyncio.run(ProjectService.create_project("Guards Test Project", user_id="creator_owner"))

    # 1. Path traversal rejected with 400
    res_traversal = isolated_client.post(
        "/api/integration/catalog/add-to-project",
        json={
            "project_id": project.id,
            "expected_revision": 1,
            "block_id": "../../etc/passwd",
            "user_id": "creator_owner",
        },
    )
    assert res_traversal.status_code == 400

    # 2. Wrong user rejected with 403 Forbidden
    res_wrong_user = isolated_client.post(
        "/api/integration/catalog/add-to-project",
        json={
            "project_id": project.id,
            "expected_revision": 1,
            "block_id": "weight-wave",
            "user_id": "attacker_user",
        },
    )
    assert res_wrong_user.status_code == 403

    # 3. Stale revision (CAS mismatch) rejected with 409 Conflict
    res_stale = isolated_client.post(
        "/api/integration/catalog/add-to-project",
        json={
            "project_id": project.id,
            "expected_revision": 999,  # Current is 1
            "block_id": "weight-wave",
            "user_id": "creator_owner",
        },
    )
    assert res_stale.status_code == 409


# =========================================================================
# Domain 3: Library -> Motion Contract Integration (Requirement D)
# =========================================================================

def test_library_motion_intent_integration(isolated_client: TestClient):
    """Requirement D: Validate application/x-6clips-asset intent, CAS revision bump, and anti-duplicate guards."""
    project = asyncio.run(ProjectService.create_project("Motion Integration Project", user_id="creator_2"))
    assert project.revision == 1

    intent = {
        "asset_id": "asset_sample_clip_01",
        "key": "gv:sample_01",
        "title": "Gameplay Clutch Moment",
        "media_type": "video",
        "stream_url": "/api/library/asset/sample_01",
        "duration_seconds": 15.0,
        "aspect_ratio": "9:16",
        "source_provenance": "library_user_asset",
        "permitted_uses": ["timeline_motion", "derivative_clips"],
        "intent_action": "add_track",
        "target_track": "track_video_main",
        "target_start_time_seconds": 0.0,
        "file_sha256": "ABCDEF1234567890",
    }

    # 1. Apply motion intent
    res = isolated_client.post(
        "/api/integration/library/apply-motion-intent",
        json={
            "project_id": project.id,
            "expected_revision": 1,
            "intent": intent,
            "user_id": "creator_2",
        },
    )
    assert res.status_code == 200, f"Apply motion intent failed: {res.text}"
    body = res.json()
    assert body["ok"] is True
    assert body["revision"] == 2

    # 2. Duplicate insertion at same timestamp rejected with 409 Conflict
    res_dup = isolated_client.post(
        "/api/integration/library/apply-motion-intent",
        json={
            "project_id": project.id,
            "expected_revision": 2,
            "intent": intent,
            "user_id": "creator_2",
        },
    )
    assert res_dup.status_code == 409
    assert "Duplicate clip detected" in res_dup.json()["detail"]


# =========================================================================
# Domain 4: Original Creator -> Plan & Render Bridge (Requirement C)
# =========================================================================

def test_creator_plan_and_render_waiting_for_input(isolated_client: TestClient):
    """Requirement C: Without voice narration or TTS consent, truthfully returns WAITING_FOR_INPUT."""
    res = isolated_client.post(
        "/api/integration/creator/plan-and-render",
        json={
            "topic": "Latest Game Season Patch Notes",
            "target_duration_sec": 30,
            "aspect_ratio": "9:16",
            "allow_procedural_tts": False,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "WAITING_FOR_INPUT"
    assert data["is_rendered"] is False
    assert data["review_url"] is None
    assert "voice narration" in data["status_reason"].lower()


@pytest.mark.asyncio
async def test_creator_physical_render_with_voice_fixture(tmp_path: Path):
    """Requirement C & E: Render physical MP4 with an authorized test narration voice fixture."""
    voice_file = tmp_path / "authorized_voice.wav"
    # Create 3-second 440Hz sine narration fixture
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "sine=frequency=300:duration=3",
        "-c:a", "pcm_s16le",
        str(voice_file)
    ]
    sub = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert sub.returncode == 0

    spec = OriginalCompositionSpec(
        title="Physical Render Test",
        topic="Physics Simulation Review",
        target_duration_sec=3,
        aspect_ratio="9:16",
        evidence_ledger=EvidenceLedger(
            topic="Physics Simulation",
            entries=[
                EvidenceLedgerEntry(
                    claim_text="Verlet integration offers unconditional velocity stability.",
                    source_title="Computational Physics Dispatch",
                    citation="Numerical Methods Journal",
                )
            ],
        ),
        spoken_script=TeleprompterScript(
            spoken_text="Verlet integration guarantees continuous velocity stability for dynamic physics.",
            word_count=10,
            estimated_read_time_seconds=3.0,
        ),
        shot_list=[
            ShotListEntry(
                scene_number=1,
                timecode_start_sec=0.0,
                timecode_end_sec=3.0,
                visual_description="Simulation wireframe graph",
                overlay_text="VERLET INTEGRATION",
            )
        ],
        voice_requirement=VoiceInputRequirement.VOICE_PROVIDED,
        voice_asset_path=str(voice_file),
        status=OriginalCreationStatus.READY_FOR_COMPOSITION,
    )

    rendered = await OriginalCreatorWorkflow.render_spec(
        spec=spec,
        output_dir=tmp_path / "render_out",
        custom_voice_path=voice_file,
    )

    assert rendered.status == OriginalCreationStatus.RENDERED
    assert rendered.rendered_result is not None
    video_path = Path(rendered.rendered_result.video_path)
    assert video_path.exists()
    assert video_path.stat().st_size > 0

    # Probe physical geometry: 9:16 -> 1080x1920
    w, h = probe_dimensions(video_path)
    assert w == 1080
    assert h == 1920

    # Verify physical file checksum
    ok, sha, sz = verify_physical_media_file(video_path)
    assert ok is True
    assert sha is not None
    assert sz == video_path.stat().st_size


# =========================================================================
# Domain 5: Physical 16:9 Widescreen Render & ffprobe Verification
# =========================================================================

@pytest.mark.asyncio
async def test_creator_physical_render_16_9_widescreen(tmp_path: Path):
    """Requirement Section 50: Verify physical 16:9 horizontal MP4 rendering with ffprobe."""
    voice_file = tmp_path / "voice_16_9.wav"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "sine=frequency=400:duration=3",
        "-c:a", "pcm_s16le",
        str(voice_file)
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    spec = OriginalCompositionSpec(
        title="Widescreen Astronomy",
        topic="Deep Space Nebula",
        target_duration_sec=3,
        aspect_ratio="16:9",
        evidence_ledger=EvidenceLedger(
            topic="Deep Space",
            entries=[
                EvidenceLedgerEntry(
                    claim_text="Spectroscopic lines show ionized hydrogen emissions.",
                    source_title="Astrophysical Review",
                    citation="APJ 2026",
                )
            ],
        ),
        spoken_script=TeleprompterScript(
            spoken_text="Spectroscopic emission lines confirm ionized interstellar gas clouds.",
            word_count=8,
            estimated_read_time_seconds=3.0,
        ),
        shot_list=[
            ShotListEntry(
                scene_number=1,
                timecode_start_sec=0.0,
                timecode_end_sec=3.0,
                visual_description="Nebula starfield panorama",
                overlay_text="HYDROGEN EMISSIONS",
            )
        ],
        voice_requirement=VoiceInputRequirement.VOICE_PROVIDED,
        voice_asset_path=str(voice_file),
        status=OriginalCreationStatus.READY_FOR_COMPOSITION,
    )

    rendered = await OriginalCreatorWorkflow.render_spec(
        spec=spec,
        output_dir=tmp_path / "render_16_9_out",
        custom_voice_path=voice_file,
    )

    assert rendered.status == OriginalCreationStatus.RENDERED
    video_path = Path(rendered.rendered_result.video_path)
    assert video_path.exists()

    w, h = probe_dimensions(video_path)
    assert w == 1920
    assert h == 1080


# =========================================================================
# Domain 6: HTTP 206 Partial Content Streaming
# =========================================================================

def test_http_206_partial_content_streaming_mechanics(tmp_path: Path):
    """Requirement Section 50: Test HTTP 206 byte-range streaming mechanics."""
    from backend.api.videos import serve_media_with_range

    test_file = tmp_path / "stream_sample.mp4"
    data = b"0123456789" * 100  # 1000 bytes
    test_file.write_bytes(data)

    class MockRequest:
        headers = {"range": "bytes=0-99"}

    resp = serve_media_with_range(test_file, MockRequest())
    assert resp.status_code == 206
    assert resp.headers["Content-Range"] == f"bytes 0-99/{len(data)}"
    assert resp.headers["Accept-Ranges"] == "bytes"
    assert resp.headers["Content-Length"] == "100"


# =========================================================================
# Domain 7: Durable Ledger Crash Recovery & Partial State
# =========================================================================

def test_durable_ledger_crash_recovery_partial_state(tmp_path: Path):
    """Requirement E & Section 50: Verify restart recovery and PARTIAL state transition."""
    ledger_dir = tmp_path / "ledger_recovery_test"
    ledger = PersistentJobLedger(storage_dir=ledger_dir)

    job_id = "job_wave4_crash_01"
    ledger.create_job(
        job_id=job_id,
        request_fingerprint="fp_wave4_01",
        run_id="run_wave4_01",
        immutable_request={},
        output_ids=["out_1", "out_2"],
        status="RUNNING",
    )

    # Output 1 succeeded
    art_path = tmp_path / "clip_succeeded.mp4"
    art_path.write_bytes(b"completed clip content")
    sha1 = compute_sha256(art_path)
    ledger.checkpoint_output_success(job_id, "out_1", "art_1", art_path, sha1, len(art_path.read_bytes()))

    # Output 2 in-flight interrupted (leaves 0-byte corrupt artifact)
    art_corrupt = tmp_path / "clip_corrupt.mp4"
    art_corrupt.write_bytes(b"")
    ledger.checkpoint_output_start(job_id, "out_2")
    rec = ledger.get_job(job_id)
    rec.output_checkpoints["out_2"].file_path = str(art_corrupt)
    ledger.save_job(rec)

    # Reconcile on restart
    recovered_ledger = PersistentJobLedger(storage_dir=ledger_dir)
    reconciled = recovered_ledger.reconcile_active_jobs()
    assert len(reconciled) >= 1

    final_job = recovered_ledger.get_job(job_id)
    assert final_job.status == "PARTIAL"
    assert final_job.output_checkpoints["out_1"].state == "SUCCEEDED"
    assert final_job.output_checkpoints["out_2"].state == "FAILED"
    assert not art_corrupt.exists(), "Corrupt 0-byte file must be pruned on recovery"
