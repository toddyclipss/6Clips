# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 3 Role 3: Tests for the discover -> filter -> inspect -> preview -> add-to-project
validated intent integration contract and API router endpoints.
"""
import pytest
from fastapi.testclient import TestClient

from backend.catalog.router import router
from backend.catalog.project_intent_contract import (
    AddToProjectIntentRequest,
    AddToProjectIntentResult,
    CatalogProjectIntentAdapter,
)
from backend.catalog.manifest_service import CatalogManifestError


def test_add_to_project_intent_creation_for_ready_block():
    """Requirement 2: Verify validated intent generation for an internalized ready block."""
    req = AddToProjectIntentRequest(
        project_id="proj_alpha_916",
        timeline_track_index=1,
        start_time_seconds=3.5,
        aspect_ratio="9:16",
        custom_variables={"channel_name": "@6clips_official"},
    )

    result = CatalogProjectIntentAdapter.create_add_to_project_intent("yt-lower-third", req)

    assert isinstance(result, AddToProjectIntentResult)
    assert result.status == "VALIDATED_INTENT"
    assert result.block_id == "yt-lower-third"
    assert result.target_project_id == "proj_alpha_916"

    # Timeline item checks
    t_item = result.timeline_item
    assert t_item.item_type == "motion_block"
    assert t_item.start_time == 3.5
    assert t_item.duration > 0
    assert t_item.end_time == round(3.5 + t_item.duration, 3)
    assert t_item.track_index == 1
    assert t_item.aspect_ratio == "9:16"
    assert t_item.internalized is True
    assert t_item.runtime_ready is True
    assert "/api/catalog/blocks/yt-lower-third/preview" in t_item.preview_url

    # Integration request contract checks
    contract = result.integration_request
    assert contract["target_service"] == "backend.services.project_service.ProjectService"
    assert contract["coordinator_action_required"] is True
    assert contract["parameters"]["project_id"] == "proj_alpha_916"


def test_add_to_project_intent_warning_for_unverified_block():
    """Requirement 2: Verify warning status when attempting to add an unverified block."""
    req = AddToProjectIntentRequest(
        project_id="proj_beta",
        timeline_track_index=0,
        start_time_seconds=0.0,
        aspect_ratio="16:9",
    )

    result = CatalogProjectIntentAdapter.create_add_to_project_intent("camcorder-hud", req)

    assert result.status == "WARNING_UNVERIFIED"
    assert result.timeline_item.internalized is False
    assert result.timeline_item.runtime_ready is False


def test_add_to_project_intent_rejects_invalid_block_id():
    """Requirement 7: Verify path traversal attempts are rejected when creating intents."""
    req = AddToProjectIntentRequest(project_id="proj_x")

    with pytest.raises(CatalogManifestError):
        CatalogProjectIntentAdapter.create_add_to_project_intent("../../malicious_id", req)


def test_router_intent_endpoint():
    """Requirement 2: Test FastAPI REST endpoint for add-to-project intent dispatch."""
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    payload = {
        "project_id": "test_proj_123",
        "timeline_track_index": 2,
        "start_time_seconds": 1.0,
        "aspect_ratio": "9:16",
        "custom_variables": {"count": 1000},
    }

    res = client.post("/api/catalog/blocks/data-chart/intent/add-to-project", json=payload)
    assert res.status_code == 200, f"Router returned {res.status_code}: {res.text}"

    data = res.json()
    assert data["status"] == "VALIDATED_INTENT"
    assert data["block_id"] == "data-chart"
    assert data["timeline_item"]["track_index"] == 2
    assert data["timeline_item"]["internalized"] is True
    assert "integration_request" in data


def test_router_factual_counts_endpoint():
    """Acceptance: Test GET /api/catalog/factual-counts returns required counts."""
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    res = client.get("/api/catalog/factual-counts")
    assert res.status_code == 200
    data = res.json()
    assert data["INVENTORIED"] == 196
    assert data["READY"] == 6
    assert data["NOT_READY"] == 190
    assert data["INTERNALIZED"] == 6
    assert data["RENDER_TESTED"] == 6
    assert data["BROWSER_VERIFIED"] == 6
    assert data["LICENSE_BLOCKED"] == 165
