# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 2 Agent 4: Tests for Library asset provenance, missing media guards, ownership security, and synthetic fixture rejection."""
import pytest
from pathlib import Path

from backend.services.library_service import (
    LibraryService,
    MissingMediaError,
    OwnershipViolationError,
    LibraryError,
)
from backend.catalog.manifest_service import CatalogManifestService, CatalogManifestError


def test_missing_media_guard_raises_error(tmp_path):
    """Requirement A19 / E02 / GT-12: missing media must raise error and never report success."""
    non_existent = tmp_path / "does_not_exist.mp4"
    with pytest.raises(MissingMediaError, match="missing on disk"):
        LibraryService.validate_media_file(non_existent)

    # Empty 0-byte file
    empty_file = tmp_path / "zero_bytes.mp4"
    empty_file.touch()
    with pytest.raises(MissingMediaError, match="empty"):
        LibraryService.validate_media_file(empty_file)

    # Valid file passes
    valid_file = tmp_path / "valid.mp4"
    valid_file.write_bytes(b"fake mp4 header and test bytes for validation")
    res = LibraryService.validate_media_file(valid_file)
    assert res == valid_file


def test_synthetic_fixture_rejection():
    """Requirement A19 / G12 / GT-12: synthetic test fixtures must be identified and rejected from production stock."""
    synthetic_samples = [
        "synth_fixture_01.mp3",
        "synthetic_tone_440hz.wav",
        "test_fixture_drum.mp3",
        "dummy_media.mp4",
        "mock_audio_sample.aac",
    ]
    for name in synthetic_samples:
        assert LibraryService.is_synthetic_fixture(name) is True, f"Failed to flag synthetic fixture: {name}"

    genuine_samples = [
        "ambient_lofi_evening.mp3",
        "cinematic_trailer_percussion.wav",
        "gameplay_victory_clip.mp4",
        "voiceover_intro_v2.wav",
    ]
    for name in genuine_samples:
        assert LibraryService.is_synthetic_fixture(name) is False, f"Falsely flagged genuine asset: {name}"


def test_ownership_guard_blocks_cross_user_actions():
    """Requirement E27 / GT-12: verify that cross-user modification is strictly blocked."""
    # Matching users pass
    LibraryService.verify_ownership("user_alice", "user_alice")
    LibraryService.verify_ownership(None, "user_alice")
    LibraryService.verify_ownership("user_alice", None)

    # Cross-user attempt raises OwnershipViolationError
    with pytest.raises(OwnershipViolationError, match="Access denied"):
        LibraryService.verify_ownership("user_alice", "user_bob")


def test_physical_media_sha256_checksum(tmp_path):
    """Requirement G14 / GT-05: verify cryptographic media content hashing."""
    test_file = tmp_path / "audio_sample.mp3"
    content = b"ID3v2.4.0 test audio physical bytes content"
    test_file.write_bytes(content)

    import hashlib
    expected = hashlib.sha256(content).hexdigest()

    computed = LibraryService.compute_sha256(test_file)
    assert computed == expected


def test_block_id_path_traversal_sanitization():
    """Security: verify block ID validation prevents directory traversal and shell injection."""
    invalid_ids = [
        "../etc/passwd",
        "..\\windows\\system32",
        "block/with/slash",
        "block\\backslash",
        "block;rm -rf",
        "block*wildcard",
        "",
    ]
    for bad_id in invalid_ids:
        with pytest.raises(CatalogManifestError):
            CatalogManifestService.validate_block_id(bad_id)

    valid_ids = [
        "weight-wave",
        "instagram-follow",
        "yt-lower-third",
        "data-chart",
        "block_123",
    ]
    for good_id in valid_ids:
        CatalogManifestService.validate_block_id(good_id)
