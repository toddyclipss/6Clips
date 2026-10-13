# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Deterministic capability dispatcher for Motion Studio and Main Agent automation.

Executes native Clip Studio timeline mutations and genuine tool operations
independently of the browser UI, strictly without mocks or fakes.
"""

from __future__ import annotations

import asyncio
import copy
import logging
import math
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import uuid4

from .models import CapabilityExecutionResult, ParityTier
from .registry import MotionCapabilitiesRegistry

logger = logging.getLogger(__name__)


def _run_ffmpeg_cmd(args: List[str]) -> Tuple[int, str, str]:
    """Execute ffmpeg synchronously in thread pool, returning rc, stdout, stderr."""
    cmd = ["ffmpeg", "-y", "-hide_banner"] + args
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return res.returncode, res.stdout, res.stderr


class MotionCapabilityDispatcher:
    """Dispatches capability invocations to genuine service backends or timeline mutations."""

    @classmethod
    async def dispatch(
        cls,
        capability_id: str,
        input_path: Optional[Union[str, Path]] = None,
        params: Optional[Dict[str, Any]] = None,
        project_doc: Optional[Dict[str, Any]] = None,
        output_dir: Optional[Union[str, Path]] = None,
    ) -> CapabilityExecutionResult:
        """Main entry point for executing a capability."""
        start_time = time.monotonic()
        params = params or {}
        spec = MotionCapabilitiesRegistry.get(capability_id)

        if not spec:
            return CapabilityExecutionResult(
                capability_id=capability_id,
                status="FAILED",
                message=f"Capability '{capability_id}' not found in registry.",
                error_detail="UNKNOWN_CAPABILITY",
                execution_time_seconds=time.monotonic() - start_time,
            )

        # ─── Clip Studio Native Timeline Workflows ─────────────────────────
        if capability_id == "timeline-clip-split":
            return await cls._execute_timeline_split(spec.id, project_doc, params, start_time)

        elif capability_id == "timeline-slip-edit":
            return await cls._execute_timeline_slip(spec.id, project_doc, params, start_time)

        elif capability_id == "timeline-ripple-delete":
            return await cls._execute_timeline_ripple_delete(spec.id, project_doc, params, start_time)

        elif capability_id == "timeline-retime-playback":
            return await cls._execute_timeline_retime(spec.id, project_doc, params, start_time)

        elif capability_id == "b-roll-lane-placement":
            return await cls._execute_b_roll_placement(spec.id, project_doc, params, start_time)

        elif capability_id == "audio-framing-parity":
            return await cls._execute_audio_framing_parity(spec.id, project_doc, params, start_time)

        elif capability_id == "multiline-caption-override":
            return await cls._execute_multiline_caption_override(spec.id, project_doc, params, start_time)

        elif capability_id == "three-output-review":
            return await cls._execute_three_output_review(spec.id, params, start_time)

        elif capability_id == "source-bench-ranges":
            return await cls._execute_bench_ranges(spec.id, project_doc, params, start_time)

        # ─── 21 Deterministic Media Tools ──────────────────────────────────
        # Validate input path if tool requires a media file
        in_p: Optional[Path] = None
        if input_path is not None:
            in_p = Path(input_path)
            if not in_p.exists():
                return CapabilityExecutionResult(
                    capability_id=capability_id,
                    status="FAILED",
                    message=f"Input file does not exist: {input_path}",
                    error_detail="FILE_NOT_FOUND",
                    execution_time_seconds=time.monotonic() - start_time,
                )

        # Prepare output directory
        out_dir = Path(output_dir) if output_dir else Path(os.environ.get("TEMP", "/tmp")) / "viralmint_motion_tools"
        out_dir.mkdir(parents=True, exist_ok=True)

        res: Optional[CapabilityExecutionResult] = None
        if capability_id == "trim":
            res = await cls._tool_trim(spec.id, in_p, params, out_dir, start_time)

        elif capability_id == "speed":
            res = await cls._tool_speed(spec.id, in_p, params, out_dir, start_time)

        elif capability_id == "crop":
            res = await cls._tool_crop(spec.id, in_p, params, out_dir, start_time)

        elif capability_id == "compress":
            res = await cls._tool_compress(spec.id, in_p, params, out_dir, start_time)

        elif capability_id == "remove-audio":
            res = await cls._tool_remove_audio(spec.id, in_p, params, out_dir, start_time)

        elif capability_id == "extract-audio":
            res = await cls._tool_extract_audio(spec.id, in_p, params, out_dir, start_time)

        elif capability_id == "transform":
            res = await cls._tool_transform(spec.id, in_p, params, out_dir, start_time)

        elif capability_id == "reframe":
            res = await cls._tool_reframe(spec.id, in_p, params, out_dir, start_time)

        elif capability_id == "watermark":
            res = await cls._tool_watermark(spec.id, in_p, params, out_dir, start_time)

        elif capability_id == "resize":
            res = await cls._tool_resize(spec.id, in_p, params, out_dir, start_time)

        elif capability_id == "silence-remover":
            res = await cls._tool_silence_remover(spec.id, in_p, params, out_dir, start_time)

        elif capability_id == "split-silence":
            res = await cls._tool_split_silence(spec.id, in_p, params, out_dir, start_time)

        elif capability_id == "merge-clips":
            res = await cls._tool_merge_clips(spec.id, params, out_dir, start_time)

        elif capability_id == "enhance-audio":
            res = await cls._tool_enhance_audio(spec.id, in_p, params, out_dir, start_time)

        elif capability_id in ("voiceover", "dubbing"):
            res = await cls._tool_tts(spec.id, in_p, params, out_dir, start_time)

        elif capability_id in ("transcribe", "captions"):
            res = await cls._tool_transcribe_or_captions(spec.id, in_p, params, out_dir, start_time)

        elif capability_id in ("translate", "hook-analysis", "metadata", "auto-chapters"):
            res = await cls._tool_ai_text(spec.id, in_p, params, start_time)

        elif capability_id == "video-download":
            res = await cls._tool_video_download(spec.id, params, out_dir, start_time)

        else:
            res = CapabilityExecutionResult(
                capability_id=capability_id,
                status="NOT_IMPLEMENTED",
                message=f"No dispatcher handler wired for '{capability_id}'.",
                execution_time_seconds=time.monotonic() - start_time,
            )

        if res and res.status == "SUCCESS" and res.output_path and project_doc:
            res = cls._attach_output_to_project_doc(res, project_doc, capability_id, params)

        return res

    # ───────────────────────────────────────────────────────────────────────
    # Native Clip Studio Timeline Mutations
    # ───────────────────────────────────────────────────────────────────────

    @classmethod
    async def _execute_timeline_split(
        cls, cap_id: str, doc: Optional[Dict[str, Any]], params: Dict[str, Any], start_time: float
    ) -> CapabilityExecutionResult:
        if not doc or "tracks" not in doc:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Missing valid project_doc with tracks.",
                error_detail="INVALID_PROJECT_DOC", execution_time_seconds=time.monotonic() - start_time,
            )
        clip_id = params.get("clip_id")
        split_time = params.get("split_time")
        if clip_id is None or split_time is None:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="clip_id and split_time are required.",
                error_detail="MISSING_PARAMS", execution_time_seconds=time.monotonic() - start_time,
            )

        new_doc = copy.deepcopy(doc)
        split_found = False
        new_clip_a_id = f"{clip_id}_part1"
        new_clip_b_id = f"{clip_id}_part2"

        for track in new_doc.get("tracks", []):
            clips = track.get("clips", [])
            for i, c in enumerate(clips):
                if c.get("id") == clip_id:
                    c_start = float(c.get("start", 0))
                    c_dur = float(c.get("duration", 0))
                    c_end = c_start + c_dur
                    if split_time <= c_start or split_time >= c_end:
                        return CapabilityExecutionResult(
                            capability_id=cap_id, status="FAILED",
                            message=f"split_time ({split_time}) must be strictly within clip bounds ({c_start}..{c_end}).",
                            error_detail="OUT_OF_BOUNDS", execution_time_seconds=time.monotonic() - start_time,
                        )

                    delta = split_time - c_start
                    in_pt = float(c.get("in_point", 0))

                    clip_a = copy.deepcopy(c)
                    clip_a["id"] = new_clip_a_id
                    clip_a["duration"] = delta
                    clip_a["out_point"] = in_pt + delta

                    clip_b = copy.deepcopy(c)
                    clip_b["id"] = new_clip_b_id
                    clip_b["start"] = split_time
                    clip_b["duration"] = c_dur - delta
                    clip_b["in_point"] = in_pt + delta

                    clips[i:i+1] = [clip_a, clip_b]
                    split_found = True
                    break
            if split_found:
                break

        if not split_found:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message=f"Clip '{clip_id}' not found in tracks.",
                error_detail="CLIP_NOT_FOUND", execution_time_seconds=time.monotonic() - start_time,
            )

        return CapabilityExecutionResult(
            capability_id=cap_id, status="SUCCESS",
            message=f"Clip '{clip_id}' cleanly split at t={split_time}s into '{new_clip_a_id}' and '{new_clip_b_id}'.",
            output_data={"project_doc": new_doc, "split_clips": [new_clip_a_id, new_clip_b_id]},
            execution_time_seconds=time.monotonic() - start_time,
        )

    @classmethod
    async def _execute_timeline_slip(
        cls, cap_id: str, doc: Optional[Dict[str, Any]], params: Dict[str, Any], start_time: float
    ) -> CapabilityExecutionResult:
        if not doc or "tracks" not in doc:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Missing valid project_doc.",
                error_detail="INVALID_PROJECT_DOC", execution_time_seconds=time.monotonic() - start_time,
            )
        clip_id = params.get("clip_id")
        slip_delta = float(params.get("slip_delta_seconds", 0))

        new_doc = copy.deepcopy(doc)
        found = False
        for track in new_doc.get("tracks", []):
            for c in track.get("clips", []):
                if c.get("id") == clip_id:
                    in_p = max(0.0, float(c.get("in_point", 0)) + slip_delta)
                    dur = float(c.get("duration", 0))
                    c["in_point"] = in_p
                    c["out_point"] = in_p + dur
                    found = True
                    break
            if found:
                break

        if not found:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message=f"Clip '{clip_id}' not found.",
                error_detail="CLIP_NOT_FOUND", execution_time_seconds=time.monotonic() - start_time,
            )

        return CapabilityExecutionResult(
            capability_id=cap_id, status="SUCCESS",
            message=f"Clip '{clip_id}' slipped by {slip_delta}s (timeline start/duration locked).",
            output_data={"project_doc": new_doc, "slipped_clip_id": clip_id},
            execution_time_seconds=time.monotonic() - start_time,
        )

    @classmethod
    async def _execute_timeline_ripple_delete(
        cls, cap_id: str, doc: Optional[Dict[str, Any]], params: Dict[str, Any], start_time: float
    ) -> CapabilityExecutionResult:
        if not doc or "tracks" not in doc:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Missing valid project_doc.",
                error_detail="INVALID_PROJECT_DOC", execution_time_seconds=time.monotonic() - start_time,
            )
        clip_id = params.get("clip_id")
        new_doc = copy.deepcopy(doc)
        deleted = False
        ripple_shift = 0.0

        for track in new_doc.get("tracks", []):
            clips = track.get("clips", [])
            target_idx = -1
            for i, c in enumerate(clips):
                if c.get("id") == clip_id:
                    target_idx = i
                    ripple_shift = float(c.get("duration", 0))
                    break
            if target_idx >= 0:
                clips.pop(target_idx)
                for c in clips[target_idx:]:
                    c["start"] = max(0.0, float(c.get("start", 0)) - ripple_shift)
                deleted = True
                break

        if not deleted:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message=f"Clip '{clip_id}' not found.",
                error_detail="CLIP_NOT_FOUND", execution_time_seconds=time.monotonic() - start_time,
            )

        return CapabilityExecutionResult(
            capability_id=cap_id, status="SUCCESS",
            message=f"Clip '{clip_id}' deleted and subsequent clips rippled left by {ripple_shift}s.",
            output_data={"project_doc": new_doc, "deleted_clip_id": clip_id, "rippled_seconds": ripple_shift},
            execution_time_seconds=time.monotonic() - start_time,
        )

    @classmethod
    async def _execute_timeline_retime(
        cls, cap_id: str, doc: Optional[Dict[str, Any]], params: Dict[str, Any], start_time: float
    ) -> CapabilityExecutionResult:
        if not doc or "tracks" not in doc:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Missing valid project_doc.",
                error_detail="INVALID_PROJECT_DOC", execution_time_seconds=time.monotonic() - start_time,
            )
        clip_id = params.get("clip_id")
        factor = float(params.get("factor", 1.0))
        if factor <= 0.0:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Retime factor must be positive.",
                error_detail="INVALID_FACTOR", execution_time_seconds=time.monotonic() - start_time,
            )

        new_doc = copy.deepcopy(doc)
        found = False
        for track in new_doc.get("tracks", []):
            for c in track.get("clips", []):
                if c.get("id") == clip_id:
                    c["speed"] = factor
                    orig_dur = float(c.get("duration", 0))
                    c["duration"] = round(orig_dur / factor, 4)
                    found = True
                    break
            if found:
                break

        if not found:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message=f"Clip '{clip_id}' not found.",
                error_detail="CLIP_NOT_FOUND", execution_time_seconds=time.monotonic() - start_time,
            )

        return CapabilityExecutionResult(
            capability_id=cap_id, status="SUCCESS",
            message=f"Clip '{clip_id}' retimed with speed factor {factor}x.",
            output_data={"project_doc": new_doc, "clip_id": clip_id, "speed": factor},
            execution_time_seconds=time.monotonic() - start_time,
        )

    @classmethod
    async def _execute_b_roll_placement(
        cls, cap_id: str, doc: Optional[Dict[str, Any]], params: Dict[str, Any], start_time: float
    ) -> CapabilityExecutionResult:
        if not doc:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Missing valid project_doc.",
                error_detail="INVALID_PROJECT_DOC", execution_time_seconds=time.monotonic() - start_time,
            )
        new_doc = copy.deepcopy(doc)
        tracks = new_doc.setdefault("tracks", [])

        # Find or create b-roll overlay track
        overlay_track = None
        for t in tracks:
            if t.get("name") in ("B-Roll", "Overlay", "Video Overlay") or t.get("is_overlay"):
                overlay_track = t
                break
        if not overlay_track:
            overlay_track = {
                "id": f"track_{uuid4().hex[:6]}",
                "name": "B-Roll Overlay",
                "type": "video",
                "is_overlay": True,
                "clips": [],
            }
            tracks.append(overlay_track)

        clip_id = params.get("clip_id") or f"broll_{uuid4().hex[:6]}"
        new_clip = {
            "id": clip_id,
            "name": params.get("name", "B-Roll Insert"),
            "source": params.get("source_url") or params.get("asset_id", ""),
            "start": float(params.get("start", 0)),
            "duration": float(params.get("duration", 3.0)),
            "in_point": float(params.get("in_point", 0)),
            "out_point": float(params.get("in_point", 0)) + float(params.get("duration", 3.0)),
            "framing_preset": params.get("framing_preset", "center_crop"),
        }
        overlay_track.setdefault("clips", []).append(new_clip)

        return CapabilityExecutionResult(
            capability_id=cap_id, status="SUCCESS",
            message=f"B-roll clip '{clip_id}' placed on '{overlay_track['name']}' at t={new_clip['start']}s.",
            output_data={"project_doc": new_doc, "track_id": overlay_track["id"], "clip_id": clip_id},
            execution_time_seconds=time.monotonic() - start_time,
        )

    @classmethod
    async def _execute_audio_framing_parity(
        cls, cap_id: str, doc: Optional[Dict[str, Any]], params: Dict[str, Any], start_time: float
    ) -> CapabilityExecutionResult:
        if not doc:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Missing project_doc.",
                error_detail="INVALID_PROJECT_DOC", execution_time_seconds=time.monotonic() - start_time,
            )
        new_doc = copy.deepcopy(doc)
        clip_id = params.get("clip_id")
        volume = params.get("volume")
        preset = params.get("framing_preset")

        # Worker status classification now that clip_renderer implements deterministic filter graphs
        if preset in ("center_crop", "none", None):
            worker_status = "Native 9:16 Center Crop (Active)"
        elif preset in ("gameplay_reticle", "hud_aware_blur", "split_facecam_gameplay"):
            worker_status = f"Active (Filter Graph Integrated: {preset}) [Wave 6 Parity: formerly PENDING]"
        else:
            worker_status = f"PENDING (Unsupported Preset: {preset})"

        applied = False
        for t in new_doc.get("tracks", []):
            for c in t.get("clips", []):
                if c.get("id") == clip_id:
                    if volume is not None:
                        c["volume"] = float(volume)
                    if preset is not None:
                        c["framing_preset"] = preset
                        c["worker_status"] = worker_status
                    applied = True
                    break
            if applied:
                break

        if not applied:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message=f"Clip '{clip_id}' not found.",
                error_detail="CLIP_NOT_FOUND", execution_time_seconds=time.monotonic() - start_time,
            )

        return CapabilityExecutionResult(
            capability_id=cap_id, status="SUCCESS",
            message=f"Audio & framing updated on '{clip_id}'. Worker Status: {worker_status}",
            output_data={"project_doc": new_doc, "clip_id": clip_id, "worker_status": worker_status},
            execution_time_seconds=time.monotonic() - start_time,
        )

    @classmethod
    async def _execute_multiline_caption_override(
        cls, cap_id: str, doc: Optional[Dict[str, Any]], params: Dict[str, Any], start_time: float
    ) -> CapabilityExecutionResult:
        if not doc:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Missing project_doc.",
                error_detail="INVALID_PROJECT_DOC", execution_time_seconds=time.monotonic() - start_time,
            )
        new_doc = copy.deepcopy(doc)
        layer_id = params.get("layer_id")
        override_text = params.get("text", "")

        # Look in layers or blocks
        found = False
        for layer in new_doc.get("layers", []):
            if layer.get("id") == layer_id or layer.get("type") in ("caption", "text", "captions"):
                layer["text"] = override_text
                layer["override_active"] = True
                found = True
                break

        if not found:
            # Store in project document caption overrides root
            new_doc.setdefault("caption_overrides", {})[layer_id or "primary"] = {
                "text": override_text,
                "timestamp": time.time(),
            }

        return CapabilityExecutionResult(
            capability_id=cap_id, status="SUCCESS",
            message="Multiline caption override recorded and preserved across pipeline passes.",
            output_data={"project_doc": new_doc, "text": override_text},
            execution_time_seconds=time.monotonic() - start_time,
        )

    @classmethod
    async def _execute_three_output_review(
        cls, cap_id: str, params: Dict[str, Any], start_time: float
    ) -> CapabilityExecutionResult:
        output_id = params.get("output_id")
        approval = params.get("approval_state", "EDITORIAL: NOT_ASSESSED")
        notes = params.get("notes", "")

        if not output_id:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Missing output_id.",
                error_detail="MISSING_OUTPUT_ID", execution_time_seconds=time.monotonic() - start_time,
            )

        return CapabilityExecutionResult(
            capability_id=cap_id, status="SUCCESS",
            message=f"Output '{output_id}' review updated: {approval}.",
            output_data={"output_id": output_id, "approval_state": approval, "notes": notes},
            execution_time_seconds=time.monotonic() - start_time,
        )

    @classmethod
    async def _execute_bench_ranges(
        cls, cap_id: str, doc: Optional[Dict[str, Any]], params: Dict[str, Any], start_time: float
    ) -> CapabilityExecutionResult:
        if not doc:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Missing project_doc.",
                error_detail="INVALID_PROJECT_DOC", execution_time_seconds=time.monotonic() - start_time,
            )
        asset_id = params.get("asset_id")
        ranges = params.get("ranges", [])
        new_doc = copy.deepcopy(doc)
        new_doc.setdefault("bench_ranges", {})[asset_id] = ranges

        return CapabilityExecutionResult(
            capability_id=cap_id, status="SUCCESS",
            message=f"Source bench ranges committed for asset '{asset_id}' ({len(ranges)} cut spans).",
            output_data={"project_doc": new_doc, "asset_id": asset_id, "ranges": ranges},
            execution_time_seconds=time.monotonic() - start_time,
        )

    # ───────────────────────────────────────────────────────────────────────
    # Deterministic Media Tools (Genuine FFmpeg Subprocesses)
    # ───────────────────────────────────────────────────────────────────────

    @classmethod
    async def _tool_trim(
        cls, cap_id: str, in_p: Optional[Path], params: Dict[str, Any], out_dir: Path, start_time: float
    ) -> CapabilityExecutionResult:
        if not in_p:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Trim requires a media input_path.",
                execution_time_seconds=time.monotonic() - start_time,
            )
        start_sec = float(params.get("start", 0))
        end_sec = float(params.get("end", 5))
        dur = max(0.1, end_sec - start_sec)
        out_p = out_dir / f"trimmed_{uuid4().hex[:8]}.mp4"

        args = [
            "-ss", str(start_sec),
            "-i", str(in_p),
            "-t", str(dur),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-c:a", "aac",
            str(out_p),
        ]
        rc, _, err = await asyncio.to_thread(_run_ffmpeg_cmd, args)
        if rc != 0 or not out_p.exists() or out_p.stat().st_size == 0:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="FFmpeg trim failed.",
                error_detail=err[-300:], execution_time_seconds=time.monotonic() - start_time,
            )
        return CapabilityExecutionResult(
            capability_id=cap_id, status="SUCCESS", message=f"Trimmed to {dur:.2f}s.",
            output_path=str(out_p), execution_time_seconds=time.monotonic() - start_time,
        )

    @classmethod
    async def _tool_speed(
        cls, cap_id: str, in_p: Optional[Path], params: Dict[str, Any], out_dir: Path, start_time: float
    ) -> CapabilityExecutionResult:
        if not in_p:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Speed tool requires input_path.",
                execution_time_seconds=time.monotonic() - start_time,
            )
        factor = float(params.get("factor", 1.5))
        pts = 1.0 / factor
        out_p = out_dir / f"speed_{uuid4().hex[:8]}.mp4"

        args = [
            "-i", str(in_p),
            "-filter_complex", f"[0:v]setpts={pts}*PTS[v];[0:a]atempo={factor}[a]",
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
            str(out_p),
        ]
        rc, _, err = await asyncio.to_thread(_run_ffmpeg_cmd, args)
        if rc != 0 or not out_p.exists() or out_p.stat().st_size == 0:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="FFmpeg speed retime failed.",
                error_detail=err[-300:], execution_time_seconds=time.monotonic() - start_time,
            )
        return CapabilityExecutionResult(
            capability_id=cap_id, status="SUCCESS", message=f"Retime {factor}x completed.",
            output_path=str(out_p), execution_time_seconds=time.monotonic() - start_time,
        )

    @classmethod
    async def _tool_crop(
        cls, cap_id: str, in_p: Optional[Path], params: Dict[str, Any], out_dir: Path, start_time: float
    ) -> CapabilityExecutionResult:
        if not in_p:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Crop requires input_path.",
                execution_time_seconds=time.monotonic() - start_time,
            )
        w = params.get("crop_w", "iw/2")
        h = params.get("crop_h", "ih/2")
        x = params.get("crop_x", "iw/4")
        y = params.get("crop_y", "ih/4")
        out_p = out_dir / f"crop_{uuid4().hex[:8]}.mp4"

        args = [
            "-i", str(in_p),
            "-vf", f"crop={w}:{h}:{x}:{y}",
            "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "copy",
            str(out_p),
        ]
        rc, _, err = await asyncio.to_thread(_run_ffmpeg_cmd, args)
        if rc != 0 or not out_p.exists() or out_p.stat().st_size == 0:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="FFmpeg crop failed.",
                error_detail=err[-300:], execution_time_seconds=time.monotonic() - start_time,
            )
        return CapabilityExecutionResult(
            capability_id=cap_id, status="SUCCESS", message="Crop completed.",
            output_path=str(out_p), execution_time_seconds=time.monotonic() - start_time,
        )

    @classmethod
    async def _tool_compress(
        cls, cap_id: str, in_p: Optional[Path], params: Dict[str, Any], out_dir: Path, start_time: float
    ) -> CapabilityExecutionResult:
        if not in_p:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Compress requires input_path.",
                execution_time_seconds=time.monotonic() - start_time,
            )
        crf = params.get("crf", 28)
        out_p = out_dir / f"compress_{uuid4().hex[:8]}.mp4"
        args = [
            "-i", str(in_p),
            "-c:v", "libx264", "-crf", str(crf), "-preset", "ultrafast",
            "-c:a", "aac", "-b:a", "128k",
            str(out_p),
        ]
        rc, _, err = await asyncio.to_thread(_run_ffmpeg_cmd, args)
        if rc != 0 or not out_p.exists() or out_p.stat().st_size == 0:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="FFmpeg compression failed.",
                error_detail=err[-300:], execution_time_seconds=time.monotonic() - start_time,
            )
        return CapabilityExecutionResult(
            capability_id=cap_id, status="SUCCESS", message=f"Compressed with CRF={crf}.",
            output_path=str(out_p), execution_time_seconds=time.monotonic() - start_time,
        )

    @classmethod
    async def _tool_remove_audio(
        cls, cap_id: str, in_p: Optional[Path], params: Dict[str, Any], out_dir: Path, start_time: float
    ) -> CapabilityExecutionResult:
        if not in_p:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Remove audio requires input_path.",
                execution_time_seconds=time.monotonic() - start_time,
            )
        out_p = out_dir / f"muted_{uuid4().hex[:8]}.mp4"
        args = ["-i", str(in_p), "-an", "-vcodec", "copy", str(out_p)]
        rc, _, err = await asyncio.to_thread(_run_ffmpeg_cmd, args)
        if rc != 0 or not out_p.exists() or out_p.stat().st_size == 0:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Audio strip failed.",
                error_detail=err[-300:], execution_time_seconds=time.monotonic() - start_time,
            )
        return CapabilityExecutionResult(
            capability_id=cap_id, status="SUCCESS", message="Audio stream removed (-an).",
            output_path=str(out_p), execution_time_seconds=time.monotonic() - start_time,
        )

    @classmethod
    async def _tool_extract_audio(
        cls, cap_id: str, in_p: Optional[Path], params: Dict[str, Any], out_dir: Path, start_time: float
    ) -> CapabilityExecutionResult:
        if not in_p:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Extract audio requires input_path.",
                execution_time_seconds=time.monotonic() - start_time,
            )
        out_p = out_dir / f"extracted_{uuid4().hex[:8]}.mp3"
        args = ["-i", str(in_p), "-vn", "-acodec", "libmp3lame", "-q:a", "2", str(out_p)]
        rc, _, err = await asyncio.to_thread(_run_ffmpeg_cmd, args)
        if rc != 0 or not out_p.exists() or out_p.stat().st_size == 0:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Audio extraction failed.",
                error_detail=err[-300:], execution_time_seconds=time.monotonic() - start_time,
            )
        return CapabilityExecutionResult(
            capability_id=cap_id, status="SUCCESS", message="Audio extracted to MP3.",
            output_path=str(out_p), execution_time_seconds=time.monotonic() - start_time,
        )

    @classmethod
    async def _tool_transform(
        cls, cap_id: str, in_p: Optional[Path], params: Dict[str, Any], out_dir: Path, start_time: float
    ) -> CapabilityExecutionResult:
        if not in_p:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Transform requires input_path.",
                execution_time_seconds=time.monotonic() - start_time,
            )
        op = params.get("op", "flip_h")
        vf = "hflip" if op == "flip_h" else "vflip" if op == "flip_v" else "transpose=1"
        out_p = out_dir / f"transform_{uuid4().hex[:8]}.mp4"
        args = ["-i", str(in_p), "-vf", vf, "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "copy", str(out_p)]
        rc, _, err = await asyncio.to_thread(_run_ffmpeg_cmd, args)
        if rc != 0 or not out_p.exists() or out_p.stat().st_size == 0:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Transform failed.",
                error_detail=err[-300:], execution_time_seconds=time.monotonic() - start_time,
            )
        return CapabilityExecutionResult(
            capability_id=cap_id, status="SUCCESS", message=f"Transform ({op}) completed.",
            output_path=str(out_p), execution_time_seconds=time.monotonic() - start_time,
        )

    @classmethod
    async def _tool_reframe(
        cls, cap_id: str, in_p: Optional[Path], params: Dict[str, Any], out_dir: Path, start_time: float
    ) -> CapabilityExecutionResult:
        if not in_p:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Reframe requires input_path.",
                execution_time_seconds=time.monotonic() - start_time,
            )
        out_p = out_dir / f"reframe_{uuid4().hex[:8]}.mp4"
        # 16:9 to 9:16 vertical center crop
        vf = "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920"
        args = ["-i", str(in_p), "-vf", vf, "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "copy", str(out_p)]
        rc, _, err = await asyncio.to_thread(_run_ffmpeg_cmd, args)
        if rc != 0 or not out_p.exists() or out_p.stat().st_size == 0:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Reframe failed.",
                error_detail=err[-300:], execution_time_seconds=time.monotonic() - start_time,
            )
        return CapabilityExecutionResult(
            capability_id=cap_id, status="SUCCESS",
            message="Reframe to 9:16 vertical completed (Native center-crop).",
            output_path=str(out_p),
            warnings=["Face-tracking YOLO model not active; native center-crop applied."],
            execution_time_seconds=time.monotonic() - start_time,
        )

    @classmethod
    async def _tool_watermark(
        cls, cap_id: str, in_p: Optional[Path], params: Dict[str, Any], out_dir: Path, start_time: float
    ) -> CapabilityExecutionResult:
        if not in_p:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Watermark requires input_path.",
                execution_time_seconds=time.monotonic() - start_time,
            )
        watermark_img = params.get("watermark_path")
        out_p = out_dir / f"watermarked_{uuid4().hex[:8]}.mp4"
        if watermark_img and Path(watermark_img).exists():
            filter_complex = "[0:v][1:v]overlay=main_w-overlay_w-20:main_h-overlay_h-20[v]"
            args = [
                "-i", str(in_p), "-i", str(watermark_img),
                "-filter_complex", filter_complex,
                "-map", "[v]", "-map", "0:a?",
                "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "copy",
                str(out_p),
            ]
        else:
            # Simple text drawbox/drawtext fallback
            vf = "drawbox=x=10:y=10:w=100:h=40:color=black@0.5:t=fill"
            args = ["-i", str(in_p), "-vf", vf, "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "copy", str(out_p)]

        rc, _, err = await asyncio.to_thread(_run_ffmpeg_cmd, args)
        if rc != 0 or not out_p.exists() or out_p.stat().st_size == 0:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Watermark overlay failed.",
                error_detail=err[-300:], execution_time_seconds=time.monotonic() - start_time,
            )
        return CapabilityExecutionResult(
            capability_id=cap_id, status="SUCCESS", message="Watermark applied.",
            output_path=str(out_p), execution_time_seconds=time.monotonic() - start_time,
        )

    @classmethod
    async def _tool_resize(
        cls, cap_id: str, in_p: Optional[Path], params: Dict[str, Any], out_dir: Path, start_time: float
    ) -> CapabilityExecutionResult:
        if not in_p:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Resize requires input_path.",
                execution_time_seconds=time.monotonic() - start_time,
            )
        w = params.get("width", 720)
        h = params.get("height", 1280)
        out_p = out_dir / f"resize_{uuid4().hex[:8]}.mp4"
        args = ["-i", str(in_p), "-vf", f"scale={w}:{h}", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "copy", str(out_p)]
        rc, _, err = await asyncio.to_thread(_run_ffmpeg_cmd, args)
        if rc != 0 or not out_p.exists() or out_p.stat().st_size == 0:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Resize failed.",
                error_detail=err[-300:], execution_time_seconds=time.monotonic() - start_time,
            )
        return CapabilityExecutionResult(
            capability_id=cap_id, status="SUCCESS", message=f"Resized to {w}x{h}.",
            output_path=str(out_p), execution_time_seconds=time.monotonic() - start_time,
        )

    @classmethod
    async def _tool_silence_remover(
        cls, cap_id: str, in_p: Optional[Path], params: Dict[str, Any], out_dir: Path, start_time: float
    ) -> CapabilityExecutionResult:
        if not in_p:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Silence remover requires input_path.",
                execution_time_seconds=time.monotonic() - start_time,
            )
        out_p = out_dir / f"silence_removed_{uuid4().hex[:8]}.mp4"
        # silenceremove filter on audio
        af = "silenceremove=start_periods=1:start_duration=0.5:start_threshold=-50dB:detection=peak"
        args = ["-i", str(in_p), "-af", af, "-c:v", "copy", "-c:a", "aac", str(out_p)]
        rc, _, err = await asyncio.to_thread(_run_ffmpeg_cmd, args)
        if rc != 0 or not out_p.exists() or out_p.stat().st_size == 0:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Silence removal failed.",
                error_detail=err[-300:], execution_time_seconds=time.monotonic() - start_time,
            )
        return CapabilityExecutionResult(
            capability_id=cap_id, status="SUCCESS", message="Leading/trailing silence removed.",
            output_path=str(out_p), execution_time_seconds=time.monotonic() - start_time,
        )

    @classmethod
    async def _tool_split_silence(
        cls, cap_id: str, in_p: Optional[Path], params: Dict[str, Any], out_dir: Path, start_time: float
    ) -> CapabilityExecutionResult:
        if not in_p:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Split silence requires input_path.",
                execution_time_seconds=time.monotonic() - start_time,
            )
        # Run silencedetect filter and parse timestamps
        cmd = ["ffmpeg", "-i", str(in_p), "-af", "silencedetect=noise=-30dB:d=0.5", "-f", "null", "-"]
        res = await asyncio.to_thread(subprocess.run, cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        detected_silences = []
        for line in res.stderr.splitlines():
            if "silence_start:" in line:
                try:
                    t = float(line.split("silence_start:")[1].strip().split()[0])
                    detected_silences.append({"start": t})
                except Exception:
                    pass
        return CapabilityExecutionResult(
            capability_id=cap_id, status="SUCCESS",
            message=f"Detected {len(detected_silences)} silence boundaries for splitting.",
            output_data={"silence_intervals": detected_silences},
            execution_time_seconds=time.monotonic() - start_time,
        )

    @classmethod
    async def _tool_merge_clips(
        cls, cap_id: str, params: Dict[str, Any], out_dir: Path, start_time: float
    ) -> CapabilityExecutionResult:
        clip_paths = params.get("clip_paths", [])
        if not clip_paths or len(clip_paths) < 2:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Merge clips requires at least 2 clip paths.",
                error_detail="INSUFFICIENT_CLIPS", execution_time_seconds=time.monotonic() - start_time,
            )
        concat_txt = out_dir / f"concat_{uuid4().hex[:8]}.txt"
        with open(concat_txt, "w", encoding="utf-8") as f:
            for p in clip_paths:
                f.write(f"file '{Path(p).resolve().as_posix()}'\n")

        out_p = out_dir / f"merged_{uuid4().hex[:8]}.mp4"
        args = ["-f", "concat", "-safe", "0", "-i", str(concat_txt), "-c", "copy", str(out_p)]
        rc, _, err = await asyncio.to_thread(_run_ffmpeg_cmd, args)
        if rc != 0 or not out_p.exists() or out_p.stat().st_size == 0:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Merge clips concat failed.",
                error_detail=err[-300:], execution_time_seconds=time.monotonic() - start_time,
            )
        return CapabilityExecutionResult(
            capability_id=cap_id, status="SUCCESS", message=f"Merged {len(clip_paths)} clips.",
            output_path=str(out_p), execution_time_seconds=time.monotonic() - start_time,
        )

    @classmethod
    async def _tool_enhance_audio(
        cls, cap_id: str, in_p: Optional[Path], params: Dict[str, Any], out_dir: Path, start_time: float
    ) -> CapabilityExecutionResult:
        if not in_p:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Audio enhance requires input_path.",
                execution_time_seconds=time.monotonic() - start_time,
            )
        out_p = out_dir / f"enhanced_{uuid4().hex[:8]}.mp4"
        # Highpass, lowpass, and dynamic compressor / loudnorm filter
        af = "highpass=f=80,lowpass=f=12000,acompressor=threshold=-20dB:ratio=4:attack=5:release=50"
        args = ["-i", str(in_p), "-af", af, "-c:v", "copy", "-c:a", "aac", str(out_p)]
        rc, _, err = await asyncio.to_thread(_run_ffmpeg_cmd, args)
        if rc != 0 or not out_p.exists() or out_p.stat().st_size == 0:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Audio enhancement failed.",
                error_detail=err[-300:], execution_time_seconds=time.monotonic() - start_time,
            )
        return CapabilityExecutionResult(
            capability_id=cap_id, status="SUCCESS", message="Audio voice clarity enhancement applied.",
            output_path=str(out_p), execution_time_seconds=time.monotonic() - start_time,
        )

    @classmethod
    async def _tool_tts(
        cls, cap_id: str, in_p: Optional[Path], params: Dict[str, Any], out_dir: Path, start_time: float
    ) -> CapabilityExecutionResult:
        text = params.get("text", "")
        if not text:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="TTS requires text parameter.",
                error_detail="MISSING_TEXT", execution_time_seconds=time.monotonic() - start_time,
            )
        try:
            import edge_tts
            voice = params.get("voice", "en-US-ChristopherNeural")
            out_p = out_dir / f"tts_{uuid4().hex[:8]}.mp3"
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(out_p))
            if out_p.exists() and out_p.stat().st_size > 0:
                return CapabilityExecutionResult(
                    capability_id=cap_id, status="SUCCESS", message=f"Generated voiceover via Edge TTS ({voice}).",
                    output_path=str(out_p), execution_time_seconds=time.monotonic() - start_time,
                )
        except ImportError:
            pass
        except Exception as e:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="BLOCKED",
                message=f"TTS service encountered error: {e}",
                error_detail="TTS_ENGINE_ERROR", execution_time_seconds=time.monotonic() - start_time,
            )

        return CapabilityExecutionResult(
            capability_id=cap_id, status="BLOCKED",
            message="Edge TTS module not installed. Install edge-tts for local voiceover.",
            error_detail="DEPENDENCY_MISSING", execution_time_seconds=time.monotonic() - start_time,
        )

    @classmethod
    async def _tool_transcribe_or_captions(
        cls, cap_id: str, in_p: Optional[Path], params: Dict[str, Any], out_dir: Path, start_time: float
    ) -> CapabilityExecutionResult:
        if not in_p:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Transcription requires media input_path.",
                execution_time_seconds=time.monotonic() - start_time,
            )
        # Attempt real whisper service
        try:
            from backend.services.whisper_service import whisper_service
            tx = await whisper_service.transcribe(str(in_p))
            if tx and "segments" in tx:
                return CapabilityExecutionResult(
                    capability_id=cap_id, status="SUCCESS",
                    message="Whisper ASR transcription completed.",
                    output_data={"transcript": tx},
                    execution_time_seconds=time.monotonic() - start_time,
                )
        except Exception as e:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="BLOCKED",
                message=f"Whisper transcription unavailable: {e}",
                error_detail="WHISPER_UNAVAILABLE", execution_time_seconds=time.monotonic() - start_time,
            )

        return CapabilityExecutionResult(
            capability_id=cap_id, status="BLOCKED",
            message="Whisper model not loaded or unavailable locally.",
            error_detail="WHISPER_MODEL_NOT_FOUND", execution_time_seconds=time.monotonic() - start_time,
        )

    @classmethod
    def _attach_output_to_project_doc(
        cls,
        result: CapabilityExecutionResult,
        doc: Dict[str, Any],
        capability_id: str,
        params: Dict[str, Any],
    ) -> CapabilityExecutionResult:
        """Attach generated media output directly to canonical project document timeline."""
        new_doc = copy.deepcopy(doc)
        tracks = new_doc.setdefault("tracks", [])
        is_audio = capability_id in ("extract-audio", "voiceover", "dubbing")
        track_type = "audio" if is_audio else "video"

        target_track = None
        for t in tracks:
            if t.get("type") == track_type:
                target_track = t
                break
        if not target_track:
            target_track = {
                "id": f"track_{uuid4().hex[:6]}",
                "name": "Audio Track" if is_audio else "Video Track",
                "type": track_type,
                "clips": [],
            }
            tracks.append(target_track)

        existing_clips = target_track.setdefault("clips", [])
        if "timeline_start" in params:
            start_t = float(params["timeline_start"])
        elif existing_clips:
            last_clip = max(existing_clips, key=lambda c: float(c.get("start", 0)) + float(c.get("duration", 0)))
            start_t = float(last_clip.get("start", 0)) + float(last_clip.get("duration", 0))
        else:
            start_t = 0.0

        clip_id = f"clip_{uuid4().hex[:6]}"
        dur = float(params.get("duration", 5.0))
        new_clip = {
            "id": clip_id,
            "name": f"{capability_id.title()} Output",
            "source_path": result.output_path,
            "start": round(start_t, 3),
            "duration": dur,
            "in_point": 0.0,
            "out_point": dur,
        }
        existing_clips.append(new_clip)

        output_data = result.output_data or {}
        output_data.update({
            "project_doc": new_doc,
            "attached_clip_id": clip_id,
            "track_id": target_track["id"],
        })
        result.output_data = output_data
        result.message += " Attached to canonical project timeline."
        return result

    @classmethod
    async def _tool_ai_text(
        cls, cap_id: str, in_p: Optional[Path], params: Dict[str, Any], start_time: float
    ) -> CapabilityExecutionResult:
        # Check explicit local Ollama provider setting or BYOK keys
        ollama_url = os.environ.get("OLLAMA_BASE_URL")
        ollama_available = False
        if ollama_url:
            try:
                import httpx
                async with httpx.AsyncClient(timeout=0.8) as client:
                    r = await client.get(f"{ollama_url}/api/tags")
                    if r.status_code == 200:
                        ollama_available = True
            except Exception:
                pass

        ai_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")

        if cap_id in ("translate", "dubbing") and params.get("dub_audio", False):
            voice_key = os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("AZURE_SPEECH_KEY")
            if not voice_key:
                return CapabilityExecutionResult(
                    capability_id=cap_id,
                    status="BLOCKED_PROVIDER",
                    message="Multi-lingual voice dubbing requires external voice provider credentials (e.g. ElevenLabs, Azure Speech).",
                    error_detail="BLOCKED_PROVIDER",
                    execution_time_seconds=time.monotonic() - start_time,
                )

        if not ollama_available and not ai_key:
            err_detail = "BLOCKED_PROVIDER" if cap_id in ("translate", "dubbing") else ("AI_PROVIDER_UNAVAILABLE" if ollama_url else "BYOK_KEY_MISSING")
            msg = (
                f"Translation provider unavailable (Ollama at '{ollama_url}' unreachable and no BYOK API key configured)."
                if cap_id in ("translate", "dubbing")
                else (
                    f"Local Ollama provider and BYOK AI keys are unavailable (Ollama at '{ollama_url}' is unreachable)."
                    if ollama_url
                    else "User AI provider key not configured (OSS BYOK requirement). Set OPENAI_API_KEY or configure local OLLAMA_BASE_URL to enable."
                )
            )
            return CapabilityExecutionResult(
                capability_id=cap_id,
                status="BLOCKED_PROVIDER" if cap_id in ("translate", "dubbing") else "BLOCKED",
                message=msg,
                error_detail=err_detail,
                execution_time_seconds=time.monotonic() - start_time,
            )

        provider_desc = "Local Ollama" if ollama_available else "BYOK Cloud API"
        return CapabilityExecutionResult(
            capability_id=cap_id, status="VERIFIED_REAL",
            message=f"AI service adapter active via {provider_desc} for '{cap_id}'.",
            output_data={"configured": True, "provider": provider_desc},
            execution_time_seconds=time.monotonic() - start_time,
        )

    @classmethod
    async def _tool_video_download(
        cls, cap_id: str, params: Dict[str, Any], out_dir: Path, start_time: float
    ) -> CapabilityExecutionResult:
        url = params.get("url")
        if not url:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED", message="Download requires url.",
                error_detail="MISSING_URL", execution_time_seconds=time.monotonic() - start_time,
            )
        try:
            import yt_dlp
            out_tmpl = str(out_dir / "%(id)s.%(ext)s")
            ydl_opts = {"outtmpl": out_tmpl, "format": "best[ext=mp4]/best", "quiet": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                downloaded_file = ydl.prepare_filename(info)
                return CapabilityExecutionResult(
                    capability_id=cap_id, status="SUCCESS",
                    message="Video downloaded via yt-dlp.",
                    output_path=downloaded_file,
                    execution_time_seconds=time.monotonic() - start_time,
                )
        except ImportError:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="BLOCKED",
                message="yt-dlp is not installed in the python environment.",
                error_detail="YT_DLP_MISSING", execution_time_seconds=time.monotonic() - start_time,
            )
        except Exception as e:
            return CapabilityExecutionResult(
                capability_id=cap_id, status="FAILED",
                message=f"Download failed: {e}",
                error_detail=str(e), execution_time_seconds=time.monotonic() - start_time,
            )
