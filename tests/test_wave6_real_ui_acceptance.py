# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 6 Role 4 — Root Real UI & Ollama Acceptance Test Suite Entrypoint.

EntryPoint test suite matching tests/test_wave6_real_ui_*.py naming requirement.
Executes end-to-end assertions against:
- Local Ollama gemma4:e4b model and High reasoning effort
- Real Playwright browser automation on system Edge
- Isolated FastAPI backend with temporary SQLite & data dir
- Mounted Distribution and Analytics routes
- Motion Graphics canonical status, review bridge & timeline controls
- Settings persistence, SPA 404 protection, and negative error states
- 285 master requirements and forensic adversarial audit
"""
import pytest

from tests.e2e_wave6.conftest import isolated_server, playwright_browser

from tests.e2e_wave6.test_ollama_real_acceptance import (
    test_ollama_daemon_health_and_version,
    test_ollama_model_gemma4_installed_no_auto_pull,
    test_ollama_show_gemma4_capabilities_and_boolean_thinking,
    test_ai_provider_reasoning_effort_high_contract,
    test_live_ollama_inference_high_reasoning,
    test_live_ollama_streaming_and_no_mock,
    test_ollama_negative_invalid_model_fails_gracefully,
)
from tests.e2e_wave6.test_audit_forensic_matrix_w6 import (
    test_master_requirements_canonical_matrix_counts,
    test_official_roadmap_continuity_plan_status,
    test_adversarial_production_mocks_and_fakes,
    test_legacy_routes_active_in_app_jsx,
    test_motion_player_canonical_status,
)
from tests.e2e_wave6.test_real_browser_journeys import (
    test_browser_viewports_and_all_mounted_routes,
    test_spa_api_404_protection,
    test_distribution_mounted_and_truthful_unconnected,
    test_analytics_mounted_and_no_fake_metrics,
    test_motion_canonical_player_and_review_bridge,
    test_legacy_routes_preserved_until_owner_signoff,
    test_settings_persistence_ollama_high,
    test_chat_websocket_live_ollama,
    test_media_negative_missing_asset,
    test_catalog_blocks_readiness,
)


def test_wave6_suite_registry():
    """Verify all Wave 6 validation units are properly registered."""
    assert callable(test_live_ollama_inference_high_reasoning)
    assert callable(test_browser_viewports_and_all_mounted_routes)
    assert callable(test_master_requirements_canonical_matrix_counts)
