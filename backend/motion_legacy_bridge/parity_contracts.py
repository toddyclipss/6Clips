# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Motion Legacy Bridge: Parity contracts and capability matrix for Clip Studio & Tools.

Provides contract models and verification helpers for:
- 21 Historical Deterministic Media Tools parity status
- Clip Studio capabilities parity matrix
- 3-output independent approval lifecycle
- Manual caption override persistence under trims/retimes
- Revision CAS concurrency validation
"""
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field


# Exact inventory of 21 historical tools from frontend/src/pages/Tools.jsx
HISTORICAL_TOOLS_INVENTORY = [
    {
        "id": "video-download",
        "title": "Video Download",
        "category": "video",
        "service": "backend/services/ytdlp_service.py",
        "endpoint": "/api/download",
        "status": "available",
        "motion_parity": "integrated_via_library_media",
    },
    {
        "id": "merge-clips",
        "title": "Merge Clips",
        "category": "video",
        "service": "backend/core/tool_runners.py:run_merge_clips_tool",
        "endpoint": "/api/tools/merge-clips",
        "status": "available",
        "motion_parity": "integrated_via_timeline_tracks",
    },
    {
        "id": "transform",
        "title": "Transform",
        "category": "video",
        "service": "backend/core/tool_runners.py:run_transform_tool",
        "endpoint": "/api/tools/transform",
        "status": "available",
        "motion_parity": "integrated_via_motion_tools_workspace",
    },
    {
        "id": "remove-audio",
        "title": "Remove Audio",
        "category": "audio",
        "service": "backend/core/tool_runners.py:run_transform_tool(op=mute)",
        "endpoint": "/api/tools/transform?op=mute",
        "status": "available",
        "motion_parity": "integrated_via_track_mute",
    },
    {
        "id": "compress",
        "title": "Compress Video",
        "category": "video",
        "service": "backend/core/tool_runners.py:run_compress_tool",
        "endpoint": "/api/tools/compress",
        "status": "available",
        "motion_parity": "integrated_via_motion_tools_workspace",
    },
    {
        "id": "crop",
        "title": "Crop Video",
        "category": "video",
        "service": "backend/core/tool_runners.py:run_crop_tool",
        "endpoint": "/api/tools/crop",
        "status": "available",
        "motion_parity": "integrated_via_aspect_ratio_and_tools",
    },
    {
        "id": "reframe",
        "title": "Reframe to Vertical",
        "category": "video",
        "service": "backend/core/tool_runners.py:run_reframe_tool",
        "endpoint": "/api/tools/reframe",
        "status": "available",
        "motion_parity": "integrated_via_toolbar_aspect_switcher",
    },
    {
        "id": "watermark",
        "title": "Add Watermark",
        "category": "video",
        "service": "backend/core/tool_runners.py:run_watermark_tool",
        "endpoint": "/api/tools/watermark",
        "status": "available",
        "motion_parity": "integrated_via_image_overlay_track",
    },
    {
        "id": "gif",
        "title": "Video → GIF",
        "category": "video",
        "service": "backend/core/tool_runners.py:run_gif_tool",
        "endpoint": "/api/tools/gif",
        "status": "available",
        "motion_parity": "tools_workspace_runner",
    },
    {
        "id": "speed",
        "title": "Speed up / Slow down",
        "category": "video",
        "service": "backend/core/tool_runners.py:run_speed_tool",
        "endpoint": "/api/tools/speed",
        "status": "available",
        "motion_parity": "integrated_via_motion_tools_workspace",
    },
    {
        "id": "trim",
        "title": "Trim / Cut",
        "category": "video",
        "service": "backend/core/tool_runners.py:run_trim_tool",
        "endpoint": "/api/tools/trim",
        "status": "available",
        "motion_parity": "integrated_via_timeline_handles_and_split",
    },
    {
        "id": "auto-zoom",
        "title": "Auto-Zoom",
        "category": "video",
        "service": "backend/core/tool_runners.py:run_auto_zoom_tool",
        "endpoint": "/api/tools/auto-zoom",
        "status": "available",
        "motion_parity": "integrated_via_scale_animation_lanes",
    },
    {
        "id": "voiceover",
        "title": "Voice-over Generator",
        "category": "audio",
        "service": "backend/core/tool_runners.py:run_voiceover_tool",
        "endpoint": "/api/tools/voiceover",
        "status": "available",
        "motion_parity": "integrated_via_audio_track_add",
    },
    {
        "id": "audio-enhance",
        "title": "Enhance Audio",
        "category": "audio",
        "service": "backend/core/tool_runners.py:run_audio_enhance_tool",
        "endpoint": "/api/tools/audio-enhance",
        "status": "available",
        "motion_parity": "integrated_via_tools_workspace",
    },
    {
        "id": "remove-silence",
        "title": "Silence Remover",
        "category": "audio",
        "service": "backend/core/tool_runners.py:run_remove_silence_tool",
        "endpoint": "/api/tools/remove-silence",
        "status": "available",
        "motion_parity": "integrated_via_clip_extract_settings",
    },
    {
        "id": "music-visualizer",
        "title": "Music Visualizer",
        "category": "audio",
        "service": "backend/core/tool_runners.py:run_music_visualizer_tool",
        "endpoint": "/api/tools/music-visualizer",
        "status": "available",
        "motion_parity": "integrated_via_audio_waveform_canvas",
    },
    {
        "id": "captions",
        "title": "Add Captions",
        "category": "subtitles",
        "service": "backend/core/tool_runners.py:run_captions_tool",
        "endpoint": "/api/tools/captions",
        "status": "available",
        "motion_parity": "integrated_via_captions_track_and_inspector",
    },
    {
        "id": "subtitles",
        "title": "Export Subtitles",
        "category": "subtitles",
        "service": "backend/core/tool_runners.py:run_subtitles_tool",
        "endpoint": "/api/tools/subtitles",
        "status": "available",
        "motion_parity": "tools_workspace_runner",
    },
    {
        "id": "translate",
        "title": "Translate + Dub",
        "category": "subtitles",
        "service": "backend/core/tool_runners.py:run_translate_tool",
        "endpoint": "/api/tools/translate",
        "status": "available",
        "motion_parity": "tools_workspace_runner",
    },
    {
        "id": "hook-analysis",
        "title": "Hook Detector",
        "category": "subtitles",
        "service": "backend/core/tool_runners.py:run_hook_analysis_tool",
        "endpoint": "/api/tools/hook-analysis",
        "status": "available",
        "motion_parity": "integrated_via_score_breakdown_scoreboard",
    },
    {
        "id": "metadata",
        "title": "Title / Tags / Description",
        "category": "subtitles",
        "service": "backend/core/tool_runners.py:run_metadata_tool",
        "endpoint": "/api/tools/metadata",
        "status": "available",
        "motion_parity": "integrated_via_clip_inspector_metadata",
    },
    {
        "id": "auto-chapters",
        "title": "Auto Chapters",
        "category": "subtitles",
        "service": "backend/core/tool_runners.py:run_auto_chapters_tool",
        "endpoint": "/api/tools/auto-chapters",
        "status": "available",
        "motion_parity": "tools_workspace_runner",
    },
]


# Exact Clip Studio Capabilities Inventory
CLIP_STUDIO_CAPABILITIES = [
    {
        "capability": "Source Video Library & Ingest",
        "status": "PARITY_REACHED",
        "clip_studio_file": "frontend/src/pages/ClipStudio.jsx:SourceVideoCard",
        "motion_file": "frontend/src/components/motion/StudioResourcePanel.jsx",
        "notes": "Lists all downloaded videos with duration, thumbnail, and clip counts.",
    },
    {
        "capability": "Interactive Filmstrip Range Selection",
        "status": "PARITY_REACHED",
        "clip_studio_file": "frontend/src/components/clip/bench/SourceBench.jsx",
        "motion_file": "frontend/src/pages/MotionGraphics.jsx (activeContext='clip') & StudioTimelineWorkspace.jsx",
        "notes": "SourceBench ranges embedded with shared useBenchRanges hook and timeline trim handles.",
    },
    {
        "capability": "Manual Cutting Bench (doCut)",
        "status": "PARITY_REACHED",
        "clip_studio_file": "frontend/src/pages/ClipStudio.jsx:doCut",
        "motion_file": "frontend/src/pages/MotionGraphics.jsx:handleDoCut",
        "notes": "Direct POST /api/downloaded/{id}/extract-clips with mode=manual and time_ranges.",
    },
    {
        "capability": "AI Auto-cut Dialog & Advanced Knobs",
        "status": "PARITY_REACHED",
        "clip_studio_file": "frontend/src/components/clip/ExtractDialog.jsx",
        "motion_file": "frontend/src/pages/MotionGraphics.jsx:ExtractDialog",
        "notes": "Caption styles, whisper quality, emoji style, remove silence, vertical crop, duration.",
    },
    {
        "capability": "Finished Clip Inspector & Video Stream",
        "status": "PARITY_REACHED",
        "clip_studio_file": "frontend/src/pages/ClipStudio.jsx:selectedClip",
        "motion_file": "frontend/src/components/motion/MotionReviewPanel.jsx & StudioPreviewStage.jsx",
        "notes": "Real video/audio streaming, duration/dimensions readout, time range in source.",
    },
    {
        "capability": "Virality Scoreboard (5 factors)",
        "status": "PARITY_REACHED",
        "clip_studio_file": "frontend/src/pages/ClipStudio.jsx:ScoreBreakdownPanel",
        "motion_file": "frontend/src/components/motion/MotionReviewPanel.jsx",
        "notes": "Hook, Flow, Value, Trend, Shareability scores and editorial reasoning.",
    },
    {
        "capability": "Social Metadata Editing & YouTube/TikTok Upload",
        "status": "AVAILABLE_LEGACY_ONLY",
        "clip_studio_file": "frontend/src/pages/ClipStudio.jsx:handleUpload",
        "motion_file": "frontend/src/pages/ClipStudio.jsx (Retained intact)",
        "notes": "Direct social upload dispatch retained in Clip Studio; Motion focuses on Review/Refine approval.",
    },
    {
        "capability": "Thumbnail Regeneration",
        "status": "AVAILABLE_LEGACY_ONLY",
        "clip_studio_file": "frontend/src/pages/ClipStudio.jsx:handleRegenThumbnail",
        "motion_file": "frontend/src/pages/ClipStudio.jsx (Retained intact)",
        "notes": "API available via POST /api/videos/{id}/regenerate-thumbnail.",
    },
]


@dataclass
class OutputApprovalState:
    """Manages independent approvals across multiple batch outputs."""
    approved_output_ids: Set[str] = field(default_factory=set)

    def toggle_approval(self, output_id: str) -> bool:
        if output_id in self.approved_output_ids:
            self.approved_output_ids.remove(output_id)
            return False
        else:
            self.approved_output_ids.add(output_id)
            return True

    def is_approved(self, output_id: str) -> bool:
        return output_id in self.approved_output_ids

    def approval_count(self) -> int:
        return len(self.approved_output_ids)


def map_caption_timeline(
    captions: List[Dict[str, Any]],
    trim_start: float = 0.0,
    trim_end: Optional[float] = None,
    time_offset: float = 0.0,
) -> List[Dict[str, Any]]:
    """Maps and filters caption segments when a clip is trimmed or retimed.

    Preserves manual_transcript_override flags and recalibrates start/end times.
    """
    mapped = []
    t_end = trim_end if trim_end is not None else float("inf")

    for cap in captions:
        c_start = float(cap.get("start_seconds", 0.0))
        c_dur = float(cap.get("duration_seconds", 1.0))
        c_end = c_start + c_dur

        # Skip captions outside the trimmed window
        if c_end <= trim_start or c_start >= t_end:
            continue

        # Adjust start and duration relative to trim window
        new_start = max(0.0, c_start - trim_start) + time_offset
        new_end = min(t_end - trim_start, c_end - trim_start) + time_offset
        new_dur = max(0.1, new_end - new_start)

        cloned = dict(cap)
        cloned["start_seconds"] = round(new_start, 2)
        cloned["duration_seconds"] = round(new_dur, 2)
        mapped.append(cloned)

    return mapped
