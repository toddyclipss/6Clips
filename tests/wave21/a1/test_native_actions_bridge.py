# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Unit and Integration Tests for NativeActionsBridge (Wave 21 Agent 1).
Verifies native execution of trimming, silence removal, reframing, caption styling,
CAS rollbacks, and truthful reporting of UNSUPPORTED for non-callable actions.
"""

import pytest

from backend.database import init_db
from backend.oaas_knowledge_orchestrator.native_actions_bridge import (
    NativeActionsBridge,
    SUPPORTED_NATIVE_ACTIONS,
)
from backend.services.project_service import ProjectService


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    monkeypatch.setenv("VIRALMINT_TEST_ENV", "1")
    monkeypatch.setenv("VIRALMINT_TEST_AUDIO_FIXTURE", "1")


@pytest.fixture(autouse=True)
async def init_database():
    await init_db()


@pytest.mark.asyncio
async def test_native_bridge_trim_and_silence():
    """Verify native trimming and dead-air silence removal mutate timeline duration."""
    proj = await ProjectService.create_project(
        name="Native Bridge Test",
        aspect_ratio="9:16",
        user_id="test_user_bridge",
    )
    initial_rev = proj.revision

    # Trim to 2.5s
    trim_res = await NativeActionsBridge.trim_range(
        project_id=proj.id,
        start_sec=0.0,
        end_sec=2.5,
        expected_revision=initial_rev,
    )
    assert trim_res["success"] is True
    assert trim_res["status"] == "EXECUTED"
    assert trim_res["new_duration"] == 2.5
    assert trim_res["new_revision"] == initial_rev + 1

    # Remove silence
    silence_res = await NativeActionsBridge.remove_silence(
        project_id=proj.id,
        threshold_db=-30.0,
        min_silence_sec=0.4,
        expected_revision=trim_res["new_revision"],
    )
    assert silence_res["success"] is True
    assert silence_res["new_duration"] < 2.5
    assert silence_res["new_revision"] == trim_res["new_revision"] + 1


@pytest.mark.asyncio
async def test_native_bridge_reframe_and_captions():
    """Verify aspect ratio reframing and caption typography styling."""
    proj = await ProjectService.create_project(
        name="Reframe Captions Test",
        aspect_ratio="9:16",
        user_id="test_user_bridge",
    )
    rev = proj.revision

    # Reframe to 16:9
    reframe_res = await NativeActionsBridge.reframe(
        project_id=proj.id,
        target_aspect="16:9",
        expected_revision=rev,
    )
    assert reframe_res["success"] is True
    assert reframe_res["target_aspect"] == "16:9"
    assert reframe_res["new_revision"] == rev + 1

    # Style captions
    cap_res = await NativeActionsBridge.style_captions(
        project_id=proj.id,
        style="word_highlight_pop",
        highlight_color="#FACC15",
        font_family="Cinzel, serif",
        expected_revision=reframe_res["new_revision"],
    )
    assert cap_res["success"] is True
    assert cap_res["highlight_color"] == "#FACC15"
    assert cap_res["new_revision"] == reframe_res["new_revision"] + 1


@pytest.mark.asyncio
async def test_native_bridge_rollback():
    """Verify rollback restores a historical project revision snapshot."""
    proj = await ProjectService.create_project(
        name="Rollback Test",
        aspect_ratio="9:16",
        user_id="test_user_bridge",
    )
    rev1 = proj.revision

    # Mutate to rev 2
    res2 = await NativeActionsBridge.reframe(project_id=proj.id, target_aspect="16:9", expected_revision=rev1)
    rev2 = res2["new_revision"]

    # Revert back to rev 1
    revert_res = await NativeActionsBridge.revert_project_revision(
        project_id=proj.id,
        target_revision=rev1,
    )
    assert revert_res["success"] is True
    assert revert_res["reverted_to"] == rev1
    assert revert_res["new_revision"] == rev2 + 1

    # Verify project document restored aspect ratio 9:16
    restored = await ProjectService.get_project(proj.id)
    assert restored.aspect_ratio == "9:16"


@pytest.mark.asyncio
async def test_native_bridge_unsupported_action():
    """Verify non-callable or unknown tool requests truthfully return UNSUPPORTED."""
    res = await NativeActionsBridge.execute_action(
        project_id="test_proj",
        action="non_existent_magic_filter",
    )
    assert res["success"] is False
    assert res["status"] == "UNSUPPORTED"
    assert "not supported" in res["message"]
