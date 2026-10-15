# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 16 Agent 2 Test Suite: Motion Workflow, Canonical ProjectRevision, CAS, and Legacy Migration."""

import json
import subprocess
from pathlib import Path
import pytest
from fastapi import HTTPException

from backend.database import init_db
from backend.services.project_service import ProjectService, RevisionConflictError
from backend.catalog.manifest_service import (
    CatalogManifestService,
    DONOR_INTERNALIZED_BLOCKS,
    RETIRED_6CLIPS_BLOCKS,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def run_node_eval(script: str):
    """Run a small node script in the frontend directory and return parsed JSON."""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=REPO_ROOT / "frontend",
        capture_output=True,
        text=True,
        check=True,
    )
    stdout = result.stdout.strip()
    if stdout.startswith("Warning:"):
        lines = stdout.splitlines()
        for idx, line in enumerate(lines):
            if line.strip().startswith("{") or line.strip().startswith("["):
                stdout = "\n".join(lines[idx:])
                break
    return json.loads(stdout)


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Ensure database schema is created for test execution."""
    await init_db()


class TestWave16Agent2MotionWorkflow:
    """Verifies Motion insertion, variable edits, CAS durability, and non-destructive legacy migration."""

    @pytest.mark.asyncio
    async def test_motion_insert_operational_block_with_cas(self):
        """Verify inserting an operational block (e.g., 'aurora') into canonical ProjectRevision increments rev."""
        initial_doc = {
            "schema_version": 2,
            "aspect_ratio": "9:16",
            "timeline": {
                "fps": 30,
                "duration_seconds": 10.0,
                "tracks": [
                    {"id": "track_video_1", "type": "video", "clips": []},
                ],
            },
        }

        # 1. Create project at revision 1
        proj = await ProjectService.create_project(
            name="Wave 16 Motion Test Project",
            aspect_ratio="9:16",
            initial_document=initial_doc,
        )
        assert proj.id is not None
        assert proj.revision == 1

        # 2. Insert operational block 'aurora'
        block_id = "aurora"
        assert block_id in DONOR_INTERNALIZED_BLOCKS

        op_payload = {
            "block_id": block_id,
            "variables": {"speed": 1.2, "intensity": 0.8},
            "start_seconds": 0.0,
            "duration_seconds": 5.0,
            "track_id": "track_video_1",
        }

        rev_res = await ProjectService.apply_operation(
            project_id=proj.id,
            expected_revision=1,
            operation_type="add_block",
            payload=op_payload,
            idempotency_key="insert_aurora_w16",
            author="motion_editor",
        )
        assert rev_res["revision"] == 2

        # 3. Reload from database and verify canonical ProjectRevision persistence
        reloaded = await ProjectService.get_project(proj.id)
        assert reloaded.revision == 2
        doc = json.loads(reloaded.document_json) if isinstance(reloaded.document_json, str) else reloaded.document_json
        
        # Verify clip exists in timeline
        track = next(t for t in doc["timeline"]["tracks"] if t["id"] == "track_video_1")
        inserted_clip = next(c for c in track["clips"] if c.get("block_id") == block_id)
        assert inserted_clip["block_id"] == "aurora"
        assert inserted_clip["duration_seconds"] == 5.0
        assert inserted_clip["variables"]["speed"] == 1.2

    @pytest.mark.asyncio
    async def test_motion_variable_editing_and_revision_increment(self):
        """Verify modifying variables on an existing block updates document and increments revision."""
        proj = await ProjectService.create_project(
            name="Wave 16 Variable Edit Test",
            aspect_ratio="9:16",
            initial_document={
                "schema_version": 2,
                "timeline": {
                    "tracks": [
                        {
                            "id": "t1",
                            "type": "video",
                            "clips": [
                                {
                                    "id": "clip_data_chart",
                                    "block_id": "data-chart",
                                    "start_seconds": 0.0,
                                    "duration_seconds": 4.0,
                                    "variables": {"theme": "dark", "title": "Initial Title"},
                                }
                            ],
                        }
                    ]
                },
            },
        )
        assert proj.revision == 1

        # Fetch doc and update variable
        doc = json.loads(proj.document_json) if isinstance(proj.document_json, str) else proj.document_json
        doc["timeline"]["tracks"][0]["clips"][0]["variables"]["title"] = "Updated Revenue Q4"

        update_res = await ProjectService.apply_operation(
            project_id=proj.id,
            expected_revision=1,
            operation_type="update_document",
            payload={"document": doc},
            idempotency_key="edit_var_w16",
            author="motion_editor",
        )
        assert update_res["revision"] == 2

        # Reload and check
        reloaded = await ProjectService.get_project(proj.id)
        assert reloaded.revision == 2
        r_doc = json.loads(reloaded.document_json) if isinstance(reloaded.document_json, str) else reloaded.document_json
        assert r_doc["timeline"]["tracks"][0]["clips"][0]["variables"]["title"] == "Updated Revenue Q4"

    @pytest.mark.asyncio
    async def test_cas_concurrency_409_rejection(self):
        """Verify submitting an operation with a stale expected_revision raises RevisionConflictError."""
        proj = await ProjectService.create_project(
            name="Wave 16 CAS Conflict Test",
            aspect_ratio="9:16",
            initial_document={"schema_version": 2, "timeline": {"tracks": []}},
        )
        assert proj.revision == 1

        # Advance to rev 2
        await ProjectService.apply_operation(
            project_id=proj.id,
            expected_revision=1,
            operation_type="update_document",
            payload={"document": {"schema_version": 2, "timeline": {"tracks": [{"id": "t1", "type": "video", "clips": []}]}}},
            idempotency_key="advance_to_rev_2",
        )

        # Attempt operation with stale revision 1 must raise RevisionConflictError
        with pytest.raises(RevisionConflictError) as exc_info:
            await ProjectService.apply_operation(
                project_id=proj.id,
                expected_revision=1,
                operation_type="update_document",
                payload={"document": {"schema_version": 2, "timeline": {"tracks": []}}},
                idempotency_key="stale_attempt",
            )
        assert exc_info.value.current_revision == 2
        assert exc_info.value.expected_revision == 1

    def test_legacy_project_migration_inspector(self):
        """Verify inspectLegacyProjectBlocks identifies retired 6Clips blocks and flags non-destructive migration."""
        legacy_doc = {
            "schema_version": 2,
            "timeline": {
                "tracks": [
                    {
                        "id": "track_main",
                        "clips": [
                            {"id": "c1", "block_id": "creator-hud", "title": "HUD Overlay"},
                            {"id": "c2", "block_id": "aurora", "title": "Aurora Background"},
                            {"id": "c3", "block_id": "glitch-transition", "title": "Glitch Cut"},
                        ],
                    }
                ]
            },
        }

        # Run frontend inspector via node
        script = f"""
            import('./src/utils/catalogOriginals.js').then(m => {{
                const result = m.inspectLegacyProjectBlocks({json.dumps(legacy_doc)});
                console.log(JSON.stringify(result));
            }});
        """
        data = run_node_eval(script)

        assert data["hasLegacy"] is True
        assert data["status"] == "REQUIRES_MIGRATION"
        assert set(data["legacyBlocks"]) == {"creator-hud", "glitch-transition"}
        assert len(data["affectedClips"]) == 2
        clip_blocks = {c["blockId"] for c in data["affectedClips"]}
        assert clip_blocks == {"creator-hud", "glitch-transition"}

    def test_clean_project_migration_inspector_returns_current(self):
        """Verify inspectLegacyProjectBlocks flags projects with only authentic donor blocks as VERIFIED_CURRENT."""
        current_doc = {
            "schema_version": 2,
            "timeline": {
                "tracks": [
                    {
                        "id": "track_main",
                        "clips": [
                            {"id": "c1", "block_id": "aurora", "title": "Aurora"},
                            {"id": "c2", "block_id": "plasma", "title": "Plasma"},
                        ],
                    }
                ]
            },
        }

        script = f"""
            import('./src/utils/catalogOriginals.js').then(m => {{
                const result = m.inspectLegacyProjectBlocks({json.dumps(current_doc)});
                console.log(JSON.stringify(result));
            }});
        """
        data = run_node_eval(script)

        assert data["hasLegacy"] is False
        assert data["status"] == "VERIFIED_CURRENT"
        assert len(data["legacyBlocks"]) == 0
        assert len(data["affectedClips"]) == 0
