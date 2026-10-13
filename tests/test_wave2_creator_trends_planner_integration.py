# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Integration and regression tests for Planner Agent, API Endpoints,
Multi-Turn Continuation, and Language Isolation under Wave 2 Creator & Trends scope.
"""
from __future__ import annotations

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch

from backend.agents.planner import PlannerAgent
from backend.core.ws_manager import ws_manager
from backend.original_creation.models import OriginalCreationStatus, VoiceInputRequirement


@pytest.fixture()
def ws_bus(monkeypatch):
    sent: list[dict] = []

    async def fake_send(msg, user_id="local"):
        sent.append(msg)

    async def fake_progress(*a, **k):
        return None

    monkeypatch.setattr(ws_manager, "send", fake_send)
    return sent


class TestPlannerOriginalCreatorIntegration:
    """Verifies that the PlannerAgent correctly handles original creation actions."""

    @pytest.mark.asyncio
    async def test_dispatch_create_original_brief_waiting_for_voice(self, ws_bus):
        agent = PlannerAgent()
        action = {
            "type": "create_original_brief",
            "topic": "Fortnite Season 4 Meta",
            "creator_context": "Shotgun spread was reduced by 10%.",
            "target_duration_sec": 60,
            "language": "en",
        }
        await agent._dispatch_action(action, None, "test_user")

        types = [m.get("type") for m in ws_bus]
        assert "original_brief_created" in types

        brief_msg = next(m for m in ws_bus if m.get("type") == "original_brief_created")
        spec = brief_msg["spec"]
        assert spec["topic"] == "Fortnite Season 4 Meta"
        assert spec["status"] == OriginalCreationStatus.WAITING_FOR_INPUT.value
        assert spec["voice_requirement"] == VoiceInputRequirement.WAITING_FOR_INPUT.value

        followup_msg = next(m for m in ws_bus if m.get("type") == "assistant_message")
        assert "WAITING_FOR_INPUT" in followup_msg["content"]
        assert "voice narration" in followup_msg["content"].lower()

    @pytest.mark.asyncio
    async def test_dispatch_create_original_brief_portuguese(self, ws_bus):
        agent = PlannerAgent()
        action = {
            "type": "create_original_brief",
            "topic": "Atualização do Fortnite",
            "creator_context": "Novo mapa e novas armas disponíveis.",
            "language": "pt",
        }
        await agent._dispatch_action(action, None, "test_user_pt")

        brief_msg = next(m for m in ws_bus if m.get("type") == "original_brief_created")
        assert brief_msg["spec"]["language"] == "pt"

        followup_msg = next(m for m in ws_bus if m.get("type") == "assistant_message")
        # Language isolation: Portuguese response
        assert "Briefing original" in followup_msg["content"]
        assert "WAITING_FOR_INPUT" in followup_msg["content"]
        assert "faixa de voz" in followup_msg["content"]

    @pytest.mark.asyncio
    async def test_dispatch_extract_reference_style(self, ws_bus):
        agent = PlannerAgent()
        action = {
            "type": "extract_reference_style",
            "reference_id": "yt-ref-888",
            "title": "Viral Movement Highlights",
            "duration_seconds": 55,
        }
        await agent._dispatch_action(action, None, "test_user")

        types = [m.get("type") for m in ws_bus]
        assert "reference_style_extracted" in types

        style_msg = next(m for m in ws_bus if m.get("type") == "reference_style_extracted")
        hypo = style_msg["hypothesis"]
        assert hypo["reference_title"] == "Viral Movement Highlights"
        assert hypo["rendering_status"] == "analysis_complete_rendering_pending"

        followup_msg = next(m for m in ws_bus if m.get("type") == "assistant_message")
        assert "Extracted creative style hypothesis" in followup_msg["content"]
        assert "rendering pending" in followup_msg["content"].lower()


class TestActionInferenceOriginalWorkflow:
    """Verifies that user messages without action tags infer the correct creator actions."""

    def test_infer_english_original_video_intent(self):
        msg = "Please create an original video explaining the new Fortnite weapon meta"
        actions = PlannerAgent._infer_missing_action(msg, "")
        assert len(actions) == 1
        data = json.loads(actions[0])
        assert data["type"] == "create_original_brief"
        assert "fortnite" in data["topic"].lower()
        assert data["language"] == "en"

    def test_infer_portuguese_original_video_intent(self):
        msg = "Crie um vídeo original sobre o novo patch do Fortnite"
        actions = PlannerAgent._infer_missing_action(msg, "")
        assert len(actions) == 1
        data = json.loads(actions[0])
        assert data["type"] == "create_original_brief"
        assert "fortnite" in data["topic"].lower()
        assert data["language"] == "pt"


class TestTrendsAndCreationApiEndpoints:
    """Tests the new HTTP API routes added to backend/api/trends.py."""

    @pytest.mark.asyncio
    async def test_trends_rank_endpoint(self):
        from backend.api.trends import rank_trends_candidates, TrendsRankRequest
        req = TrendsRankRequest(
            items=[
                {"id": "short-1", "title": "Viral Short", "duration_seconds": 45, "views": 1000000},
                {"id": "long-1", "title": "Long Gameplay VOD", "duration_seconds": 600, "views": 200000},
            ],
            goal="clip_repurposing",
            count=1,
        )
        res = await rank_trends_candidates(req)
        assert res["goal"] == "clip_repurposing"
        assert res["total_evaluated"] == 2
        assert res["selected_count"] == 1
        assert res["results"][0]["id"] == "long-1"
        assert res["results"][0]["editorial_role"] == "editable_source_candidate"

    @pytest.mark.asyncio
    async def test_reference_style_endpoint(self):
        from backend.api.trends import extract_reference_style_endpoint, ReferenceStyleRequest
        req = ReferenceStyleRequest(
            reference_id="vid-xyz",
            title="Fast Paced Gaming Reel",
            duration_seconds=50,
        )
        res = await extract_reference_style_endpoint(req)
        assert res["reference_source_id"] == "vid-xyz"
        assert res["rendering_status"] == "analysis_complete_rendering_pending"
        assert res["observable_features"]["suggested_aspect_ratio"] == "9:16"

    @pytest.mark.asyncio
    async def test_original_brief_endpoint(self):
        from backend.api.trends import create_original_brief_endpoint, OriginalBriefRequest
        req = OriginalBriefRequest(
            topic="Fortnite Update",
            creator_context="Movement speed adjusted.",
            target_duration_sec=60,
        )
        res = await create_original_brief_endpoint(req)
        assert res["spec"]["topic"] == "Fortnite Update"
        assert res["spec"]["status"] == "WAITING_FOR_INPUT"
        assert res["canonical_project_payload"]["title"] == "Original: Fortnite Update"
        assert res["canonical_project_payload"]["metadata"]["rendered_mp4_ready"] is False
