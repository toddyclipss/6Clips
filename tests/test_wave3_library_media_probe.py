# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for Wave 3 Media Probe: deep byte verification, container formats, and hash integrity."""
import hashlib
from pathlib import Path
import pytest

from backend.library_workflows.media_probe import (
    probe_media_file,
    detect_magic_container,
    compute_file_sha256,
    calculate_aspect_ratio,
    MediaProbeError,
    MissingMediaError,
    UnrecognizedMediaError,
)


def test_probe_mp4_header(tmp_path: Path):
    f = tmp_path / "sample.mp4"
    # ISO BMFF ftyp isom header
    content = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 64
    f.write_bytes(content)

    meta = probe_media_file(f)
    assert meta.file_size_bytes == len(content)
    assert meta.container_format == "mp4"
    assert meta.mime_type == "video/mp4"
    assert meta.sha256_hash == hashlib.sha256(content).hexdigest()
    assert meta.has_video is True


def test_probe_riff_wav_header(tmp_path: Path):
    f = tmp_path / "sample.wav"
    # RIFF WAVE header
    content = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x02\x00\x44\xac\x00\x00\x10\xb1\x02\x00\x04\x00\x10\x00data\x00\x00\x00\x00"
    f.write_bytes(content)

    meta = probe_media_file(f)
    assert meta.container_format == "wav"
    assert meta.mime_type == "audio/wav"
    assert meta.has_audio is True
    assert meta.has_video is False


def test_probe_mp3_header(tmp_path: Path):
    f = tmp_path / "audio.mp3"
    # ID3v2 container header
    content = b"ID3\x04\x00\x00\x00\x00\x00\x10" + b"\xff\xfb\x90\x64" + b"\x00" * 32
    f.write_bytes(content)

    meta = probe_media_file(f)
    assert meta.container_format == "mp3"
    assert meta.mime_type == "audio/mpeg"
    assert meta.has_audio is True


def test_probe_webm_header(tmp_path: Path):
    f = tmp_path / "sample.webm"
    # EBML magic bytes with 'webm'
    content = b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81\x01\x42\xf7\x81\x01webm" + b"\x00" * 32
    f.write_bytes(content)

    meta = probe_media_file(f)
    assert meta.container_format == "webm"
    assert meta.mime_type == "video/webm"
    assert meta.has_video is True


def test_probe_png_image(tmp_path: Path):
    f = tmp_path / "poster.png"
    content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x10\x00\x00\x00\x10\x08\x06\x00\x00\x00\x1f\xf3\xffa"
    f.write_bytes(content)

    meta = probe_media_file(f)
    assert meta.container_format == "png"
    assert meta.mime_type == "image/png"


def test_probe_jpeg_image(tmp_path: Path):
    f = tmp_path / "thumbnail.jpg"
    content = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb"
    f.write_bytes(content)

    meta = probe_media_file(f)
    assert meta.container_format == "jpeg"
    assert meta.mime_type == "image/jpeg"


def test_probe_rejects_empty_file(tmp_path: Path):
    f = tmp_path / "empty.mp4"
    f.write_bytes(b"")

    with pytest.raises(MediaProbeError, match="empty"):
        probe_media_file(f)


def test_probe_rejects_non_media_or_corrupt_file(tmp_path: Path):
    f = tmp_path / "fake.mp4"
    f.write_bytes(b"This is just a plain text document pretending to be an mp4 video file.")

    with pytest.raises(UnrecognizedMediaError, match="Unrecognized or unsupported"):
        probe_media_file(f)


def test_probe_non_existent_file(tmp_path: Path):
    f = tmp_path / "does_not_exist.mp4"
    with pytest.raises(MissingMediaError, match="missing on disk"):
        probe_media_file(f)


def test_aspect_ratio_classification():
    assert calculate_aspect_ratio(1080, 1920) == "9:16"
    assert calculate_aspect_ratio(720, 1280) == "9:16"
    assert calculate_aspect_ratio(1920, 1080) == "16:9"
    assert calculate_aspect_ratio(1280, 720) == "16:9"
    assert calculate_aspect_ratio(1080, 1080) == "1:1"
    assert calculate_aspect_ratio(500, 500) == "1:1"
    assert calculate_aspect_ratio(None, None) is None


def test_sha256_hash_utility(tmp_path: Path):
    f = tmp_path / "hash_test.bin"
    sample = b"ViralMint media streaming and hashing test payload 123456" * 50
    f.write_bytes(sample)

    expected = hashlib.sha256(sample).hexdigest()
    assert compute_file_sha256(f) == expected
