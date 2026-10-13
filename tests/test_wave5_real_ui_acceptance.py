# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Wave 5 Role 4 — Root Real UI & Ollama Acceptance Test Suite.

EntryPoint test suite matching tests/test_wave5_real_ui_*.py naming requirement.
Executes end-to-end assertions against:
- Local Ollama gemma4:e4b model and High reasoning effort
- Real Playwright browser automation on system Edge
- Isolated FastAPI backend with temporary SQLite
- Motion Graphics canonical status and timeline controls
- Settings persistence and negative error states
"""
import pytest

from tests.e2e_wave5.conftest import isolated_server, playwright_browser

from tests.e2e_wave5.test_ollama_gemma4_reasoning import (
    test_ollama_daemon_health_and_version,
    test_ollama_model_gemma4_installed,
    test_ollama_show_gemma4_capabilities,
    test_ai_provider_reasoning_effort_high_contract,
    test_live_ollama_inference_high_reasoning,
    test_live_ollama_streaming_and_no_mock,
)
from tests.e2e_wave5.test_audit_forensic_matrix import (
    test_adversarial_production_mocks_and_fakes,
    test_legacy_routes_active_in_app_jsx,
    test_unmounted_distribution_and_analytics_in_main_py,
    test_motion_player_canonical_status,
    test_master_requirements_category_counts,
)
from tests.e2e_wave5.test_real_browser_e2e import (
    test_browser_viewports_and_main_routes,
    test_settings_persistence_ollama_high,
    test_motion_canonical_player_and_timeline_dom,
    test_legacy_routes_not_falsely_claimed_retired,
    test_distribution_and_analytics_unmounted_disclosure,
    test_negative_disconnected_accounts_contract,
    test_media_negative_missing_asset,
    test_chat_websocket_ollama_live_roundtrip,
)


def test_wave5_suite_registry():
    """Verify all Wave 5 validation units are properly registered."""
    assert callable(test_live_ollama_inference_high_reasoning)
    assert callable(test_browser_viewports_and_main_routes)
    assert callable(test_master_requirements_category_counts)
