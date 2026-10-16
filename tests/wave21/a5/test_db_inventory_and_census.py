# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 21 Agent 5: Database Inventory & Census Tests."""

import json
from pathlib import Path
import pytest

from backend.config import settings
from backend.knowledge_migration.runner import compute_file_sha256
from tools.wave21_a5.reconcile_db_inventory import run_inventory_audit


def test_census_baseline_reconciliation():
    report = run_inventory_audit()
    comp = report["baseline_reconciliation"]

    # Projects
    assert comp["projects_total"]["actual"] == 345
    assert comp["projects_total"]["match"] is True

    # Revisions
    assert comp["revisions_total"]["actual"] == 1752
    assert comp["revisions_total"]["match"] is True

    # Dependent projects and revisions
    assert comp["projects_dependent"]["actual"] == 232
    assert comp["projects_dependent"]["match"] is True

    assert comp["revisions_dependent"]["actual"] == 920
    assert comp["revisions_dependent"]["match"] is True

    # Block clips
    assert comp["block_clips_in_projects"]["actual"] == 274
    assert comp["block_clips_in_projects"]["match"] is True

    # Combined slugs
    assert comp["distinct_slug_ids_combined_db"]["actual"] == 15
    assert comp["distinct_slug_ids_combined_db"]["match"] is True

    # Folders
    assert comp["imported_donor_folders"]["actual"] == 156
    assert comp["imported_donor_folders"]["match"] is True

    assert comp["total_shipped_folders"]["actual"] == 158
    assert comp["total_shipped_folders"]["match"] is True

    # Verify immutability
    assert report["database_metadata"]["immutability_verified"] is True
