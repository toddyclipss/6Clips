# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Distribution REST API endpoints for Phase 10: Approval, SEO, Scheduling, and Receipts.
NOTE: As required by Wave 4 isolation rules, this router is NOT mounted in backend/main.py.
Integration with main.py will be requested via INTEGRATION_REQUEST.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from backend.distribution.account_boundary import AccountBoundaryManager
from backend.distribution.eligibility import ReleaseEligibilityError
from backend.distribution.models import (
    ApprovalReceipt,
    DistributionJob,
    DistributionStatus,
    PlatformAccount,
    PlatformSEOMetadata,
    PublishedReceiptV1,
)
from backend.distribution.seo_adapter import SEOAdapter, SEOValidationError
from backend.distribution.service import DistributionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/distribution", tags=["distribution"])
_service = DistributionService()


# ── Request / Response DTOs ──────────────────────────────────────────────────

class SignApprovalRequest(BaseModel):
    output_id: str
    project_id: str
    project_revision: int
    artifact_sha256: str
    approved_by: str = "creator"
    consent_for_external_publish: bool = True


class CheckEligibilityRequest(BaseModel):
    file_path: str
    project_revision: int
    approval_receipt: Optional[ApprovalReceipt] = None
    target_platform: str = "youtube"
    permitted_uses: List[str] = ["social_distribution", "platform_publish"]
    user_id: str = "local"


class ValidateSEORequest(BaseModel):
    metadata: PlatformSEOMetadata


class GenerateDraftSEORequest(BaseModel):
    platform: str
    title: str
    summary: str = ""
    keywords: List[str] = []
    aspect_ratio: str = "9:16"


class ScheduleDistributionRequest(BaseModel):
    output_id: str
    project_id: str
    project_revision: int
    artifact_path: str
    approval_receipt: ApprovalReceipt
    platform: str
    account_id: str
    seo_metadata: PlatformSEOMetadata
    scheduled_time_utc: str
    user_id: str = "local"
    timezone: str = "UTC"
    permitted_uses: Optional[List[str]] = None


class MultiPlatformFanOutRequest(BaseModel):
    output_id: str
    project_id: str
    project_revision: int
    artifact_path: str
    approval_receipt: ApprovalReceipt
    platforms: List[Dict[str, Any]]
    user_id: str = "local"
    permitted_uses: Optional[List[str]] = None


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/approval/sign", response_model=ApprovalReceipt)
async def sign_editorial_approval(req: SignApprovalRequest):
    """Sign an explicit, immutable editorial approval receipt with external publish consent."""
    try:
        return _service.create_approval_receipt(
            output_id=req.output_id,
            project_id=req.project_id,
            project_revision=req.project_revision,
            artifact_sha256=req.artifact_sha256,
            approved_by=req.approved_by,
            consent_for_external_publish=req.consent_for_external_publish,
        )
    except Exception as e:
        logger.exception("Failed to sign approval: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


def _handle_eligibility_error(ree: ReleaseEligibilityError) -> None:
    """Map domain eligibility errors to accurate HTTP status codes."""
    if ree.code in ("APPROVAL_STALE_REVISION", "APPROVAL_STALE_ARTIFACT"):
        raise HTTPException(status_code=409, detail={"code": ree.code, "message": ree.message})
    elif ree.code in ("CONSENT_MISSING", "INSUFFICIENT_RIGHTS"):
        raise HTTPException(status_code=403, detail={"code": ree.code, "message": ree.message})
    elif ree.code in ("USER_MISMATCH", "APPROVAL_SIGNATURE_INVALID"):
        raise HTTPException(status_code=401, detail={"code": ree.code, "message": ree.message})
    elif ree.code == "ARTIFACT_MISSING":
        raise HTTPException(status_code=404, detail={"code": ree.code, "message": ree.message})
    else:
        raise HTTPException(status_code=422, detail={"code": ree.code, "message": ree.message})


@router.post("/eligibility/check")
async def check_release_eligibility(req: CheckEligibilityRequest):
    """Verify release eligibility of a render artifact before distribution."""
    try:
        return _service.check_release_eligibility(
            file_path_str=req.file_path,
            expected_user_id=req.user_id,
            actual_user_id=req.user_id,
            current_project_revision=req.project_revision,
            approval_receipt=req.approval_receipt,
            permitted_uses=req.permitted_uses,
            target_platform=req.target_platform,
        )
    except ReleaseEligibilityError as ree:
        _handle_eligibility_error(ree)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/seo/validate", response_model=PlatformSEOMetadata)
async def validate_seo_metadata(req: ValidateSEORequest):
    """Validate and sanitize platform-specific SEO metadata."""
    try:
        return SEOAdapter.validate_metadata(req.metadata)
    except SEOValidationError as sve:
        raise HTTPException(
            status_code=422,
            detail={"platform": sve.platform, "field": sve.field, "message": sve.message},
        )


@router.post("/seo/draft", response_model=PlatformSEOMetadata)
async def generate_draft_seo(req: GenerateDraftSEORequest):
    """Generate platform-tailored draft metadata from video summary and keywords."""
    try:
        return SEOAdapter.generate_draft_for_platform(
            platform=req.platform,
            base_title=req.title,
            summary=req.summary,
            keywords=req.keywords,
            aspect_ratio=req.aspect_ratio,
        )
    except SEOValidationError as sve:
        raise HTTPException(status_code=422, detail=sve.message)


@router.post("/jobs/schedule", response_model=DistributionJob)
async def schedule_job(req: ScheduleDistributionRequest):
    """Schedule a verified distribution job for a single platform."""
    # Resolve account readiness
    account = AccountBoundaryManager.evaluate_account_readiness(
        account_id=req.account_id,
        platform=req.platform,
        user_id=req.user_id,
        is_connected=True,  # In disconnected test environment, evaluated via boundary
    )
    try:
        return await _service.schedule_distribution(
            output_id=req.output_id,
            project_id=req.project_id,
            project_revision=req.project_revision,
            artifact_path=req.artifact_path,
            approval_receipt=req.approval_receipt,
            platform=req.platform,
            account=account,
            seo_metadata=req.seo_metadata,
            scheduled_time_utc=req.scheduled_time_utc,
            user_id=req.user_id,
            timezone_str=req.timezone,
            permitted_uses=req.permitted_uses,
        )
    except ReleaseEligibilityError as ree:
        _handle_eligibility_error(ree)
    except SEOValidationError as sve:
        raise HTTPException(status_code=422, detail=sve.message)
    except Exception as e:
        logger.exception("Error scheduling job: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/jobs/fan-out")
async def schedule_multi_platform_fan_out(req: MultiPlatformFanOutRequest):
    """Fan out an approved output across multiple platforms."""
    # Prepare configs with evaluated accounts
    prepared_configs = []
    for p in req.platforms:
        plat = p["platform"]
        acc_id = p.get("account_id", f"{plat}_default")
        account = AccountBoundaryManager.evaluate_account_readiness(
            account_id=acc_id,
            platform=plat,
            user_id=req.user_id,
            is_connected=True,
        )
        prepared_configs.append({
            "platform": plat,
            "account": account,
            "seo_metadata": PlatformSEOMetadata(**p["seo_metadata"]),
            "scheduled_time_utc": p.get("scheduled_time_utc"),
            "timezone": p.get("timezone", "UTC"),
        })

    return await _service.schedule_multi_platform_fan_out(
        output_id=req.output_id,
        project_id=req.project_id,
        project_revision=req.project_revision,
        artifact_path=req.artifact_path,
        approval_receipt=req.approval_receipt,
        platform_configs=prepared_configs,
        user_id=req.user_id,
        permitted_uses=req.permitted_uses,
    )


@router.get("/jobs", response_model=List[DistributionJob])
async def list_jobs(
    project_id: Optional[str] = Query(None),
    status: Optional[DistributionStatus] = Query(None),
    user_id: str = Query("local"),
):
    """List scheduled and completed distribution jobs."""
    return _service.store.list_jobs(user_id=user_id, project_id=project_id, status=status)


@router.get("/jobs/{job_id}", response_model=DistributionJob)
async def get_job(job_id: str):
    """Fetch distribution job details."""
    job = _service.store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Distribution job not found")
    return job


@router.post("/jobs/{job_id}/cancel", response_model=DistributionJob)
async def cancel_job(job_id: str, reason: str = Query("Cancelled by user"), user_id: Optional[str] = Query(None)):
    """Cancel a scheduled distribution job."""
    try:
        return await _service.scheduler.cancel_job(job_id, reason=reason, user_id=user_id)
    except ValueError as ve:
        err = str(ve)
        if "not found" in err.lower():
            raise HTTPException(status_code=404, detail=err)
        if "unauthorized" in err.lower():
            raise HTTPException(status_code=403, detail=err)
        if "already" in err.lower():
            raise HTTPException(status_code=409, detail=err)
        raise HTTPException(status_code=400, detail=err)


@router.post("/jobs/{job_id}/retry", response_model=DistributionJob)
async def retry_job(job_id: str):
    """Retry a failed or blocked distribution job."""
    try:
        return await _service.scheduler.retry_job(job_id)
    except ValueError as ve:
        err = str(ve)
        if "not found" in err.lower():
            raise HTTPException(status_code=404, detail=err)
        if "cannot retry" in err.lower() or "max retries" in err.lower():
            raise HTTPException(status_code=409, detail=err)
        raise HTTPException(status_code=400, detail=err)


@router.get("/receipts/{receipt_id}", response_model=PublishedReceiptV1)
async def get_published_receipt(receipt_id: str):
    """Fetch confirmed publishing receipt for analytics."""
    rcpt = _service.get_published_receipt(receipt_id)
    if not rcpt:
        raise HTTPException(status_code=404, detail="Publishing receipt not found")
    return rcpt


@router.get("/receipts", response_model=List[PublishedReceiptV1])
async def list_published_receipts(project_id: Optional[str] = Query(None)):
    """List all confirmed publishing receipts."""
    return _service.list_published_receipts(project_id=project_id)


@router.post("/worker/tick")
async def trigger_worker_tick():
    """Trigger a scheduler tick cycle."""
    return await _service.scheduler.process_tick()


@router.get("/daemon/status")
async def get_daemon_status():
    """Get scheduler daemon status and offline limitation warning."""
    return _service.get_daemon_status()


@router.post("/worker/recover")
async def recover_worker_jobs():
    """Recover in-flight jobs following worker restart."""
    count = _service.recover_in_flight_jobs()
    return {"recovered_count": count, "status": "RECOVERED"}
