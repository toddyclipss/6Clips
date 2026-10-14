# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Production Acceptance API Routes (Wave 9 / Checkpoint C & D).

Exposes verifiable production acceptance endpoints:
- GET  /api/acceptance/status      - Returns live gate readiness states for GT-05, GT-06, GT-07
- GET  /api/acceptance/protocol    - Protocol specifications and directory requirements
- POST /api/acceptance/gt05        - Runs V1 Gameplay Orchestrator on real source media
- POST /api/acceptance/gt06        - Runs V3 Long-Form Orchestrator on real source media
- POST /api/acceptance/gt07        - Runs V2 Multi-Source Orchestrator on real source media
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.production_acceptance.contracts import (
    RightsVerificationStatus,
    SourceMediaAsset,
)
from backend.production_acceptance.registry import ProductionAcceptanceRegistry
from backend.production_acceptance.protocol import get_acceptance_protocol_spec
from backend.production_acceptance.orchestration import (
    V1GameplayOrchestrator,
    V2MultiSourceOrchestrator,
    V3LongFormOrchestrator,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/acceptance", tags=["acceptance"])


class GT05VerificationRequest(BaseModel):
    source_file_path: str
    project_id: str = "proj_gt05_eval"
    rights_status: str = "authorized_user_media"
    permitted_uses: List[str] = Field(default_factory=lambda: ["creator_edit", "social_distribution"])
    is_real_user_media: bool = False


class GT06VerificationRequest(BaseModel):
    source_file_path: str
    project_id: str = "proj_gt06_eval"
    rights_status: str = "authorized_user_media"
    permitted_uses: List[str] = Field(default_factory=lambda: ["creator_edit", "social_distribution"])
    is_real_user_media: bool = False


class GT07VerificationRequest(BaseModel):
    source_file_paths: List[str]
    project_id: str = "proj_gt07_eval"
    rights_status: str = "authorized_user_media"
    permitted_uses: List[str] = Field(default_factory=lambda: ["creator_edit", "social_distribution"])
    is_real_user_media: bool = False


@router.get("/status")
async def get_acceptance_status():
    """Returns grounded truth matrix for production acceptance gates."""
    return ProductionAcceptanceRegistry.get_all_gate_statuses()


@router.get("/protocol")
async def get_acceptance_protocol():
    """Returns acceptance protocol specifications and physical paths."""
    return get_acceptance_protocol_spec()


@router.post("/gt05")
async def verify_gt05_production_path(req: GT05VerificationRequest):
    """Executes V1 gameplay production acceptance on candidate media."""
    p = Path(req.source_file_path)
    if ".." in req.source_file_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path traversal prohibited")
    if not p.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Source file not found: {req.source_file_path}")

    source = SourceMediaAsset(
        source_id="src_gt05_request",
        file_path=str(p),
        rights_status=RightsVerificationStatus(req.rights_status),
        permitted_uses=req.permitted_uses,
    )
    orch = V1GameplayOrchestrator(project_id=req.project_id)
    contract = orch.build_contract(source, is_real_user_media=req.is_real_user_media)
    result = orch.evaluate_acceptance(contract)
    return result.to_dict()


@router.post("/gt06")
async def verify_gt06_production_path(req: GT06VerificationRequest):
    """Executes V3 long-form narrative production acceptance on candidate media."""
    p = Path(req.source_file_path)
    if ".." in req.source_file_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path traversal prohibited")
    if not p.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Source file not found: {req.source_file_path}")

    source = SourceMediaAsset(
        source_id="src_gt06_request",
        file_path=str(p),
        rights_status=RightsVerificationStatus(req.rights_status),
        permitted_uses=req.permitted_uses,
    )
    orch = V3LongFormOrchestrator(project_id=req.project_id)
    contract = orch.build_contract(source, is_real_user_media=req.is_real_user_media)
    result = orch.evaluate_acceptance(contract)
    return result.to_dict()


@router.post("/gt07")
async def verify_gt07_production_path(req: GT07VerificationRequest):
    """Executes V2 multi-source production acceptance on candidate media."""
    sources = []
    for i, path_str in enumerate(req.source_file_paths):
        p = Path(path_str)
        if ".." in path_str:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path traversal prohibited")
        if not p.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Source file not found: {path_str}")
        sources.append(SourceMediaAsset(
            source_id=f"src_gt07_{i+1}",
            file_path=str(p),
            rights_status=RightsVerificationStatus(req.rights_status),
            permitted_uses=req.permitted_uses,
        ))

    orch = V2MultiSourceOrchestrator(project_id=req.project_id)
    contract = orch.build_contract(sources, is_real_user_media=req.is_real_user_media)
    result = orch.evaluate_acceptance(contract)
    return result.to_dict()
