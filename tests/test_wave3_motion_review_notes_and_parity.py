# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 3 Motion Review Experience, Framing Presets & 21-Tool Parity Tests.

Tests:
- 21 Historical Tools readiness inventory: verified in-memory evaluation with FUNCTIONAL / PARTIAL / BLOCKED statuses
- 3-output independent review notes: cross-output isolation and note persistence
- 3-output independent approvals: default editorial=NOT_ASSESSED until explicit user approval
- Framing & safe-region presets: gameplay_reticle, hud_aware_blur, split_facecam_gameplay, center_crop
- Authoritative manual caption override: preservation of user edits, line breaks, and word timings over Whisper retranscription
"""
import pytest
from backend.motion_legacy_bridge.parity_contracts import (
    get_tool_readiness_inventory,
    HISTORICAL_TOOLS_INVENTORY,
    FRAMING_PRESETS,
    apply_framing_preset,
    OutputApprovalState,
    ReviewNotesManager,
    preserve_caption_overrides,
    map_caption_timeline,
)


def test_historical_tools_readiness_inventory():
    """Verify that all historical deterministic tools are indexed with verified readiness status."""
    inventory = get_tool_readiness_inventory()
    assert len(inventory) >= 21, f"Expected at least 21 tools in inventory, got {len(inventory)}"

    valid_statuses = {"FUNCTIONAL", "PARTIAL", "BLOCKED"}
    categories = set()

    for tool in inventory:
        assert "id" in tool
        assert "title" in tool
        assert "category" in tool
        assert tool["readiness_status"] in valid_statuses, f"Tool {tool['id']} has invalid readiness status {tool['readiness_status']}"
        assert "evidence" in tool, f"Tool {tool['id']} missing evidence"
        assert "endpoint" in tool, f"Tool {tool['id']} missing endpoint"
        assert "service" in tool, f"Tool {tool['id']} missing service runner"
        assert "test_method" in tool, f"Tool {tool['id']} missing linked test method"
        categories.add(tool["category"])

    assert "video" in categories
    assert "audio" in categories
    assert "subtitles" in categories


def test_wave3_tool_video_download_status():
    """Verify video-download tool status."""
    tool = next(t for t in HISTORICAL_TOOLS_INVENTORY if t["id"] == "video-download")
    assert tool["parity_readiness"] == "FUNCTIONAL"
    assert "/api/download" in tool["endpoint"]


def test_wave3_tool_merge_clips_status():
    """Verify merge-clips tool status."""
    tool = next(t for t in HISTORICAL_TOOLS_INVENTORY if t["id"] == "merge-clips")
    assert tool["parity_readiness"] == "FUNCTIONAL"
    assert "run_merge_clips_tool" in tool["service"]


def test_wave3_tool_transform_status():
    """Verify transform tool status."""
    tool = next(t for t in HISTORICAL_TOOLS_INVENTORY if t["id"] == "transform")
    assert tool["parity_readiness"] == "FUNCTIONAL"


def test_wave3_tool_remove_audio_status():
    """Verify remove-audio tool status."""
    tool = next(t for t in HISTORICAL_TOOLS_INVENTORY if t["id"] == "remove-audio")
    assert tool["parity_readiness"] == "FUNCTIONAL"


def test_wave3_tool_compress_status():
    """Verify compress tool status."""
    tool = next(t for t in HISTORICAL_TOOLS_INVENTORY if t["id"] == "compress")
    assert tool["parity_readiness"] == "FUNCTIONAL"


def test_wave3_tool_crop_status():
    """Verify crop tool status."""
    tool = next(t for t in HISTORICAL_TOOLS_INVENTORY if t["id"] == "crop")
    assert tool["parity_readiness"] == "FUNCTIONAL"


def test_wave3_tool_reframe_status():
    """Verify reframe tool status."""
    tool = next(t for t in HISTORICAL_TOOLS_INVENTORY if t["id"] == "reframe")
    assert tool["parity_readiness"] == "FUNCTIONAL"


def test_wave3_tool_watermark_status():
    """Verify watermark tool status."""
    tool = next(t for t in HISTORICAL_TOOLS_INVENTORY if t["id"] == "watermark")
    assert tool["parity_readiness"] == "FUNCTIONAL"


def test_wave3_tool_gif_status():
    """Verify gif tool status."""
    tool = next(t for t in HISTORICAL_TOOLS_INVENTORY if t["id"] == "gif")
    assert tool["parity_readiness"] == "FUNCTIONAL"


def test_wave3_tool_speed_status():
    """Verify speed tool status."""
    tool = next(t for t in HISTORICAL_TOOLS_INVENTORY if t["id"] == "speed")
    assert tool["parity_readiness"] == "FUNCTIONAL"


def test_wave3_tool_trim_status():
    """Verify trim tool status."""
    tool = next(t for t in HISTORICAL_TOOLS_INVENTORY if t["id"] == "trim")
    assert tool["parity_readiness"] == "FUNCTIONAL"


def test_wave3_tool_auto_zoom_status():
    """Verify auto-zoom tool status."""
    tool = next(t for t in HISTORICAL_TOOLS_INVENTORY if t["id"] == "auto-zoom")
    assert tool["parity_readiness"] == "FUNCTIONAL"


def test_wave3_tool_voiceover_status():
    """Verify voiceover tool status."""
    tool = next(t for t in HISTORICAL_TOOLS_INVENTORY if t["id"] == "voiceover")
    assert tool["parity_readiness"] == "FUNCTIONAL"


def test_wave3_tool_audio_enhance_status():
    """Verify audio-enhance tool status."""
    tool = next(t for t in HISTORICAL_TOOLS_INVENTORY if t["id"] == "audio-enhance")
    assert tool["parity_readiness"] == "FUNCTIONAL"


def test_wave3_tool_remove_silence_status():
    """Verify remove-silence tool status."""
    tool = next(t for t in HISTORICAL_TOOLS_INVENTORY if t["id"] == "remove-silence")
    assert tool["parity_readiness"] == "FUNCTIONAL"


def test_wave3_tool_music_visualizer_status():
    """Verify music-visualizer tool status."""
    tool = next(t for t in HISTORICAL_TOOLS_INVENTORY if t["id"] == "music-visualizer")
    assert tool["parity_readiness"] == "FUNCTIONAL"


def test_wave3_tool_captions_status():
    """Verify captions tool status."""
    tool = next(t for t in HISTORICAL_TOOLS_INVENTORY if t["id"] == "captions")
    assert tool["parity_readiness"] == "FUNCTIONAL"


def test_wave3_tool_subtitles_status():
    """Verify subtitles tool status."""
    tool = next(t for t in HISTORICAL_TOOLS_INVENTORY if t["id"] == "subtitles")
    assert tool["parity_readiness"] == "FUNCTIONAL"


def test_wave3_tool_translate_status():
    """Verify translate tool status: text is functional; external dub provider is partial."""
    tool = next(t for t in HISTORICAL_TOOLS_INVENTORY if t["id"] == "translate")
    assert tool["parity_readiness"] == "PARTIAL"


def test_wave3_tool_hook_analysis_status():
    """Verify hook-analysis tool status."""
    tool = next(t for t in HISTORICAL_TOOLS_INVENTORY if t["id"] == "hook-analysis")
    assert tool["parity_readiness"] == "FUNCTIONAL"


def test_wave3_tool_metadata_status():
    """Verify metadata tool status."""
    tool = next(t for t in HISTORICAL_TOOLS_INVENTORY if t["id"] == "metadata")
    assert tool["parity_readiness"] == "FUNCTIONAL"


def test_wave3_tool_auto_chapters_status():
    """Verify auto-chapters tool status."""
    tool = next(t for t in HISTORICAL_TOOLS_INVENTORY if t["id"] == "auto-chapters")
    assert tool["parity_readiness"] == "FUNCTIONAL"


def test_three_output_review_notes_isolation():
    """Verify freeform review notes per clip maintain strict cross-output isolation in a 3-output batch."""
    manager = ReviewNotesManager()
    output_ids = ["clip_batch_001", "clip_batch_002", "clip_batch_003"]

    manager.set_note(output_ids[0], "Pacing is great in the opening 3 seconds.")
    manager.set_note(output_ids[1], "Music volume is slightly too loud over voiceover.")
    manager.set_note(output_ids[2], "Approved for TikTok upload.")

    # Strict isolation
    assert manager.get_note(output_ids[0]) == "Pacing is great in the opening 3 seconds."
    assert manager.get_note(output_ids[1]) == "Music volume is slightly too loud over voiceover."
    assert manager.get_note(output_ids[2]) == "Approved for TikTok upload."

    # Update note on output 1 without affecting output 2 or 3
    manager.set_note(output_ids[0], "Revised note: trim first 0.5s.")
    assert manager.get_note(output_ids[0]) == "Revised note: trim first 0.5s."
    assert manager.get_note(output_ids[1]) == "Music volume is slightly too loud over voiceover."


def test_three_output_approval_lifecycle_and_default_state():
    """Verify default editorial status is NOT_ASSESSED and approvals remain independent per output."""
    state = OutputApprovalState()
    output_ids = ["out_1", "out_2", "out_3"]

    # Initial state: ALL outputs must be NOT_ASSESSED
    for oid in output_ids:
        assert state.is_approved(oid) is False
        assert state.get_editorial_status(oid) == "NOT_ASSESSED"

    assert state.approval_count() == 0

    # User explicitly approves Output 1
    toggled = state.toggle_approval("out_1")
    assert toggled is True
    assert state.is_approved("out_1") is True
    assert state.get_editorial_status("out_1") == "APPROVED"

    # Outputs 2 and 3 remain untouched and NOT_ASSESSED!
    assert state.is_approved("out_2") is False
    assert state.get_editorial_status("out_2") == "NOT_ASSESSED"
    assert state.is_approved("out_3") is False
    assert state.get_editorial_status("out_3") == "NOT_ASSESSED"
    assert state.approval_count() == 1

    # Toggling Output 1 again reverts to NOT_ASSESSED
    toggled_again = state.toggle_approval("out_1")
    assert toggled_again is False
    assert state.is_approved("out_1") is False
    assert state.get_editorial_status("out_1") == "NOT_ASSESSED"
    assert state.approval_count() == 0


def test_framing_presets_contract():
    """Verify safe-region framing presets application to timeline clip."""
    clip = {
        "id": "clip_gameplay_1",
        "title": "FPS Highlights",
        "type": "video",
        "start_seconds": 0.0,
        "duration_seconds": 15.0,
    }

    # Apply gameplay_reticle
    reticle_clip = apply_framing_preset(clip, "gameplay_reticle")
    assert reticle_clip["framing_preset"] == "gameplay_reticle"
    assert reticle_clip["framing_params"]["crosshair_safe_radius"] == 0.25
    assert reticle_clip["framing_params"]["radar_protection"] is True

    # Apply hud_aware_blur
    blur_clip = apply_framing_preset(clip, "hud_aware_blur")
    assert blur_clip["framing_preset"] == "hud_aware_blur"
    assert blur_clip["framing_params"]["blur_sigma"] == 20

    # Apply split_facecam_gameplay
    split_clip = apply_framing_preset(clip, "split_facecam_gameplay")
    assert split_clip["framing_preset"] == "split_facecam_gameplay"
    assert split_clip["framing_params"]["facecam_ratio"] == 0.35

    # Apply center_crop
    crop_clip = apply_framing_preset(clip, "center_crop")
    assert crop_clip["framing_preset"] == "center_crop"
    assert crop_clip["framing_params"]["crop_ratio"] == "9:16"

    # Unknown preset raises ValueError
    with pytest.raises(ValueError):
        apply_framing_preset(clip, "nonexistent_preset")


def test_authoritative_caption_override_preservation():
    """Verify user manual caption edits, multiline formatting, and timings survive Whisper retranscription."""
    original_captions = [
        {
            "id": "c1",
            "start_seconds": 0.0,
            "duration_seconds": 2.5,
            "caption_text": "HOOK LINE\nSECOND LINE OF HOOK",
            "manual_transcript_override": True,
        },
        {
            "id": "c2",
            "start_seconds": 2.5,
            "duration_seconds": 3.0,
            "caption_text": "Unedited raw whisper segment",
            "manual_transcript_override": False,
        },
    ]

    # Fresh Whisper run provides alternative text for both segments
    fresh_whisper_captions = [
        {
            "id": "c1",
            "start_seconds": 0.0,
            "duration_seconds": 2.4,
            "caption_text": "Hook line second line of hook without newlines",
            "manual_transcript_override": False,
        },
        {
            "id": "c2",
            "start_seconds": 2.5,
            "duration_seconds": 3.0,
            "caption_text": "Whisper updated raw transcript segment",
            "manual_transcript_override": False,
        },
    ]

    merged = preserve_caption_overrides(original_captions, fresh_whisper_captions)
    assert len(merged) == 2

    # Segment c1: user manual override with newline MUST be preserved
    c1 = next(c for c in merged if c["id"] == "c1")
    assert c1["caption_text"] == "HOOK LINE\nSECOND LINE OF HOOK"
    assert c1["manual_transcript_override"] is True

    # Segment c2: unedited segment is safely updated by fresh Whisper
    c2 = next(c for c in merged if c["id"] == "c2")
    assert c2["caption_text"] == "Whisper updated raw transcript segment"
    assert c2["manual_transcript_override"] is False
