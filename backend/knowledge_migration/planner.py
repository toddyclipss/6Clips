# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Project migration planner for legacy block dependencies."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from backend.knowledge_migration.detector import LegacyBlockDetector
from backend.knowledge_migration.inventory import DonorInventoryLedger, LEGACY_TO_NATIVE_MAPPING
from backend.knowledge_migration.models import (
    LegacyBlockRef,
    MigrationStatus,
    ProjectMigrationPlan,
    ProjectReadiness,
    ReplacementFeasibility,
    RiskLevel,
)


class ProjectMigrationPlanner:
    """Evaluates project readiness and plans safe migration to native motion v1."""

    def __init__(self, ledger: Optional[DonorInventoryLedger] = None):
        self.ledger = ledger or DonorInventoryLedger()

    def assess_project_readiness(
        self,
        project_id: str,
        project_name: str,
        revision: int,
        document_doc: Dict[str, Any]
    ) -> ProjectReadiness:
        """Assess migration readiness and risks for a single project."""
        legacy_blocks = LegacyBlockDetector.detect_in_project_doc(document_doc)
        if not legacy_blocks:
            return ProjectReadiness(
                project_id=project_id,
                project_name=project_name,
                current_revision=revision,
                has_legacy_blocks=False,
                legacy_block_count=0,
                legacy_slugs=[],
                risk_level=RiskLevel.LOW,
                feasibility=ReplacementFeasibility.FEASIBLE_DIRECT,
                status=MigrationStatus.READY,
                notes="Project has zero legacy block dependencies. Fully native."
            )

        slugs = sorted(list({b.block_id for b in legacy_blocks}))
        missing_assets: List[str] = []

        # Check media assets in project
        timeline = document_doc.get("timeline") or {}
        for track in timeline.get("tracks") or []:
            for clip in track.get("clips") or []:
                asset = clip.get("asset_file") or clip.get("file")
                if asset and "tmp" in str(asset).lower():
                    # Reference to temp files might be missing or ephemeral
                    missing_assets.append(str(asset))

        # Determine feasibility
        all_mapped = all(s in LEGACY_TO_NATIVE_MAPPING for s in slugs)
        has_custom = any(b.is_retired_custom for b in legacy_blocks)
        
        if all_mapped and len(slugs) == 1:
            feasibility = ReplacementFeasibility.FEASIBLE_DIRECT
            risk = RiskLevel.LOW
        elif all_mapped:
            feasibility = ReplacementFeasibility.FEASIBLE_COMPOSED
            risk = RiskLevel.MEDIUM
        else:
            feasibility = ReplacementFeasibility.FEASIBLE_NATIVE_FALLBACK
            risk = RiskLevel.HIGH if missing_assets else RiskLevel.MEDIUM

        if has_custom:
            risk = RiskLevel.MEDIUM

        return ProjectReadiness(
            project_id=project_id,
            project_name=project_name,
            current_revision=revision,
            has_legacy_blocks=True,
            legacy_block_count=len(legacy_blocks),
            legacy_slugs=slugs,
            risk_level=risk,
            feasibility=feasibility,
            missing_assets=missing_assets[:5],
            backup_state="PENDING",
            status=MigrationStatus.READY,
            notes=f"Found {len(legacy_blocks)} legacy blocks across {len(slugs)} slugs. Feasible for native migration."
        )

    def plan_project_migration(
        self,
        project_id: str,
        project_name: str,
        revision: int,
        document_doc: Dict[str, Any]
    ) -> ProjectMigrationPlan:
        """Create a detailed migration plan for a project."""
        readiness = self.assess_project_readiness(project_id, project_name, revision, document_doc)
        legacy_blocks = LegacyBlockDetector.detect_in_project_doc(document_doc)

        proposed_element_count = len(legacy_blocks) * 2  # typically primary text + secondary shape
        proposed_scene_count = max(1, len(legacy_blocks))

        return ProjectMigrationPlan(
            project_id=project_id,
            project_name=project_name,
            current_revision=revision,
            target_revision=revision + 1,
            legacy_blocks=legacy_blocks,
            replacement_strategy="native_motion_v1",
            proposed_scene_count=proposed_scene_count,
            proposed_element_count=proposed_element_count,
            status=MigrationStatus.READY if readiness.has_legacy_blocks else MigrationStatus.DRY_RUN_PASSED
        )
