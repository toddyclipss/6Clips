# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for Phase 10 PublishedReceiptV1 Interoperability Contract and Fan-Out Isolation."""
from datetime import datetime, timezone
from pathlib import Path
import pytest

from backend.distribution.job_store import DistributionJobStore
from backend.distribution.models import (
    AccountState,
    ApprovalReceipt,
    DistributionJob,
    DistributionStatus,
    PlatformAccount,
    PlatformSEOMetadata,
    PublishedReceiptV1,
)
from backend.distribution.service import DistributionService
from backend.distribution.transport import InProcessFakeTransport


def test_published_receipt_contract_schema():
    receipt = PublishedReceiptV1(
        receipt_id="rcpt_canonical_01",
        job_id="dist_job_01",
        output_id="out_canonical_01",
        project_id="proj_01",
        project_revision=2,
        artifact_sha256="abc123sha256",
        platform="youtube",
        account_id="acc_yt_01",
        account_handle="viralmint",
        remote_post_id="post_yt_987",
        remote_post_url="https://youtube.com/watch?v=post_yt_987",
        published_at_utc=datetime.now(timezone.utc).isoformat(),
        verified_status="CONFIRMED",
        provenance={
            "transport": "InProcessFakeTransport",
            "approval_receipt_id": "appr_01",
        },
    )

    d = receipt.model_dump()
    assert d["schema_version"] == "distribution.receipt.v1"
    assert d["verified_status"] == "CONFIRMED"
    assert d["remote_post_id"] == "post_yt_987"
    assert "access_token" not in d
    assert "token" not in d["provenance"]


@pytest.mark.asyncio
async def test_fan_out_failure_isolation_and_partial_state(tmp_path: Path):
    store = DistributionJobStore(base_dir=tmp_path)
    transport = InProcessFakeTransport()
    service = DistributionService(store=store, transport=transport)

    # Valid physical artifact
    f = tmp_path / "valid_fanout.mp4"
    f.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 512)
    file_sha256 = service.check_release_eligibility.__globals__["ReleaseEligibilityVerifier"].calculate_file_sha256(f)

    approval = service.create_approval_receipt(
        output_id="out_fanout_01",
        project_id="proj_fanout_01",
        project_revision=1,
        artifact_sha256=file_sha256,
        approved_by="creator",
        consent_for_external_publish=True,
    )

    yt_acc = PlatformAccount(
        account_id="yt_acc",
        platform="youtube",
        account_name="YouTube",
        state=AccountState.READY,
        granted_scopes=["https://www.googleapis.com/auth/youtube.upload"],
        required_scopes=["https://www.googleapis.com/auth/youtube.upload"],
        can_publish=True,
    )

    tt_acc = PlatformAccount(
        account_id="tt_acc",
        platform="tiktok",
        account_name="TikTok",
        state=AccountState.READY,
        granted_scopes=["video.upload", "video.publish"],
        required_scopes=["video.upload", "video.publish"],
        can_publish=True,
    )

    # YouTube config has valid 9:16 metadata
    yt_cfg = {
        "platform": "youtube",
        "account": yt_acc,
        "seo_metadata": PlatformSEOMetadata(platform="youtube", title="YouTube Title", description="Desc"),
    }

    # TikTok config intentionally has invalid 16:9 aspect ratio (TikTok requires 9:16)
    tt_cfg = {
        "platform": "tiktok",
        "account": tt_acc,
        "seo_metadata": PlatformSEOMetadata(platform="tiktok", title="TikTok Title", aspect_ratio="16:9"),
    }

    fan_out_result = await service.schedule_multi_platform_fan_out(
        output_id="out_fanout_01",
        project_id="proj_fanout_01",
        project_revision=1,
        artifact_path=str(f),
        approval_receipt=approval,
        platform_configs=[yt_cfg, tt_cfg],
        user_id="local",
        permitted_uses=["social_distribution"],
    )

    # TikTok failed validation, but YouTube succeeded -> PARTIAL aggregate status
    assert fan_out_result["status"] == "PARTIAL"
    assert len(fan_out_result["jobs"]) == 1
    assert fan_out_result["jobs"][0].platform == "youtube"
    assert len(fan_out_result["errors"]) == 1
    assert fan_out_result["errors"][0]["platform"] == "tiktok"
