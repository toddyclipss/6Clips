# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 20 Knowledge-First & Legacy Project Migration Subsystem."""

from backend.knowledge_migration.converter import LegacyProjectConverter
from backend.knowledge_migration.detector import LegacyBlockDetector
from backend.knowledge_migration.inventory import DonorInventoryLedger
from backend.knowledge_migration.models import (
    LegacyBlockRef,
    MigrationResult,
    MigrationStatus,
    ProjectMigrationPlan,
    ProjectReadiness,
    ReplacementFeasibility,
    RiskLevel,
    RollbackManifest,
    RollbackRecord,
)
from backend.knowledge_migration.planner import ProjectMigrationPlanner
from backend.knowledge_migration.rollback import RollbackEngine
from backend.knowledge_migration.runner import MigrationRunner
from backend.knowledge_migration.zero_bundle_audit import ZeroBundleAuditor

__all__ = [
    "DonorInventoryLedger",
    "LegacyBlockDetector",
    "LegacyBlockRef",
    "LegacyProjectConverter",
    "MigrationResult",
    "MigrationRunner",
    "MigrationStatus",
    "ProjectMigrationPlan",
    "ProjectMigrationPlanner",
    "ProjectReadiness",
    "ReplacementFeasibility",
    "RiskLevel",
    "RollbackEngine",
    "RollbackManifest",
    "RollbackRecord",
    "ZeroBundleAuditor",
]
