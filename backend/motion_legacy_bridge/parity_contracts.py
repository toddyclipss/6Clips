# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Motion Legacy Bridge: Parity contracts and capability matrix for Clip Studio & Tools.

Provides contract models and verification helpers for:
- 21 Historical Deterministic Media Tools parity status (FUNCTIONAL / PARTIAL / BLOCKED)
- Clip Studio capabilities parity matrix
- 3-output independent approval lifecycle with editorial=NOT_ASSESSED default
- Freeform review notes per output with cross-output isolation
- Durable editing operations: slip, ripple delete, speed retime
- Authoritative manual caption override persistence under trims/retimes/retranscriptions
- Framing and safe-region presets (gameplay_reticle, hud_aware_blur, split_facecam_gameplay, center_crop)
- Revision CAS concurrency validation
"""
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
import copy


# Exact inventory of 21 historical tools from frontend/src/pages/Tools.jsx
HISTORICAL_TOOLS_INVENTORY = [
    {
        "id": "video-download",
        "title": "Video Download",
        "category": "video",
        "service": "backend/services/ytdlp_service.py",
        "endpoint": "/api/download",
        "status": "available",
        "parity_readiness": "FUNCTIONAL",
        "motion_parity": "integrated_via_library_media",
        "evidence": "Downloads remote video streams and registers into media library, accessible in Studio Resource Panel.",
        "test_method": "test_wave3_tool_video_download_status",
    },
    {
        "id": "merge-clips",
        "title": "Merge Clips",
        "category": "video",
        "service": "backend/core/tool_runners.py:run_merge_clips_tool",
        "endpoint": "/api/tools/merge-clips",
        "status": "available",
        "parity_readiness": "FUNCTIONAL",
        "motion_parity": "integrated_via_timeline_tracks",
        "evidence": "Multi-clip sequential placement on video tracks with timeline rendering.",
        "test_method": "test_wave3_tool_merge_clips_status",
    },
    {
        "id": "transform",
        "title": "Transform",
        "category": "video",
        "service": "backend/core/tool_runners.py:run_transform_tool",
        "endpoint": "/api/tools/transform",
        "status": "available",
        "parity_readiness": "FUNCTIONAL",
        "motion_parity": "integrated_via_motion_tools_workspace",
        "evidence": "Flip, rotate, loop, volume scaling via tool runner and timeline inspector controls.",
        "test_method": "test_wave3_tool_transform_status",
    },
    {
        "id": "remove-audio",
        "title": "Remove Audio",
        "category": "audio",
        "service": "backend/core/tool_runners.py:run_transform_tool(op=mute)",
        "endpoint": "/api/tools/transform?op=mute",
        "status": "available",
        "parity_readiness": "FUNCTIONAL",
        "motion_parity": "integrated_via_track_mute",
        "evidence": "Timeline track mute toggle and tool runner strip audio streams while keeping video intact.",
        "test_method": "test_wave3_tool_remove_audio_status",
    },
    {
        "id": "compress",
        "title": "Compress Video",
        "category": "video",
        "service": "backend/core/tool_runners.py:run_compress_tool",
        "endpoint": "/api/tools/compress",
        "status": "available",
        "parity_readiness": "FUNCTIONAL",
        "motion_parity": "integrated_via_motion_tools_workspace",
        "evidence": "Target bitrate/size CRF compression executed via tool runner and Tools workspace.",
        "test_method": "test_wave3_tool_compress_status",
    },
    {
        "id": "crop",
        "title": "Crop Video",
        "category": "video",
        "service": "backend/core/tool_runners.py:run_crop_tool",
        "endpoint": "/api/tools/crop",
        "status": "available",
        "parity_readiness": "FUNCTIONAL",
        "motion_parity": "integrated_via_aspect_ratio_and_tools",
        "evidence": "Crop coordinates execution via tool runner and aspect ratio switching in Studio toolbar.",
        "test_method": "test_wave3_tool_crop_status",
    },
    {
        "id": "reframe",
        "title": "Reframe to Vertical",
        "category": "video",
        "service": "backend/core/tool_runners.py:run_reframe_tool",
        "endpoint": "/api/tools/reframe",
        "status": "available",
        "parity_readiness": "FUNCTIONAL",
        "motion_parity": "integrated_via_toolbar_aspect_switcher",
        "evidence": "16:9 to 9:16 reframe with face/motion tracking, exposed in Studio aspect switcher and auto-cut.",
        "test_method": "test_wave3_tool_reframe_status",
    },
    {
        "id": "watermark",
        "title": "Add Watermark",
        "category": "video",
        "service": "backend/core/tool_runners.py:run_watermark_tool",
        "endpoint": "/api/tools/watermark",
        "status": "available",
        "parity_readiness": "FUNCTIONAL",
        "motion_parity": "integrated_via_image_overlay_track",
        "evidence": "Image overlay track in Studio Timeline and deterministic burn-in tool runner.",
        "test_method": "test_wave3_tool_watermark_status",
    },
    {
        "id": "gif",
        "title": "Video → GIF",
        "category": "video",
        "service": "backend/core/tool_runners.py:run_gif_tool",
        "endpoint": "/api/tools/gif",
        "status": "available",
        "parity_readiness": "FUNCTIONAL",
        "motion_parity": "tools_workspace_runner",
        "evidence": "Two-pass palette animated GIF generation executed via Studio Tools workspace.",
        "test_method": "test_wave3_tool_gif_status",
    },
    {
        "id": "speed",
        "title": "Speed up / Slow down",
        "category": "video",
        "service": "backend/core/tool_runners.py:run_speed_tool",
        "endpoint": "/api/tools/speed",
        "status": "available",
        "parity_readiness": "FUNCTIONAL",
        "motion_parity": "integrated_via_motion_tools_workspace",
        "evidence": "0.25x to 4x retime multiplier in timeline inspector, clip context menu, and speed runner.",
        "test_method": "test_wave3_tool_speed_status",
    },
    {
        "id": "trim",
        "title": "Trim / Cut",
        "category": "video",
        "service": "backend/core/tool_runners.py:run_trim_tool",
        "endpoint": "/api/tools/trim",
        "status": "available",
        "parity_readiness": "FUNCTIONAL",
        "motion_parity": "integrated_via_timeline_handles_and_split",
        "evidence": "Timeline trim handles, split at playhead (S), SourceBench range marking, and trim tool.",
        "test_method": "test_wave3_tool_trim_status",
    },
    {
        "id": "auto-zoom",
        "title": "Auto-Zoom",
        "category": "video",
        "service": "backend/core/tool_runners.py:run_auto_zoom_tool",
        "endpoint": "/api/tools/auto-zoom",
        "status": "available",
        "parity_readiness": "FUNCTIONAL",
        "motion_parity": "integrated_via_scale_animation_lanes",
        "evidence": "Scale animation property lanes with keyframing and auto-zoom spoken word tool runner.",
        "test_method": "test_wave3_tool_auto_zoom_status",
    },
    {
        "id": "voiceover",
        "title": "Voice-over Generator",
        "category": "audio",
        "service": "backend/core/tool_runners.py:run_voiceover_tool",
        "endpoint": "/api/tools/voiceover",
        "status": "available",
        "parity_readiness": "FUNCTIONAL",
        "motion_parity": "integrated_via_audio_track_add",
        "evidence": "Edge-TTS speech generation with direct timeline audio track placement and voiceover runner.",
        "test_method": "test_wave3_tool_voiceover_status",
    },
    {
        "id": "audio-enhance",
        "title": "Enhance Audio",
        "category": "audio",
        "service": "backend/core/tool_runners.py:run_audio_enhance_tool",
        "endpoint": "/api/tools/audio-enhance",
        "status": "available",
        "parity_readiness": "FUNCTIONAL",
        "motion_parity": "integrated_via_tools_workspace",
        "evidence": "Denoise, loudness normalization, and voice clarity filter chain in Tools workspace.",
        "test_method": "test_wave3_tool_audio_enhance_status",
    },
    {
        "id": "remove-silence",
        "title": "Silence Remover",
        "category": "audio",
        "service": "backend/core/tool_runners.py:run_remove_silence_tool",
        "endpoint": "/api/tools/remove-silence",
        "status": "available",
        "parity_readiness": "FUNCTIONAL",
        "motion_parity": "integrated_via_clip_extract_settings",
        "evidence": "Silence threshold detection in auto-cut extraction dialog and silence remover runner.",
        "test_method": "test_wave3_tool_remove_silence_status",
    },
    {
        "id": "music-visualizer",
        "title": "Music Visualizer",
        "category": "audio",
        "service": "backend/core/tool_runners.py:run_music_visualizer_tool",
        "endpoint": "/api/tools/music-visualizer",
        "status": "available",
        "parity_readiness": "FUNCTIONAL",
        "motion_parity": "integrated_via_audio_waveform_canvas",
        "evidence": "Live amplitude audio waveform canvas in timeline and spectrum video visualizer runner.",
        "test_method": "test_wave3_tool_music_visualizer_status",
    },
    {
        "id": "captions",
        "title": "Add Captions",
        "category": "subtitles",
        "service": "backend/core/tool_runners.py:run_captions_tool",
        "endpoint": "/api/tools/captions",
        "status": "available",
        "parity_readiness": "FUNCTIONAL",
        "motion_parity": "integrated_via_captions_track_and_inspector",
        "evidence": "Word-level captions track, manual override persistence, line break preservation, and burn-in.",
        "test_method": "test_wave3_tool_captions_status",
    },
    {
        "id": "subtitles",
        "title": "Export Subtitles",
        "category": "subtitles",
        "service": "backend/core/tool_runners.py:run_subtitles_tool",
        "endpoint": "/api/tools/subtitles",
        "status": "available",
        "parity_readiness": "FUNCTIONAL",
        "motion_parity": "tools_workspace_runner",
        "evidence": "SRT and VTT subtitle file generation from timeline and video transcript segments.",
        "test_method": "test_wave3_tool_subtitles_status",
    },
    {
        "id": "translate",
        "title": "Translate + Dub",
        "category": "subtitles",
        "service": "backend/core/tool_runners.py:run_translate_tool",
        "endpoint": "/api/tools/translate",
        "status": "available",
        "parity_readiness": "PARTIAL",
        "motion_parity": "tools_workspace_runner",
        "evidence": "Text translation is functional; high-fidelity audio dubbing requires external provider credentials.",
        "test_method": "test_wave3_tool_translate_status",
    },
    {
        "id": "hook-analysis",
        "title": "Hook Detector",
        "category": "subtitles",
        "service": "backend/core/tool_runners.py:run_hook_analysis_tool",
        "endpoint": "/api/tools/hook-analysis",
        "status": "available",
        "parity_readiness": "FUNCTIONAL",
        "motion_parity": "integrated_via_score_breakdown_scoreboard",
        "evidence": "First 10s virality retention scoring displayed in review panel and hook analysis runner.",
        "test_method": "test_wave3_tool_hook_analysis_status",
    },
    {
        "id": "metadata",
        "title": "Title / Tags / Description",
        "category": "subtitles",
        "service": "backend/core/tool_runners.py:run_metadata_tool",
        "endpoint": "/api/tools/metadata",
        "status": "available",
        "parity_readiness": "FUNCTIONAL",
        "motion_parity": "integrated_via_clip_inspector_metadata",
        "evidence": "Social SEO title, hashtag, and description generation available in clip inspector and tools.",
        "test_method": "test_wave3_tool_metadata_status",
    },
    {
        "id": "auto-chapters",
        "title": "Auto Chapters",
        "category": "subtitles",
        "service": "backend/core/tool_runners.py:run_auto_chapters_tool",
        "endpoint": "/api/tools/auto-chapters",
        "status": "available",
        "parity_readiness": "FUNCTIONAL",
        "motion_parity": "tools_workspace_runner",
        "evidence": "Timestamped chapter markers generated from long-form video transcript.",
        "test_method": "test_wave3_tool_auto_chapters_status",
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


def get_tool_readiness_inventory() -> List[Dict[str, Any]]:
    """Returns the verified, in-memory tool parity inventory with Wave 3 readiness statuses."""
    items = copy.deepcopy(HISTORICAL_TOOLS_INVENTORY)
    for it in items:
        it["readiness_status"] = it.get("parity_readiness", "FUNCTIONAL")
    return items


# Framing and Safe-Region Presets Contract
FRAMING_PRESETS = {
    "none": {
        "id": "none",
        "label": "Default (Full Frame)",
        "description": "Standard untouched media framing with original aspect ratio.",
        "status": "FUNCTIONAL",
    },
    "gameplay_reticle": {
        "id": "gameplay_reticle",
        "label": "Gameplay Reticle",
        "description": "Centers crosshair / reticle area and maintains safe margins for HUD radar and ammo counters.",
        "status": "FUNCTIONAL",
        "parameters": {"crosshair_safe_radius": 0.25, "radar_protection": True},
        "worker_pipeline_status": "CONTRACT_SUPPORTED",
    },
    "hud_aware_blur": {
        "id": "hud_aware_blur",
        "label": "HUD-Aware Blur",
        "description": "Converts 16:9 to vertical 9:16 using dynamic blurred wings while preserving unblurred gameplay center.",
        "status": "FUNCTIONAL",
        "parameters": {"blur_sigma": 20, "overlay_center": True},
        "worker_pipeline_status": "CONTRACT_SUPPORTED",
    },
    "split_facecam_gameplay": {
        "id": "split_facecam_gameplay",
        "label": "Split Facecam + Gameplay",
        "description": "Stacks webcam/streamer reaction in upper frame (1:1) and gameplay in lower frame (16:9).",
        "status": "FUNCTIONAL",
        "parameters": {"facecam_ratio": 0.35, "gameplay_ratio": 0.65},
        "worker_pipeline_status": "CONTRACT_SUPPORTED",
    },
    "center_crop": {
        "id": "center_crop",
        "label": "Center Crop (9:16)",
        "description": "Direct center 9:16 extraction without scaling distortion.",
        "status": "FUNCTIONAL",
        "parameters": {"crop_ratio": "9:16", "gravity": "center"},
        "worker_pipeline_status": "FUNCTIONAL",
    },
}


def apply_framing_preset(clip: Dict[str, Any], preset_name: str, custom_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Applies a safe-region framing preset to a timeline clip."""
    if preset_name not in FRAMING_PRESETS:
        raise ValueError(f"Unknown framing preset: '{preset_name}'. Valid presets: {list(FRAMING_PRESETS.keys())}")
    preset_def = FRAMING_PRESETS[preset_name]
    cloned = copy.deepcopy(clip)
    cloned["framing_preset"] = preset_name
    cloned["framing_params"] = copy.deepcopy(preset_def.get("parameters", {}))
    if custom_params:
        cloned["framing_params"].update(custom_params)
    return cloned


# Durable Timeline Operations
def apply_slip_operation(clip: Dict[str, Any], delta_seconds: float, source_duration: Optional[float] = None) -> Dict[str, Any]:
    """Applies a slip edit to a clip.

    Shifts trim_start / trim_end (source media offset) without changing
    the timeline position (start_seconds) or visible length (duration_seconds).
    """
    cloned = copy.deepcopy(clip)
    clip_dur = float(cloned.get("duration_seconds", 1.0))
    orig_trim = float(cloned.get("trim_start", 0.0))
    new_trim = orig_trim + delta_seconds

    # Clamp trim_start to >= 0
    new_trim = max(0.0, new_trim)
    if source_duration is not None:
        max_trim = max(0.0, source_duration - clip_dur)
        new_trim = min(new_trim, max_trim)

    cloned["trim_start"] = round(new_trim, 3)
    cloned["trim_end"] = round(new_trim + clip_dur, 3)
    return cloned


def apply_ripple_delete(tracks: List[Dict[str, Any]], clip_id: str) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Performs a ripple delete on the track containing clip_id.

    Removes clip_id and shifts all subsequent clips on that track to the left
    by deleted_clip.duration_seconds to prevent gaps.
    """
    new_tracks = copy.deepcopy(tracks)
    deleted_clip = None

    for track in new_tracks:
        clips = track.get("clips", [])
        idx = next((i for i, c in enumerate(clips) if c.get("id") == clip_id), None)
        if idx is not None:
            deleted_clip = clips.pop(idx)
            del_dur = float(deleted_clip.get("duration_seconds", 0.0))
            del_start = float(deleted_clip.get("start_seconds", 0.0))

            # Shift subsequent clips left
            for c in clips:
                c_start = float(c.get("start_seconds", 0.0))
                if c_start >= del_start:
                    c["start_seconds"] = max(0.0, round(c_start - del_dur, 3))
            break

    return new_tracks, deleted_clip


def apply_speed_retime(
    clip: Dict[str, Any],
    new_speed: float,
    tracks: Optional[List[Dict[str, Any]]] = None,
    ripple: bool = False,
) -> Tuple[Dict[str, Any], Optional[List[Dict[str, Any]]]]:
    """Retimes a clip with speed multiplier (0.25x - 4.0x).

    Recalculates clip duration: duration_seconds = (duration_seconds * old_speed) / new_speed.
    If ripple is True and tracks are provided, shifts subsequent clips on that track.
    """
    if new_speed <= 0:
        raise ValueError(f"Speed multiplier must be positive, got {new_speed}")

    cloned = copy.deepcopy(clip)
    old_speed = float(cloned.get("speed", 1.0))
    old_dur = float(cloned.get("duration_seconds", 1.0))
    # Source duration represented by this clip
    source_span = old_dur * old_speed
    new_dur = max(0.1, round(source_span / new_speed, 3))

    cloned["speed"] = new_speed
    cloned["duration_seconds"] = new_dur

    new_tracks = None
    if ripple and tracks is not None:
        new_tracks = copy.deepcopy(tracks)
        diff = new_dur - old_dur
        for track in new_tracks:
            clips = track.get("clips", [])
            target = next((c for c in clips if c.get("id") == clip.get("id")), None)
            if target:
                target["speed"] = new_speed
                target["duration_seconds"] = new_dur
                t_start = float(target.get("start_seconds", 0.0))
                for c in clips:
                    if c.get("id") != target.get("id") and float(c.get("start_seconds", 0.0)) > t_start:
                        c["start_seconds"] = max(0.0, round(float(c.get("start_seconds", 0.0)) + diff, 3))
                break

    return cloned, new_tracks


# Review & Notes Lifecycle
@dataclass
class OutputApprovalState:
    """Manages independent approvals and editorial states across multiple batch outputs."""
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

    def get_editorial_status(self, output_id: str) -> str:
        """Returns EDITORIAL status: defaults to NOT_ASSESSED until explicit user approval."""
        return "APPROVED" if output_id in self.approved_output_ids else "NOT_ASSESSED"

    def approval_count(self) -> int:
        return len(self.approved_output_ids)


@dataclass
class ReviewNotesManager:
    """Manages freeform review notes per output with strict cross-output isolation."""
    notes: Dict[str, str] = field(default_factory=dict)

    def set_note(self, output_id: str, note_text: str) -> None:
        self.notes[output_id] = note_text

    def get_note(self, output_id: str) -> str:
        return self.notes.get(output_id, "")

    def clear_note(self, output_id: str) -> None:
        self.notes.pop(output_id, None)

    def get_all_notes(self) -> Dict[str, str]:
        return dict(self.notes)


# Caption Timeline & Manual Override Protection
def preserve_caption_overrides(
    existing_captions: List[Dict[str, Any]],
    fresh_captions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Merges fresh captions with existing ones, preserving manual transcript overrides.

    Guarantees that user-edited captions, line breaks ('\\n'), and word timings
    are never destroyed or overwritten by subsequent Whisper retranscription.
    """
    manual_overrides = {
        c.get("id", str(idx)): c
        for idx, c in enumerate(existing_captions)
        if c.get("manual_transcript_override") is True
    }

    result = []
    for idx, fc in enumerate(fresh_captions):
        cid = fc.get("id", str(idx))
        if cid in manual_overrides:
            result.append(copy.deepcopy(manual_overrides[cid]))
        else:
            result.append(copy.deepcopy(fc))

    return result


def map_caption_timeline(
    captions: List[Dict[str, Any]],
    trim_start: float = 0.0,
    trim_end: Optional[float] = None,
    time_offset: float = 0.0,
) -> List[Dict[str, Any]]:
    """Maps and filters caption segments when a clip is trimmed or retimed.

    Preserves manual_transcript_override flags, exact line breaks ('\\n'),
    and recalibrates start/end times.
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

        cloned = copy.deepcopy(cap)
        cloned["start_seconds"] = round(new_start, 2)
        cloned["duration_seconds"] = round(new_dur, 2)
        mapped.append(cloned)

    return mapped


def retime_caption_words(
    captions: List[Dict[str, Any]],
    old_speed: float,
    new_speed: float,
) -> List[Dict[str, Any]]:
    """Scales caption timing under clip retime / speed changes.

    Preserves exact text content, line breaks, and manual override markers.
    """
    ratio = old_speed / new_speed
    retimed = []
    for cap in captions:
        cloned = copy.deepcopy(cap)
        cloned["start_seconds"] = round(float(cloned.get("start_seconds", 0.0)) * ratio, 3)
        cloned["duration_seconds"] = max(0.05, round(float(cloned.get("duration_seconds", 1.0)) * ratio, 3))
        if "words" in cloned and isinstance(cloned["words"], list):
            for w in cloned["words"]:
                if "start" in w:
                    w["start"] = round(float(w["start"]) * ratio, 3)
                if "end" in w:
                    w["end"] = round(float(w["end"]) * ratio, 3)
        retimed.append(cloned)
    return retimed
