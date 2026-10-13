# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Motion-graphics render — drives HyperFrames as an asyncio subprocess.

Materializes a composition from a bundled template + JSON variables, invokes
`node cli.js render … --variables …`, validates the MP4 with ffprobe, and
returns its Path. Everything here is local: headless Chrome draws the frames and
FFmpeg encodes them, so a motion piece costs nothing per render and needs no
network once the plugin is installed.

Two entry points:
  - render()          — a BUNDLED template (motion_assets/templates/<id>) with
                        variables injected. Used by the install smoke-render and
                        the Settings "test render" button.
  - render_project()  — an already-staged project directory (index.html +
                        assets/), for compositions authored elsewhere.
"""
import asyncio
import json
import logging
import platform
import re
import shutil
import sys
import uuid
from pathlib import Path
from typing import Optional

from backend.config import settings
from backend.core.exceptions import (
    HyperFramesNotInstalledError,
    MotionRenderError,
)
from backend.services.hyperframes_service import HyperFramesService
from backend.services.hyperframes_contract import (
    ASPECT_RESOLUTION, render_argv, resolve_gsap_js,
)
from backend.services.motion_proc import run_capped

logger = logging.getLogger(__name__)

# Render time scales with FRAMES, not wall-clock intent: measured on this
# machine a 6s pure-motion piece renders in ~11s at 1080p, a 6s piece with a
# VIDEO background ~70s at 4K, and a 30s pure-motion piece ~133s at 4K. A 30s
# video-backed piece therefore lands near six minutes of perfectly healthy
# work. The absolute cap is a backstop for the pathological case; the real
# hang detector is SILENCE (below), which is what actually distinguishes a
# stuck render from a long one.
_RENDER_TIMEOUT_SECONDS = 900
# No output at all for this long means the CLI is wedged, at any length.
_RENDER_SILENCE_SECONDS = 180


def _templates_src_dir() -> Path:
    """Locate the bundled motion templates that ship with the app.

    These live under <repo>/motion_assets/, deliberately SEPARATE from the
    runtime MOTION_DIR (DATA_DIR/motion) where the HyperFrames plugin installs:
    uninstall_plugin() does rmtree() on that whole directory, so keeping the
    tracked source out of it is what stops a reinstall or a version bump from
    deleting the templates.

    Frozen (PyInstaller): added to the BACKEND bundle root under
    motion_assets/templates — rendering runs in the backend process, so they
    have to be in ITS _MEIPASS, not the launcher's.
    """
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return base / "motion_assets" / "templates"
    # backend/services/motion_render_service.py → repo root is parents[2]
    return Path(__file__).resolve().parents[2] / "motion_assets" / "templates"


_DIMS_RE = re.compile(
    r'<[^>]*data-composition-id=[^>]*>', re.I)


def _composition_aspect(project_dir: Path, requested: str) -> str:
    """The aspect the COMPOSITION actually is — not the one the caller believes.

    Callers pass the aspect they BELIEVE the composition has, which is a UI
    setting that may have drifted from the artifact. HyperFrames validates the
    pairing and hard-fails: "outputResolution portrait-4k (2160x3840) does not
    match the aspect ratio of the composition (1080x1080)". Compose a square
    card, export while the panel still says 9:16, and a perfectly good
    composition refuses to render.

    The composition's own root element carries data-width/data-height, so read
    the truth from the artifact and correct the request. Unparseable → the
    caller's value, unchanged.
    """
    try:
        html = (project_dir / "index.html").read_text(errors="replace")
    except OSError:
        return requested
    for tag in _DIMS_RE.findall(html):
        w = re.search(r'data-width="(\d+)"', tag)
        h = re.search(r'data-height="(\d+)"', tag)
        if not (w and h):
            continue
        ww, hh = int(w.group(1)), int(h.group(1))
        if ww <= 0 or hh <= 0:
            continue
        ratio = ww / hh
        actual = ("1:1" if abs(ratio - 1) < 0.02
                  else "9:16" if ratio < 1
                  else "16:9")
        if actual != requested:
            logger.warning(
                "Motion render: composition is %dx%d (%s) but %s was requested "
                "— rendering as %s so the export can't fail on a mismatch",
                ww, hh, actual, requested, actual)
        return actual
    return requested


class MotionRenderService:
    """Stateless render façade over the HyperFrames CLI."""

    @staticmethod
    def _stage_gsap(project_dir: Path) -> None:
        """Copy the installed GSAP runtime into <project>/assets/gsap.min.js.

        Compositions link `assets/gsap.min.js` relatively, so the animation
        runtime has to sit inside whatever directory the CLI is pointed at.
        GSAP is NOT vendored into this repository — it ships under GreenSock's
        own licence, not a free-software one — so it is installed alongside
        HyperFrames on the user's machine and staged per render instead. See
        hyperframes_contract's module docstring.

        A composition that never references it still gets the file; that costs
        ~70 KB in a temporary directory and removes a whole class of "worked in
        the studio, rendered blank" failure.
        """
        gsap = resolve_gsap_js(settings.MOTION_DIR / "hyperframes")
        if not gsap.exists():
            raise MotionRenderError(
                "The GSAP animation runtime is missing from the Motion Graphics "
                "install. Reinstall it from Settings → Motion Graphics."
            )
        assets = project_dir / "assets"
        assets.mkdir(parents=True, exist_ok=True)
        shutil.copy2(gsap, assets / "gsap.min.js")

    @classmethod
    async def render(
        cls,
        template_id: str,
        variables: dict,
        aspect: str = "9:16",
        fps: int = 30,
        quality: str = "standard",
        out_path: Optional[Path] = None,
        skip_gate: bool = False,
        supersample: Optional[bool] = None,
    ) -> Path:
        """Render a bundled template with injected variables → MP4 Path.

        Raises HyperFramesNotInstalledError (the install gate) when the plugin
        is absent, MotionRenderError on any render failure. `skip_gate` is used
        by the install smoke-render before the marker is written.
        """
        if not skip_gate and not HyperFramesService.is_installed():
            raise HyperFramesNotInstalledError(
                "Motion Graphics (HyperFrames) isn't installed. "
                "Install it from Settings → Motion Graphics."
            )

        src = _templates_src_dir() / template_id
        if not (src / "index.html").exists():
            raise MotionRenderError(f"Unknown motion template: {template_id!r}")

        # Stage a writable copy of the bundled template (the app bundle is read-only).
        rid = uuid.uuid4().hex[:12]
        work = settings.MOTION_DIR / "tmp" / rid
        work.parent.mkdir(parents=True, exist_ok=True)
        try:
            await asyncio.to_thread(shutil.copytree, src, work)
            await asyncio.to_thread(cls._stage_gsap, work)
        except MotionRenderError:
            raise
        except Exception as e:
            raise MotionRenderError(f"Could not stage template: {e}") from e

        return await cls._finish_render(work, dict(variables), aspect, fps, quality,
                                        out_path, supersample=supersample)

    @classmethod
    async def render_project(cls, project_dir: Path, aspect: str = "9:16",
                             out_path: Optional[Path] = None, fps: int = 30,
                             quality: str = "standard", skip_gate: bool = False,
                             keep: bool = False,
                             supersample: Optional[bool] = None) -> Path:
        """Render an already-staged project dir (index.html + assets/) → MP4.

        For compositions authored outside the bundled-template path, with their
        own media already staged in assets/. `out_path` must be OUTSIDE
        project_dir. With `keep=True` the project dir is
        preserved after the render (so it can be re-opened/edited in the studio);
        otherwise it's removed.
        """
        if not skip_gate and not HyperFramesService.is_installed():
            raise HyperFramesNotInstalledError(
                "Motion Graphics (HyperFrames) isn't installed."
            )
        if not (project_dir / "index.html").exists():
            raise MotionRenderError("Project has no index.html to render")
        await asyncio.to_thread(cls._stage_gsap, project_dir)
        rendered_mp4 = await cls._finish_render(project_dir, {}, aspect, fps, quality, out_path,
                                                keep=keep, supersample=supersample)
        return await cls._mux_project_audio(rendered_mp4, project_dir)

    @classmethod
    async def _finish_render(cls, work: Path, variables: dict, aspect: str,
                             fps: int, quality: str, out_path: Optional[Path],
                             keep: bool = False,
                             supersample: Optional[bool] = None) -> Path:
        """Invoke the CLI on the staged composition, validate, clean up (unless keep)."""
        # The artifact is the truth: HyperFrames refuses a resolution whose
        # aspect doesn't match the composition, so a stale caller-side aspect
        # would fail the render outright rather than produce a wrong file.
        aspect = _composition_aspect(work, aspect)
        resolution = ASPECT_RESOLUTION.get(aspect)
        if not resolution:
            raise MotionRenderError(
                f"Unsupported aspect {aspect!r}. Supported: {', '.join(ASPECT_RESOLUTION)}"
            )
        # SUPERSAMPLE. HyperFrames keeps the
        # composition's layout and captures it at a higher device-pixel ratio,
        # so TEXT AND VECTORS re-rasterize at 4K — which is what a motion
        # graphic is made of — and the platform's downscale then lands on
        # genuinely sharper edges. Raster media gains nothing, hence the
        # opt-out below. Costs render time and memory only: the render is
        # local, so this is a time trade and never a money one.
        want_ss = settings.MOTION_SUPERSAMPLE if supersample is None else supersample
        if want_ss and f"{aspect}-4k" in ASPECT_RESOLUTION:
            resolution = ASPECT_RESOLUTION[f"{aspect}-4k"]
            logger.info("Motion render: supersampling %s → %s", aspect, resolution)

        # Output is a SIBLING of the work dir so the staging copy can be removed
        # in `finally` without touching the MP4.
        final = out_path or (work.parent / f"{work.name}.mp4")
        final.parent.mkdir(parents=True, exist_ok=True)

        cmd = render_argv(
            HyperFramesService.node_bin(), HyperFramesService.cli_js(),
            work, final, resolution, fps, quality, json.dumps(variables),
        )
        import time as _t
        _t0 = _t.monotonic()
        try:
            await cls._run(cmd)
            elapsed = _t.monotonic() - _t0
            # Supersampling is a TIME trade, so measure it rather than assume:
            # if a short piece starts costing real minutes, say so —
            # MOTION_SUPERSAMPLE=false turns it off without a rebuild.
            if want_ss and elapsed > 120:
                logger.warning(
                    "Motion render took %.0fs at %s. If renders feel slow, set "
                    "MOTION_SUPERSAMPLE=false (1080p, faster, softer text).",
                    elapsed, resolution)
            else:
                logger.info("Motion render: %.1fs at %s", elapsed, resolution)
            if not final.exists() or final.stat().st_size < 1024:
                raise MotionRenderError("Render produced no usable MP4")
            await cls._ffprobe_validate(final)
            return final
        finally:
            if not keep:
                await asyncio.to_thread(shutil.rmtree, work, ignore_errors=True)

    @classmethod
    async def _mux_project_audio(cls, video_path: Path, project_dir: Path) -> Path:
        """Mux timeline audio streams (from gameplay/video clips or audio tracks) onto rendered MP4."""
        doc_path = project_dir / "project_doc.json"
        if not doc_path.exists():
            return video_path

        try:
            doc = json.loads(doc_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("Could not read project_doc.json for audio muxing: %s", e)
            return video_path

        tracks = doc.get("timeline", {}).get("tracks", [])
        assets_dir = project_dir / "assets"
        import subprocess

        # Check which clips have valid audio
        audio_inputs = []
        for t in tracks:
            if t.get("muted"):
                continue
            t_type = t.get("type", "video")
            if t_type not in ("video", "audio"):
                continue
            t_vol = float(t.get("volume", 1.0) if t.get("volume") is not None else 1.0)
            for c in t.get("clips", []):
                if c.get("muted") or not c.get("visible", True):
                    continue
                c_vol = float(c.get("volume", 1.0) if c.get("volume") is not None else 1.0)
                eff_vol = max(0.0, min(2.0, t_vol * c_vol))
                if eff_vol <= 0.0:
                    continue

                asset_file = c.get("file") or c.get("asset_file") or c.get("filename") or ""
                src_path = None
                if asset_file and (assets_dir / asset_file).is_file():
                    src_path = assets_dir / asset_file
                else:
                    aid = c.get("asset_id") or c.get("video_id")
                    if aid:
                        from backend.services.asset_resolver import resolve_asset_record_and_path
                        try:
                            _, resolved_p, _ = await resolve_asset_record_and_path(aid, must_exist=False)
                            if resolved_p and resolved_p.is_file():
                                src_path = resolved_p
                        except Exception:
                            pass

                if not src_path or not src_path.is_file():
                    continue

                has_audio = False
                try:
                    probe_cmd = [
                        "ffprobe", "-v", "error",
                        "-select_streams", "a:0",
                        "-show_entries", "stream=codec_name",
                        "-of", "csv=p=0", str(src_path)
                    ]
                    probe_res = subprocess.check_output(probe_cmd, stderr=subprocess.DEVNULL)
                    if probe_res.decode("utf-8").strip():
                        has_audio = True
                except Exception:
                    pass

                if not has_audio:
                    continue

                c_start = float(c.get("start_seconds") if c.get("start_seconds") is not None else (c.get("start_time") if c.get("start_time") is not None else 0.0))
                c_dur = float(c.get("duration_seconds") if c.get("duration_seconds") is not None else (c.get("duration") if c.get("duration") is not None else 5.0))
                trim_start = float(c.get("trim_start") if c.get("trim_start") is not None else (c.get("trim_in") if c.get("trim_in") is not None else (c.get("source_in") if c.get("source_in") is not None else 0.0)))

                audio_inputs.append({
                    "path": str(src_path),
                    "start": max(0.0, c_start),
                    "duration": max(0.1, c_dur),
                    "source_in": max(0.0, trim_start),
                    "volume": eff_vol,
                })

        if not audio_inputs:
            logger.info("Motion render: no timeline clips have audio streams — video-only output.")
            return video_path

        logger.info("Motion render: muxing %d timeline audio stream(s) into %s", len(audio_inputs), video_path.name)
        tmp_muxed = video_path.with_name(f"{video_path.stem}_muxed_{uuid.uuid4().hex[:6]}.mp4")

        cmd = ["ffmpeg", "-y", "-i", str(video_path)]
        for item in audio_inputs:
            cmd.extend(["-ss", f"{item['source_in']:.3f}", "-t", f"{item['duration']:.3f}", "-i", item["path"]])

        filter_parts = []
        mix_inputs = []
        for idx, item in enumerate(audio_inputs, start=1):
            delay_ms = int(round(item["start"] * 1000))
            f_chain = f"[{idx}:a]volume={item['volume']:.2f}"
            if delay_ms > 0:
                f_chain += f",adelay={delay_ms}|{delay_ms}"
            f_label = f"[a{idx}]"
            f_chain += f_label
            filter_parts.append(f_chain)
            mix_inputs.append(f_label)

        if len(mix_inputs) > 1:
            all_labels = "".join(mix_inputs)
            filter_parts.append(f"{all_labels}amix=inputs={len(mix_inputs)}:duration=longest:dropout_transition=0,aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[aout]")
        else:
            filter_parts.append(f"{mix_inputs[0]}aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[aout]")

        filter_str = ";".join(filter_parts)
        cmd.extend([
            "-filter_complex", filter_str,
            "-map", "0:v:0",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(tmp_muxed)
        ])

        try:
            res = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, timeout=120)
            if res.returncode == 0 and tmp_muxed.exists() and tmp_muxed.stat().st_size > 1024:
                shutil.move(str(tmp_muxed), str(video_path))
                logger.info("Motion render: timeline audio successfully muxed into %s", video_path.name)
            else:
                err_msg = res.stderr.decode("utf-8", errors="replace")[-300:] if res.stderr else "unknown error"
                logger.warning("Motion render: audio muxing failed (%d): %s; keeping video as-is", res.returncode, err_msg)
                if tmp_muxed.exists():
                    tmp_muxed.unlink(missing_ok=True)
        except Exception as ex:
            logger.warning("Motion render: audio muxing exception: %s; keeping video as-is", ex)
            if tmp_muxed.exists():
                tmp_muxed.unlink(missing_ok=True)

        return video_path

    @classmethod
    async def _run(cls, cmd: list[str]) -> None:
        rc, tail, timed_out = await run_capped(
            cmd,
            cwd=str(settings.MOTION_DIR),
            env=HyperFramesService.render_env(),
            overall_timeout=_RENDER_TIMEOUT_SECONDS,
            line_timeout=15.0,
            silence_timeout=_RENDER_SILENCE_SECONDS,
            tail_lines=12,
        )
        if timed_out:
            raise MotionRenderError(
                "Render stalled — no progress for "
                f"{_RENDER_SILENCE_SECONDS}s (or exceeded "
                f"{_RENDER_TIMEOUT_SECONDS}s overall)")
        if rc != 0:
            detail = "; ".join(tail[-4:]) or f"exit {rc}"
            raise MotionRenderError(f"HyperFrames render failed (exit {rc}): {detail}")

    @staticmethod
    async def _ffprobe_validate(path: Path) -> None:
        """Confirm the output is a real video rather than a plausible-looking
        file: a render that exits 0 having produced an unplayable MP4 must fail
        here, not on the user's timeline."""
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            return  # can't validate; don't block
        if platform.system() == "Windows":
            import subprocess
            try:
                out = await asyncio.to_thread(
                    subprocess.check_output,
                    [
                        ffprobe, "-v", "error",
                        "-select_streams", "v:0",
                        "-show_entries", "stream=codec_name,width,height",
                        "-of", "csv=p=0", str(path)
                    ],
                    stderr=subprocess.STDOUT
                )
                text = out.decode("utf-8", errors="replace").strip()
            except subprocess.CalledProcessError as e:
                text = e.output.decode("utf-8", errors="replace").strip()
                proc_returncode = e.returncode
            else:
                proc_returncode = 0
        else:
            proc = await asyncio.create_subprocess_exec(
                ffprobe, "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_name,width,height",
                "-of", "csv=p=0", str(path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            out, _ = await proc.communicate()
            text = out.decode("utf-8", errors="replace").strip()
            proc_returncode = proc.returncode

        if proc_returncode != 0 or "h264" not in text.lower():
            raise MotionRenderError(f"Output failed ffprobe validation: {text[:120]}")
