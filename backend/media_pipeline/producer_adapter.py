# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""MediaProducerPort implementation — durable batch submission, execution, polling, cancellation, and recovery."""

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
from backend.production_jobs.ledger import (
    PersistentJobLedger,
    compute_sha256,
    verify_physical_media_file,
)
from backend.production_jobs.types import (
    ErrorClassification,
    JobRecord,
    RecoveryClassification,
)

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class MediaProducerPort:
    """Canonical MediaProducerPort interface implementation for 6Clips.
    
    Coordinates audiovisual analysis, cutting, reframing, and rendering
    under strict provenance, duration policy, durable persistence, and fault isolation.
    """

    def __init__(
        self,
        storage_dir: Optional[Path] = None,
        ledger: Optional[PersistentJobLedger] = None,
    ):
        self._storage_dir = storage_dir or (DATA_DIR / "media_production")
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._ledger = ledger or PersistentJobLedger(storage_dir=self._storage_dir / "ledger")
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._job_tasks: Dict[str, asyncio.Task] = {}
        self._artifact_index: Dict[str, Path] = {}
        self._fingerprints: Dict[str, str] = {}  # fingerprint -> job_id (idempotency)

        # Rehydrate in-memory indexes and reconcile any crashed/interrupted jobs from persistent ledger
        self._rehydrate_from_ledger()

    def _rehydrate_from_ledger(self) -> None:
        """Scan persistent ledger on startup, reconcile incomplete jobs, and index valid artifacts."""
        try:
            self._ledger.reconcile_active_jobs()
            for rec in self._ledger.list_jobs():
                if rec.request_fingerprint:
                    self._fingerprints[rec.request_fingerprint] = rec.job_id
                for out_id, cp in rec.output_checkpoints.items():
                    if cp.state == "SUCCEEDED" and cp.artifact_id and cp.file_path:
                        p = Path(cp.file_path)
                        if p.exists() and p.stat().st_size > 0:
                            self._artifact_index[cp.artifact_id] = p
        except Exception as ex:
            logger.warning("Error rehydrating MediaProducerPort from persistent ledger: %s", ex)

    def _compute_request_fingerprint(self, req: ProductionRequestV1) -> str:
        data = {
            "contract_id": req.contract_id,
            "contract_version": req.contract_version,
            "project_id": req.project_id,
            "user_id": req.user_id,
            "source_assets": [a.model_dump() for a in req.source_assets],
            "outputs": [o.model_dump() for o in req.outputs],
        }
        raw = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def resolve_artifact_path(self, artifact_id: str) -> Optional[Path]:
        """Resolve an artifact ID to its verified local file path for streaming."""
        # 1. Fast in-memory cache
        path = self._artifact_index.get(artifact_id)
        if path and path.exists() and path.stat().st_size > 0:
            return path

        # 2. Durable ledger lookup (survives restarts)
        path = self._ledger.resolve_artifact_path(artifact_id)
        if path:
            self._artifact_index[artifact_id] = path
            return path
        return None

    async def submit_batch(
        self,
        request: Any,
        simulate_failure_output_index: Optional[int] = None,
        force_new: bool = False,
    ) -> Dict[str, Any]:
        """Submit a batch production request. Accepts ProductionRequestV1 or dict."""
        if isinstance(request, dict):
            request = ProductionRequestV1.model_validate(request)

        fingerprint = self._compute_request_fingerprint(request)

        # Idempotency check: if exact request was submitted before and not forced new
        if not force_new:
            existing_job_id = self._fingerprints.get(fingerprint) or self._ledger.get_job_id_by_fingerprint(fingerprint)
            if existing_job_id:
                # Check status of existing job
                existing_report = self.get_batch(existing_job_id)
                if existing_report.status in (BatchStatus.COMPLETE, BatchStatus.RUNNING):
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
            self._record_blocked_job(job_id, request, blocker, fingerprint)
            return {"job_id": job_id, "accepted": False, "blocker": blocker.model_dump()}

        primary_asset = request.source_assets[0]
        rights_blocker = inspect_source_provenance_and_rights(primary_asset)
        if rights_blocker:
            self._record_blocked_job(job_id, request, rights_blocker, fingerprint)
            return {"job_id": job_id, "accepted": False, "blocker": rights_blocker.model_dump()}

        # 2. Inspect physical file
        source_path = Path(primary_asset.local_path) if primary_asset.local_path else None
        if not source_path or not source_path.exists():
            blocker = BlockerV1(
                code="PHYSICAL_BYTES_MISSING",
                precise_reason=f"Local media bytes not found at: '{source_path}'.",
                next_action="Ensure the physical file exists and is accessible.",
            )
            self._record_blocked_job(job_id, request, blocker, fingerprint)
            return {"job_id": job_id, "accepted": False, "blocker": blocker.model_dump()}

        media_probe, probe_blocker = await probe_physical_media(source_path)
        if probe_blocker:
            self._record_blocked_job(job_id, request, probe_blocker, fingerprint)
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
            self._record_blocked_job(job_id, request, select_blocker, fingerprint)
            return {"job_id": job_id, "accepted": False, "blocker": select_blocker.model_dump()}

        # 4. Initialize durable job state
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

        step_events = [
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
            step_events=step_events,
        )

        # Persist to durable ledger atomically
        self._ledger.create_job(
            job_id=job_id,
            request_fingerprint=fingerprint,
            run_id=request.run_id,
            immutable_request=request.model_dump(),
            output_ids=[spec.output_id for spec in request.outputs],
            contract_id=request.contract_id,
            project_id=request.project_id,
            user_id=request.user_id,
            status="RUNNING",
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

    def _record_blocked_job(
        self,
        job_id: str,
        request: ProductionRequestV1,
        blocker: BlockerV1,
        fingerprint: str,
    ) -> None:
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
        self._ledger.create_job(
            job_id=job_id,
            request_fingerprint=fingerprint,
            run_id=request.run_id,
            immutable_request=request.model_dump(),
            output_ids=[s.output_id for s in request.outputs],
            contract_id=request.contract_id,
            project_id=request.project_id,
            user_id=request.user_id,
            status="BLOCKED",
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
                logger.info("Job %s cancelled mid-execution before output %s.", job_id, spec.output_id)
                self._ledger.checkpoint_output_cancelled(job_id, spec.output_id)
                break

            range_spec = source_ranges[idx] if idx < len(source_ranges) else None
            if not range_spec:
                continue

            # Check if this output was already rendered and valid from a prior run (resume optimization)
            expected_out_file = job_dir / f"{spec.output_id}.mp4"
            is_valid, existing_sha, existing_size = verify_physical_media_file(expected_out_file)
            if is_valid:
                logger.info("Output %s already verified on disk; skipping re-render.", spec.output_id)
                artifact_id = f"artifact_{spec.output_id}_reused"
                self._artifact_index[artifact_id] = expected_out_file
                self._ledger.checkpoint_output_success(
                    job_id=job_id,
                    output_id=spec.output_id,
                    artifact_id=artifact_id,
                    file_path=expected_out_file,
                    file_hash=existing_sha,
                    file_size=existing_size,
                )
                reused_out = OutputResultV1(
                    output_id=spec.output_id,
                    artifact_id=artifact_id,
                    source_ranges=[range_spec],
                    checks=ChecksV1(technical="PASS", contract="PASS", editorial="NOT_ASSESSED"),
                    state=OutputState.SUCCEEDED,
                )
                results.append(reused_out)
                report.evidence_refs.append(f"artifact:{artifact_id}")
                continue

            sim_fail = (simulate_failure_output_index is not None and idx == simulate_failure_output_index)

            # Checkpoint start in durable ledger
            self._ledger.checkpoint_output_start(job_id, spec.output_id)

            report.step_events.append(StepEventV1(
                step_name=f"render_output_{spec.output_id}",
                status="running",
                timestamp=_utc_now_iso(),
                detail=f"Rendering {spec.output_id} ({spec.aspect_ratio}, {range_spec.duration_seconds}s)",
            ))

            # Bounded retry loop (max 3 attempts with backoff)
            max_attempts = req.execution_limits.max_attempts if req.execution_limits else 3
            out_res: Optional[OutputResultV1] = None

            for attempt in range(1, max_attempts + 1):
                out_res = await render_output_clip(
                    source_path=source_path,
                    source_range=range_spec,
                    spec=spec,
                    project_id=req.project_id,
                    output_dir=job_dir,
                    simulate_failure=sim_fail,
                    user_id=req.user_id,
                )

                if out_res.state == OutputState.SUCCEEDED and out_res.artifact_id:
                    # Physical byte verification gate
                    out_path = job_dir / f"{spec.output_id}.mp4"
                    file_ok, sha_hash, file_sz = verify_physical_media_file(out_path)
                    if file_ok:
                        self._artifact_index[out_res.artifact_id] = out_path
                        self._ledger.checkpoint_output_success(
                            job_id=job_id,
                            output_id=spec.output_id,
                            artifact_id=out_res.artifact_id,
                            file_path=out_path,
                            file_hash=sha_hash,
                            file_size=file_sz,
                        )
                        report.evidence_refs.append(f"artifact:{out_res.artifact_id}")
                        break
                    else:
                        out_res.state = OutputState.FAILED
                        out_res.error_detail = "Render finished but output file missing or zero bytes on disk."

                if attempt < max_attempts and not sim_fail:
                    await asyncio.sleep(0.05 * attempt)

            if out_res.state != OutputState.SUCCEEDED:
                # Classify error and record in ledger
                err_code = ErrorClassification.TRANSIENT_RENDER_IO if sim_fail else ErrorClassification.UNKNOWN_EXECUTION_ERROR
                recovery = RecoveryClassification.SAFE_RETRY if attempt < max_attempts else RecoveryClassification.RESUME
                self._ledger.checkpoint_output_failure(
                    job_id=job_id,
                    output_id=spec.output_id,
                    error_detail=out_res.error_detail or "Render failed",
                    error_classification=err_code,
                    recovery_classification=recovery,
                )

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
            self._ledger.record_transition(job_id, "CANCELLED", detail="Job cancelled by user")
            return

        # Determine aggregate status
        num_success = sum(1 for r in results if r.state == OutputState.SUCCEEDED)
        total = len(req.outputs)

        if num_success == total and total > 0:
            report.status = BatchStatus.COMPLETE
            self._ledger.record_transition(job_id, "COMPLETE", detail=f"All {total} outputs rendered and verified")
        elif num_success > 0:
            report.status = BatchStatus.PARTIAL
            report.blockers.append(BlockerV1(
                code="PARTIAL_OUTPUT_FAILURE",
                precise_reason=f"{num_success}/{total} outputs succeeded. Remaining outputs encountered errors.",
                next_action="Review individual output error details or retry failed output.",
            ))
            self._ledger.record_transition(job_id, "PARTIAL", detail=f"{num_success}/{total} outputs succeeded")
        else:
            report.status = BatchStatus.BLOCKED
            report.blockers.append(BlockerV1(
                code="ALL_OUTPUTS_FAILED",
                precise_reason="All requested outputs failed to render.",
                next_action="Inspect pipeline errors and render logs.",
            ))
            self._ledger.record_transition(job_id, "BLOCKED", detail="All outputs failed")

    def get_batch(self, job_id: str) -> ProductionReportV1:
        """Poll the current production batch report with physical artifact verification."""
        job_data = self._jobs.get(job_id)
        if job_data:
            report: ProductionReportV1 = job_data["report"]
            # Verify physical artifacts for any output claiming SUCCEEDED
            self._verify_report_artifacts(job_id, report)
            return report

        # Fallback: check durable ledger (e.g. after process restart)
        rec = self._ledger.get_job(job_id)
        if rec:
            report = self._reconstruct_report_from_record(rec)
            self._verify_report_artifacts(job_id, report)
            # Rehydrate into memory cache
            self._jobs[job_id] = {
                "report": report,
                "cancelled": rec.cancelled,
            }
            return report

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

    def _verify_report_artifacts(self, job_id: str, report: ProductionReportV1) -> None:
        """Enforces invariant: never declare COMPLETE or SUCCEEDED without verified artifacts on disk."""
        degraded = False
        for out in report.outputs:
            if out.state == OutputState.SUCCEEDED and out.artifact_id:
                path = self.resolve_artifact_path(out.artifact_id)
                if not path or not path.exists() or path.stat().st_size == 0:
                    logger.warning("Degrading output %s in job %s: missing physical bytes", out.output_id, job_id)
                    out.state = OutputState.FAILED
                    out.error_detail = "Artifact bytes missing or corrupted on disk."
                    degraded = True

        if degraded and report.status == BatchStatus.COMPLETE:
            report.status = BatchStatus.PARTIAL
            report.blockers.append(BlockerV1(
                code="ARTIFACT_VERIFICATION_FAILED",
                precise_reason="One or more output artifact files were missing or corrupted on disk.",
                next_action="Retry rendering for missing outputs.",
            ))
            self._ledger.record_transition(job_id, "PARTIAL", detail="Degraded due to missing physical artifacts")

    def _reconstruct_report_from_record(self, rec: JobRecord) -> ProductionReportV1:
        """Reconstruct a typed ProductionReportV1 from a durable JobRecord."""
        outputs: List[OutputResultV1] = []
        for out_id, cp in rec.output_checkpoints.items():
            state = OutputState(cp.state) if cp.state in OutputState._value2member_map_ else OutputState.FAILED
            tech_check = "PASS" if state == OutputState.SUCCEEDED else "NOT_RUN"
            cont_check = "PASS" if state == OutputState.SUCCEEDED else "NOT_RUN"
            outputs.append(
                OutputResultV1(
                    output_id=out_id,
                    artifact_id=cp.artifact_id,
                    checks=ChecksV1(technical=tech_check, contract=cont_check, editorial="NOT_ASSESSED"),
                    state=state,
                    error_detail=cp.error_detail,
                )
            )

        status_enum = BatchStatus(rec.status) if rec.status in BatchStatus._value2member_map_ else BatchStatus.BLOCKED
        blockers = [BlockerV1.model_validate(b) for b in rec.blockers]

        return ProductionReportV1(
            schema_version="production.v1",
            job_id=rec.job_id,
            run_id=rec.run_id,
            contract_version=str(rec.immutable_request.get("contract_version", "1.0.0")),
            status=status_enum,
            outputs=outputs,
            blockers=blockers,
            evidence_refs=rec.evidence_refs,
            step_events=[StepEventV1.model_validate(ev) for ev in rec.step_events],
        )

    def cancel_batch(self, job_id: str) -> Dict[str, Any]:
        """Cancel an in-flight batch job.
        
        Returns:
            {"acknowledged": bool, "effects_already_committed": list[str]}
        """
        job_data = self._jobs.get(job_id)
        if not job_data:
            # Check ledger
            rec = self._ledger.get_job(job_id)
            if not rec:
                return {"acknowledged": False, "effects_already_committed": []}
            committed = [
                out_id for out_id, cp in rec.output_checkpoints.items()
                if cp.state == "SUCCEEDED"
            ]
            self._ledger.record_transition(job_id, "CANCELLED", detail="Cancelled via ledger")
            return {"acknowledged": True, "effects_already_committed": committed}

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

        # Checkpoint cancelled outputs in durable ledger
        for out in report.outputs:
            if out.state != OutputState.SUCCEEDED:
                out.state = OutputState.CANCELLED
                self._ledger.checkpoint_output_cancelled(job_id, out.output_id)

        self._ledger.record_transition(job_id, "CANCELLED", detail="User requested job cancellation")

        return {
            "acknowledged": True,
            "effects_already_committed": committed,
        }


# Singleton producer instance
_global_producer: Optional[MediaProducerPort] = None


def get_media_producer() -> MediaProducerPort:
    global _global_producer
    if _global_producer is None or not hasattr(_global_producer, "_ledger"):
        _global_producer = MediaProducerPort()
    return _global_producer
