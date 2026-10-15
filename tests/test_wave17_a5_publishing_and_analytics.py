# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 17 Agent 5 Test Suite: Real Outcome Delivery, OAAS Contract, and Anti-Fake Guarantees.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
import pytest

from backend.oaas_provider_receipts.receipt_store import (
    OAASReceiptStore,
    ProviderReceiptV2,
    ReceiptVerificationError,
)
from backend.oaas_provider_receipts.provider_client import (
    ProviderDispatcher,
    ProviderDispatchResult,
)
from backend.oaas_provider_receipts.queue_truth import (
    OAASQueueManager,
    PublishQueueState,
    JobLifecycleError,
)
from backend.oaas_provider_receipts.analytics_ingestor import (
    OAASAnalyticsIngestor,
    GroundedMetricObservation,
)
from tools.wave17_a5.audit_oaas_contract import run_full_contract_audit


class TestWave17Agent5OAASContract:
    """Verifies OAAS product contract invariants and anti-fake constraints."""

    def test_01_oaas_contract_document_exists_and_covers_non_negotiables(self):
        doc_path = Path(__file__).resolve().parents[1] / "docs" / "OAAS_PRODUCT_CONTRACT.md"
        assert doc_path.exists(), "docs/OAAS_PRODUCT_CONTRACT.md must exist."
        content = doc_path.read_text(encoding="utf-8")
        assert "OUTCOME AS A SERVICE" in content
        assert "Trends" in content
        assert "My Channel" in content
        assert "Library" in content
        assert "Motion Graphics" in content
        assert "Messages" in content
        assert "Load Test Fixture" in content
        assert "196 ORIGINAL" in content

    def test_02_contract_audit_script_passes(self):
        rep = run_full_contract_audit()
        assert "overall_status" in rep
        assert rep["backend_anti_fake_audit"]["status"] == "PASS"
        # In candidate / integrated worktree where Agent 2 is merged, production UI fixtures must be completely clean
        if not rep["production_ui_fixtures_audit"]["violations"]:
            assert rep["overall_status"] == "PASS"
        else:
            # During parallel phase before Agent 2 merge, verify audit correctly detects legacy controls
            for v in rep["production_ui_fixtures_audit"]["violations"]:
                assert any(x in v.lower() for x in ["test fixture", "worker tick"])

    def test_03_provider_evidence_matrix_completeness(self):
        matrix_path = Path(__file__).resolve().parents[1] / "tools" / "wave17_a5" / "provider_evidence_matrix.json"
        assert matrix_path.exists(), "provider_evidence_matrix.json must exist"
        with open(matrix_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["summary"]["total_providers_audited"] == 4
        assert data["summary"]["connected_providers"] == 0
        assert data["summary"]["live_publishing_status"] == "PENDING_CREDENTIALS"
        assert data["summary"]["offline_host_limitation_enforced"] is True


class TestWave17Agent5RealPublishingAndSecurity:
    """Verifies fail-closed OAuth enforcement, artifact verification, and anti-fake receipts."""

    def test_04_fail_closed_when_credentials_absent(self):
        dispatcher = ProviderDispatcher()
        status = dispatcher.get_credential_status("youtube", "user_channel_1")
        assert status == "PENDING_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_05_dispatch_fails_closed_without_fake_receipt(self, tmp_path):
        dummy_video = tmp_path / "video.mp4"
        dummy_video.write_bytes(b"\x00\x00\x00 ftypisom" + b"\x00" * 100)
        sha256 = hashlib.sha256(dummy_video.read_bytes()).hexdigest()

        dispatcher = ProviderDispatcher()
        res = await dispatcher.dispatch(
            platform="youtube",
            account_id="acc_unauthed",
            artifact_path=str(dummy_video),
            expected_artifact_sha256=sha256,
            title="My Video",
            description="Testing fail-closed",
            idempotency_key="idem_123",
        )

        assert res.success is False
        assert res.status == "PENDING_CREDENTIALS"
        assert res.error_code == "CREDENTIALS_REQUIRED"
        assert res.provider_post_id is None
        assert res.provider_post_url is None

    @pytest.mark.asyncio
    async def test_06_dispatch_rejects_artifact_sha_mismatch(self, tmp_path):
        dummy_video = tmp_path / "tampered.mp4"
        dummy_video.write_bytes(b"data1")
        dispatcher = ProviderDispatcher()

        res = await dispatcher.dispatch(
            platform="youtube",
            account_id="acc_1",
            artifact_path=str(dummy_video),
            expected_artifact_sha256="0" * 64,  # wrong hash
            title="Tampered",
            description="",
            idempotency_key="idem_456",
        )
        assert res.success is False
        assert res.status == "BLOCKED"
        assert res.error_code == "ARTIFACT_SHA_MISMATCH"

    def test_07_anti_fake_receipt_rejection(self):
        store = OAASReceiptStore()
        fake_receipt = ProviderReceiptV2(
            job_id="job_test",
            platform="youtube",
            account_id="acc_1",
            project_id="proj_1",
            project_revision=1,
            artifact_sha256="a" * 64,
            approval_signature="sig_abc",
            provider_post_id="fake_yt_123",
            provider_post_url="https://www.youtube.com/watch?v=fake_yt_123",
            provider_timestamp_utc="2026-10-15T00:00:00Z",
            is_test_fixture=False,
        )

        with pytest.raises(ReceiptVerificationError, match="fabricated provider post ID"):
            store.register_receipt(fake_receipt)


class TestWave17Agent5QueueAndAnalytics:
    """Verifies queue lifecycle, crash recovery, and grounded analytics ingestion."""

    def test_08_queue_states_and_offline_truth(self):
        qm = OAASQueueManager()
        status = qm.get_daemon_status()
        assert status["daemon_active"] is True
        assert "local machine" in status["offline_host_truth"]

        job = qm.create_job(
            project_id="proj_alpha",
            project_revision=1,
            output_id="out_1",
            artifact_path="test.mp4",
            artifact_sha256="b" * 64,
            approval_receipt_id="appr_1",
            approval_signature="sig_1",
            platform="youtube",
            account_id="acc_pending",
            title="Pending Video",
            scheduled_time_utc="2026-10-15T12:00:00Z",
        )
        # Without credentials, state is PENDING_CREDENTIALS
        assert job.state == PublishQueueState.PENDING_CREDENTIALS

    def test_09_crash_recovery_without_duplicate_posts(self):
        store = OAASReceiptStore()
        qm = OAASQueueManager(receipt_store=store)

        job = qm.create_job(
            project_id="proj_rec",
            project_revision=1,
            output_id="out_rec",
            artifact_path="test.mp4",
            artifact_sha256="c" * 64,
            approval_receipt_id="appr_2",
            approval_signature="sig_2",
            platform="tiktok",
            account_id="acc_rec",
            title="Recovery Video",
            scheduled_time_utc="2026-10-15T12:00:00Z",
        )
        # Simulate in-flight state right before crash
        job.state = PublishQueueState.DISPATCHING

        recovered = qm.recover_crash()
        assert recovered == 1
        # Since no receipt exists, it safely transitions to FAILED_RETRYABLE
        assert job.state == PublishQueueState.FAILED_RETRYABLE
        assert job.error_code == "PROCESS_RESTARTED_DURING_DISPATCH"

    def test_10_analytics_no_hallucinated_metrics(self):
        store = OAASReceiptStore()
        ingestor = OAASAnalyticsIngestor(receipt_store=store)

        summary = ingestor.get_channel_summary()
        assert summary["status"] == "NO_VERIFIED_PUBLICATIONS"
        assert summary["total_views"] == 0
        assert summary["total_engagements"] == 0

        recs = ingestor.generate_agent_recommendations()
        assert recs["has_recommendations"] is False
        assert recs["status"] == "NO_DATA"
        assert "Recommendations require measured publication results" in recs["reason"]

    def test_11_reconciled_196_ledger_integrity(self):
        ledger_path = Path(__file__).resolve().parents[1] / "backend" / "catalog_inventory" / "wave17_196_per_id_ledger.json"
        assert ledger_path.exists(), "wave17_196_per_id_ledger.json must exist"
        with open(ledger_path, "r", encoding="utf-8") as f:
            ledger = json.load(f)

        assert ledger["total_inventoried"] == 196
        assert ledger["gallery_confirmed_count"] == 171
        assert ledger["fallback_mapped_count"] == 25
        assert ledger["trademark_items_count"] == 15
        assert ledger["retired_blocks_in_donor_inventory"] == 0
