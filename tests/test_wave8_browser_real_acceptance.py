# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 8 unified entrypoint for independent browser, backend, and Ollama acceptance suite."""

from tests.e2e_wave8.conftest import (
    isolated_server,
    playwright_browser,
    sample_media_mp4,
)

from tests.e2e_wave8.test_ollama_real_acceptance import (
    test_ollama_daemon_health_and_version,
    test_ollama_model_gemma4_installed_no_auto_pull,
    test_ollama_show_gemma4_capabilities_and_boolean_thinking,
    test_ai_provider_reasoning_effort_high_contract,
    test_live_ollama_inference_high_reasoning,
    test_live_ollama_streaming_and_no_mock,
    test_ollama_negative_invalid_model_fails_gracefully,
)

from tests.e2e_wave8.test_forensic_matrix_and_proposal_w8 import (
    test_master_requirements_285_canonical_counts,
    test_official_roadmap_continuity_plan_absence,
    test_checkpoint_b_ancestry_proof,
    test_adversarial_production_mocks_and_fakes_w8,
    test_quality_gates_gt01_gt28_literal_definitions,
)

from tests.e2e_wave8.test_real_browser_journeys import (
    test_browser_viewports_and_all_mounted_routes,
    test_spa_api_404_protection_returns_json,
    test_settings_and_ollama_high_stream,
    test_library_media_upload_and_http_206_streaming,
    test_motion_canonical_player_and_review_bridge,
    test_motion_native_clip_renderer_export,
    test_hyperframes_catalog_blocks_and_export_contract,
    test_original_creator_voice_input_gating,
    test_distribution_and_analytics_truth_disconnected,
    test_legacy_routes_preserved_until_owner_signoff,
)

__all__ = [
    "isolated_server",
    "playwright_browser",
    "sample_media_mp4",
    "test_ollama_daemon_health_and_version",
    "test_ollama_model_gemma4_installed_no_auto_pull",
    "test_ollama_show_gemma4_capabilities_and_boolean_thinking",
    "test_ai_provider_reasoning_effort_high_contract",
    "test_live_ollama_inference_high_reasoning",
    "test_live_ollama_streaming_and_no_mock",
    "test_ollama_negative_invalid_model_fails_gracefully",
    "test_master_requirements_285_canonical_counts",
    "test_official_roadmap_continuity_plan_absence",
    "test_checkpoint_b_ancestry_proof",
    "test_adversarial_production_mocks_and_fakes_w8",
    "test_quality_gates_gt01_gt28_literal_definitions",
    "test_browser_viewports_and_all_mounted_routes",
    "test_spa_api_404_protection_returns_json",
    "test_settings_and_ollama_high_stream",
    "test_library_media_upload_and_http_206_streaming",
    "test_motion_canonical_player_and_review_bridge",
    "test_motion_native_clip_renderer_export",
    "test_hyperframes_catalog_blocks_and_export_contract",
    "test_original_creator_voice_input_gating",
    "test_distribution_and_analytics_truth_disconnected",
    "test_legacy_routes_preserved_until_owner_signoff",
]
