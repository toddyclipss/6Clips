# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 10 unified entrypoint for independent browser, backend, and Ollama acceptance suite."""

from tests.e2e_wave10.conftest import (
    isolated_server,
    playwright_browser,
    sample_media_mp4,
    sample_horizontal_mp4,
)

from tests.e2e_wave10.test_forensic_matrix_and_proposal_w10 import (
    test_master_proposal_sha256_hash,
    test_master_requirements_285_canonical_counts,
    test_official_roadmap_continuity_plan_absence,
    test_checkpoint_d_and_wave10_ancestry_proof,
    test_quality_gates_gt01_gt28_literal_definitions,
    test_adversarial_production_mocks_and_fakes_w10,
)

from tests.e2e_wave10.test_ollama_real_acceptance import (
    test_ollama_daemon_health_and_version,
    test_ollama_model_gemma4_installed_no_auto_pull,
    test_ollama_show_gemma4_capabilities_and_boolean_thinking,
    test_ai_provider_reasoning_effort_high_contract,
    test_live_ollama_inference_high_reasoning,
    test_live_ollama_streaming_and_no_mock,
    test_ollama_negative_invalid_model_fails_gracefully,
)

from tests.e2e_wave10.test_real_browser_journeys import (
    test_journey0_browser_viewports_and_all_mounted_routes,
    test_journey0_spa_api_404_protection_returns_json,
    test_journey1_settings_and_ollama_main_agent,
    test_journey2_library_media_upload_streaming_and_native_motion_export,
    test_journey3_catalog_hyperframes_instance_export,
    test_journey4_triple_candidate_partial_state_semantics,
    test_journey5_authentic_production_acceptance_guard,
    test_journey6_distribution_and_analytics_truth,
    test_journey7_real_visual_audio_preview_parity,
    test_legacy_routes_preserved_until_owner_signoff,
)

__all__ = [
    "isolated_server",
    "playwright_browser",
    "sample_media_mp4",
    "sample_horizontal_mp4",
    "test_master_proposal_sha256_hash",
    "test_master_requirements_285_canonical_counts",
    "test_official_roadmap_continuity_plan_absence",
    "test_checkpoint_d_and_wave10_ancestry_proof",
    "test_quality_gates_gt01_gt28_literal_definitions",
    "test_adversarial_production_mocks_and_fakes_w10",
    "test_ollama_daemon_health_and_version",
    "test_ollama_model_gemma4_installed_no_auto_pull",
    "test_ollama_show_gemma4_capabilities_and_boolean_thinking",
    "test_ai_provider_reasoning_effort_high_contract",
    "test_live_ollama_inference_high_reasoning",
    "test_live_ollama_streaming_and_no_mock",
    "test_ollama_negative_invalid_model_fails_gracefully",
    "test_journey0_browser_viewports_and_all_mounted_routes",
    "test_journey0_spa_api_404_protection_returns_json",
    "test_journey1_settings_and_ollama_main_agent",
    "test_journey2_library_media_upload_streaming_and_native_motion_export",
    "test_journey3_catalog_hyperframes_instance_export",
    "test_journey4_triple_candidate_partial_state_semantics",
    "test_journey5_authentic_production_acceptance_guard",
    "test_journey6_distribution_and_analytics_truth",
    "test_journey7_real_visual_audio_preview_parity",
    "test_legacy_routes_preserved_until_owner_signoff",
]
