# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Durable, crash-tolerant persistent job ledger for 6Clips production jobs."""

import asyncio
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from backend.config import DATA_DIR
from backend.production_jobs.types import (
    ErrorClassification,
    JobRecord,
    OutputCheckpoint,
    RecoveryClassification,
    StateTransitionRecord,
    _utc_now_iso,
)

logger = logging.getLogger(__name__)


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 hash of a file by streaming chunks."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def verify_physical_media_file(file_path: Path) -> Tuple[bool, Optional[str], Optional[int]]:
    """Verify that a media artifact exists physically, has non-zero size, and compute its hash."""
    if not file_path.exists():
        return False, None, None
    try:
        size = file_path.stat().st_size
        if size <= 0:
            return False, None, 0
        sha = compute_sha256(file_path)
        return True, sha, size
    except Exception as ex:
        logger.warning("Error verifying physical media file %s: %s", file_path, ex)
        return False, None, None


class PersistentJobLedger:
    """Thread-safe, crash-tolerant persistent ledger storing immutable job identities,
    state transitions, output checkpoints, physical artifact refs, and idempotency fingerprints.
    """

    def __init__(self, storage_dir: Optional[Path] = None):
        self._base_dir = storage_dir or (DATA_DIR / "production_jobs")
        self._jobs_dir = self._base_dir / "jobs"
        self._fingerprints_dir = self._base_dir / "fingerprints"
        self._artifacts_dir = self._base_dir / "artifacts"
        self._ensure_dirs()
        self._lock = asyncio.Lock()

    def _ensure_dirs(self) -> None:
        self._jobs_dir.mkdir(parents=True, exist_ok=True)
        self._fingerprints_dir.mkdir(parents=True, exist_ok=True)
        self._artifacts_dir.mkdir(parents=True, exist_ok=True)

    def _atomic_write_json(self, target_path: Path, data: Any) -> None:
        """Write JSON atomically to disk using a temporary file and replace."""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target_path.parent / f"{target_path.name}.tmp.{uuid4().hex[:8]}"
        serialized = json.dumps(data, indent=2, default=str)
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(serialized)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, target_path)

    # -------------------------------------------------------------------------
    # Idempotency and Fingerprints
    # -------------------------------------------------------------------------

    def register_fingerprint(self, fingerprint: str, job_id: str) -> None:
        """Map request fingerprint to job_id atomically."""
        fp_path = self._fingerprints_dir / f"{fingerprint}.json"
        self._atomic_write_json(fp_path, {"job_id": job_id, "created_at": _utc_now_iso()})

    def get_job_id_by_fingerprint(self, fingerprint: str) -> Optional[str]:
        """Lookup job_id from fingerprint."""
        fp_path = self._fingerprints_dir / f"{fingerprint}.json"
        if fp_path.exists():
            try:
                data = json.loads(fp_path.read_text(encoding="utf-8"))
                return data.get("job_id")
            except Exception as ex:
                logger.warning("Failed reading fingerprint %s: %s", fingerprint, ex)
        return None

    # -------------------------------------------------------------------------
    # Artifact Registry
    # -------------------------------------------------------------------------

    def register_artifact(
        self,
        artifact_id: str,
        file_path: Path,
        file_hash: Optional[str] = None,
        file_size: Optional[int] = None,
    ) -> None:
        """Register artifact location and verification metadata."""
        art_path = self._artifacts_dir / f"{artifact_id}.json"
        data = {
            "artifact_id": artifact_id,
            "file_path": str(file_path.resolve()),
            "file_hash": file_hash,
            "file_size": file_size,
            "registered_at": _utc_now_iso(),
        }
        self._atomic_write_json(art_path, data)

    def resolve_artifact_path(self, artifact_id: str) -> Optional[Path]:
        """Resolve artifact ID to verified physical file on disk."""
        art_path = self._artifacts_dir / f"{artifact_id}.json"
        if not art_path.exists():
            return None
        try:
            data = json.loads(art_path.read_text(encoding="utf-8"))
            raw_path = data.get("file_path")
            if not raw_path:
                return None
            p = Path(raw_path)
            if p.exists() and p.stat().st_size > 0:
                return p
            logger.warning("Artifact %s path %s does not physically exist or is 0 bytes", artifact_id, raw_path)
            return None
        except Exception as ex:
            logger.warning("Failed resolving artifact %s: %s", artifact_id, ex)
            return None

    # -------------------------------------------------------------------------
    # Job CRUD and Checkpointing
    # -------------------------------------------------------------------------

    def create_job(
        self,
        job_id: str,
        request_fingerprint: str,
        run_id: str,
        immutable_request: Dict[str, Any],
        output_ids: List[str],
        contract_id: Optional[str] = None,
        project_id: Optional[str] = None,
        user_id: str = "local",
        status: str = "PENDING",
    ) -> JobRecord:
        """Create and atomically persist a new JobRecord."""
        checkpoints: Dict[str, OutputCheckpoint] = {}
        for out_id in output_ids:
            checkpoints[out_id] = OutputCheckpoint(
                output_id=out_id,
                state="PENDING",
                attempts=0,
                max_attempts=3,
            )

        job = JobRecord(
            job_id=job_id,
            request_fingerprint=request_fingerprint,
            run_id=run_id,
            contract_id=contract_id,
            project_id=project_id,
            user_id=user_id,
            status=status,
            immutable_request=immutable_request,
            output_checkpoints=checkpoints,
            transitions=[
                StateTransitionRecord(
                    from_state="NONE",
                    to_state=status,
                    detail=f"Job initialized with {len(output_ids)} outputs",
                )
            ],
        )
        self.save_job(job)
        self.register_fingerprint(request_fingerprint, job_id)
        return job

    def save_job(self, job: JobRecord) -> None:
        """Persist JobRecord atomically."""
        job.updated_at = _utc_now_iso()
        target = self._jobs_dir / f"{job.job_id}.json"
        self._atomic_write_json(target, job.model_dump())

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        """Load JobRecord from disk."""
        target = self._jobs_dir / f"{job_id}.json"
        if not target.exists():
            return None
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
            return JobRecord.model_validate(data)
        except Exception as ex:
            logger.warning("Failed loading job %s: %s", job_id, ex)
            return None

    def list_jobs(self, user_id: Optional[str] = None) -> List[JobRecord]:
        """List all persisted jobs, optionally filtered by user_id for multi-user isolation."""
        jobs: List[JobRecord] = []
        for p in self._jobs_dir.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                rec = JobRecord.model_validate(data)
                if user_id is None or rec.user_id == user_id:
                    jobs.append(rec)
            except Exception as ex:
                logger.warning("Failed loading job record from %s: %s", p, ex)
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    def record_transition(self, job_id: str, new_status: str, detail: Optional[str] = None) -> Optional[JobRecord]:
        """Record status transition and persist."""
        job = self.get_job(job_id)
        if not job:
            return None
        old_status = job.status
        if old_status != new_status:
            job.status = new_status
            job.transitions.append(
                StateTransitionRecord(
                    from_state=old_status,
                    to_state=new_status,
                    detail=detail,
                )
            )
            self.save_job(job)
        return job

    def checkpoint_output_start(self, job_id: str, output_id: str) -> Optional[JobRecord]:
        """Checkpoint output execution start, incrementing attempts."""
        job = self.get_job(job_id)
        if not job:
            return None
        cp = job.output_checkpoints.get(output_id)
        if not cp:
            cp = OutputCheckpoint(output_id=output_id)
            job.output_checkpoints[output_id] = cp
        cp.state = "PROCESSING"
        cp.attempts += 1
        cp.updated_at = _utc_now_iso()
        self.save_job(job)
        return job

    def checkpoint_output_success(
        self,
        job_id: str,
        output_id: str,
        artifact_id: str,
        file_path: Path,
        file_hash: str,
        file_size: int,
    ) -> Optional[JobRecord]:
        """Checkpoint output success with verified physical media metadata."""
        job = self.get_job(job_id)
        if not job:
            return None
        cp = job.output_checkpoints.get(output_id)
        if not cp:
            cp = OutputCheckpoint(output_id=output_id)
            job.output_checkpoints[output_id] = cp
        cp.state = "SUCCEEDED"
        cp.artifact_id = artifact_id
        cp.file_path = str(file_path.resolve())
        cp.file_hash = file_hash
        cp.file_size_bytes = file_size
        cp.error_detail = None
        cp.error_classification = None
        cp.recovery_action = None
        cp.updated_at = _utc_now_iso()

        if f"artifact:{artifact_id}" not in job.evidence_refs:
            job.evidence_refs.append(f"artifact:{artifact_id}")
        effect = f"rendered_clip:{output_id}:{artifact_id}"
        if effect not in job.attempted_effects:
            job.attempted_effects.append(effect)

        self.save_job(job)
        self.register_artifact(artifact_id, file_path, file_hash, file_size)
        return job

    def checkpoint_output_failure(
        self,
        job_id: str,
        output_id: str,
        error_detail: str,
        error_classification: ErrorClassification,
        recovery_classification: RecoveryClassification,
    ) -> Optional[JobRecord]:
        """Checkpoint output failure with error classification."""
        job = self.get_job(job_id)
        if not job:
            return None
        cp = job.output_checkpoints.get(output_id)
        if not cp:
            cp = OutputCheckpoint(output_id=output_id)
            job.output_checkpoints[output_id] = cp
        cp.state = "FAILED"
        cp.error_detail = error_detail
        cp.error_classification = error_classification.value
        cp.recovery_action = recovery_classification.value
        cp.updated_at = _utc_now_iso()
        self.save_job(job)
        return job

    def checkpoint_output_cancelled(self, job_id: str, output_id: str) -> Optional[JobRecord]:
        """Checkpoint output cancelled."""
        job = self.get_job(job_id)
        if not job:
            return None
        cp = job.output_checkpoints.get(output_id)
        if not cp:
            cp = OutputCheckpoint(output_id=output_id)
            job.output_checkpoints[output_id] = cp
        if cp.state != "SUCCEEDED":
            cp.state = "CANCELLED"
            cp.updated_at = _utc_now_iso()
        self.save_job(job)
        return job

    # -------------------------------------------------------------------------
    # Startup Reconciliation & Crash Recovery
    # -------------------------------------------------------------------------

    def reconcile_active_jobs(self) -> List[JobRecord]:
        """Reconcile all persisted jobs after worker restart or process crash.
        
        Scans for jobs left in RUNNING / PROCESSING status. Validates physical artifacts
        on disk, cleans corrupted 0-byte outputs, marks uncompleted items as interrupted,
        and transitions the job to PARTIAL or BLOCKED with recovery instructions.
        """
        reconciled: List[JobRecord] = []
        for job in self.list_jobs():
            if job.status not in ("RUNNING", "PENDING"):
                # Also verify complete jobs have real artifacts
                if job.status == "COMPLETE":
                    all_intact = True
                    for out_id, cp in job.output_checkpoints.items():
                        if cp.state == "SUCCEEDED" and cp.file_path:
                            is_valid, _, _ = verify_physical_media_file(Path(cp.file_path))
                            if not is_valid:
                                logger.warning("Job %s artifact %s missing on disk! Reconciling to PARTIAL", job.job_id, out_id)
                                cp.state = "FAILED"
                                cp.error_classification = ErrorClassification.CORRUPTED_ARTIFACT.value
                                cp.recovery_action = RecoveryClassification.SAFE_RETRY.value
                                all_intact = False
                    if not all_intact:
                        job.status = "PARTIAL"
                        job.transitions.append(
                            StateTransitionRecord(
                                from_state="COMPLETE",
                                to_state="PARTIAL",
                                detail="Degraded from COMPLETE: one or more output files were missing on disk.",
                            )
                        )
                        self.save_job(job)
                        reconciled.append(job)
                continue

            # Job was interrupted mid-flight by restart/crash!
            logger.info("Reconciling interrupted job %s (previous status: %s)", job.job_id, job.status)
            succeeded_count = 0
            total_count = len(job.output_checkpoints)

            for out_id, cp in job.output_checkpoints.items():
                if cp.state == "SUCCEEDED" and cp.file_path:
                    is_valid, sha, size = verify_physical_media_file(Path(cp.file_path))
                    if is_valid:
                        succeeded_count += 1
                        continue
                    else:
                        cp.state = "FAILED"
                        cp.error_detail = "Artifact missing or 0 bytes after restart."
                        cp.error_classification = ErrorClassification.CORRUPTED_ARTIFACT.value
                        cp.recovery_action = RecoveryClassification.SAFE_RETRY.value

                elif cp.state in ("PROCESSING", "PENDING"):
                    # Was in flight when crash happened
                    if cp.file_path:
                        p = Path(cp.file_path)
                        if p.exists():
                            # Remove incomplete corrupt render from interrupted process
                            try:
                                p.unlink(missing_ok=True)
                            except Exception:
                                pass
                    cp.state = "FAILED"
                    cp.error_detail = "Process crash or host restart interrupted render."
                    cp.error_classification = ErrorClassification.INTERRUPTED_CRASH.value
                    cp.recovery_action = RecoveryClassification.RESUME.value

            # Determine aggregate reconciled status
            old_status = job.status
            if succeeded_count == total_count and total_count > 0:
                job.status = "COMPLETE"
            elif succeeded_count > 0:
                job.status = "PARTIAL"
                job.blockers.append({
                    "code": "PARTIAL_RECOVERED_AFTER_RESTART",
                    "precise_reason": f"{succeeded_count}/{total_count} outputs verified intact. Remaining interrupted by restart.",
                    "next_action": "Resume execution to complete remaining pending outputs.",
                })
            else:
                job.status = "BLOCKED"
                job.blockers.append({
                    "code": "INTERRUPTED_BEFORE_OUTPUTS",
                    "precise_reason": "Process restarted before any outputs completed rendering.",
                    "next_action": "Resume or resubmit batch execution.",
                })

            job.transitions.append(
                StateTransitionRecord(
                    from_state=old_status,
                    to_state=job.status,
                    detail=f"Reconciled on process startup: {succeeded_count}/{total_count} outputs verified.",
                )
            )
            self.save_job(job)
            reconciled.append(job)

        return reconciled
