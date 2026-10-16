# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Data models for Wave 20 Agent 5 Knowledge & Legacy Project Migration Subsystem."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class MigrationStatus(str, enum.Enum):
    PENDING = "PENDING"
    DRY_RUN_PASSED = "DRY_RUN_PASSED"
    READY = "READY"
    MIGRATED = "MIGRATED"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    BLOCKED_USER_DATA_ACCESS = "BLOCKED_USER_DATA_ACCESS"


class ReplacementFeasibility(str, enum.Enum):
    FEASIBLE_DIRECT = "FEASIBLE_DIRECT"
    FEASIBLE_COMPOSED = "FEASIBLE_COMPOSED"
    FEASIBLE_NATIVE_FALLBACK = "FEASIBLE_NATIVE_FALLBACK"
    UNSUPPORTED = "UNSUPPORTED"


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class LegacyBlockRef:
    """Represents a reference to a legacy or donor block found in a project or revision."""
    clip_id: str
    block_id: str
    track_id: str
    track_type: str = "graphics"
    start_seconds: float = 0.0
    duration_seconds: float = 0.0
    variables: Dict[str, Any] = field(default_factory=dict)
    is_retired_custom: bool = False
    source_asset_path: Optional[str] = None


@dataclass
class ProjectReadiness:
    """Readiness and risk ledger entry for a single project."""
    project_id: str
    project_name: str
    current_revision: int
    has_legacy_blocks: bool
    legacy_block_count: int
    legacy_slugs: List[str] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    feasibility: ReplacementFeasibility = ReplacementFeasibility.FEASIBLE_DIRECT
    missing_assets: List[str] = field(default_factory=list)
    backup_state: str = "PENDING"
    status: MigrationStatus = MigrationStatus.PENDING
    notes: str = ""


@dataclass
class ProjectMigrationPlan:
    """Execution plan to migrate a project from legacy block bundles to native motion v1."""
    project_id: str
    project_name: str
    current_revision: int
    target_revision: int
    legacy_blocks: List[LegacyBlockRef] = field(default_factory=list)
    replacement_strategy: str = "native_motion_v1"
    proposed_scene_count: int = 1
    proposed_element_count: int = 1
    rollback_sha256: str = ""
    status: MigrationStatus = MigrationStatus.PENDING


@dataclass
class MigrationResult:
    """Result of running migration on a project."""
    project_id: str
    success: bool
    status: MigrationStatus
    pre_revision: int
    post_revision: int
    pre_doc_hash: str
    post_doc_hash: str
    migrated_block_count: int
    duration_ms: float = 0.0
    error: Optional[str] = None
    is_dry_run: bool = True


@dataclass
class RollbackRecord:
    """Rollback record allowing bit-for-bit restore of a project revision."""
    project_id: str
    original_revision: int
    migrated_revision: int
    original_doc_json: str
    migrated_doc_json: str
    original_sha256: str
    migrated_sha256: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class RollbackManifest:
    """Persistent ledger of all project migrations with reversible restore proof."""
    manifest_version: str = "1.0.0"
    wave: int = 20
    agent: int = 5
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    total_projects_audited: int = 0
    total_projects_migrated: int = 0
    records: Dict[str, Dict[str, Any]] = field(default_factory=dict)
