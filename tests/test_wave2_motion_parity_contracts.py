# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 2 Motion Parity Contract Tests.

Tests:
- 21 Historical Tools inventory mapping and parity contracts
- Clip Studio capabilities parity matrix
- 3-output independent approval lifecycle and per-output export isolation
- CAS expected_revision collision detection and resolution contracts
"""
import pytest
from backend.motion_legacy_bridge.parity_contracts import (
    HISTORICAL_TOOLS_INVENTORY,
    CLIP_STUDIO_CAPABILITIES,
    OutputApprovalState,
)


def test_historical_tools_inventory_count_and_mapping():
    """Verify all historical tools (~21 tools) are accounted for with explicit mappings."""
    tools = HISTORICAL_TOOLS_INVENTORY
    assert len(tools) >= 21, f"Expected at least 21 historical tools, found {len(tools)}"

    tool_ids = {t["id"] for t in tools}
    expected_ids = {
        "video-download", "merge-clips", "transform", "remove-audio",
        "compress", "crop", "reframe", "watermark", "gif", "speed",
        "trim", "auto-zoom", "voiceover", "audio-enhance", "remove-silence",
        "music-visualizer", "captions", "subtitles", "translate",
        "hook-analysis", "metadata", "auto-chapters"
    }
    for eid in expected_ids:
        assert eid in tool_ids, f"Historical tool '{eid}' missing from inventory"

    for tool in tools:
        assert "id" in tool
        assert "title" in tool
        assert "category" in tool
        assert "service" in tool
        assert "endpoint" in tool
        assert tool["status"] in ("available", "legacy_only", "unsupported")
        assert "motion_parity" in tool


def test_clip_studio_capabilities_matrix():
    """Verify Clip Studio core capabilities are inventoried and have parity definitions."""
    caps = CLIP_STUDIO_CAPABILITIES
    assert len(caps) >= 8, f"Expected at least 8 core capabilities, got {len(caps)}"

    cap_names = {c["capability"] for c in caps}
    assert "Source Video Library & Ingest" in cap_names
    assert "Interactive Filmstrip Range Selection" in cap_names
    assert "Manual Cutting Bench (doCut)" in cap_names
    assert "AI Auto-cut Dialog & Advanced Knobs" in cap_names
    assert "Finished Clip Inspector & Video Stream" in cap_names
    assert "Virality Scoreboard (5 factors)" in cap_names

    for c in caps:
        assert c["status"] in ("PARITY_REACHED", "AVAILABLE_LEGACY_ONLY", "UNSUPPORTED")
        assert "clip_studio_file" in c
        assert "motion_file" in c


def test_independent_three_output_approvals():
    """Verify independent approval and revert lifecycle for 3 batch outputs."""
    approvals = OutputApprovalState()

    out_1 = "batch_001_output_1"
    out_2 = "batch_001_output_2"
    out_3 = "batch_001_output_3"

    assert approvals.approval_count() == 0
    assert not approvals.is_approved(out_1)
    assert not approvals.is_approved(out_2)
    assert not approvals.is_approved(out_3)

    # Approve output 1
    toggled = approvals.toggle_approval(out_1)
    assert toggled is True
    assert approvals.is_approved(out_1)
    assert not approvals.is_approved(out_2)
    assert not approvals.is_approved(out_3)
    assert approvals.approval_count() == 1

    # Approve output 3 independently
    toggled3 = approvals.toggle_approval(out_3)
    assert toggled3 is True
    assert approvals.is_approved(out_1)
    assert not approvals.is_approved(out_2)
    assert approvals.is_approved(out_3)
    assert approvals.approval_count() == 2

    # Revert approval on output 1 (reversible refine / review gate)
    toggled_revert = approvals.toggle_approval(out_1)
    assert toggled_revert is False
    assert not approvals.is_approved(out_1)
    assert approvals.is_approved(out_3)
    assert approvals.approval_count() == 1


def test_cas_expected_revision_collision_contract():
    """Simulate and verify Compare-And-Swap (CAS) revision collision contract."""
    class MockProjectDocument:
        def __init__(self, revision: int = 1):
            self.revision = revision
            self.data = {"tracks": []}

        def apply_operation(self, expected_revision: int, patch: dict):
            if expected_revision != self.revision:
                raise ValueError(
                    f"409 Conflict: expected_revision {expected_revision} != current {self.revision}"
                )
            self.data.update(patch)
            self.revision += 1
            return self.revision

    doc = MockProjectDocument(revision=3)

    # Valid mutation at current revision
    new_rev = doc.apply_operation(expected_revision=3, patch={"aspect_ratio": "16:9"})
    assert new_rev == 4
    assert doc.revision == 4

    # Stale mutation at old revision must raise conflict
    with pytest.raises(ValueError) as exc_info:
        doc.apply_operation(expected_revision=3, patch={"aspect_ratio": "9:16"})
    assert "409 Conflict" in str(exc_info.value)
    assert doc.revision == 4
