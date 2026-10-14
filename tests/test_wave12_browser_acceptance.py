# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 12 Stage 3: Unified Browser, Backend, and Idle-Egress Acceptance Suite.

Imports and exposes all Stage 3 validator tests:
- Machine baseline & process attribution
- Proposal SHA-256 and 285 canonical requirements audit
- Wave 11 visual regressions & Refine zero-spinner verification
- Positive control real Ollama gemma4:e4b inference
- Adversarial attack and boundary cases
- Real idle network windows and traffic matrix verification
"""

from tests.e2e_wave12.conftest import (
    isolated_server,
    playwright_browser,
)

from tests.e2e_wave12.test_machine_baseline_and_process_attribution import (
    test_ollama_daemon_and_resident_state,
    test_machine_baseline_capture_and_persistence,
    test_process_attribution_resolution,
)

from tests.e2e_wave12.test_reference_proposal_and_requirements_285 import (
    test_master_proposal_sha256_hash,
    test_master_requirements_285_canonical_counts,
    test_official_roadmap_continuity_plan_absence,
    test_git_ancestry_proof,
)

from tests.e2e_wave12.test_wave11_visual_regression_and_motion import (
    test_refine_mode_zero_overlapping_spinners_and_no_eternal_loading,
    test_catalog_bounded_loading_and_resources_display,
    test_studio_preview_stage_source_code_contract,
)

from tests.e2e_wave12.test_positive_control_and_real_ollama import (
    test_positive_control_authorized_guard_check,
    test_live_ollama_streaming_positive_control,
    test_privacy_and_no_payload_leaks,
)

from tests.e2e_wave12.test_adversarial_attack_cases import (
    test_attack_unauthorized_generative_inference_fails_closed,
    test_attack_discovery_route_permitted_generative_blocked,
    test_attack_unauthorized_publish_schedule_blocked,
    test_attack_outbound_allowlist_enforcement,
    test_attack_unknown_api_404_no_external_egress,
    test_attack_unconfigured_cloud_keys_no_egress,
    test_attack_offline_ollama_graceful_handling,
)

from tests.e2e_wave12.test_real_idle_network_windows import (
    test_window_a_backend_idle_zero_inference_and_zero_external,
    test_window_b_browser_global_chat_idle_zero_inference,
    test_window_c_motion_refine_idle_zero_inference,
    test_traffic_matrix_coverage_and_classification,
)

__all__ = [
    "isolated_server",
    "playwright_browser",
    "test_ollama_daemon_and_resident_state",
    "test_machine_baseline_capture_and_persistence",
    "test_process_attribution_resolution",
    "test_master_proposal_sha256_hash",
    "test_master_requirements_285_canonical_counts",
    "test_official_roadmap_continuity_plan_absence",
    "test_git_ancestry_proof",
    "test_refine_mode_zero_overlapping_spinners_and_no_eternal_loading",
    "test_catalog_bounded_loading_and_resources_display",
    "test_studio_preview_stage_source_code_contract",
    "test_positive_control_authorized_guard_check",
    "test_live_ollama_streaming_positive_control",
    "test_privacy_and_no_payload_leaks",
    "test_attack_unauthorized_generative_inference_fails_closed",
    "test_attack_discovery_route_permitted_generative_blocked",
    "test_attack_unauthorized_publish_schedule_blocked",
    "test_attack_outbound_allowlist_enforcement",
    "test_attack_unknown_api_404_no_external_egress",
    "test_attack_unconfigured_cloud_keys_no_egress",
    "test_attack_offline_ollama_graceful_handling",
    "test_window_a_backend_idle_zero_inference_and_zero_external",
    "test_window_b_browser_global_chat_idle_zero_inference",
    "test_window_c_motion_refine_idle_zero_inference",
    "test_traffic_matrix_coverage_and_classification",
]
