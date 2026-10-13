# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""MediaProducerPort implementation — batch submission, execution, polling, and cancellation."""

import asyncio
import datetime
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.config import DATA_DIR, settings
from backend.media_pipeline.clip_renderer import render_output_clip
from backend.media_pipeline.media_inspector import (
    inspect_source_provenance_and_rights,
    probe_physical_media,
)
from backend.media_pipeline.models import (
    BatchStatus,
    BlockerV1,
    ChecksV1,
    OutputResultV1,
    OutputSpecV1,
    OutputState,
    ProductionReportV1,
    ProductionRequestV1,
    SourceAssetV1,
    SourceRangeV1,
    StepEventV1,
)
from backend.media_pipeline.segment_selector import (
    extract_transcript_if_needed,
    select_editorial_segments,
)

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class MediaProducerPort:
    """Canonical MediaProducerPort interface implementation for 6Clips.
    
    Coordinates audiovisual analysis, cutting, reframing, and rendering
    under strict provenance, duration policy, and fault isolation.
    """

    def __init__(self, storage_dir: Optional[Path] = None):
        self._storage_dir = storage_dir or (DATA_DIR / "media_production")
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._job_tasks: Dict[str, asyncio.Task] = {}
        self._artifact_index: Dict[str, Path] = {}
        self._fingerprints: Dict[str, str] = {}  # fingerprint -> job_id (idempotency)

    def _compute_request_fingerprint(self, req: ProductionRequestV1) -> str:
        data = {
            "contract_id": req.contract_id,
            "contract_version": req.contract_version,
            "project_id": req.project_id,
            "source_assets": [a.model_dump() for a in req.source_assets],
            "outputs": [o.model_dump() for o in req.outputs],
        }
        raw = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def resolve_artifact_path(self, artifact_id: str) -> Optional[Path]:
        """Resolve an artifact ID to its local file path for streaming."""
        return self._artifact_index.get(artifact_id)

    async def submit_batch(self, request: Any, simulate_failure_output_index: Optional[int] = None) -> Dict[str, Any]:
        """Submit a batch production request. Accepts ProductionRequestV1 or dict."""
        if isinstance(request, dict):
            request = ProductionRequestV1.model_validate(request)

        fingerprint = self._compute_request_fingerprint(request)
        if fingerprint in self._fingerprints:
            existing_job_id = self._fingerprints[fingerprint]
            logger.info("Idempotent replay for media production batch: %s", existing_job_id)
            return {
                "job_id": existing_job_id,
                "accepted": True,
                "blocker": None,
                "idempotent_replay": True,
            }

        job_id = f"job_prod_{uuid4().hex[:12]}"
        self._fingerprints[fingerprint] = job_id

        # 1. Inspect source asset provenance and rights
        if not request.source_assets:
            blocker = BlockerV1(
                code="NO_SOURCE_ASSETS",
                precise_reason="Request contains zero source assets.",
                next_action="Provide at least one primary source asset.",
            )
            self._record_blocked_job(job_id, request, blocker)
            return {"job_id": job_id, "accepted": False, "blocker": blocker.model_dump()}

        primary_asset = request.source_assets[0]
        rights_blocker = inspect_source_provenance_and_rights(primary_asset)
        if rights_blocker:
            self._record_blocked_job(job_id, request, rights_blocker)
            return {"job_id": job_id, "accepted": False, "blocker": rights_blocker.model_dump()}

        # 2. Inspect physical file
        source_path = Path(primary_asset.local_path) if primary_asset.local_path else None
        if not source_path or not source_path.exists():
            blocker = BlockerV1(
                code="PHYSICAL_BYTES_MISSING",
                precise_reason=f"Local media bytes not found at: '{source_path}'.",
                next_action="Ensure the physical file exists and is accessible.",
            )
            self._record_blocked_job(job_id, request, blocker)
            return {"job_id": job_id, "accepted": False, "blocker": blocker.model_dump()}

        media_probe, probe_blocker = await probe_physical_media(source_path)
        if probe_blocker:
            self._record_blocked_job(job_id, request, probe_blocker)
            return {"job_id": job_id, "accepted": False, "blocker": probe_blocker.model_dump()}

        # 3. Select distinct editorial segments
        transcript = await extract_transcript_if_needed(source_path, media_probe)
        source_ranges, select_blocker = select_editorial_segments(
            media_probe,
            request.outputs,
            transcript_segments=transcript,
            asset_id=primary_asset.asset_id,
        )
        if select_blocker:
            self._record_blocked_job(job_id, request, select_blocker)
            return {"job_id": job_id, "accepted": False, "blocker": select_blocker.model_dump()}

        # 4. Initialize job state
        job_dir = self._storage_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        initial_outputs = [
            OutputResultV1(
                output_id=spec.output_id,
                source_ranges=[source_ranges[idx]] if idx < len(source_ranges) else [],
                checks=ChecksV1(technical="NOT_RUN", contract="NOT_RUN", editorial="NOT_ASSESSED"),
                state=OutputState.PENDING,
            )
            for idx, spec in enumerate(request.outputs)
        ]

        report = ProductionReportV1(
            schema_version="production.v1",
            job_id=job_id,
            run_id=request.run_id,
            contract_version=request.contract_version,
            status=BatchStatus.RUNNING,
            outputs=initial_outputs,
            blockers=[],
            evidence_refs=[],
            step_events=[
                StepEventV1(
                    step_name="submit_batch",
                    status="accepted",
                    timestamp=_utc_now_iso(),
                    detail=f"Accepted batch with {len(request.outputs)} outputs.",
                ),
                StepEventV1(
                    step_name="inspect_media",
                    status="success",
                    timestamp=_utc_now_iso(),
                    detail=f"Source probed: {media_probe.width}x{media_probe.height}, {media_probe.duration_seconds:.1f}s",
                ),
            ],
        )

        self._jobs[job_id] = {
            "request": request,
            "report": report,
            "source_path": source_path,
            "source_ranges": source_ranges,
            "job_dir": job_dir,
            "cancelled": False,
        }

        # 5. Launch execution worker
        task = asyncio.create_task(
            self._execute_batch(job_id, simulate_failure_output_index)
        )
        self._job_tasks[job_id] = task

        return {"job_id": job_id, "accepted": True, "blocker": None}

    def _record_blocked_job(self, job_id: str, request: ProductionRequestV1, blocker: BlockerV1):
        report = ProductionReportV1(
            schema_version="production.v1",
            job_id=job_id,
            run_id=request.run_id,
            contract_version=request.contract_version,
            status=BatchStatus.BLOCKED,
            outputs=[],
            blockers=[blocker],
            evidence_refs=[],
            step_events=[
                StepEventV1(
                    step_name="submit_batch",
                    status="blocked",
                    timestamp=_utc_now_iso(),
                    detail=blocker.precise_reason,
                )
            ],
        )
        self._jobs[job_id] = {
            "request": request,
            "report": report,
            "cancelled": False,
        }

    async def _execute_batch(self, job_id: str, simulate_failure_output_index: Optional[int] = None):
        job_data = self._jobs.get(job_id)
        if not job_data:
            return

        req: ProductionRequestV1 = job_data["request"]
        report: ProductionReportV1 = job_data["report"]
        source_path: Path = job_data["source_path"]
        source_ranges: List[SourceRangeV1] = job_data["source_ranges"]
        job_dir: Path = job_data["job_dir"]

        results: List[OutputResultV1] = []

        for idx, spec in enumerate(req.outputs):
            if job_data.get("cancelled"):
                logger.info("Job %s cancelled mid-execution.", job_id)
                break

            range_spec = source_ranges[idx] if idx < len(source_ranges) else None
            if not range_spec:
                continue

            sim_fail = (simulate_failure_output_index is not None and idx == simulate_failure_output_index)
            
            report.step_events.append(StepEventV1(
                step_name=f"render_output_{spec.output_id}",
                status="running",
                timestamp=_utc_now_iso(),
                detail=f"Rendering {spec.output_id} ({spec.aspect_ratio}, {range_spec.duration_seconds}s)",
            ))

            out_res = await render_output_clip(
                source_path=source_path,
                source_range=range_spec,
                spec=spec,
                project_id=req.project_id,
                output_dir=job_dir,
                simulate_failure=sim_fail,
                user_id=req.user_id,
            )

            if out_res.artifact_id and out_res.state == OutputState.SUCCEEDED:
                # Register artifact path for streaming
                out_path = job_dir / f"{spec.output_id}.mp4"
                if out_path.exists():
                    self._artifact_index[out_res.artifact_id] = out_path
                    report.evidence_refs.append(f"artifact:{out_res.artifact_id}")

            results.append(out_res)

            report.step_events.append(StepEventV1(
                step_name=f"render_output_{spec.output_id}",
                status=out_res.state.value.lower(),
                timestamp=_utc_now_iso(),
                detail=out_res.error_detail or "Render complete",
            ))

        report.outputs = results

        if job_data.get("cancelled"):
            report.status = BatchStatus.CANCELLED
            return

        # Determine aggregate status
        num_success = sum(1 for r in results if r.state == OutputState.SUCCEEDED)
        total = len(req.outputs)

        if num_success == total:
            report.status = BatchStatus.COMPLETE
        elif num_success > 0:
            report.status = BatchStatus.PARTIAL
            report.blockers.append(BlockerV1(
                code="PARTIAL_OUTPUT_FAILURE",
                precise_reason=f"{num_success}/{total} outputs succeeded. Remaining outputs encountered errors.",
                next_action="Review individual output error details or retry failed output.",
            ))
        else:
            report.status = BatchStatus.BLOCKED
            report.blockers.append(BlockerV1(
                code="ALL_OUTPUTS_FAILED",
                precise_reason="All requested outputs failed to render.",
                next_action="Inspect pipeline errors and render logs.",
            ))

    def get_batch(self, job_id: str) -> ProductionReportV1:
        """Poll the current production batch report."""
        job_data = self._jobs.get(job_id)
        if not job_data:
            return ProductionReportV1(
                schema_version="production.v1",
                job_id=job_id,
                run_id="unknown",
                contract_version="1.0.0",
                status=BatchStatus.BLOCKED,
                outputs=[],
                blockers=[BlockerV1(
                    code="JOB_NOT_FOUND",
                    precise_reason=f"No media production batch found for job_id '{job_id}'.",
                    next_action="Check job_id or submit a new batch.",
                )],
            )
        return job_data["report"]

    def cancel_batch(self, job_id: str) -> Dict[str, Any]:
        """Cancel an in-flight batch job.
        
        Returns:
            {"acknowledged": bool, "effects_already_committed": list[str]}
        """
        job_data = self._jobs.get(job_id)
        if not job_data:
            return {"acknowledged": False, "effects_already_committed": []}

        job_data["cancelled"] = True
        task = self._job_tasks.get(job_id)
        if task and not task.done():
            task.cancel()

        report: ProductionReportV1 = job_data["report"]
        report.status = BatchStatus.CANCELLED
        committed = [
            out.output_id for out in report.outputs
            if out.state == OutputState.SUCCEEDED
        ]
        return {
            "acknowledged": True,
            "effects_already_committed": committed,
        }


# Singleton producer instance
_global_producer: Optional[MediaProducerPort] = None


def get_media_producer() -> MediaProducerPort:
    global _global_producer
    if _global_producer is None:
        _global_producer = MediaProducerPort()
    return _global_producer
