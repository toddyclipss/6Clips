# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""6Clips Media Intelligence — audiovisual analysis, scene cuts, audio energy, reframing, and caption grounding."""

from backend.media_intelligence.audio_energy import AudioEnergyProfile, analyze_audio_energy
from backend.media_intelligence.scene_analyzer import (
    detect_scene_changes,
    detect_frozen_frames,
    detect_black_frames,
)
from backend.media_intelligence.reframing import ReframePreset, build_reframe_filter
from backend.media_intelligence.caption_grounding import ground_and_remap_captions
from backend.media_intelligence.candidate_ranker import (
    CandidateSegment,
    generate_and_rank_segments,
)

__all__ = [
    "AudioEnergyProfile",
    "analyze_audio_energy",
    "detect_scene_changes",
    "detect_frozen_frames",
    "detect_black_frames",
    "ReframePreset",
    "build_reframe_filter",
    "ground_and_remap_captions",
    "CandidateSegment",
    "generate_and_rank_segments",
]
