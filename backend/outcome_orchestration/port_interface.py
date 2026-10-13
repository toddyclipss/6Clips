# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""MediaProducerPort abstract interface and deterministic test adapter for Outcome Orchestration."""

import abc
import asyncio
import hashlib
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.outcome_orchestration.models import (
    Blocker,
    Checks,
    MediaProbe,
    OutcomeContract,
    OutputResult,
    OutputState,
    ProductionReport,
    SourceRange,
    StepEvent,
)


class MediaProducerPort(abc.ABC):
    """Abstract interface defining the frozen Production V1 Audiovisual Data Plane Port."""

    @abc.abstractmethod
    async def submit_batch(self, request: Any, simulate_failure_index: Optional[int] = None) -> Dict[str, Any]:
        """Submit a batch production request.

        Returns:
            {"job_id": str, "accepted": bool, "blocker": Optional[dict]}
        """
        pass

    @abc.abstractmethod
    async def get_batch(self, job_id: str) -> ProductionReport:
        """Poll the execution status and output results of a batch job."""
        pass

    @abc.abstractmethod
    async def cancel_batch(self, job_id: str) -> Dict[str, Any]:
        """Request cancellation of an active batch job.

        Returns:
            {"acknowledged": bool, "effects_already_committed": list}
        """
        pass


class InProcessFakeProducerPort(MediaProducerPort):
    """Deterministic, isolated implementation of MediaProducerPort for orchestration testing.

    Adheres 100% to Production V1 contract semantics:
    - Verifies source asset accessibility and rights permissions.
    - Emits distinct output_id results for each requested output.
    - Never declares human editorial approval (editorial = 'NOT_ASSESSED').
    - Provides simulated failure of arbitrary outputs (e.g. index 2) to test PARTIAL state.
    - Honors batch cancellation with recorded committed effects.
    """

    def __init__(self, ledger=None):
        self._jobs: Dict[str, ProductionReport] = {}
        self._cancelled_jobs: set[str] = set()
        from backend.production_jobs.ledger import PersistentJobLedger
        self._ledger = ledger or PersistentJobLedger()

    async def submit_batch(self, request: Any, simulate_failure_index: Optional[int] = None) -> Dict[str, Any]:
        job_id = f"job_fake_{uuid4().hex[:12]}"

        # Extract request attributes (compatible with OutcomeContract or dict)
        if isinstance(request, dict):
            source_assets = request.get("source_assets", [])
            outputs = request.get("outputs", [])
            run_id = request.get("run_id", "run_test")
            contract_ver = request.get("contract_version", 1)
        else:
            source_assets = getattr(request, "source_assets", [])
            outputs = getattr(request, "outputs", [])
            run_id = getattr(request, "run_id", "run_test")
            contract_ver = getattr(request, "contract_version", 1)

        # 1. Access and Permission Gate
        if not source_assets:
            blocker = Blocker(
                code="NO_SOURCE_ASSETS",
                precise_reason="ProductionRequest contains zero source assets.",
                next_action="Provide at least one primary source footage asset.",
            )
            return {"job_id": job_id, "accepted": False, "blocker": blocker.model_dump()}

        inaccessible = [
            a for a in source_assets
            if not getattr(a, "is_accessible", True) or not getattr(a, "rights_verified", True)
        ]
        if inaccessible:
            first = inaccessible[0]
            a_id = getattr(first, "asset_id", "unknown")
            blocker = Blocker(
                code="SOURCE_ACCESS_DENIED",
                precise_reason=f"Source asset '{a_id}' is not physically accessible or lacks verified reuse permissions.",
                next_action="Provide an accessible, legally permitted recording or select an authorized asset from Library.",
            )
            return {"job_id": job_id, "accepted": False, "blocker": blocker.model_dump()}

        # 2. Build initial running report
        report = ProductionReport(
            schema_version="production.v1",
            job_id=job_id,
            run_id=run_id,
            contract_version=contract_ver,
            status="RUNNING",
            step_events=[
                StepEvent(step_name="SUBMIT_BATCH", status="ACCEPTED", detail=f"Accepted batch of {len(outputs)} clips")
            ],
        )

        output_results: List[OutputResult] = []
        has_failed = False
        has_succeeded = False

        for idx, out_spec in enumerate(outputs):
            out_id = getattr(out_spec, "output_id", f"out_{idx}")
            dur = getattr(out_spec, "seconds", 60.0)

            # Simulated failure for testing fault tolerance and PARTIAL isolation
            if simulate_failure_index is not None and idx == simulate_failure_index:
                output_results.append(
                    OutputResult(
                        output_id=out_id,
                        state=OutputState.FAILED,
                        error_detail=f"Simulated render encoder timeout on output #{idx + 1}",
                        checks=Checks(technical="FAIL", contract="FAIL", editorial="NOT_ASSESSED"),
                    )
                )
                has_failed = True
                continue

            # Deterministic successful synthetic probe
            fake_hash = hashlib.sha256(f"probe_{job_id}_{out_id}".encode()).hexdigest()
            probe = MediaProbe(
                width=1080,
                height=1920,
                duration_seconds=float(dur),
                video_codec="h264",
                audio_codec="aac",
                fps=30.0,
                audio_channels=2,
                sample_rate=48000,
                content_hash=fake_hash,
                mean_volume_db=-14.2,
                is_silent=False,
                is_black=False,
            )

            primary_asset_id = getattr(source_assets[0], "asset_id", "src_default")
            s_range = SourceRange(
                asset_id=primary_asset_id,
                start_seconds=idx * dur,
                end_seconds=(idx + 1) * dur,
                duration_seconds=float(dur),
                editorial_reason=f"High-density highlight sequence #{idx + 1}",
                relevance_score=88.5 + idx,
            )

            output_results.append(
                OutputResult(
                    output_id=out_id,
                    project_revision_id=f"rev_{out_id}",
                    artifact_id=f"art_mp4_{out_id}",
                    snapshot_manifest_ref=f"snap_{out_id}",
                    media_probe=probe,
                    source_ranges=[s_range],
                    checks=Checks(technical="PASS", contract="PASS", editorial="NOT_ASSESSED"),
                    preview_ref=f"/api/v1/media/preview/{out_id}",
                    state=OutputState.SUCCEEDED,
                )
            )
            has_succeeded = True

        report.outputs = output_results
        if has_failed and has_succeeded:
            report.status = "PARTIAL"
        elif has_failed and not has_succeeded:
            report.status = "BLOCKED"
        else:
            report.status = "COMPLETE"

        report.step_events.append(
            StepEvent(step_name="PRODUCTION_COMPLETE", status=report.status, detail=f"Batch finalized with status {report.status}")
        )
        self._jobs[job_id] = report

        return {"job_id": job_id, "accepted": True, "blocker": None}

    async def get_batch(self, job_id: str) -> ProductionReport:
        if job_id not in self._jobs:
            return ProductionReport(
                schema_version="production.v1",
                job_id=job_id,
                run_id="unknown",
                contract_version=1,
                status="BLOCKED",
                blockers=[Blocker(code="JOB_NOT_FOUND", precise_reason=f"Job {job_id} does not exist", next_action="Verify job ID")],
            )
        return self._jobs[job_id]

    async def cancel_batch(self, job_id: str) -> Dict[str, Any]:
        self._cancelled_jobs.add(job_id)
        report = self._jobs.get(job_id)
        committed = []
        if report:
            report.status = "CANCELLED"
            for out in report.outputs:
                if out.state == OutputState.SUCCEEDED:
                    committed.append(out.output_id)
                elif out.state != OutputState.FAILED:
                    out.state = OutputState.CANCELLED
            report.step_events.append(
                StepEvent(step_name="CANCEL_BATCH", status="CANCELLED", detail="User requested job cancellation")
            )
        return {"acknowledged": True, "effects_already_committed": committed}


_ACTIVE_PORT: Optional[MediaProducerPort] = None


def get_media_producer_port() -> MediaProducerPort:
    """Resolve the active MediaProducerPort instance.

    If the real producer adapter from Agent B is available in the Python path
    (after coordinated branch merge), instantiate it. Otherwise, return the
    deterministic InProcessFakeProducerPort.
    """
    global _ACTIVE_PORT
    if _ACTIVE_PORT is not None:
        return _ACTIVE_PORT

    try:
        from backend.media_pipeline.producer_adapter import get_media_producer
        _ACTIVE_PORT = get_media_producer()
    except (ImportError, AttributeError):
        _ACTIVE_PORT = InProcessFakeProducerPort()

    return _ACTIVE_PORT


def set_media_producer_port(port: MediaProducerPort) -> None:
    """Override the active MediaProducerPort for testing and runtime wiring."""
    global _ACTIVE_PORT
    _ACTIVE_PORT = port
    try:
        from backend.media_pipeline import producer_adapter
        producer_adapter._global_producer = port
    except Exception:
        pass
