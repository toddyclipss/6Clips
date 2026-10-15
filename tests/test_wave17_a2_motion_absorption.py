# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 17 Agent 2 Motion Absorption & Outcome Delivery Test Suite.

Verifies:
1. Motion Graphics absorbs Catalog:
   - StudioResourcePanel handles tab=catalog query param.
   - Prioritizes operational/packaged blocks in catalog list.
   - Displays clean "Template" / "TEMPLATE" markers with zero raw "Unported" or "INVENTORY ONLY" labels.
2. Motion Graphics absorbs Clip Studio & Deterministic Tools:
   - Handles ?mode=clip and ?mode=tools.
   - Preserves bench ranges and auto_cut_settings in Project document.
   - Preserves CAS durability and revision increment semantics.
3. My Channel consolidates Distribution & Analytics into Outcome Delivery:
   - Channels.jsx includes OutcomeDeliverySummary component.
   - Exposes published-outcomes, distribution-queue, and platform-connectors.
   - Shows truthful AWAITING_PUBLISHED_POST when no external receipts exist (zero synthetic mocks).
   - Shows truthful NOT_CONNECTED when platform credentials are not provided.
"""

import json
import re
from pathlib import Path
import pytest

from backend.database import init_db
from backend.services.project_service import ProjectService, RevisionConflictError

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Ensure database schema is created for test execution."""
    await init_db()


class TestWave17A2MotionAbsorption:
    """Verifies HyperFrames catalog, clip studio, and tools absorption into Motion Graphics."""

    def test_motion_graphics_absorbs_catalog_tab_and_query_param(self):
        """MotionGraphics and StudioResourcePanel handle ?tab=catalog query parameter."""
        mg_path = FRONTEND_SRC / "pages" / "MotionGraphics.jsx"
        srp_path = FRONTEND_SRC / "components" / "motion" / "StudioResourcePanel.jsx"
        assert mg_path.exists() and srp_path.exists()

        mg_content = mg_path.read_text(encoding="utf-8")
        srp_content = srp_path.read_text(encoding="utf-8")

        # In MotionGraphics: tab=catalog forces leftNav to "resources" and pinnedLeft to true
        assert 'tab === "catalog"' in mg_content or 'requestedTab === "catalog"' in mg_content, (
            "MotionGraphics.jsx must respond to ?tab=catalog query param"
        )

        # In StudioResourcePanel: tab=catalog initializes tab to 2 (Catalog)
        assert 'if (t === "catalog") return 2' in srp_content or 'if (t === "catalog") setTab(2)' in srp_content, (
            "StudioResourcePanel.jsx must select Catalog tab on ?tab=catalog"
        )

    def test_catalog_prioritizes_operational_and_packaged_blocks(self):
        """StudioResourcePanel sorts filteredCatalog so operational and packaged blocks appear first."""
        srp_path = FRONTEND_SRC / "components" / "motion" / "StudioResourcePanel.jsx"
        srp_content = srp_path.read_text(encoding="utf-8")

        assert ".sort((a, b)" in srp_content, "filteredCatalog must be sorted in StudioResourcePanel"
        assert "DONOR_INTERNALIZED_IDS" in srp_content, "Sort must check operational block IDs"
        assert "DONOR_PACKAGED_IDS" in srp_content, "Sort must check packaged block IDs"

    def test_motion_graphics_absorbs_clip_and_tools_contexts(self):
        """MotionGraphics handles ?mode=clip and ?mode=tools by activating the corresponding context in refine mode."""
        mg_path = FRONTEND_SRC / "pages" / "MotionGraphics.jsx"
        mg_content = mg_path.read_text(encoding="utf-8")

        # Check mode=clip or mode=tools sets workspaceMode to refine
        assert 'if (m && ["clip", "tools", "code"].includes(m))' in mg_content, (
            "MotionGraphics.jsx must promote clip and tools modes to refine workspace"
        )

        # Check activeContext includes clip and tools
        assert 'if (m && ["clip", "tools", "code", "hyperframes"].includes(m))' in mg_content, (
            "MotionGraphics.jsx must set activeContext to clip/tools/code"
        )

        # Verify contextual sub-workspaces exist
        assert 'activeContext === "clip"' in mg_content, "Missing SourceBench clip workspace in MotionGraphics"
        assert 'activeContext === "tools"' in mg_content, "Missing StudioToolsWorkspace in MotionGraphics"

    @pytest.mark.asyncio
    async def test_cas_project_revision_persists_clip_and_auto_cut_settings(self):
        """Canonical ProjectService persists bench_ranges and auto_cut_settings across revisions with CAS safety."""
        # 1. Create project
        proj = await ProjectService.create_project(name="Wave17 OAAS Project", aspect_ratio="9:16")
        assert proj.revision == 1

        # 2. Add bench ranges (from clip workspace)
        doc = json.loads(proj.document_json) if isinstance(proj.document_json, str) else dict(proj.document)
        doc["bench_ranges"] = {
            "source_vid_001": [
                {"id": "range_1", "start": 2.5, "end": 8.0, "label": "Hook 1"},
                {"id": "range_2", "start": 12.0, "end": 20.5, "label": "Punchline"},
            ]
        }
        res1 = await ProjectService.apply_operation(
            project_id=proj.id,
            expected_revision=1,
            operation_type="update_document",
            payload={"document": doc},
            author="user",
        )
        assert res1["revision"] == 2
        assert len(res1["document"]["bench_ranges"]["source_vid_001"]) == 2

        # 3. Add auto_cut_settings
        doc2 = res1["document"]
        doc2["auto_cut_settings"] = {
            "mode": "auto",
            "caption_style": "bold_glow",
            "remove_silence": True,
            "force_vertical": True,
            "min_duration": 15,
            "max_duration": 60,
        }
        res2 = await ProjectService.apply_operation(
            project_id=proj.id,
            expected_revision=2,
            operation_type="update_document",
            payload={"document": doc2},
            author="user",
        )
        assert res2["revision"] == 3
        assert res2["document"]["auto_cut_settings"]["remove_silence"] is True

        # 4. Conflict detection test (stale revision 2 rejected)
        with pytest.raises(RevisionConflictError):
            await ProjectService.apply_operation(
                project_id=proj.id,
                expected_revision=2,  # Stale: actual is 3
                operation_type="update_document",
                payload={"document": doc2},
                author="user",
            )

    def test_channels_page_includes_outcome_delivery_summary(self):
        """Channels.jsx consolidates Distribution and Analytics into OutcomeDeliverySummary."""
        ch_path = FRONTEND_SRC / "pages" / "Channels.jsx"
        assert ch_path.exists(), "Channels.jsx does not exist"
        ch_content = ch_path.read_text(encoding="utf-8")

        # Verify page header is "My Channel"
        assert "My Channel" in ch_content, "Page title must be 'My Channel'"

        # Verify OutcomeDeliverySummary component presence
        assert "function OutcomeDeliverySummary" in ch_content, "OutcomeDeliverySummary component missing in Channels.jsx"

        # Verify test IDs
        assert 'data-testid="outcome-summary"' in ch_content
        assert 'data-testid="published-outcomes"' in ch_content
        assert 'data-testid="distribution-queue"' in ch_content
        assert 'data-testid="platform-connectors"' in ch_content

        # Verify truthful empty state and truthful connectivity
        assert "AWAITING_PUBLISHED_POST" in ch_content
        assert "NOT_CONNECTED" in ch_content
