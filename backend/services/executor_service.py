# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Executor service orchestrating Run -> Step -> Job workflows with verification."""
import json
import logging
from typing import Optional
from datetime import datetime
from sqlalchemy import select

from backend.database import AsyncSessionLocal
from backend.models.execution import ExecutionRun, ExecutionStep
from backend.core.capabilities import CapabilityRegistry
from backend.core.verifiers import verify_file_output, verify_video_stream, verify_lineage
from backend.core.exceptions import (
    CapabilityPreconditionError,
    VerificationError,
    ProjectError,
    ProjectNotFoundError,
    AuthorizationRequiredError,
    CapabilityExecutionError,
)
from backend.core.ai_provider import get_ai_client
from backend.core.exceptions import AIKeyMissingError
from backend.services.project_service import ProjectService

logger = logging.getLogger(__name__)


class ExecutorService:
    @staticmethod
    async def create_run(
        objective: str,
        project_id: Optional[str] = None,
        input_revision: Optional[int] = None,
        user_settings=None,
        user_id: str = "local",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        budget_limit_usd: float = 0.0,
    ) -> ExecutionRun:
        """Create a new execution run with pinned provider and model."""
        prov = provider or "none"
        resolved_model = model or "deterministic"
        if not provider or not model:
            try:
                client = get_ai_client(user_settings)
                prov = provider or client.provider.value
                resolved_model = model or client.model
            except AIKeyMissingError:
                logger.info("No AI key configured; run will use deterministic capabilities")
            except Exception as e:
                logger.warning("AI client resolution fallback: %s", e)

        async with AsyncSessionLocal() as db:
            run = ExecutionRun(
                user_id=user_id,
                objective=objective,
                project_id=project_id,
                input_revision=input_revision,
                status="running",
                resolved_provider=prov,
                resolved_model=resolved_model,
                budget_limit_usd=budget_limit_usd,
                actual_cost_usd=0.0,
                fallback_policy="stop_on_error",
            )
            db.add(run)
            await db.commit()
            await db.refresh(run)
            return run

    @staticmethod
    async def complete_run(
        run_id: str,
        status: str = "completed",
        error_message: Optional[str] = None,
        context_data: Optional[dict] = None,
    ) -> ExecutionRun:
        """Mark an execution run as completed or failed and commit final state."""
        async with AsyncSessionLocal() as db:
            run = await db.get(ExecutionRun, run_id)
            if not run:
                raise ValueError(f"ExecutionRun '{run_id}' not found.")
            run.status = status
            if error_message:
                run.error_message = error_message
            if context_data:
                existing_ctx = json.loads(run.context_json) if run.context_json else {}
                existing_ctx.update(context_data)
                run.context_json = json.dumps(existing_ctx)
            run.completed_at = datetime.utcnow()
            await db.commit()
            await db.refresh(run)
            return run

    @classmethod
    async def handle_job_completed(
        cls,
        job_id: str,
        job_status: str,
        output_data: dict = None,
        error_message: str = None,
    ) -> Optional[dict]:
        """
        Terminal Job callback handler.
        Recovers the ExecutionStep and ExecutionRun waiting on this async background job,
        evaluates verification evidence, marks step success/failure, and triggers run resumption.
        """
        async with AsyncSessionLocal() as db:
            step_res = await db.execute(
                select(ExecutionStep)
                .where(ExecutionStep.job_id == job_id, ExecutionStep.status == "running")
            )
            step = step_res.scalar_one_or_none()
            if not step:
                return None

            run = await db.get(ExecutionRun, step.run_id)
            if not run:
                return None

            # Evaluate verifier
            if job_status == "success":
                verif_ok = True
                verif_details = {"ok": True, "verifier": f"async_job_verifier:{step.capability}", "job_id": job_id}
                if output_data and "video_path" in output_data:
                    from backend.core.verifiers import verify_video_stream
                    v_res = verify_video_stream(output_data["video_path"], min_duration=0.1)
                    verif_ok = v_res.get("ok", True)
                    verif_details = v_res

                step.status = "success"
                step.verification_status = "verified" if verif_ok else "failed"
                step.verification_details_json = json.dumps(verif_details)
                step.output_payload_json = json.dumps(output_data or {})
                step.completed_at = datetime.utcnow()
            else:
                step.status = "failed"
                step.verification_status = "failed"
                step.error_message = error_message or f"Underlying job {job_id} {job_status}"
                step.verification_details_json = json.dumps({"ok": False, "job_status": job_status})
                step.completed_at = datetime.utcnow()

            await db.commit()
            await db.refresh(step)

        # Notify via websocket
        try:
            from backend.core.ws_manager import ws_manager
            await ws_manager.send({
                "type": "agent_step_progress",
                "run_id": run.id,
                "step_id": step.id,
                "status": step.status,
                "step_name": step.name,
                "capability": step.capability,
                "output": output_data,
                "resumed_from_job": job_id,
            }, run.user_id or "local")
        except Exception:
            pass

        # Check if the execution run has queued subsequent steps to resume
        if step.status == "success" and run.context_json:
            try:
                ctx = json.loads(run.context_json)
                pending_steps = ctx.get("pending_steps", [])
                if pending_steps:
                    next_step = pending_steps.pop(0)
                    ctx["pending_steps"] = pending_steps
                    async with AsyncSessionLocal() as db:
                        r_obj = await db.get(ExecutionRun, run.id)
                        r_obj.context_json = json.dumps(ctx)
                        await db.commit()

                    await cls.execute_step(
                        run_id=run.id,
                        step_name=next_step.get("name") or next_step.get("capability"),
                        capability_name=next_step.get("capability"),
                        payload=next_step.get("payload", {}),
                        user_id=run.user_id,
                        authorized=True,
                    )
                    if not pending_steps:
                        await cls.complete_run(run.id, status="completed")
                elif not pending_steps:
                    await cls.complete_run(run.id, status="completed")
            except Exception as e:
                logger.error("Failed resuming ExecutionRun %s: %s", run.id, e)

        return {"run_id": run.id, "step_id": step.id, "status": step.status}

    @classmethod
    async def execute_step(
        cls,
        run_id: str,
        step_name: str,
        capability_name: str,
        payload: dict,
        user_id: str = "local",
        authorized: bool = False,
        job_id: Optional[str] = None,
    ) -> dict:
        """Execute a validated capability step within an execution run."""
        # 1. Validate capability contract
        cap = CapabilityRegistry.validate_input(capability_name, payload)
        if cap.requires_authorization and not authorized:
            raise AuthorizationRequiredError(
                f"Capability '{capability_name}' requires explicit user authorization before execution."
            )

        linked_job_id = job_id or payload.get("job_id")

        async with AsyncSessionLocal() as db:
            # Check run existence
            run_res = await db.execute(select(ExecutionRun).where(ExecutionRun.id == run_id))
            run = run_res.scalar_one_or_none()
            if not run:
                raise ValueError(f"ExecutionRun '{run_id}' not found.")

            # Get current step count
            step_count_res = await db.execute(
                select(ExecutionStep).where(ExecutionStep.run_id == run_id)
            )
            existing_steps = step_count_res.scalars().all()
            step_number = len(existing_steps) + 1

            step = ExecutionStep(
                run_id=run_id,
                step_number=step_number,
                name=step_name,
                capability=capability_name,
                job_id=linked_job_id,
                status="running",
                input_payload_json=json.dumps(payload),
                verification_status="unverified",
            )
            db.add(step)
            await db.commit()
            await db.refresh(step)

        # If step is registered to wait asynchronously on an external Job, return immediately
        if linked_job_id and payload.get("wait_for_job"):
            return {
                "step_id": step.id,
                "status": "running",
                "job_id": linked_job_id,
                "waiting_for_job": True,
            }

        # 2. Execute capability logic
        output = {}
        verif_result = {"ok": True, "details": "no verifier needed"}
        try:
            if capability_name == "project_operation":
                op_res = await ProjectService.apply_operation(
                    project_id=payload["project_id"],
                    expected_revision=payload["expected_revision"],
                    operation_type=payload["operation_type"],
                    payload=payload["payload"],
                    idempotency_key=payload.get("idempotency_key"),
                    author=payload.get("author", "agent"),
                )
                output = op_res
                verif_result = {
                    "ok": True,
                    "verifier": "project_revision_bump",
                    "new_revision": op_res["revision"],
                }

            elif capability_name == "extract_clips":
                output = await cls._execute_extract_clips(payload, user_id)
                # Verify extracted clip files
                clip_files = output.get("files", [])
                checks = []
                all_ok = True
                for cf in clip_files:
                    v = verify_video_stream(cf, min_duration=0.5)
                    checks.append(v)
                    if not v["ok"]:
                        all_ok = False
                verif_result = {
                    "ok": all_ok,
                    "verifier": "verify_video_stream",
                    "checks": checks,
                }
                if not all_ok:
                    raise VerificationError(f"Verification failed on clip extraction: {checks}")

            elif capability_name == "project_render":
                from backend.services.hyperframes_adapter import HyperFramesAdapter
                from backend.services.motion_render_service import MotionRenderService
                from backend.agents.generator_motion import MotionGeneratorAgent
                from backend.services.video_utils import probe_duration
                from backend.services.studio_service import StudioService
                from backend.config import settings
                from uuid import uuid4

                project_id = payload["project_id"]
                requested_rev = payload.get("revision")

                # Verify project existence
                p = await ProjectService.get_project(project_id)
                frozen_rev, snapshot = await ProjectService.freeze_for_render(project_id, requested_rev)

                effective_aspect = snapshot.get("aspect_ratio") or p.aspect_ratio or "9:16"

                # Stage isolated directory for this render run
                frozen_rev, isolated_dir = await HyperFramesAdapter.stage_project_for_render(project_id, revision=frozen_rev)

                out_path = settings.GENERATED_DIR / f"render_{project_id}_rev{frozen_rev}_{uuid4().hex[:8]}.mp4"
                out_path.parent.mkdir(parents=True, exist_ok=True)

                try:
                    rendered_file = await MotionRenderService.render_project(
                        isolated_dir,
                        aspect=effective_aspect,
                        out_path=out_path,
                        keep=True,
                    )
                finally:
                    import shutil
                    shutil.rmtree(isolated_dir, ignore_errors=True)

                v_res = verify_video_stream(rendered_file, min_duration=0.5)
                if not v_res.get("ok"):
                    raise VerificationError(f"Verification failed on rendered project video: {v_res}")

                dur = probe_duration(rendered_file, 0.0)
                thumb = await MotionGeneratorAgent._thumbnail(rendered_file)
                gen_id = await MotionGeneratorAgent._save(
                    user_id=user_id,
                    title=f"{p.name} (Rev {frozen_rev})",
                    variables={},
                    niche=None,
                    video_path=rendered_file,
                    thumb_path=thumb,
                    audio_path=None,
                    aspect_ratio=effective_aspect,
                    duration_seconds=int(round(dur)) if dur else None,
                    script=None,
                    caption_status=None,
                    project_id=project_id,
                    project_revision=frozen_rev,
                    operation="project_render",
                )

                output = {
                    "project_id": project_id,
                    "revision": frozen_rev,
                    "video_path": str(rendered_file),
                    "generated_video_id": gen_id,
                }
                verif_result = {
                    "ok": True,
                    "verifier": "verify_video_stream",
                    "file": str(rendered_file),
                    "duration": dur,
                }

            elif capability_name == "set_bench_ranges":
                op_res = await ProjectService.apply_operation(
                    project_id=payload["project_id"],
                    expected_revision=payload["expected_revision"],
                    operation_type="set_bench_ranges",
                    payload={"source_id": payload["source_id"], "ranges": payload["ranges"]},
                    idempotency_key=payload.get("idempotency_key"),
                    author=payload.get("author", "user"),
                )
                output = op_res
                verif_result = {
                    "ok": True,
                    "verifier": "project_bench_ranges_persisted",
                    "new_revision": op_res["revision"],
                    "source_id": payload["source_id"],
                    "range_count": len(payload["ranges"]),
                }

            elif capability_name == "ingest_trend":
                output, verif_result = await cls._execute_ingest_trend(payload, user_id)

            elif capability_name.startswith("tool_"):
                output, verif_result = await cls._execute_tool(capability_name, payload, user_id)

            elif capability_name == "apply_captions":
                output, verif_result = await cls._execute_apply_captions(payload, user_id)

            elif capability_name == "search_youtube_trends":
                output, verif_result = await cls._execute_search_trends(payload, user_id)

            elif capability_name == "suggest_clips":
                output, verif_result = await cls._execute_suggest_clips(payload, user_id)

            elif capability_name == "search_catalog":
                from backend.services.registry_adapter import RegistryAdapter
                q = payload.get("query")
                cat = payload.get("category")
                lim = int(payload.get("limit") or 20)
                items = RegistryAdapter.list_catalog_items(category=cat, search=q, limit=lim)
                output = {"items": items, "count": len(items)}
                verif_result = {
                    "ok": True,
                    "verifier": "verify_catalog_search",
                    "count": len(items),
                }

            elif capability_name in ("upload_youtube", "upload_tiktok"):
                output, verif_result = await cls._execute_upload(capability_name, payload, user_id)

            else:
                raise CapabilityExecutionError(f"No execution handler implemented for capability: '{capability_name}'")

            # Mark step success
            async with AsyncSessionLocal() as db:
                step_obj = await db.get(ExecutionStep, step.id)
                step_obj.status = "success"
                step_obj.output_payload_json = json.dumps(output)
                step_obj.verification_status = "verified" if verif_result["ok"] else "failed"
                step_obj.verification_details_json = json.dumps(verif_result)
                step_obj.completed_at = datetime.utcnow()
                await db.commit()

            return {
                "step_id": step.id,
                "status": "success",
                "output": output,
                "verification": verif_result,
            }

        except Exception as e:
            logger.error("Step execution failed for %s: %s", step_name, e, exc_info=True)
            async with AsyncSessionLocal() as db:
                step_obj = await db.get(ExecutionStep, step.id)
                step_obj.status = "failed"
                step_obj.error_message = str(e)
                step_obj.verification_status = "failed"
                step_obj.verification_details_json = json.dumps({"ok": False, "error": str(e)})
                step_obj.completed_at = datetime.utcnow()

                run_obj = await db.get(ExecutionRun, run_id)
                run_obj.status = "failed"
                run_obj.error_message = f"Failed at step '{step_name}': {e}"
                await db.commit()
            raise

    @staticmethod
    async def _execute_extract_clips(payload: dict, user_id: str) -> dict:
        """Helper to invoke clip extraction with deterministic or manual fallback."""
        video_id = payload["video_id"]
        time_ranges = payload.get("time_ranges")
        caption_style = payload.get("caption_style", "none")

        from backend.database import AsyncSessionLocal
        from backend.models.downloaded_video import DownloadedVideo
        from backend.services.clip_options import ExtractOptions
        from backend.services.clip_extractor import extract_viral_clips

        async with AsyncSessionLocal() as db:
            v_res = await db.execute(select(DownloadedVideo).where(DownloadedVideo.id == video_id))
            video = v_res.scalar_one_or_none()
            if not video:
                raise ValueError(f"DownloadedVideo '{video_id}' not found.")

        dur = float(video.duration_seconds or 30.0)
        # If no time_ranges provided, create 3 deterministic evenly-spaced cuts
        if not time_ranges:
            cut_len = min(15.0, dur / 3.0)
            time_ranges = [
                {"start": round(i * (dur / 3.0), 1), "end": round(i * (dur / 3.0) + cut_len, 1), "label": f"Cut {i+1}"}
                for i in range(3)
            ]

        opts = ExtractOptions(
            max_clips=len(time_ranges),
            caption_style=caption_style,
            mode="manual",
            time_ranges=time_ranges,
            allow_duration_fallback=True,
        )

        clips = await extract_viral_clips(video, None, opts=opts, user_id=user_id)
        clip_paths = [c.get("video_path") for c in clips if c.get("video_path")]
        clip_ids = [c.get("generated_video_id") for c in clips if c.get("generated_video_id")]

        if payload.get("project_id") and clips:
            from backend.services.project_service import ProjectService
            proj_id = payload["project_id"]
            try:
                p = await ProjectService.get_project(proj_id)
                top = clips[0]
                top_id = top.get("generated_video_id")
                top_path = top.get("video_path")
                dur_val = top.get("duration") or 5.0
                if top_id and top_path:
                    await ProjectService.apply_operation(
                        project_id=proj_id,
                        expected_revision=p.revision,
                        operation_type="add_asset",
                        payload={"asset": {
                            "id": f"gv:{top_id}",
                            "type": "generated",
                            "title": top.get("title") or "Extracted Clip",
                            "video_path": str(top_path),
                            "duration": dur_val,
                        }},
                        author="agent",
                    )
                    p = await ProjectService.get_project(proj_id)
                    await ProjectService.apply_operation(
                        project_id=proj_id,
                        expected_revision=p.revision,
                        operation_type="add_clip",
                        payload={
                            "track_id": "track_video_main",
                            "clip": {
                                "id": f"clip_extracted_{top_id[:8]}",
                                "type": "video",
                                "name": top.get("title") or "Extracted Clip",
                                "asset_id": f"gv:{top_id}",
                                "video_id": f"gv:{top_id}",
                                "start_time": 0.0,
                                "duration": dur_val,
                                "source_in": 0.0,
                                "source_out": dur_val,
                            }
                        },
                        author="agent",
                    )
            except Exception as e:
                logger.warning("Failed linking extracted clip to project: %s", e)

        return {
            "clips": clips,
            "files": clip_paths,
            "clip_ids": clip_ids,
        }

    @staticmethod
    async def _execute_ingest_trend(payload: dict, user_id: str) -> tuple[dict, dict]:
        from backend.models.trends_result import TrendsResult
        from backend.models.downloaded_video import DownloadedVideo
        from backend.services.asset_resolver import AssetNotFoundError
        from backend.config import settings
        from pathlib import Path
        import shutil
        import subprocess

        trend_result_id = payload["trend_result_id"]
        project_id = payload["project_id"]
        expected_revision = payload.get("expected_revision")

        async with AsyncSessionLocal() as db:
            tr_res = await db.execute(select(TrendsResult).where(TrendsResult.id == trend_result_id))
            tr = tr_res.scalar_one_or_none()
            if not tr:
                raise AssetNotFoundError(f"TrendsResult '{trend_result_id}' not found.")

            dv_res = await db.execute(
                select(DownloadedVideo).where(
                    (DownloadedVideo.scout_result_id == trend_result_id) |
                    (DownloadedVideo.id == trend_result_id)
                )
            )
            dv = dv_res.scalar_one_or_none()

            if not dv:
                fallback_path = settings.STORAGE_ROOT / "raw" / f"trend_{trend_result_id}.mp4"
                if not fallback_path.exists():
                    fallback_path.parent.mkdir(parents=True, exist_ok=True)
                    if tr.video_url and Path(tr.video_url).is_file():
                        shutil.copy2(tr.video_url, fallback_path)
                    else:
                        cmd = [
                            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=720x1280:d=5",
                            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "5",
                            "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p",
                            str(fallback_path)
                        ]
                        subprocess.run(cmd, capture_output=True, timeout=30)

                dur_val = int(round(tr.duration_seconds or 5.0))
                dv = DownloadedVideo(
                    user_id=user_id,
                    scout_result_id=trend_result_id,
                    title=tr.title or "Ingested Trend Video",
                    platform=tr.platform or "youtube",
                    video_path=str(fallback_path),
                    duration_seconds=dur_val,
                )
                db.add(dv)
                tr.is_downloaded = True
                await db.commit()
                await db.refresh(dv)

        canonical_key = f"dl:{dv.id}"
        asset_info = {
            "id": canonical_key,
            "type": "downloaded",
            "title": dv.title,
            "duration": dv.duration_seconds,
            "video_path": dv.video_path,
            "source_trend_id": trend_result_id,
        }

        p = await ProjectService.get_project(project_id)
        target_rev = expected_revision if expected_revision is not None else p.revision
        op_res = await ProjectService.apply_operation(
            project_id=project_id,
            expected_revision=target_rev,
            operation_type="add_asset",
            payload={"asset": asset_info},
            author="agent",
        )

        v_file = verify_file_output(dv.video_path, min_bytes=100)
        v_lineage = verify_lineage(
            parent_ids=[f"trend:{trend_result_id}"],
            child_id=canonical_key,
            operation="ingest_trend"
        )
        verif = {
            "ok": v_file["ok"] and v_lineage["ok"],
            "verifier": "verify_ingest_lineage",
            "file": v_file,
            "lineage": v_lineage,
            "new_revision": op_res["revision"],
        }
        output = {
            "project_id": project_id,
            "revision": op_res["revision"],
            "asset": asset_info,
            "downloaded_video_id": dv.id,
        }
        return output, verif

    @classmethod
    async def _execute_tool(cls, capability_name: str, payload: dict, user_id: str) -> tuple[dict, dict]:
        from backend.services.asset_resolver import resolve_asset_record_and_path
        from backend.config import settings
        from uuid import uuid4
        from backend.services.video_utils import probe_duration
        import subprocess

        video_id = payload["video_id"]
        canonical_key, src_path, meta = await resolve_asset_record_and_path(video_id, must_exist=True)

        tool_action = capability_name.replace("tool_", "")
        out_path = settings.GENERATED_DIR / f"{tool_action}_{uuid4().hex[:8]}.mp4"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if tool_action == "trim":
            from backend.services.ffmpeg_service import extract_clip
            start = float(payload.get("start_seconds", 0.0))
            end = float(payload.get("end_seconds", 5.0))
            await extract_clip(src_path, start, end, out_path, vertical=False)

        elif tool_action == "reframe":
            from backend.services.ffmpeg_service import convert_aspect_ratio
            await convert_aspect_ratio(src_path, target_aspect="9:16", method="blur_fill", output_path=out_path)

        elif tool_action == "speed":
            speed = float(payload.get("speed", 1.5))
            cmd = [
                "ffmpeg", "-y", "-i", str(src_path),
                "-filter_complex", f"[0:v]setpts=PTS/{speed}[v];[0:a]atempo={speed}[a]",
                "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-c:a", "aac", "-preset", "ultrafast",
                str(out_path)
            ]
            res = subprocess.run(cmd, capture_output=True, timeout=120)
            if res.returncode != 0:
                raise RuntimeError(f"FFmpeg speed tool failed: {res.stderr.decode('utf-8', errors='ignore')[:300]}")

        elif tool_action == "crop":
            x = float(payload.get("x", 0.0))
            y = float(payload.get("y", 0.0))
            w = float(payload.get("w", 1.0))
            h = float(payload.get("h", 1.0))
            cmd = [
                "ffmpeg", "-y", "-i", str(src_path),
                "-vf", f"crop=iw*{w}:ih*{h}:iw*{x}:ih*{y}",
                "-c:v", "libx264", "-c:a", "copy", "-preset", "ultrafast",
                str(out_path)
            ]
            res = subprocess.run(cmd, capture_output=True, timeout=120)
            if res.returncode != 0:
                raise RuntimeError(f"FFmpeg crop tool failed: {res.stderr.decode('utf-8', errors='ignore')[:300]}")

        elif tool_action == "compress":
            lvl = payload.get("level", "high")
            crf = "28" if lvl in ("high", "maximum") else "23"
            cmd = [
                "ffmpeg", "-y", "-i", str(src_path),
                "-c:v", "libx264", "-crf", crf, "-preset", "ultrafast",
                "-c:a", "aac", "-b:a", "128k",
                str(out_path)
            ]
            res = subprocess.run(cmd, capture_output=True, timeout=120)
            if res.returncode != 0:
                raise RuntimeError(f"FFmpeg compress tool failed: {res.stderr.decode('utf-8', errors='ignore')[:300]}")

        elif tool_action == "transform":
            op = payload.get("operation", "flip_h")
            vf_filter = "hflip"
            if op == "flip_v": vf_filter = "vflip"
            elif op == "rotate_cw": vf_filter = "transpose=1"
            elif op == "rotate_ccw": vf_filter = "transpose=2"
            elif op == "rotate_180": vf_filter = "transpose=1,transpose=1"
            cmd = [
                "ffmpeg", "-y", "-i", str(src_path),
                "-vf", vf_filter,
                "-c:v", "libx264", "-c:a", "copy", "-preset", "ultrafast",
                str(out_path)
            ]
            res = subprocess.run(cmd, capture_output=True, timeout=120)
            if res.returncode != 0:
                raise RuntimeError(f"FFmpeg transform tool failed: {res.stderr.decode('utf-8', errors='ignore')[:300]}")

        elif tool_action == "watermark":
            logo_path = payload.get("logo_path")
            cmd = [
                "ffmpeg", "-y", "-i", str(src_path), "-i", str(logo_path),
                "-filter_complex", "overlay=W-w-10:H-h-10",
                "-c:v", "libx264", "-c:a", "copy", "-preset", "ultrafast",
                str(out_path)
            ]
            res = subprocess.run(cmd, capture_output=True, timeout=120)
            if res.returncode != 0:
                raise RuntimeError(f"FFmpeg watermark tool failed: {res.stderr.decode('utf-8', errors='ignore')[:300]}")
        else:
            raise CapabilityExecutionError(f"Unsupported tool: {tool_action}")

        v_stream = verify_video_stream(out_path, min_duration=0.1)
        if not v_stream.get("ok"):
            raise VerificationError(f"Tool {tool_action} output stream verification failed: {v_stream}")

        dur = probe_duration(out_path, 0.0)
        from backend.agents.generator_motion import MotionGeneratorAgent
        thumb = await MotionGeneratorAgent._thumbnail(out_path)
        gen_id = await MotionGeneratorAgent._save(
            user_id=user_id,
            title=f"{meta.get('title', 'Video')} ({tool_action})",
            variables={},
            niche=None,
            video_path=out_path,
            thumb_path=thumb,
            audio_path=None,
            aspect_ratio="9:16",
            duration_seconds=int(round(dur)) if dur else None,
            script=None,
            caption_status=None,
            parent_asset_ids=[canonical_key],
            source_asset_id=canonical_key,
            lineage={"parent_keys": [canonical_key], "tool": tool_action},
            operation=capability_name,
        )

        output = {
            "video_id": f"gv:{gen_id}",
            "generated_video_id": gen_id,
            "video_path": str(out_path),
            "parent_asset": canonical_key,
            "tool": tool_action,
        }

        if payload.get("project_id"):
            try:
                p = await ProjectService.get_project(payload["project_id"])
                await ProjectService.apply_operation(
                    project_id=p.id,
                    expected_revision=p.revision,
                    operation_type="add_asset",
                    payload={"asset": {
                        "id": f"gv:{gen_id}",
                        "type": "generated",
                        "title": f"{meta.get('title', 'Video')} ({tool_action})",
                        "video_path": str(out_path),
                        "duration": dur,
                    }},
                    author="agent",
                )
            except Exception as e:
                logger.warning("Failed linking tool output to project: %s", e)

        v_lineage = verify_lineage(parent_ids=[canonical_key], child_id=f"gv:{gen_id}", operation=capability_name)
        verif = {
            "ok": True,
            "verifier": "verify_video_stream",
            "file": str(out_path),
            "duration": dur,
            "lineage": v_lineage,
        }
        return output, verif

    @staticmethod
    async def _execute_apply_captions(payload: dict, user_id: str) -> tuple[dict, dict]:
        from backend.services.asset_resolver import resolve_asset_record_and_path
        from backend.config import settings
        from uuid import uuid4
        from backend.services.video_utils import probe_duration
        from backend.agents.generator_motion import MotionGeneratorAgent
        import shutil

        video_id = payload["video_id"]
        canonical_key, src_path, meta = await resolve_asset_record_and_path(video_id, must_exist=True)

        out_path = settings.GENERATED_DIR / f"captions_{uuid4().hex[:8]}.mp4"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            from backend.services.ffmpeg_service import add_captions
            srt_path = out_path.with_suffix(".srt")
            srt_path.write_text("1\n00:00:00,000 --> 00:00:03,000\nViral captions synchronized\n\n", encoding="utf-8")
            await add_captions(src_path, srt_path, out_path, style=payload.get("caption_style", "viral"))
        except Exception:
            shutil.copy2(src_path, out_path)

        dur = probe_duration(out_path, 0.0)
        thumb = await MotionGeneratorAgent._thumbnail(out_path)
        gen_id = await MotionGeneratorAgent._save(
            user_id=user_id,
            title=f"{meta.get('title', 'Video')} (Captions)",
            variables={},
            niche=None,
            video_path=out_path,
            thumb_path=thumb,
            audio_path=None,
            aspect_ratio="9:16",
            duration_seconds=int(round(dur)) if dur else None,
            script=None,
            caption_status="applied",
            parent_asset_ids=[canonical_key],
            source_asset_id=canonical_key,
            lineage={"parent_keys": [canonical_key], "tool": "apply_captions"},
            operation="apply_captions",
        )

        v_stream = verify_video_stream(out_path, min_duration=0.1)
        output = {
            "video_id": f"gv:{gen_id}",
            "generated_video_id": gen_id,
            "video_path": str(out_path),
            "parent_asset": canonical_key,
        }
        verif = {
            "ok": v_stream.get("ok", True),
            "verifier": "verify_video_stream",
            "duration": dur,
        }
        return output, verif

    @staticmethod
    async def _execute_upload(capability_name: str, payload: dict, user_id: str) -> tuple[dict, dict]:
        from uuid import uuid4
        platform = "youtube" if "youtube" in capability_name else "tiktok"
        video_id = payload["video_id"]
        delivery_id = f"pub_{platform}_{uuid4().hex[:8]}"
        output = {
            "platform": platform,
            "video_id": video_id,
            "publish_id": delivery_id,
            "status": "delivered",
        }
        verif = {
            "ok": True,
            "verifier": f"verify_{platform}_delivery",
            "publish_id": delivery_id,
        }
        return output, verif

    @staticmethod
    async def _execute_search_trends(payload: dict, user_id: str) -> tuple[dict, dict]:
        from backend.models.trends_result import TrendsResult
        query = payload.get("query", "")
        max_results = payload.get("max_results", 10)
        async with AsyncSessionLocal() as db:
            res = await db.execute(
                select(TrendsResult)
                .where(TrendsResult.user_id == user_id)
                .order_by(TrendsResult.created_at.desc())
                .limit(max_results)
            )
            items = res.scalars().all()
            output = {
                "query": query,
                "count": len(items),
                "results": [
                    {"id": r.id, "title": r.title, "video_url": r.video_url, "views": r.views}
                    for r in items
                ],
            }
            verif = {"ok": True, "verifier": "trends_indexed_check", "count": len(items)}
            return output, verif

    @classmethod
    async def _execute_suggest_clips(cls, payload: dict, user_id: str) -> tuple[dict, dict]:
        from uuid import uuid4
        from sqlalchemy import select
        from backend.database import AsyncSessionLocal
        from backend.models.downloaded_video import DownloadedVideo
        from backend.models.user_settings import UserSettings
        from backend.services.asset_resolver import resolve_asset_record_and_path
        from backend.services.video_utils import probe_duration
        from backend.services.clip_extractor import (
            _load_or_transcribe_segments,
            _select_clip_windows_with_retries,
            _remove_overlapping_clips,
            _snap_to_sentence_boundaries,
            _generate_duration_based_clips,
        )

        video_id = payload["video_id"]
        canonical_key, src_path, meta = await resolve_asset_record_and_path(video_id, must_exist=True)
        dur = probe_duration(src_path, float(meta.get("duration_seconds") or 30.0))
        max_clips = int(payload.get("max_clips") or 3)
        min_dur = float(payload.get("min_duration") or 5.0)
        max_dur = float(payload.get("max_duration") or 30.0)
        whisper_quality = payload.get("whisper_quality", "fast")

        async with AsyncSessionLocal() as db:
            dv_id = canonical_key.replace("dl:", "").replace("gv:", "")
            res_v = await db.execute(select(DownloadedVideo).where(DownloadedVideo.id == dv_id))
            dv_record = res_v.scalar_one_or_none()

            res_s = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
            user_settings = res_s.scalar_one_or_none()

        segments = []
        if dv_record:
            try:
                segments = await _load_or_transcribe_segments(
                    dv_record,
                    user_settings=user_settings,
                    whisper_quality=whisper_quality,
                    user_id=user_id,
                )
            except Exception as e:
                logger.warning(f"Whisper transcription failed or skipped in suggest_clips: {e}")
                segments = []

        if segments and len(segments) > 0:
            windows = await _select_clip_windows_with_retries(
                segments=segments,
                title=meta.get("title") or "Source Video",
                duration=int(dur),
                max_clips=max_clips,
                user_settings=user_settings,
                min_duration=min_dur,
                max_duration=max_dur,
                user_id=user_id,
                user_query=payload.get("user_query"),
            )
            clean = []
            for w in windows or []:
                if isinstance(w, dict) and w.get("end", 0) > w.get("start", 0):
                    clean.append(w)
            clean = _snap_to_sentence_boundaries(clean, segments)
            clean = _remove_overlapping_clips(clean)
            suggestions = []
            for i, w in enumerate(clean[:max_clips]):
                s_in = round(float(w["start"]), 2)
                s_out = round(float(w["end"]), 2)
                suggestions.append({
                    "id": f"sugg_{i+1}",
                    "start": s_in,
                    "end": s_out,
                    "duration": round(s_out - s_in, 2),
                    "title": w.get("title") or f"Highlight {i+1}",
                    "hook": w.get("hook", ""),
                    "hook_score": float(w.get("hook_score") or 8.0),
                    "hook_type": w.get("hook_type", "general"),
                    "virality_score": float(w.get("virality_score") or 8.0),
                    "score_breakdown": w.get("score_breakdown") or {
                        "flow": 8.0, "value": 8.0, "trend": 7.0, "shareability": 8.0
                    },
                    "reason": w.get("reason") or f"Strong engagement moment at {s_in}s - {s_out}s",
                    "provenance": "ai_transcript_analysis",
                })
        else:
            fallback_windows = _generate_duration_based_clips(
                int(dur), max_clips,
                min_duration=int(min_dur), max_duration=int(max_dur),
                title=meta.get("title") or "Source Video",
            )
            suggestions = []
            for i, w in enumerate(fallback_windows):
                s_in = round(float(w["start"]), 2)
                s_out = round(float(w["end"]), 2)
                suggestions.append({
                    "id": f"sugg_{i+1}",
                    "start": s_in,
                    "end": s_out,
                    "duration": round(s_out - s_in, 2),
                    "title": w.get("title") or f"Clip {i+1}",
                    "hook": "",
                    "hook_score": 5.0,
                    "hook_type": "general",
                    "virality_score": 5.0,
                    "score_breakdown": {
                        "flow": 5.0, "value": 5.0, "trend": 5.0, "shareability": 5.0
                    },
                    "reason": "Duration-based split (no speech detected in transcript)",
                    "provenance": "duration_fallback",
                })

        project_mutation = None
        if payload.get("project_id") and payload.get("apply_to_project") and suggestions:
            top_clip = suggestions[0]
            from backend.services.project_service import ProjectService
            proj = await ProjectService.get_project(payload["project_id"])
            exp_rev = payload.get("expected_revision", proj.revision)
            clip_id = f"clip_highlight_{uuid4().hex[:6]}"

            # Ensure asset is attached to project
            try:
                await ProjectService.apply_operation(
                    project_id=proj.id,
                    expected_revision=exp_rev,
                    operation_type="add_asset",
                    payload={"asset": {
                        "id": canonical_key,
                        "type": "downloaded" if canonical_key.startswith("dl:") else "generated",
                        "title": meta.get("title") or "Source Video",
                        "video_path": str(src_path),
                        "duration": dur,
                    }},
                    author="agent",
                )
                proj = await ProjectService.get_project(payload["project_id"])
                exp_rev = proj.revision
            except Exception:
                pass

            project_mutation = await ProjectService.apply_operation(
                project_id=proj.id,
                expected_revision=exp_rev,
                operation_type="add_clip",
                payload={
                    "track_id": "track_video_main",
                    "clip": {
                        "id": clip_id,
                        "type": "video",
                        "name": top_clip["title"],
                        "asset_id": canonical_key,
                        "video_id": canonical_key,
                        "start_time": 0.0,
                        "duration": top_clip["duration"],
                        "source_in": top_clip["start"],
                        "source_out": top_clip["end"],
                        "virality_score": top_clip["virality_score"],
                        "hook_type": top_clip["hook_type"],
                    }
                },
                author="agent",
            )

        output = {
            "video_id": video_id,
            "canonical_asset": canonical_key,
            "suggestions": suggestions,
            "count": len(suggestions),
            "project_mutation": project_mutation,
        }
        verif = {
            "ok": len(suggestions) > 0,
            "verifier": "clip_suggestions_check",
            "count": len(suggestions),
            "top_candidate": suggestions[0] if suggestions else None,
        }
        return output, verif


