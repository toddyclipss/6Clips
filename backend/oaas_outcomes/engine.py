# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Outcome Delivery Engine.
Core orchestration engine implementing Outcome-as-a-Service (OAAS).
Provides idempotent task execution, durable disk persistence, crash resumability,
physical media verification, project revision registration, and fail-closed distribution handoff.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from backend.config import DATA_DIR, settings
from backend.database import AsyncSessionLocal
from backend.models.generated_video import GeneratedVideo
from backend.models.project import Project
from backend.models.project_revision import ProjectRevision
from backend.oaas_outcomes.block_selector import BlockSelector
from backend.oaas_outcomes.distribution_handoff import DistributionHandoffManager
from backend.oaas_outcomes.media_verifier import MediaVerificationError, MediaVerifier
from backend.oaas_outcomes.models import (
    Agent5DistributionHandoffContract,
    MediaVerificationResult,
    OutcomeJobRecord,
    OutcomeJobState,
    OutcomePlan,
    OutcomeRequestContract,
)
from backend.oaas_outcomes.state_machine import OutcomeStateMachine
from backend.original_creation.models import (
    EvidenceLedger,
    OriginalCompositionSpec,
    OriginalCreationStatus,
    ShotListEntry,
    TeleprompterScript,
    VoiceInputRequirement,
)
from backend.original_creation.renderer import OriginalVideoRenderer
from backend.services.project_service import ProjectService

logger = logging.getLogger(__name__)


class OutcomeDeliveryEngine:
    """Orchestrates end-to-end outcome delivery with durable job persistence and auditability."""

    _active_jobs: Dict[str, OutcomeJobRecord] = {}
    _idempotency_index: Dict[str, str] = {}  # idempotency_token -> job_id

    @classmethod
    def _storage_dir(cls) -> Path:
        base = settings.STORAGE_ROOT / "oaas_outcomes" / "jobs"
        base.mkdir(parents=True, exist_ok=True)
        return base

    @classmethod
    def _save_job(cls, record: OutcomeJobRecord) -> None:
        """Persist job state to durable JSON storage."""
        try:
            p = cls._storage_dir() / f"{record.job_id}.json"
            p.write_text(record.model_dump_json(indent=2), encoding="utf-8")
            cls._active_jobs[record.job_id] = record
            if record.request and record.request.idempotency_token:
                cls._idempotency_index[record.request.idempotency_token] = record.job_id
        except Exception as ex:
            logger.warning("Failed to persist OAAS job %s: %s", record.job_id, ex)

    @classmethod
    def load_job(cls, job_id: str) -> Optional[OutcomeJobRecord]:
        """Load job from memory or disk storage."""
        if job_id in cls._active_jobs:
            return cls._active_jobs[job_id]
        p = cls._storage_dir() / f"{job_id}.json"
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                record = OutcomeJobRecord.model_validate(data)
                cls._active_jobs[record.job_id] = record
                if record.request and record.request.idempotency_token:
                    cls._idempotency_index[record.request.idempotency_token] = record.job_id
                return record
            except Exception as ex:
                logger.warning("Failed to load OAAS job %s: %s", job_id, ex)
        return None

    @classmethod
    def find_by_idempotency_token(cls, token: str) -> Optional[OutcomeJobRecord]:
        """Check for existing job with matching idempotency token."""
        if token in cls._idempotency_index:
            return cls.load_job(cls._idempotency_index[token])
        # Scan disk files
        for f in cls._storage_dir().glob("*.json"):
            rec = cls.load_job(f.stem)
            if rec and rec.request and rec.request.idempotency_token == token:
                return rec
        return None

    @classmethod
    async def execute_outcome(
        cls,
        request: OutcomeRequestContract,
        allow_test_fixture: bool = False,
    ) -> OutcomeJobRecord:
        """
        Execute full end-to-end outcome workflow from high-level goal to verified delivery.
        Ensures idempotency, real physical rendering, media verification, and fail-closed handoff.
        """
        # 1. Idempotency check: prevent duplicate dispatches
        existing = cls.find_by_idempotency_token(request.idempotency_token)
        if existing:
            logger.info(
                "Idempotency hit: Reusing existing job %s for token %s (state: %s)",
                existing.job_id,
                request.idempotency_token,
                existing.state.value,
            )
            return existing

        # Create new job record in REQUESTED state
        job_record = OutcomeJobRecord(
            request=request,
            state=OutcomeJobState.REQUESTED,
        )
        sm = OutcomeStateMachine(job_record)
        cls._save_job(job_record)

        try:
            # Step 2: PLAN
            pref = request.minimal_preferences or {}
            aspect = pref.get("aspect_ratio", "9:16")
            dur = float(pref.get("duration_seconds", 60.0))
            category_pref = pref.get("category")
            requested_block = pref.get("block_id")

            block_id, cat, rationale = BlockSelector.select_operable_block(
                intent_text=request.user_intent,
                preferred_category=category_pref,
                requested_block_id=requested_block,
            )

            plan = OutcomePlan(
                selected_block_id=block_id,
                block_category=cat,
                creative_treatment=rationale,
                aspect_ratio=aspect,
                duration_seconds=dur,
            )
            job_record.plan = plan
            sm.transition_to(OutcomeJobState.PLANNED, reason=rationale)
            cls._save_job(job_record)

            # Step 3: PRODUCE (Project creation/lookup & timeline structure)
            sm.transition_to(OutcomeJobState.PRODUCING, reason="Constructing or retrieving versioned project and timeline")
            cls._save_job(job_record)

            title_candidate = f"OAAS - {request.user_intent[:40]}"
            if request.project_id:
                project = await ProjectService.get_project(request.project_id)
                logger.info("Reusing existing project %s at revision %d", project.id, project.revision)
            else:
                project = await ProjectService.create_project(
                    name=title_candidate,
                    aspect_ratio=aspect,
                    user_id=request.user_id,
                )

            # Apply any requested native editor actions directly on the canonical project
            if request.editor_actions:
                from backend.oaas_motion_actions.adapter import OAASMotionActionAdapter
                batch_res = await OAASMotionActionAdapter.batch_execute(
                    project_id=project.id,
                    commands=request.editor_actions,
                    author="main_agent",
                    user_id=request.user_id,
                )
                project = await ProjectService.get_project(project.id)
                logger.info("Applied %d native editor actions; project %s at revision %d", len(batch_res), project.id, project.revision)

            job_record.project_id = project.id
            job_record.revision_id = project.revision
            cls._save_job(job_record)

            # Step 4: RENDER (Physical MP4 generation via OriginalVideoRenderer)
            word_count = max(10, int(dur * 2.5))
            spoken_text = (
                f"{request.user_intent}. Analyzing high-density insights and essential details. "
                f"Featuring visual presentation with {block_id} motion design."
            )

            spec = OriginalCompositionSpec(
                title=title_candidate,
                topic=request.user_intent,
                target_duration_sec=int(dur),
                aspect_ratio=aspect,
                language=pref.get("language", "en"),
                evidence_ledger=EvidenceLedger(
                    topic=request.user_intent,
                    primary_claim=f"Verified automated composition with {block_id}",
                ),
                spoken_script=TeleprompterScript(
                    spoken_text=spoken_text,
                    word_count=word_count,
                    estimated_read_time_seconds=int(dur),
                ),
                shot_list=[
                    ShotListEntry(
                        scene_number=1,
                        timecode_start_sec=0.0,
                        timecode_end_sec=dur,
                        visual_description=f"Scene rendered with {block_id} dynamic motion",
                        overlay_text=title_candidate,
                        motion_template_id=block_id,
                    )
                ],
                voice_requirement=VoiceInputRequirement.PROCEDURAL_SYNTHESIS_ALLOWED,
            )

            if allow_test_fixture:
                import os
                os.environ["VIRALMINT_TEST_AUDIO_FIXTURE"] = "1"

            render_result_spec = await OriginalVideoRenderer.render_composition(spec)

            if render_result_spec.status != OriginalCreationStatus.RENDERED or not render_result_spec.rendered_result:
                err_msg = render_result_spec.status_reason or "Physical render failed to produce output"
                sm.transition_to(OutcomeJobState.FAILED, reason="Render failed", error_detail=err_msg)
                cls._save_job(job_record)
                return job_record

            rendered_mp4_path = Path(render_result_spec.rendered_result.video_path)
            sm.transition_to(OutcomeJobState.RENDERED, reason="Physical MP4 render complete")
            cls._save_job(job_record)

            # Step 5: VERIFY (Rigorous ffprobe & SHA-256 validation)
            verification = MediaVerifier.verify_media_file(
                media_path=rendered_mp4_path,
                expected_aspect_ratio=aspect,
                min_duration_sec=min(dur, 2.0),
                raise_on_failure=True,
            )
            sm.transition_to(
                OutcomeJobState.VERIFIED,
                reason="Physical media verified with ffprobe and SHA-256",
                verification_result=verification,
            )
            job_record.media_verification = verification
            cls._save_job(job_record)

            # Step 6: PERSIST TO LIBRARY
            lib_asset_id = str(uuid4())
            async with AsyncSessionLocal() as db:
                gen_video = GeneratedVideo(
                    id=lib_asset_id,
                    user_id=request.user_id,
                    title=title_candidate,
                    script=spoken_text,
                    niche=cat,
                    video_path=str(rendered_mp4_path),
                    aspect_ratio=aspect,
                    duration_seconds=int(verification.probe_duration_sec),
                    gen_tier="oaas_outcome",
                )
                db.add(gen_video)
                await db.commit()

            job_record.library_asset_id = lib_asset_id
            cls._save_job(job_record)

            # Step 7: DISTRIBUTION HANDOFF CHECK
            target_dest = request.permitted_channel_targets[0] if request.permitted_channel_targets else "youtube_shorts"
            handoff = await DistributionHandoffManager.prepare_handoff_contract(
                job_id=job_record.job_id,
                idempotency_token=request.idempotency_token,
                render_file_sha256=verification.sha256_hash,
                media_path=str(rendered_mp4_path),
                project_id=project.id,
                revision_id=project.revision,
                destination_channel=target_dest,
                user_id=request.user_id,
                user_authorized=request.standing_authorization,
            )
            job_record.distribution_handoff = handoff

            # Guarded linear transition based on real credentials & authorization
            if handoff.fail_closed:
                if handoff.provider_status in ("PENDING_CREDENTIALS", "NOT_CONNECTED"):
                    sm.transition_to(
                        OutcomeJobState.PENDING_CREDENTIALS,
                        reason="Target distribution provider credentials missing or not connected",
                        error_detail=handoff.error_truth,
                    )
                else:
                    sm.transition_to(
                        OutcomeJobState.NEEDS_APPROVAL,
                        reason="Standing authorization not set; explicit approval required before delivery",
                    )
            else:
                sm.transition_to(
                    OutcomeJobState.READY_FOR_DELIVERY,
                    reason="Media verified, library indexed, and channel connected with authorization",
                )

            cls._save_job(job_record)
            return job_record

        except Exception as exc:
            logger.exception("Outcome delivery failed for job %s: %s", job_record.job_id, exc)
            if sm.can_transition_to(OutcomeJobState.FAILED):
                sm.transition_to(OutcomeJobState.FAILED, reason="Execution exception", error_detail=str(exc))
            else:
                job_record.state = OutcomeJobState.FAILED
                job_record.error_truth = str(exc)
            cls._save_job(job_record)
            return job_record

    @classmethod
    async def retry_job(cls, job_id: str, allow_test_fixture: bool = False) -> OutcomeJobRecord:
        """Idempotently retry a failed job if retry limits have not been exhausted."""
        job = cls.load_job(job_id)
        if not job:
            raise ValueError(f"Job '{job_id}' not found.")

        if job.retries_count >= job.max_retries:
            raise ValueError(f"Job '{job_id}' exceeded maximum retries ({job.max_retries}).")

        job.retries_count += 1
        sm = OutcomeStateMachine(job)
        if sm.can_transition_to(OutcomeJobState.REQUESTED):
            sm.transition_to(OutcomeJobState.REQUESTED, reason=f"Idempotent retry attempt {job.retries_count}")
        else:
            job.state = OutcomeJobState.REQUESTED

        cls._save_job(job)
        return await cls.execute_outcome(job.request, allow_test_fixture=allow_test_fixture)

    @classmethod
    def cancel_job(cls, job_id: str, reason: str = "User requested cancellation") -> OutcomeJobRecord:
        """Cancel an in-progress or pending outcome job."""
        job = cls.load_job(job_id)
        if not job:
            raise ValueError(f"Job '{job_id}' not found.")

        sm = OutcomeStateMachine(job)
        if sm.can_transition_to(OutcomeJobState.CANCELLED):
            sm.transition_to(OutcomeJobState.CANCELLED, reason=reason)
            cls._save_job(job)
        return job

    @classmethod
    async def reconcile_job(cls, job_id: str) -> Optional[OutcomeJobRecord]:
        """
        Reconcile an interrupted or crashed job against physical files and database state.
        Ensures true crash-resumability without fake state transitions.
        """
        job = cls.load_job(job_id)
        if not job:
            return None

        # If job was in PRODUCING or RENDERED when interrupted:
        if job.state in (OutcomeJobState.PRODUCING, OutcomeJobState.RENDERED):
            # Check if project exists
            if job.project_id:
                async with AsyncSessionLocal() as db:
                    p = await db.get(Project, job.project_id)
                    if not p:
                        job.state = OutcomeJobState.FAILED
                        job.error_truth = "Reconciliation: Project record missing in database after crash."
                        cls._save_job(job)
                        return job

            # Check if rendered MP4 exists
            expected_dir = settings.GENERATED_DIR / f"original_orig-{job.job_id[-8:]}"
            found_mp4 = None
            if expected_dir.exists():
                for f in expected_dir.glob("*.mp4"):
                    if f.is_file() and f.stat().st_size > 1024:
                        found_mp4 = f
                        break

            if found_mp4:
                try:
                    verification = MediaVerifier.verify_media_file(found_mp4, raise_on_failure=False)
                    if verification.is_verified:
                        job.media_verification = verification
                        job.state = OutcomeJobState.VERIFIED
                        cls._save_job(job)
                        return job
                except Exception:
                    pass

            # If no media found and interrupted, mark FAILED with clear crash details
            job.state = OutcomeJobState.FAILED
            job.error_truth = "Worker process interrupted during physical render. Ready for idempotent retry."
            cls._save_job(job)

        return job

    @classmethod
    async def reconcile_all_active_jobs(cls) -> List[OutcomeJobRecord]:
        """Scan storage and reconcile all incomplete jobs."""
        reconciled = []
        for p in cls._storage_dir().glob("*.json"):
            job = cls.load_job(p.stem)
            if job and job.state in (OutcomeJobState.REQUESTED, OutcomeJobState.PLANNED, OutcomeJobState.PRODUCING, OutcomeJobState.RENDERED):
                rec = await cls.reconcile_job(job.job_id)
                if rec:
                    reconciled.append(rec)
        return reconciled
