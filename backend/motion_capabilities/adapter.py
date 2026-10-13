# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Motion Tool-Runner compatibility adapter with CAS revision mutation enforcement."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union
from uuid import uuid4

from fastapi import HTTPException

from backend.core.exceptions import RevisionConflictError
from backend.services.project_service import ProjectService
from .dispatcher import MotionCapabilityDispatcher
from .models import CapabilityExecutionResult

logger = logging.getLogger(__name__)


class StaleRevisionConflictError(Exception):
    """Raised when expected revision does not match current authoritative project revision."""
    pass


class MotionToolRunnerAdapter:
    """Bridges historical tool runners and Main Agent automation into canonical ProjectRevisions."""

    @classmethod
    async def execute_tool_with_cas_revision(
        cls,
        project_id: str,
        expected_revision: int,
        tool_name: str,
        params: Optional[Dict[str, Any]] = None,
        input_path: Optional[Union[str, Path]] = None,
        author: str = "motion_agent",
        user_id: str = "local",
    ) -> Dict[str, Any]:
        """Execute a tool operation and atomically mutate the project document via CAS revision.

        Raises:
            HTTPException(409): If expected_revision does not match current project revision.
            HTTPException(404): If project does not exist.
        """
        params = params or {}

        # 1. Fetch current project state
        proj = await ProjectService.get_project(project_id)
        if not proj:
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")

        # 2. Strict CAS concurrency check (Mandate 6)
        if proj.revision != expected_revision:
            logger.warning(
                "CAS Revision mismatch for project %s: expected %d, authoritative is %d",
                project_id, expected_revision, proj.revision
            )
            raise HTTPException(
                status_code=409,
                detail=f"Stale revision conflict: current authoritative revision is {proj.revision}, requested was {expected_revision}."
            )

        # 3. Parse project document and dispatch capability
        project_doc = json.loads(proj.document_json) if isinstance(proj.document_json, str) else (proj.document_json or {})
        dispatch_res = await MotionCapabilityDispatcher.dispatch(
            capability_id=tool_name,
            input_path=input_path,
            params=params,
            project_doc=project_doc,
        )

        if dispatch_res.status != "SUCCESS":
            return {
                "success": False,
                "status": dispatch_res.status,
                "message": dispatch_res.message,
                "error_detail": dispatch_res.error_detail,
                "revision": proj.revision,
            }

        # 4. Extract updated project document
        updated_doc = dispatch_res.output_data.get("project_doc") if dispatch_res.output_data else None
        new_revision = proj.revision

        if updated_doc:
            # Atomically commit canonical revision via apply_operation
            try:
                update_outcome = await ProjectService.apply_operation(
                    project_id=proj.id,
                    expected_revision=proj.revision,
                    operation_type="update_document",
                    payload={"document": updated_doc},
                    idempotency_key=f"tool_exec_{tool_name}_{uuid4().hex[:8]}",
                    author=author,
                )
                new_revision = update_outcome["revision"]
            except RevisionConflictError as rce:
                raise HTTPException(
                    status_code=409,
                    detail=f"Stale revision conflict: {rce}"
                )

        return {
            "success": True,
            "status": "SUCCESS",
            "message": dispatch_res.message,
            "output_path": dispatch_res.output_path,
            "output_data": dispatch_res.output_data,
            "previous_revision": expected_revision,
            "current_revision": new_revision,
        }

