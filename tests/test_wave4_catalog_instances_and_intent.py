# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 4 Role 3: Tests for Editable Instances, Project Intent Contract,
CAS Optimistic Concurrency, and Input Sanitization.
"""
import pytest
from fastapi.testclient import TestClient

from backend.catalog.router import router
from backend.catalog.project_intent_contract import (
    AddToProjectIntentRequest,
    AddToProjectIntentResult,
    CatalogProjectIntentAdapter,
)
from backend.catalog.ghost_preview import GhostPreviewContract
from backend.catalog.manifest_service import CatalogManifestError


def test_unique_scoped_instance_ids_per_invocation():
    """Verify that multiple intents for the same block yield unique scoped instance_ids."""
    req1 = AddToProjectIntentRequest(
        project_id="proj_alpha",
        timeline_track_index=0,
        start_time_seconds=0.0,
        aspect_ratio="9:16",
    )
    req2 = AddToProjectIntentRequest(
        project_id="proj_alpha",
        timeline_track_index=0,
        start_time_seconds=5.0,
        aspect_ratio="9:16",
    )

    res1 = CatalogProjectIntentAdapter.create_add_to_project_intent("flowing-gradient", req1)
    res2 = CatalogProjectIntentAdapter.create_add_to_project_intent("flowing-gradient", req2)

    # Scoped instance IDs must be distinct
    assert res1.timeline_item.instance_id != res2.timeline_item.instance_id
    assert res1.timeline_item.instance_id.startswith("inst_flowing-gradient_")
    assert res2.timeline_item.instance_id.startswith("inst_flowing-gradient_")

    # Item IDs must be distinct
    assert res1.timeline_item.item_id != res2.timeline_item.item_id


def test_user_defined_instance_id_preservation():
    """Verify that a client-provided instance_id is preserved faithfully."""
    req = AddToProjectIntentRequest(
        project_id="proj_alpha",
        instance_id="custom_user_inst_42",
        aspect_ratio="9:16",
    )
    res = CatalogProjectIntentAdapter.create_add_to_project_intent("creator-hud", req)

    assert res.timeline_item.instance_id == "custom_user_inst_42"
    assert res.timeline_item.is_independently_editable is True


def test_variable_independence_across_instances():
    """Verify that variable overrides in one instance do not contaminate another."""
    req1 = AddToProjectIntentRequest(
        custom_variables={"channel_name": "@ChannelAlpha", "color": "#ff0000"},
    )
    req2 = AddToProjectIntentRequest(
        custom_variables={"channel_name": "@ChannelBeta", "color": "#0000ff"},
    )

    res1 = CatalogProjectIntentAdapter.create_add_to_project_intent("yt-lower-third", req1)
    res2 = CatalogProjectIntentAdapter.create_add_to_project_intent("yt-lower-third", req2)

    assert res1.timeline_item.variables["channel_name"] == "@ChannelAlpha"
    assert res2.timeline_item.variables["channel_name"] == "@ChannelBeta"
    assert res1.timeline_item.variables != res2.timeline_item.variables


def test_cas_expected_revision_concurrency_precondition():
    """Verify that expected_revision is validated and populated in the coordinator contract."""
    # With CAS revision specified
    req_with_cas = AddToProjectIntentRequest(
        project_id="proj_cas",
        expected_revision=7,
    )
    res = CatalogProjectIntentAdapter.create_add_to_project_intent("plasma", req_with_cas)
    cas_meta = res.integration_request["cas_precondition"]
    assert cas_meta["expected_revision"] == 7
    assert cas_meta["optimistic_concurrency_required"] is True

    # Without CAS revision
    req_no_cas = AddToProjectIntentRequest(
        project_id="proj_cas",
    )
    res_no_cas = CatalogProjectIntentAdapter.create_add_to_project_intent("plasma", req_no_cas)
    cas_meta_no = res_no_cas.integration_request["cas_precondition"]
    assert cas_meta_no["expected_revision"] is None
    assert cas_meta_no["optimistic_concurrency_required"] is False


def test_input_sanitization_script_and_prototype_pollution():
    """Verify input sanitization strips XSS script payloads and rejects prototype pollution."""
    # Test script injection sanitization
    sanitized = CatalogProjectIntentAdapter.sanitize_variable_value(
        "title",
        "<script>alert('xss')</script>Safe Headline",
    )
    assert "<script>" not in sanitized
    assert "Safe Headline" in sanitized

    # Test prototype pollution key rejection
    with pytest.raises(CatalogManifestError):
        CatalogProjectIntentAdapter.sanitize_variable_value("__proto__", "polluted")

    with pytest.raises(CatalogManifestError):
        CatalogProjectIntentAdapter.sanitize_variable_value("constructor", "polluted")


def test_ghost_preview_contract_is_read_only_and_muted():
    """Verify that Ghost Preview contract guarantees muted audio and read-only non-destructive behavior."""
    config = GhostPreviewContract.get_preview_config("flowing-gradient", aspect_ratio="9:16")

    assert config["read_only"] is True
    assert config["audio_muted"] is True
    assert config["creates_revision"] is False
    assert config["has_destructive_side_effects"] is False
    assert config["aspect_ratio"] == "9:16"


def test_router_wave4_endpoints():
    """Verify FastAPI router endpoints for wave4-factual-counts, audit, and category summary."""
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    # 1. wave4-factual-counts
    res_w4 = client.get("/api/catalog/wave4-factual-counts")
    assert res_w4.status_code == 200
    counts = res_w4.json()
    assert counts["INVENTORIED"] == 196
    assert counts["READY"] == 10
    assert counts["NOT_READY"] == 186

    # 2. factual-audit
    res_audit = client.get("/api/catalog/factual-audit")
    assert res_audit.status_code == 200
    audit_data = res_audit.json()
    assert audit_data["baseline_wave3"]["READY"] == 6
    assert audit_data["expanded_wave4"]["READY"] == 10
    assert audit_data["delta"]["ready_count_diff"] == 4

    # 3. category-summary
    res_cat = client.get("/api/catalog/category-summary")
    assert res_cat.status_code == 200
    assert res_cat.json()["total_categories"] >= 7

    # 4. render probe endpoint
    res_probe = client.get("/api/catalog/blocks/creator-hud/probe?aspect_ratio=9:16")
    assert res_probe.status_code == 200
    assert res_probe.json()["probe_passed"] is True
