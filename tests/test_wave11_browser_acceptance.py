# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 11 unified entrypoint for independent browser, backend, and Ollama acceptance suite."""

from tests.e2e_wave11.conftest import (
    isolated_server,
    playwright_browser,
    sample_media_mp4,
    sample_horizontal_mp4,
)

from tests.e2e_wave11.test_forensic_matrix_and_proposal_w11 import (
    test_master_proposal_sha256_hash,
    test_master_requirements_285_canonical_counts,
    test_official_roadmap_continuity_plan_absence,
    test_wave11_ancestry_proof,
    test_quality_gates_gt01_gt28_literal_definitions,
    test_adversarial_production_mocks_and_fakes_w11,
)

from tests.e2e_wave11.test_p0_double_spinner_and_refine import (
    test_p0_refine_mode_zero_overlapping_spinners_and_no_eternal_loading,
    test_p0_single_spinner_during_active_project_loading,
    test_p0_motion_state_bootstrap_api,
    test_p0_catalog_resource_list_bounded_loading,
)

from tests.e2e_wave11.test_ollama_real_acceptance_w11 import (
    test_ollama_daemon_health_and_version,
    test_ollama_model_gemma4_installed_no_auto_pull,
    test_ollama_show_gemma4_capabilities_and_boolean_thinking,
    test_ai_provider_reasoning_effort_high_contract,
    test_live_ollama_inference_high_reasoning,
    test_live_ollama_streaming_and_no_mock,
    test_ollama_negative_invalid_model_fails_gracefully,
)

from tests.e2e_wave11.test_real_user_journeys_w11 import (
    test_user1_settings_and_ollama_main_agent,
    test_user2_library_media_upload_streaming_and_native_motion_export,
    test_user3_catalog_hyperframes_instance_export,
    test_user4_tools_parity_and_cas_concurrency,
    test_user5_authentic_production_acceptance_guard,
    test_user6_distribution_and_analytics_truth,
    test_user7_hyperframes_zero_runtime_donor_dependency,
    test_user8_gt09_10_11_22_and_responsive_viewports,
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
    "test_wave11_ancestry_proof",
    "test_quality_gates_gt01_gt28_literal_definitions",
    "test_adversarial_production_mocks_and_fakes_w11",
    "test_p0_refine_mode_zero_overlapping_spinners_and_no_eternal_loading",
    "test_p0_single_spinner_during_active_project_loading",
    "test_p0_motion_state_bootstrap_api",
    "test_p0_catalog_resource_list_bounded_loading",
    "test_ollama_daemon_health_and_version",
    "test_ollama_model_gemma4_installed_no_auto_pull",
    "test_ollama_show_gemma4_capabilities_and_boolean_thinking",
    "test_ai_provider_reasoning_effort_high_contract",
    "test_live_ollama_inference_high_reasoning",
    "test_live_ollama_streaming_and_no_mock",
    "test_ollama_negative_invalid_model_fails_gracefully",
    "test_user1_settings_and_ollama_main_agent",
    "test_user2_library_media_upload_streaming_and_native_motion_export",
    "test_user3_catalog_hyperframes_instance_export",
    "test_user4_tools_parity_and_cas_concurrency",
    "test_user5_authentic_production_acceptance_guard",
    "test_user6_distribution_and_analytics_truth",
    "test_user7_hyperframes_zero_runtime_donor_dependency",
    "test_user8_gt09_10_11_22_and_responsive_viewports",
    "test_legacy_routes_preserved_until_owner_signoff",
]
