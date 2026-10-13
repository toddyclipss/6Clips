# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Deterministic authorial tests for Grounded Original Creation Vertical Slice:
- Source-backed evidence ledger
- Clean teleprompter script (zero stage brackets)
- Scene shot list & factcheck notes
- Truthful WAITING_FOR_INPUT status
- Production V1 canonical project adapter
"""
from __future__ import annotations

import re
import pytest

from backend.original_creation.models import (
    EvidenceLedger,
    EvidenceLedgerEntry,
    FactcheckNote,
    OriginalCompositionSpec,
    OriginalCreationStatus,
    ProductionV1Adapter,
    ShotListEntry,
    TeleprompterScript,
    VoiceInputRequirement,
)
from backend.original_creation.workflow import (
    OriginalCreatorWorkflow,
    calculate_spoken_read_time,
    clean_teleprompter_text,
)


class TestTeleprompterScriptFormatting:
    """Verifies that teleprompter scripts strictly contain clean spoken words."""

    def test_clean_teleprompter_strips_stage_directions(self):
        raw = (
            "[Intro: High energy music swells]\n"
            "Hook: Have you seen the crazy new changes in the update?\n"
            "[Cut to B-roll of shotgun gameplay]\n"
            "(Camera zooms in on character)\n"
            "Voiceover: The pump shotgun damage was completely reworked.\n"
            "[Overlay: DAMAGE +20%]\n"
            "Drop a comment if you think this meta is balanced."
        )
        cleaned = clean_teleprompter_text(raw)
        assert "[" not in cleaned
        assert "]" not in cleaned
        assert "Intro:" not in cleaned
        assert "Hook:" not in cleaned
        assert "Voiceover:" not in cleaned
        assert "Have you seen the crazy new changes in the update?" in cleaned
        assert "The pump shotgun damage was completely reworked." in cleaned
        assert "Drop a comment if you think this meta is balanced." in cleaned

    def test_spoken_read_time_calculation(self):
        text = "This is a clean twenty word test sentence designed to verify the approximate reading time calculation for spoken teleprompter voiceover narration."
        dur = calculate_spoken_read_time(text, words_per_minute=140)
        assert 5.0 <= dur <= 15.0


class TestOriginalCreatorWorkflowGroundedBrief:
    """Tests brief generation with traceable evidence and truthful status."""

    def test_create_brief_with_creator_context(self):
        creator_notes = (
            "The sniper rifle reload speed was nerfed by 15 percent. "
            "A new thermal scope attachment was added to the loot pool."
        )
        spec = OriginalCreatorWorkflow.create_brief(
            topic="Fortnite Season 4 Balance Patch",
            creator_context=creator_notes,
            target_duration_sec=60,
            language="en",
        )
        assert spec.topic == "Fortnite Season 4 Balance Patch"
        assert len(spec.evidence_ledger.entries) >= 2
        assert "sniper rifle reload" in spec.evidence_ledger.entries[0].claim_text.lower()
        assert spec.evidence_ledger.verification_status == "GROUNDED"

        # Teleprompter script must be clean
        assert "[" not in spec.spoken_script.spoken_text
        assert "]" not in spec.spoken_script.spoken_text
        assert spec.spoken_script.word_count > 0
        assert spec.spoken_script.estimated_read_time_seconds > 0.0

        # Shot list exists and covers timeline
        assert len(spec.shot_list) >= 4
        assert spec.shot_list[0].timecode_start_sec == 0.0
        assert spec.shot_list[-1].timecode_end_sec == 60.0

        # Factcheck notes cite primary source
        assert len(spec.factcheck_notes) >= 2
        assert spec.factcheck_notes[0].verdict == "CONFIRMED"

        # Truthful voice requirement: waiting for creator input
        assert spec.voice_requirement == VoiceInputRequirement.WAITING_FOR_INPUT
        assert spec.status == OriginalCreationStatus.WAITING_FOR_INPUT
        assert "WAITING_FOR_INPUT" in spec.status_reason

    def test_create_brief_with_voice_provided(self):
        spec = OriginalCreatorWorkflow.create_brief(
            topic="Fortnite Update",
            creator_context="New vehicle mobility added.",
            target_duration_sec=60,
            creator_voice_asset_id="asset-voice-creator-001",
        )
        assert spec.voice_requirement == VoiceInputRequirement.VOICE_PROVIDED
        assert spec.status == OriginalCreationStatus.READY_FOR_COMPOSITION
        assert spec.voice_asset_id == "asset-voice-creator-001"
        assert "Ready for timeline composition" in spec.status_reason

    def test_create_brief_with_procedural_tts_authorized(self):
        spec = OriginalCreatorWorkflow.create_brief(
            topic="Minecraft Pale Garden Update",
            target_duration_sec=45,
            allow_procedural_tts=True,
        )
        assert spec.voice_requirement == VoiceInputRequirement.PROCEDURAL_SYNTHESIS_ALLOWED
        assert spec.status == OriginalCreationStatus.READY_FOR_COMPOSITION

    def test_create_brief_in_portuguese(self):
        spec = OriginalCreatorWorkflow.create_brief(
            topic="Atualização do Fortnite",
            creator_context="O dano da escopeta mudou bastante.",
            target_duration_sec=60,
            language="pt",
        )
        assert spec.language == "pt"
        assert spec.spoken_script.language == "pt"
        assert "Você já viu" in spec.spoken_script.spoken_text or "Fortnite" in spec.spoken_script.spoken_text


class TestProductionV1Adapter:
    """Tests translation of OriginalCompositionSpec into canonical ProjectService payload."""

    def test_adapter_generates_valid_project_payload(self):
        spec = OriginalCreatorWorkflow.create_brief(
            topic="Apex Legends Patch",
            creator_context="Movement tech slide hop distance increased.",
            target_duration_sec=60,
        )
        payload = ProductionV1Adapter.to_canonical_project_payload(spec, user_id="creator-1")

        assert payload["title"] == spec.title
        assert payload["user_id"] == "creator-1"
        assert payload["target_duration_sec"] == 60
        assert payload["aspect_ratio"] == "9:16"

        # Verifies tracks structure
        assert len(payload["tracks"]) == 2
        video_track = payload["tracks"][0]
        audio_track = payload["tracks"][1]
        assert video_track["type"] == "video"
        assert audio_track["type"] == "audio"
        assert len(video_track["items"]) == len(spec.shot_list)

        # Verifies metadata honestly reports that physical render is NOT ready
        meta = payload["metadata"]
        assert meta["source_workflow"] == "original_creation_v1"
        assert meta["production_stage"] == "PLANNING_ARTIFACT"
        assert meta["rendered_mp4_ready"] is False
        assert meta["script_word_count"] == spec.spoken_script.word_count
