# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for Phase 10 Release Eligibility: physical artifacts, lineage, signed approval, and rights."""
from pathlib import Path
import pytest

from backend.distribution.eligibility import (
    ReleaseEligibilityError,
    ReleaseEligibilityVerifier,
)
from backend.distribution.models import ApprovalReceipt


def test_verify_physical_artifact_success(tmp_path: Path):
    f = tmp_path / "valid_render.mp4"
    # ISO BMFF header
    f.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 1024)

    path, sha256, size = ReleaseEligibilityVerifier.verify_physical_artifact(str(f))
    assert path == f
    assert len(sha256) == 64
    assert size > 0


def test_verify_physical_artifact_missing():
    with pytest.raises(ReleaseEligibilityError) as exc:
        ReleaseEligibilityVerifier.verify_physical_artifact("non_existent_file.mp4")
    assert exc.value.code == "ARTIFACT_MISSING"


def test_verify_physical_artifact_empty(tmp_path: Path):
    f = tmp_path / "empty.mp4"
    f.write_bytes(b"")

    with pytest.raises(ReleaseEligibilityError) as exc:
        ReleaseEligibilityVerifier.verify_physical_artifact(str(f))
    assert exc.value.code == "ARTIFACT_EMPTY"


def test_verify_physical_artifact_non_media(tmp_path: Path):
    f = tmp_path / "fake.mp4"
    f.write_bytes(b"This is just a text document masquerading as video.")

    with pytest.raises(ReleaseEligibilityError) as exc:
        ReleaseEligibilityVerifier.verify_physical_artifact(str(f))
    assert exc.value.code == "UNSUPPORTED_CONTAINER"


def test_verify_editorial_approval_success():
    receipt = ApprovalReceipt(
        output_id="out_123",
        project_id="proj_abc",
        project_revision=4,
        artifact_sha256="abc123hash",
        approved_by="director",
        consent_for_external_publish=True,
    )
    receipt.signature = receipt.compute_signature()

    # Valid check
    ReleaseEligibilityVerifier.verify_editorial_approval(
        approval_receipt=receipt,
        current_project_revision=4,
        current_artifact_sha256="abc123hash",
    )


def test_verify_editorial_approval_missing():
    with pytest.raises(ReleaseEligibilityError) as exc:
        ReleaseEligibilityVerifier.verify_editorial_approval(
            approval_receipt=None,
            current_project_revision=1,
            current_artifact_sha256="some_hash",
        )
    assert exc.value.code == "APPROVAL_MISSING"


def test_verify_editorial_approval_invalid_signature():
    receipt = ApprovalReceipt(
        output_id="out_123",
        project_id="proj_abc",
        project_revision=4,
        artifact_sha256="abc123hash",
        approved_by="director",
        consent_for_external_publish=True,
        signature="tampered_signature",
    )

    with pytest.raises(ReleaseEligibilityError) as exc:
        ReleaseEligibilityVerifier.verify_editorial_approval(
            approval_receipt=receipt,
            current_project_revision=4,
            current_artifact_sha256="abc123hash",
        )
    assert exc.value.code == "APPROVAL_SIGNATURE_INVALID"


def test_verify_editorial_approval_stale_revision():
    receipt = ApprovalReceipt(
        output_id="out_123",
        project_id="proj_abc",
        project_revision=3,  # Approved at rev 3
        artifact_sha256="abc123hash",
        approved_by="director",
        consent_for_external_publish=True,
    )
    receipt.signature = receipt.compute_signature()

    # Project advanced to rev 4
    with pytest.raises(ReleaseEligibilityError) as exc:
        ReleaseEligibilityVerifier.verify_editorial_approval(
            approval_receipt=receipt,
            current_project_revision=4,
            current_artifact_sha256="abc123hash",
        )
    assert exc.value.code == "APPROVAL_STALE_REVISION"


def test_verify_editorial_approval_stale_artifact_hash():
    receipt = ApprovalReceipt(
        output_id="out_123",
        project_id="proj_abc",
        project_revision=4,
        artifact_sha256="original_hash",
        approved_by="director",
        consent_for_external_publish=True,
    )
    receipt.signature = receipt.compute_signature()

    # Render was recomputed with a different hash
    with pytest.raises(ReleaseEligibilityError) as exc:
        ReleaseEligibilityVerifier.verify_editorial_approval(
            approval_receipt=receipt,
            current_project_revision=4,
            current_artifact_sha256="recomputed_hash",
        )
    assert exc.value.code == "APPROVAL_STALE_ARTIFACT"


def test_verify_editorial_approval_missing_consent():
    receipt = ApprovalReceipt(
        output_id="out_123",
        project_id="proj_abc",
        project_revision=4,
        artifact_sha256="abc123hash",
        approved_by="director",
        consent_for_external_publish=False,  # Editor reviewed but creator did not consent to external publish
    )
    receipt.signature = receipt.compute_signature()

    with pytest.raises(ReleaseEligibilityError) as exc:
        ReleaseEligibilityVerifier.verify_editorial_approval(
            approval_receipt=receipt,
            current_project_revision=4,
            current_artifact_sha256="abc123hash",
        )
    assert exc.value.code == "CONSENT_MISSING"


def test_verify_permitted_uses_platform_rights():
    # General social distribution permitted
    ReleaseEligibilityVerifier.verify_permitted_uses(["social_distribution"], "youtube")
    ReleaseEligibilityVerifier.verify_permitted_uses(["commercial_creator"], "tiktok")
    ReleaseEligibilityVerifier.verify_permitted_uses(["distribute_instagram"], "instagram")

    # Insufficient rights
    with pytest.raises(ReleaseEligibilityError) as exc:
        ReleaseEligibilityVerifier.verify_permitted_uses(["internal_review_only"], "youtube")
    assert exc.value.code == "INSUFFICIENT_RIGHTS"


def test_full_release_eligibility_end_to_end(tmp_path: Path):
    f = tmp_path / "valid_render.mp4"
    f.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 1024)
    file_sha256 = ReleaseEligibilityVerifier.calculate_file_sha256(f)

    receipt = ApprovalReceipt(
        output_id="out_123",
        project_id="proj_abc",
        project_revision=2,
        artifact_sha256=file_sha256,
        approved_by="user_creator",
        consent_for_external_publish=True,
    )
    receipt.signature = receipt.compute_signature()

    res = ReleaseEligibilityVerifier.verify_eligibility(
        file_path_str=str(f),
        expected_user_id="user_creator",
        actual_user_id="user_creator",
        current_project_revision=2,
        approval_receipt=receipt,
        permitted_uses=["social_distribution"],
        target_platform="youtube",
        technical_checks_status="PASS",
        contract_checks_status="PASS",
    )
    assert res["eligible"] is True
    assert res["artifact_sha256"] == file_sha256
