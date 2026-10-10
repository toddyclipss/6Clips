# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Tests for OaaS action-intent chat routing, non-action conversation, and model pinning.

Verifies Directives 6, 7, and 8:
- Action intent ("Add a lower third at 2 seconds") -> ExecutionRun -> ExecutionStep -> ProjectRevision -> Verifier -> Run Completed.
- Conversational-only ("Explain what a lower third is") -> No ExecutionRun -> No ProjectRevision bump -> direct prose.
- Model pinning survives active run: modifying user settings or later turns never mutates active run's pinned provider/model.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from sqlalchemy import select

from backend.database import init_db, AsyncSessionLocal
from backend.agents.planner import PlannerAgent
from backend.services.project_service import ProjectService
from backend.services.executor_service import ExecutorService
from backend.models.execution import ExecutionRun, ExecutionStep
from backend.models.project import Project


@pytest.fixture(scope="module", autouse=True)
def _schema():
    asyncio.run(init_db())


@pytest.mark.asyncio
async def test_action_intent_creates_execution_run_and_advances_revision():
    """Directive 6: Sending action intent routes through ExecutionRun, Step, advances ProjectRevision and verifies."""
    user_id = "test_user_p0_action"
    planner = PlannerAgent()

    # Setup project at revision 1
    p = await ProjectService.create_project("Action Routing Project", user_id=user_id)
    initial_rev = p.revision

    # Mock AI response to simulate model streaming prose and confirming intent
    mock_ai = AsyncMock()
    # The AI does not include an action block so safety-net / planner recognizes the action intent
    async def mock_stream(*args, **kwargs):
        yield "Adding a lower third at 2 seconds to your timeline now."
    mock_ai.chat_stream = mock_stream

    with patch("backend.agents.planner.get_ai_client", return_value=mock_ai), \
         patch("backend.core.ws_manager.ws_manager.send", new=AsyncMock()):
        
        response = await planner.handle_message(
            message="Add a lower third at 2 seconds",
            history=[],
            user_settings=None,
            user_id=user_id,
            pinned_provider="deepseek",
            pinned_model="deepseek-chat",
            project_id=p.id,
        )

    # 1. Project revision must have advanced
    p_after = await ProjectService.get_project(p.id)
    assert p_after.revision > initial_rev, f"Project revision did not advance! Before: {initial_rev}, After: {p_after.revision}"

    # 2. An ExecutionRun must have been created with pinned provider & model
    async with AsyncSessionLocal() as db:
        runs_res = await db.execute(
            select(ExecutionRun)
            .where(ExecutionRun.project_id == p.id)
            .order_by(ExecutionRun.created_at.desc())
        )
        runs = runs_res.scalars().all()
        assert len(runs) >= 1, "No ExecutionRun was created for action intent!"
        active_run = runs[0]
        assert active_run.status == "completed"
        assert active_run.resolved_provider == "deepseek"
        assert active_run.resolved_model == "deepseek-chat"

        # 3. An ExecutionStep must exist and be verified
        steps_res = await db.execute(
            select(ExecutionStep)
            .where(ExecutionStep.run_id == active_run.id)
        )
        steps = steps_res.scalars().all()
        assert len(steps) >= 1, "No ExecutionStep was created for ExecutionRun!"
        step = steps[0]
        assert step.capability == "project_operation"
        assert step.status == "success"
        assert step.verification_status == "verified"


@pytest.mark.asyncio
async def test_conversational_turn_creates_no_execution_run_and_no_revision_change():
    """Directive 7: Conversational queries ('Explain what a lower third is') stream prose and do NOT mutate project or create runs."""
    user_id = "test_user_p0_conv"
    planner = PlannerAgent()

    p = await ProjectService.create_project("Conv Only Project", user_id=user_id)
    initial_rev = p.revision

    mock_ai = AsyncMock()
    async def mock_stream(*args, **kwargs):
        yield "A lower third is an overlay graphic placed in the lower third of the screen."
    mock_ai.chat_stream = mock_stream

    with patch("backend.agents.planner.get_ai_client", return_value=mock_ai), \
         patch("backend.core.ws_manager.ws_manager.send", new=AsyncMock()):
        
        response = await planner.handle_message(
            message="Explain what a lower third is",
            history=[],
            user_settings=None,
            user_id=user_id,
            pinned_provider="anthropic",
            pinned_model="claude-3-5-sonnet",
            project_id=p.id,
        )

    # 1. Project revision MUST NOT change
    p_after = await ProjectService.get_project(p.id)
    assert p_after.revision == initial_rev, "Conversational query modified project revision!"

    # 2. NO ExecutionRun must exist for this project
    async with AsyncSessionLocal() as db:
        runs_res = await db.execute(
            select(ExecutionRun).where(ExecutionRun.project_id == p.id)
        )
        runs = runs_res.scalars().all()
        assert len(runs) == 0, f"Spurious ExecutionRun created for conversational query: {runs}"


@pytest.mark.asyncio
async def test_model_pinning_survives_active_run_and_settings_changes():
    """Directive 8: Pinned provider and model survive on active ExecutionRun when global settings or later calls change."""
    user_id = "test_user_p0_pinning"
    
    # Create an active run pinned to DeepSeek
    run = await ExecutorService.create_run(
        objective="Run with pinned DeepSeek",
        user_id=user_id,
        provider="deepseek",
        model="deepseek-chat",
    )
    assert run.resolved_provider == "deepseek"
    assert run.resolved_model == "deepseek-chat"

    # Simulate subsequent action or settings change with a different provider (e.g. OpenAI)
    run2 = await ExecutorService.create_run(
        objective="Subsequent run with OpenAI",
        user_id=user_id,
        provider="openai",
        model="gpt-4o-mini",
    )
    assert run2.resolved_provider == "openai"
    assert run2.resolved_model == "gpt-4o-mini"

    # Verify original run row was NOT mutated
    async with AsyncSessionLocal() as db:
        reloaded_run = await db.get(ExecutionRun, run.id)
        assert reloaded_run.resolved_provider == "deepseek"
        assert reloaded_run.resolved_model == "deepseek-chat"
