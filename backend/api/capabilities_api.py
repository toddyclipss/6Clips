# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Capabilities REST API: exposes registered deterministic and agent capabilities through ExecutorService."""
import json
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db, AsyncSessionLocal
from backend.core.capabilities import CapabilityRegistry
from backend.services.executor_service import ExecutorService
from backend.core.exceptions import (
    CapabilityPreconditionError,
    AuthorizationRequiredError,
    VerificationError,
    CapabilityExecutionError,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/capabilities", tags=["capabilities"])


@router.get("")
async def list_capabilities():
    """List all registered capabilities in the system."""
    caps = CapabilityRegistry.all()
    return {
        "capabilities": [
            {
                "name": c.name,
                "description": c.description,
                "surface": c.surface,
                "required_params": c.required_params,
                "optional_params": c.optional_params,
                "idempotent": c.idempotent,
                "requires_authorization": c.requires_authorization,
            }
            for c in caps
        ]
    }


@router.post("/{capability_name}/execute")
async def execute_capability(capability_name: str, body: dict = None):
    """
    Execute a capability via ExecutorService within a tracked ExecutionRun.
    Applies input validation, policy verification, and returns verified execution output.
    """
    payload = body or {}
    project_id = payload.get("project_id")
    user_id = payload.get("user_id", "local")

    try:
        # Validate capability presence and arguments
        cap = CapabilityRegistry.validate_input(capability_name, payload)

        run = await ExecutorService.create_run(
            objective=f"Direct execution of capability '{capability_name}'",
            project_id=project_id,
            user_id=user_id,
        )

        res = await ExecutorService.execute_step(
            run_id=run.id,
            step_name=f"Execute {capability_name}",
            capability_name=capability_name,
            payload=payload,
            user_id=user_id,
            authorized=True,
        )

        await ExecutorService.complete_run(
            run_id=run.id,
            status="completed",
            context_data={"capability": capability_name},
        )

        return {
            "run_id": run.id,
            "step_id": res["step_id"],
            "status": res["status"],
            "output": res["output"],
            "verification": res["verification"],
        }
    except (CapabilityPreconditionError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AuthorizationRequiredError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except VerificationError as e:
        raise HTTPException(status_code=422, detail=f"Verification failed: {e}")
    except CapabilityExecutionError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("Failed executing capability '%s': %s", capability_name, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Capability execution failed: {e}")
