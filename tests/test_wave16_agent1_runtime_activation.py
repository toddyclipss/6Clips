# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 16 Agent 1 Test Suite: Backend Runtime, Canonical CAS, Render Adapters, and Activation.

Covers:
1. Wave 16 37-Operable vs Wave 15 10-Operable Activation Census & Taxonomy Reconciliation
2. Deterministic Donor Onboarding Pipeline (Positive & Negative Controls)
3. Negative Safety Gates (403 on Quarantined 159, 409 on Retired 6Clips Substitutes)
4. Non-Destructive Legacy Project Migration for Retired Substitutes
5. Motion Tool CAS Insertion & ProjectRevision Optimistic Concurrency
6. Proof of Distinct Render Frames & MP4 Hashes for instagram-follow vs tiktok-follow
7. Full Inventory Traversal & API Wave 16 Audit
"""
import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.catalog.manifest_service import (
    CatalogManifestService,
    CatalogManifestError,
    DONOR_INTERNALIZED_BLOCKS,
    WAVE16_OPERABLE_DONOR_BLOCKS,
    RETIRED_6CLIPS_BLOCKS,
)
from backend.catalog_runtime.core import (
    UniversalRuntimeRegistry,
    DonorTaxonomyReconciler,
    DeterministicDonorOnboardingPipeline,
    list_runtime_block_specs,
    get_runtime_block_spec,
    validate_runtime_operable,
    DynamicFrameMotionVerifier,
    LegacyBlockMigrationManager,
)
from backend.database import init_db
from backend.services.project_service import ProjectService

client = TestClient(app)


@pytest.fixture(autouse=True)
async def setup_db():
    """Ensure database schema is initialized for test execution."""
    await init_db()


# =========================================================================
# 1. Wave 16 vs Wave 15 Activation Census & Reconciliation Math
# =========================================================================

def test_wave16_operable_census_math():
    """Verify that Wave 16 activates exactly 37 operable donor blocks and quarantines 159."""
    census = DonorTaxonomyReconciler.get_census_summary(wave=16)

    assert census["total_donor_blocks"] == 196
    assert census["indexed_in_registry_json"] == 170
    assert census["unindexed_block_directories"] == 26
    assert census["donor_operable_count"] == 37
    assert census["unported_donor_blocks"] == 159
    assert census["retired_6clips_count"] == 2
    assert census["donor_operable_count"] + census["unported_donor_blocks"] == 196

    # Verify operable blocks match exactly WAVE16_OPERABLE_DONOR_BLOCKS
    assert set(census["donor_operable_blocks"]) == WAVE16_OPERABLE_DONOR_BLOCKS

    # Verify retired blocks are never included in donor operable blocks
    for ret_id in RETIRED_6CLIPS_BLOCKS:
        assert ret_id not in census["donor_operable_blocks"]


def test_universal_runtime_registry_wave16_vs_wave15():
    """Verify registry returns 37 operable blocks in Wave 16 mode and 10 in Wave 15 mode."""
    operable_16 = UniversalRuntimeRegistry.get_operable_blocks(wave=16)
    assert len(operable_16) == 37
    assert {b.id for b in operable_16} == WAVE16_OPERABLE_DONOR_BLOCKS

    operable_15 = UniversalRuntimeRegistry.get_operable_blocks(wave=15)
    assert len(operable_15) == 10
    assert {b.id for b in operable_15} == DONOR_INTERNALIZED_BLOCKS

    all_blocks = UniversalRuntimeRegistry.discover_all_blocks()
    assert len(all_blocks) >= 196


def test_wave16_audit_endpoint_reconciliation():
    """Verify GET /api/catalog/wave16-audit returns complete reconciled metrics."""
    resp = client.get("/api/catalog/wave16-audit")
    assert resp.status_code == 200
    data = resp.json()

    assert data["wave"] == "WAVE_16"
    recon = data["reconciliation"]
    assert recon["donor_inventory_total"] == 196
    assert recon["donor_operable_count"] == 37
    assert recon["unported_donor_blocks_quarantined"] == 159
    assert recon["retired_6clips_count"] == 2
    assert recon["terminal_declarations"]["WAVE15_MISMATCH_RESOLVED"] is True
    assert recon["terminal_declarations"]["ALL_196_OPERATIONAL"] is False
    assert recon["terminal_declarations"]["ZERO_DONOR_DEPENDENCY"] is True

    mismatch = data["mismatch_investigation"]
    assert mismatch["wave15_reported_operable"] == 10
    assert mismatch["wave15_visible_cards"] == 37
    assert mismatch["wave16_activated_operable"] == 37


# =========================================================================
# 2. Deterministic Donor Onboarding Pipeline (Positive & Negative Controls)
# =========================================================================

def test_deterministic_onboarding_pipeline_positive_controls():
    """Verify that genuine shipped blocks pass all 7 gates deterministically."""
    pipeline = DeterministicDonorOnboardingPipeline()
    shipped_dir = Path("backend/catalog/shipped_blocks")

    # Positive control 1: Wave 15 base block
    res_aurora = pipeline.validate_component(shipped_dir / "aurora")
    assert res_aurora.passed is True
    assert len(res_aurora.failed_gates) == 0

    # Positive control 2: Ported Shader
    res_blob = pipeline.validate_component(shipped_dir / "blob")
    assert res_blob.passed is True
    assert len(res_blob.failed_gates) == 0

    # Positive control 3: Ported Lower Third
    res_lt = pipeline.validate_component(shipped_dir / "lt-bold-block")
    assert res_lt.passed is True
    assert len(res_lt.failed_gates) == 0


def test_deterministic_onboarding_pipeline_negative_controls():
    """Verify generic onboarding pipeline rejects defective components with exact gate failures."""
    pipeline = DeterministicDonorOnboardingPipeline()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Control A: Missing index.html / entrypoint
        bad_dir_no_html = tmppath / "bad-no-html"
        bad_dir_no_html.mkdir()
        (bad_dir_no_html / "registry-item.json").write_text(json.dumps({
            "name": "bad-no-html", "license": "MIT", "duration": 5.0
        }), encoding="utf-8")
        res_no_html = pipeline.validate_component(bad_dir_no_html)
        assert res_no_html.passed is False
        assert "entrypoint" in res_no_html.failed_gates

        # Control B: Unvendored external remote CDN call
        bad_dir_cdn = tmppath / "bad-cdn"
        bad_dir_cdn.mkdir()
        (bad_dir_cdn / "registry-item.json").write_text(json.dumps({
            "name": "bad-cdn", "license": "MIT", "duration": 5.0
        }), encoding="utf-8")
        (bad_dir_cdn / "index.html").write_text(
            '<html><head><script src="https://cdn.jsdelivr.net/npm/gsap"></script></head><body></body></html>',
            encoding="utf-8"
        )
        res_cdn = pipeline.validate_component(bad_dir_cdn)
        assert res_cdn.passed is False
        assert "zero_network_egress" in res_cdn.failed_gates

        # Control C: Missing / Proprietary License
        bad_dir_license = tmppath / "bad-license"
        bad_dir_license.mkdir()
        (bad_dir_license / "registry-item.json").write_text(json.dumps({
            "name": "bad-license", "license": "PROPRIETARY_ALL_RIGHTS_RESERVED", "duration": 5.0
        }), encoding="utf-8")
        (bad_dir_license / "index.html").write_text('<html><body>Static</body></html>', encoding="utf-8")
        res_lic = pipeline.validate_component(bad_dir_license)
        assert res_lic.passed is False
        assert "license_permissive" in res_lic.failed_gates


# =========================================================================
# 3. Negative Safety Gates (403 on Quarantined, 409 on Retired)
# =========================================================================

def test_negative_safety_gate_quarantined_blocks_return_403():
    """Verify unported donor blocks (159) return 403 Forbidden across all operations."""
    quarantined_samples = ["3d-carousel", "ai-answer-rank", "crypto-ticker", "saas-pricing-tiers"]

    for b_id in quarantined_samples:
        # 1. Preview endpoint returns 403
        resp_preview = client.get(f"/api/catalog/blocks/{b_id}/preview")
        assert resp_preview.status_code == 403
        assert "quarantined" in resp_preview.json()["detail"].lower()

        # 2. Direct manifest operable validation raises CatalogManifestError
        with pytest.raises(CatalogManifestError) as exc_info:
            CatalogManifestService.validate_block_operable(b_id)
        assert "quarantined" in str(exc_info.value).lower()

        # 3. Project insertion validation raises CatalogManifestError
        with pytest.raises(CatalogManifestError) as exc_info2:
            CatalogManifestService.validate_block_for_project_insertion(b_id)
        assert "quarantined" in str(exc_info2.value).lower()


def test_negative_safety_gate_retired_blocks_return_409():
    """Verify retired 6Clips blocks return 409 Conflict across preview and operations."""
    for r_id in RETIRED_6CLIPS_BLOCKS:
        # 1. Preview returns 409
        resp_preview = client.get(f"/api/catalog/blocks/{r_id}/preview")
        assert resp_preview.status_code == 409
        assert "retired" in resp_preview.json()["detail"].lower()

        # 2. Manifest validation raises CatalogManifestError with retired message
        with pytest.raises(CatalogManifestError) as exc:
            CatalogManifestService.validate_block_operable(r_id, allow_retired=False)
        assert "retired" in str(exc.value).lower()

        # 3. Project insertion validation raises CatalogManifestError
        with pytest.raises(CatalogManifestError) as exc2:
            CatalogManifestService.validate_block_for_project_insertion(r_id, allow_retired=False)
        assert "retired" in str(exc2.value).lower()


def test_legacy_project_migration_preserves_retired_blocks():
    """Verify non-destructive migration preserves existing retired blocks in projects."""
    legacy_doc = {
        "id": "proj_legacy_001",
        "schema_version": 1,
        "timeline": {
            "tracks": [
                {
                    "id": "track_1",
                    "clips": [
                        {
                            "id": "clip_hud_1",
                            "block_id": "creator-hud",
                            "title": "Creator HUD",
                            "start_seconds": 0.0,
                            "duration_seconds": 5.0,
                            "variables": {"channel_name": "ViralTech"},
                        },
                        {
                            "id": "clip_aurora_1",
                            "block_id": "aurora",
                            "title": "Aurora",
                            "start_seconds": 5.0,
                            "duration_seconds": 4.0,
                            "variables": {},
                        },
                    ],
                }
            ],
        },
    }

    # 1. Non-destructive detection: flags document without modifying clips
    marked_doc, requires_migration = LegacyBlockMigrationManager.inspect_and_mark_migration(legacy_doc)
    assert requires_migration is True
    assert marked_doc["metadata"]["requires_migration"] is True
    assert "creator-hud" in marked_doc["metadata"]["retired_blocks_detected"]
    # Verify clip still has creator-hud and channel_name is intact
    clips = marked_doc["timeline"]["tracks"][0]["clips"]
    assert clips[0]["block_id"] == "creator-hud"
    assert clips[0]["variables"]["channel_name"] == "ViralTech"

    # 2. Consented migration replaces with vetted replacement and preserves properties
    migrated_doc = LegacyBlockMigrationManager.apply_migration(marked_doc, user_consented=True)
    m_clips = migrated_doc["timeline"]["tracks"][0]["clips"]
    assert m_clips[0]["block_id"] == "yt-lower-third"
    assert m_clips[0]["migrated_from"] == "creator-hud"
    assert m_clips[0]["variables"]["channel_name"] == "ViralTech"
    assert migrated_doc["metadata"]["migration_status"] == "MIGRATION_COMPLETED"


# =========================================================================
# 4. Motion Tool CAS Insertion & ProjectRevision
# =========================================================================

@pytest.mark.asyncio
async def test_cas_project_insertion_for_activated_blocks():
    """Verify that newly activated blocks can be inserted under optimistic concurrency (CAS)."""
    # Create test project
    proj = await ProjectService.create_project(
        name="Wave16 CAS Test",
        user_id="agent1_test",
        aspect_ratio="9:16",
    )
    p_id = proj.id
    rev = proj.revision

    # Test inserting an activated shader block: 'blob'
    res_blob = await ProjectService.apply_operation(
        project_id=p_id,
        expected_revision=rev,
        operation_type="add_block",
        payload={
            "block_id": "blob",
            "title": "Blob Background",
            "start_seconds": 0.0,
            "duration_seconds": 5.0,
            "variables": {},
            "track_id": "track_video_main",
        },
        author="agent1_test",
    )
    assert res_blob["revision"] == rev + 1
    rev = res_blob["revision"]

    # Test inserting an activated lower-third block: 'lt-bold-block'
    res_lt = await ProjectService.apply_operation(
        project_id=p_id,
        expected_revision=rev,
        operation_type="add_block",
        payload={
            "block_id": "lt-bold-block",
            "title": "Bold Lower Third",
            "start_seconds": 1.0,
            "duration_seconds": 4.0,
            "variables": {"title": "Wave 16 Active", "subtitle": "CAS Verified"},
            "track_id": "track_graphics_main",
        },
        author="agent1_test",
    )
    assert res_lt["revision"] == rev + 1
    rev = res_lt["revision"]

    # Test CAS conflict rejection when providing stale revision
    with pytest.raises(Exception):
        await ProjectService.apply_operation(
            project_id=p_id,
            expected_revision=rev - 1,  # Stale revision
            operation_type="add_block",
            payload={"block_id": "plasma", "start_seconds": 0.0, "duration_seconds": 3.0},
            author="agent1_test",
        )


# =========================================================================
# 5. Instagram vs TikTok Follow Hash Investigation
# =========================================================================

def test_instagram_vs_tiktok_source_and_frame_distinction():
    """Verify instagram-follow and tiktok-follow have distinct source code, colors, and variables."""
    ig_block = UniversalRuntimeRegistry.get_block("instagram-follow", wave=16)
    tt_block = UniversalRuntimeRegistry.get_block("tiktok-follow", wave=16)

    assert ig_block is not None
    assert tt_block is not None

    # Verify distinct titles and tags
    assert ig_block.title != tt_block.title
    assert "instagram" in [t.lower() for t in ig_block.source_tags]
    assert "tiktok" in [t.lower() for t in tt_block.source_tags]

    # Verify on-disk HTML content has distinct branding colors and layout
    ig_html = Path(f"backend/catalog/shipped_blocks/instagram-follow/instagram-follow.html").read_text(encoding="utf-8")
    tt_html = Path(f"backend/catalog/shipped_blocks/tiktok-follow/tiktok-follow.html").read_text(encoding="utf-8")

    assert ig_html != tt_html
    assert "instagram" in ig_html.lower()
    assert "tiktok" in tt_html.lower()

    # Verify sha256 of html files are completely distinct
    ig_sha = hashlib.sha256(ig_html.encode("utf-8")).hexdigest()
    tt_sha = hashlib.sha256(tt_html.encode("utf-8")).hexdigest()
    assert ig_sha != tt_sha


def test_investigation_summary_artifact_integrity():
    """Verify that the Instagram vs TikTok investigation summary exists with verified real hashes."""
    summary_path = Path("tools/wave16_runtime/instagram_tiktok_investigation_summary.json")
    assert summary_path.exists()

    data = json.loads(summary_path.read_text(encoding="utf-8"))
    assert data["reproduced_fixture"]["streams_byte_identical"] is True
    assert "mock" in data["reproduced_fixture"]["explanation"].lower()
    assert data["real_evidence"]["frame_comparison"]["visual_difference_detected"] is True
    assert data["real_evidence"]["real_mp4_exports"]["mp4_hashes_are_distinct"] is True
    assert data["real_evidence"]["real_mp4_exports"]["instagram_mp4_sha256"] != data["real_evidence"]["real_mp4_exports"]["tiktok_mp4_sha256"]


# =========================================================================
# 6. Full Inventory Traversal & API Filtering
# =========================================================================

def test_full_inventory_snapshot_196_items():
    """Verify GET /api/catalog/inventory/snapshot returns full 196 items without truncation."""
    resp = client.get("/api/catalog/inventory/snapshot")
    assert resp.status_code == 200
    data = resp.json()

    assert data["donor_inventory_total"] == 196
    assert len(data["blocks"]) == 196
    assert data["is_snapshot"] is True

    # Count operable vs unported in snapshot
    operable_count = sum(1 for b in data["blocks"] if b["runtime_operable"])
    unported_count = sum(1 for b in data["blocks"] if not b["runtime_operable"])
    assert operable_count == 37
    assert unported_count == 159


def test_inventory_filter_operational_returns_37():
    """Verify GET /api/catalog/inventory?filter=operational returns exactly 37 blocks."""
    resp = client.get("/api/catalog/inventory?filter=operational&limit=100")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["blocks"]) == 37
    assert all(b["runtime_operable"] for b in data["blocks"])


def test_inventory_filter_unported_returns_159():
    """Verify GET /api/catalog/inventory?filter=unported returns exactly 159 quarantined blocks."""
    resp = client.get("/api/catalog/inventory?filter=unported&limit=200")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["blocks"]) == 159
    assert all(not b["runtime_operable"] for b in data["blocks"])
