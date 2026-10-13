# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for Wave 3 Media Streaming and HTTP Range-based seeking."""
import io
from pathlib import Path
import pytest

from backend.core.http_range import parse_range, RangeNotSatisfiable, OPEN_RANGE_WINDOW_BYTES


def test_streaming_range_initial_chunk():
    total_size = 5000000  # 5MB
    start, end = parse_range("bytes=0-1048575", total_size)
    assert start == 0
    assert end == 1048575
    length = (end - start) + 1
    assert length == 1048576  # exactly 1MB chunk for video buffer


def test_streaming_range_suffix_tail_moov_atom():
    total_size = 10000000  # 10MB
    start, end = parse_range("bytes=-1024", total_size)
    assert start == total_size - 1024
    assert end == total_size - 1
    assert (end - start) + 1 == 1024


def test_streaming_range_mid_seek():
    total_size = 2000000
    start, end = parse_range("bytes=500000-999999", total_size)
    assert start == 500000
    assert end == 999999


def test_streaming_range_out_of_bounds_raises():
    total_size = 1000
    with pytest.raises(RangeNotSatisfiable):
        parse_range("bytes=2000-3000", total_size)

    with pytest.raises(RangeNotSatisfiable):
        parse_range("bytes=1000-", total_size)


def test_streaming_generator_slicing(tmp_path: Path):
    f = tmp_path / "stream_video.mp4"
    dummy_data = b"0123456789abcdef" * 1024  # 16 KB
    f.write_bytes(dummy_data)

    start = 16
    end = 47
    # Read slice via file seek
    with open(f, "rb") as fp:
        fp.seek(start)
        data = fp.read(end - start + 1)

    assert len(data) == 32
    assert data == dummy_data[start : end + 1]
