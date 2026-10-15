# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Native Capability Registry: Maps legacy Tools (21) and Clip Studio (9) into canonical Motion commands.
"""
from __future__ import annotations

from typing import Dict, List, Optional
from backend.oaas_editor_native.models import (
    CapabilityDescriptor,
    NativeCommandType,
    ParityStatus,
)


class NativeCapabilityRegistry:
    """Registry maintaining authoritative mapping of all 30 historical capabilities."""

    def __init__(self):
        self._capabilities: Dict[str, CapabilityDescriptor] = {}
        self._register_all_historical()

    def register(self, cap: CapabilityDescriptor) -> None:
        self._capabilities[cap.capability_id] = cap

    def get(self, capability_id: str) -> Optional[CapabilityDescriptor]:
        return self._capabilities.get(capability_id)

    def list_all(self) -> List[CapabilityDescriptor]:
        return list(self._capabilities.values())

    def get_by_category(self, is_clip_studio: bool) -> List[CapabilityDescriptor]:
        prefix = "clip_" if is_clip_studio else "tool_"
        return [c for c in self._capabilities.values() if c.capability_id.startswith(prefix)]

    def _register_all_historical(self) -> None:
        # ── 21 Historical Tools ──────────────────────────────────────────────
        tools_specs = [
            ("tool_captions", "Captions", "/api/tools/captions", NativeCommandType.CAPTIONS_EDIT, "Refine Inspector: Tools Tab", ParityStatus.NATIVE_END_TO_END, "tracks.clips.captions", "Generates styled synchronized animated captions."),
            ("tool_reframe", "Smart Reframe", "/api/tools/reframe", NativeCommandType.REFRAME, "Refine Inspector: Tools Tab", ParityStatus.NATIVE_END_TO_END, "tracks.clips.transform", "Reframes video into 9:16 vertical or 16:9 horizontal with focal tracking."),
            ("tool_audio_enhance", "Audio Enhance", "/api/tools/audio-enhance", NativeCommandType.AUDIO_ENHANCE, "Refine Inspector: Tools Tab", ParityStatus.NATIVE_PARTIAL, "tracks.clips.audio_filters", "Applies dynamic range compression, de-essing, and voice normalization."),
            ("tool_watermark", "Watermark", "/api/tools/watermark", NativeCommandType.WATERMARK, "Refine Inspector: Tools Tab", ParityStatus.NATIVE_END_TO_END, "tracks.overlays", "Places brand watermark logo at configurable anchor and opacity."),
            ("tool_merge_clips", "Merge Clips", "/api/tools/merge-clips", NativeCommandType.MERGE_CLIPS, "Timeline Workspace", ParityStatus.NATIVE_END_TO_END, "tracks.clips", "Sequences multiple video clips into a single continuous timeline track."),
            ("tool_remove_silence", "Remove Silence", "/api/tools/remove-silence", NativeCommandType.REMOVE_SILENCE, "Refine Inspector: Tools Tab", ParityStatus.NATIVE_END_TO_END, "tracks.clips", "Detects dead air and ripple-deletes silent segments."),
            ("tool_translate", "Translate Audio", "/api/tools/translate", NativeCommandType.TRANSLATE, "Refine Inspector: Tools Tab", ParityStatus.NATIVE_PARTIAL, "tracks.clips.captions", "Translates speech and synchronizes multilingual subtitle tracks."),
            ("tool_hook_analysis", "Hook Analysis", "/api/tools/hook-analysis", NativeCommandType.HOOK_ANALYSIS, "Refine Inspector: Tools Tab", ParityStatus.NATIVE_END_TO_END, "metadata.hook_score", "Evaluates first 3 seconds retention score and pacing recommendations."),
            ("tool_enhance_prompt", "Enhance Prompt", "/api/tools/enhance-prompt", NativeCommandType.ENHANCE_PROMPT, "Main Agent Goal Bar", ParityStatus.NATIVE_END_TO_END, "metadata.prompt", "Expands short creative intent into full motion composition specification."),
            ("tool_voiceover", "Voiceover Generator", "/api/tools/voiceover", NativeCommandType.VOICEOVER, "Refine Inspector: Tools Tab", ParityStatus.NATIVE_PARTIAL, "tracks.audio", "Generates neural voiceover using local Edge-TTS."),
            ("tool_transform", "Transform & Rotate", "/api/tools/transform", NativeCommandType.TRANSFORM, "Refine Inspector: Tools Tab", ParityStatus.NATIVE_END_TO_END, "tracks.clips.transform", "Applies scaling, rotation, and anchor positioning to visual layers."),
            ("tool_music_visualizer", "Music Visualizer", "/api/tools/music-visualizer", NativeCommandType.MUSIC_VISUALIZER, "Refine Inspector: Tools Tab", ParityStatus.NATIVE_END_TO_END, "tracks.blocks", "Binds audio waveform frequencies to reactive HyperFrames motion layers."),
            ("tool_gif", "GIF Generator", "/api/tools/gif", NativeCommandType.GIF, "Refine Inspector: Tools Tab", ParityStatus.NATIVE_END_TO_END, "output.gif", "Exports animated GIF loop from marked in/out region."),
            ("tool_speed", "Speed Presets", "/api/tools/speed", NativeCommandType.SPEED, "Refine Inspector: Tools Tab", ParityStatus.NATIVE_END_TO_END, "tracks.clips.playback_rate", "Adjusts clip playback velocity (0.25x to 4x) with pitch preservation."),
            ("tool_metadata", "Metadata Editor", "/api/tools/metadata", NativeCommandType.METADATA, "Refine Inspector: Properties Tab", ParityStatus.NATIVE_END_TO_END, "metadata", "Inspects and edits video container title, tags, and SEO tags."),
            ("tool_auto_chapters", "Auto Chapters", "/api/tools/auto-chapters", NativeCommandType.AUTO_CHAPTERS, "Refine Inspector: Tools Tab", ParityStatus.NATIVE_END_TO_END, "metadata.chapters", "Generates topic chapters from transcript boundary shifts."),
            ("tool_trim", "Video Trim", "/api/tools/trim", NativeCommandType.TRIM, "Timeline Workspace", ParityStatus.NATIVE_END_TO_END, "tracks.clips.trim", "Natively trims head and tail of selected media clip."),
            ("tool_subtitles", "Subtitles Burner", "/api/tools/subtitles", NativeCommandType.SUBTITLES, "Refine Inspector: Tools Tab", ParityStatus.NATIVE_END_TO_END, "tracks.clips.captions", "Burns stylized subtitle blocks onto exported frames."),
            ("tool_compress", "Video Compressor", "/api/tools/compress", NativeCommandType.COMPRESS, "Refine Inspector: Tools Tab", ParityStatus.NATIVE_PARTIAL, "output.compression", "Transcodes output media targeting specific bitrate or file size budget."),
            ("tool_crop", "Crop Aspect", "/api/tools/crop", NativeCommandType.CROP, "Refine Inspector: Tools Tab", ParityStatus.NATIVE_END_TO_END, "tracks.clips.crop", "Crops video rectangle to 9:16, 16:9, 1:1, or 4:5 ratios."),
            ("tool_auto_zoom", "Auto Dynamic Zoom", "/api/tools/auto-zoom", NativeCommandType.AUTO_ZOOM, "Refine Inspector: Tools Tab", ParityStatus.NATIVE_END_TO_END, "tracks.clips.keyframes", "Injects progressive zoom keyframes on emphasis words or scene cuts."),
        ]
        for cap_id, name, route, cmd, ui_loc, status, target, desc in tools_specs:
            self.register(CapabilityDescriptor(
                capability_id=cap_id,
                legacy_source_name=name,
                legacy_source_route=route,
                native_command=cmd,
                native_ui_location=ui_loc,
                parity_status=status,
                cas_document_target=target,
                description=desc,
            ))

        # ── 9 Historical Clip Studio Workflows ───────────────────────────────
        clip_specs = [
            ("clip_source_upload", "Source Video Upload", "/api/projects/assets", NativeCommandType.GRAPHIC_INSERT, "Motion Resources Panel: Assets", ParityStatus.NATIVE_END_TO_END, "assets", "Uploads and binds raw long-form footage into project CAS."),
            ("clip_filmstrip_bench", "Filmstrip Range Bench", "/api/projects/bench_ranges", NativeCommandType.RANGE_SELECT, "Timeline Workspace: Range Bench", ParityStatus.NATIVE_END_TO_END, "bench_ranges", "Selects in/out points directly on canvas filmstrip without separate player."),
            ("clip_virality_scoreboard", "Virality Scoreboard", "/api/scoring/score", NativeCommandType.VIRALITY_SCORE, "Refine Inspector: Properties Tab", ParityStatus.NATIVE_END_TO_END, "metadata.virality", "Displays 5-factor virality score breakdown on candidate clips."),
            ("clip_auto_cut_dialog", "Auto-Cut Silence", "/api/tools/remove-silence", NativeCommandType.REMOVE_SILENCE, "Timeline Workspace: Auto-Cut", ParityStatus.NATIVE_END_TO_END, "tracks.clips", "Extracts candidate clips automatically based on speech pause detection."),
            ("clip_split_playhead", "Split at Playhead", "/api/projects/split", NativeCommandType.SPLIT, "Timeline Workspace: Split Action", ParityStatus.NATIVE_END_TO_END, "tracks.clips", "Splits clip at current transport playhead time into two contiguous clips."),
            ("clip_slip_editing", "Slip Edit Operation", "/api/projects/slip", NativeCommandType.SLIP, "Timeline Workspace: Slip Action", ParityStatus.NATIVE_END_TO_END, "tracks.clips.source_offset", "Nudges source media window while preserving timeline duration and position."),
            ("clip_ripple_delete", "Ripple Delete", "/api/projects/ripple_delete", NativeCommandType.RIPPLE_DELETE, "Timeline Workspace: Ripple Delete", ParityStatus.NATIVE_END_TO_END, "tracks.clips", "Removes clip and shifts all subsequent clips left to prevent timeline gaps."),
            ("clip_caption_override", "Caption Word Override", "/api/projects/caption_override", NativeCommandType.CAPTIONS_EDIT, "Refine Inspector: Variables & Captions", ParityStatus.NATIVE_END_TO_END, "tracks.clips.caption_overrides", "Persists word corrections across transcriptions."),
            ("clip_batch_approval_publish", "Batch Approval & Publish", "/api/distribution/approval/sign", NativeCommandType.EXPORT, "Motion Header: Export & Approval", ParityStatus.NATIVE_END_TO_END, "output.approved_revisions", "Cryptographically signs approved revision for background distribution handoff."),
        ]
        for cap_id, name, route, cmd, ui_loc, status, target, desc in clip_specs:
            self.register(CapabilityDescriptor(
                capability_id=cap_id,
                legacy_source_name=name,
                legacy_source_route=route,
                native_command=cmd,
                native_ui_location=ui_loc,
                parity_status=status,
                cas_document_target=target,
                description=desc,
            ))
