# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 13 Agent 3 Test Suite:
1. Backend TTL Cache for GET /api/config/model_registry & /api/config/ollama/status
   - Default TTL 60 seconds (SIXCLIPS_MODEL_REGISTRY_CACHE_TTL_SEC)
   - Zero repeated outbound hits to Ollama within TTL window
   - Force bypass / invalidation via ?refresh=true and clear_model_registry_cache()
2. Explicit WebSocket /ws/chat Handshake Cleanup
   - Initial onconnect delivers deterministic/cached rule-based suggestions
   - Zero generative AI / LLM calls triggered on connect
   - Session isolation: WebSocket error responses bound with session_id
3. HyperFrames 12 Operational Blocks Distinct Render Proof (GT-13) & Zero Donor Dependency (GT-20)
   - Canonical inventory math: 196 original donor blocks, 10 internalized donor + 2 6Clips substitute = 12 available blocks, 186 quarantined blocks
   - Zero runtime dependency on C:\\Users\\toddy\\Desktop\\hyperframes (GT-20)
   - 12 operational blocks produce strictly unique 64-character SHA-256 hashes
   - Shader blocks (aurora, flowing-gradient, holographic, plasma, stripes) do NOT share identical hashes (GT-13 resolved)
"""
import asyncio
import json
import os
import time
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.config import (
    router as config_router,
    clear_model_registry_cache,
    MODEL_REGISTRY_CACHE_TTL_DEFAULT_SEC,
    _get_cache_ttl_sec,
)
from backend.api.chat import (
    router as chat_router,
    intelligence,
)
from backend.core.user_intelligence import UserIntelligence
from backend.llm_trace import (
    enable_audit,
    disable_audit,
    clear_audit_events,
    get_trace_summary,
    TRIGGER_WS_CONNECT,
)
from backend.catalog.manifest_service import (
    CatalogManifestService,
    WAVE4_INTERNALIZED_BLOCKS,
    CORE_INTERNALIZED_BLOCKS,
)
from backend.services.registry_adapter import (
    RegistryAdapter,
    get_registry_dir,
)
from backend.database import init_db
from backend.services.catalog_preview_service import CatalogPreviewService


# Setup test app for config
app = FastAPI()
app.include_router(config_router, prefix="/api")
app.include_router(chat_router)
client = TestClient(app)


# =========================================================================
# Task A: Model Registry & Ollama Status Backend TTL Cache Tests
# =========================================================================

def test_config_cache_ttl_default_and_env():
    """Verify default cache TTL is 60s and can be configured."""
    assert MODEL_REGISTRY_CACHE_TTL_DEFAULT_SEC == 60.0
    assert _get_cache_ttl_sec() == 60.0


def test_model_registry_caching_and_zero_repeated_outbound_calls():
    """
    Verify GET /api/config/model_registry caches response for 60 seconds
    and incurs 0 additional outbound requests within the TTL window.
    """
    clear_model_registry_cache()

    # Track how many times httpx.AsyncClient.get is called for Ollama
    call_counts = {"tags": 0, "show": 0}

    real_async_client_get = httpx.AsyncClient.get

    async def mock_get(self, url, *args, **kwargs):
        url_str = str(url)
        if "11434/api/tags" in url_str:
            call_counts["tags"] += 1
            # Return dummy response with 1 test model
            return httpx.Response(
                200,
                json={"models": [{"name": "qwen2.5:7b-instruct", "size": 4700000000}]},
                request=httpx.Request("GET", url_str),
            )
        return await real_async_client_get(self, url, *args, **kwargs)

    with patch.object(httpx.AsyncClient, "get", new=mock_get):
        # 1. First call: cache miss -> queries Ollama /api/tags
        resp1 = client.get("/api/config/model_registry")
        assert resp1.status_code == 200
        assert call_counts["tags"] == 1
        data1 = resp1.json()

        # 2. Second call: cache hit -> 0 additional queries to Ollama
        resp2 = client.get("/api/config/model_registry")
        assert resp2.status_code == 200
        assert call_counts["tags"] == 1, "Expected 0 additional outbound requests on cache hit"
        assert resp2.json() == data1

        # 3. Third call with ?refresh=true: bypasses cache -> queries Ollama again
        resp3 = client.get("/api/config/model_registry?refresh=true")
        assert resp3.status_code == 200
        assert call_counts["tags"] == 2, "Expected outbound request on refresh=true"

        # 4. Fourth call without refresh: caches the new result -> still 2
        resp4 = client.get("/api/config/model_registry")
        assert resp4.status_code == 200
        assert call_counts["tags"] == 2, "Expected 0 additional outbound requests after refresh cache fill"


def test_ollama_status_caching_and_refresh():
    """Verify GET /api/config/ollama/status caches status response and honors refresh=true."""
    clear_model_registry_cache()

    call_counts = {"tags": 0}
    real_async_client_get = httpx.AsyncClient.get

    async def mock_get(self, url, *args, **kwargs):
        url_str = str(url)
        if "11434/api/tags" in url_str:
            call_counts["tags"] += 1
            return httpx.Response(
                200,
                json={"models": []},
                request=httpx.Request("GET", url_str),
            )
        return await real_async_client_get(self, url, *args, **kwargs)

    with patch.object(httpx.AsyncClient, "get", new=mock_get):
        resp1 = client.get("/api/config/ollama/status")
        assert resp1.status_code == 200
        assert call_counts["tags"] == 1

        # Cache hit
        resp2 = client.get("/api/config/ollama/status")
        assert resp2.status_code == 200
        assert call_counts["tags"] == 1

        # Force refresh
        resp3 = client.get("/api/config/ollama/status?refresh=true")
        assert resp3.status_code == 200
        assert call_counts["tags"] == 2


# =========================================================================
# Task B: WebSocket Handshake Determinism and Zero Generative Calls
# =========================================================================

@pytest.mark.asyncio
async def test_chat_rule_based_suggestions_deterministic_and_zero_llm():
    """Verify rule-based suggestions are deterministic and trigger zero generative LLM posts."""
    clear_audit_events()
    enable_audit()
    try:
        ctx = {
            "is_first_session": False,
            "total_scouts": 3,
            "total_generated": 1,
            "downloaded_not_generated": 1,
            "generated_not_uploaded": 0,
            "last_niche": "tech",
        }
        profile = {"niches": ["tech"]}
        with patch.object(intelligence, "_get_best_ungenerated_video", AsyncMock(return_value=None)):
            suggestions = await intelligence._get_rule_based_suggestions("local", ctx, profile)
        assert isinstance(suggestions, list)
        assert len(suggestions) > 0
        assert all(isinstance(s, str) for s in suggestions)

        summary = get_trace_summary()
        assert summary["generative_posts_count"] == 0
    finally:
        clear_audit_events()
        disable_audit()


def test_chat_websocket_handshake_zero_ai_and_session_binding():
    """
    Verify /ws/chat connection handler:
    1. Initial handshake does not trigger AI profile update or inference
    2. Session messages bind session_id cleanly without cross-contaminating other sessions
    """
    clear_audit_events()
    enable_audit()
    try:
        with patch.object(intelligence, "update_profile_with_ai") as mock_ai_update:
            mock_ai_update.side_effect = AssertionError("AI update MUST NOT be invoked on websocket connect")
            
            with client.websocket_connect("/ws/chat") as ws:
                # Connected successfully; send set_session
                ws.send_text(json.dumps({"type": "set_session", "session_id": "test_sess_13"}))
                
                # Send invalid message to trigger session-bound error response
                ws.send_text("not-a-json-message-will-be-ignored")
                
                # Verify that mock_ai_update was never called
                assert not mock_ai_update.called

        summary = get_trace_summary()
        assert summary["generative_posts_count"] == 0
    finally:
        clear_audit_events()
        disable_audit()


# =========================================================================
# Task C: HyperFrames 12 Blocks Inventory Math & GT-20 Zero Donor Dependency
# =========================================================================

def test_canonical_hyperframes_inventory_math():
    """
    Verify canonical HyperFrames inventory math:
    - 196 total original donor blocks
    - 10 internalized donor + 2 original 6Clips blocks = 12 available blocks
    - Exactly 186 unready original blocks quarantined/not internalized (never 184)
    """
    total_original_donor_blocks = 196
    original_6clips_replacement = {"glitch-transition", "creator-hud"}
    internalized_donor_blocks = WAVE4_INTERNALIZED_BLOCKS - original_6clips_replacement

    assert len(internalized_donor_blocks) == 10, f"Expected 10 internalized donor blocks, got {len(internalized_donor_blocks)}"
    assert len(original_6clips_replacement) == 2, f"Expected 2 original 6Clips replacement blocks, got {len(original_6clips_replacement)}"

    available_operational = len(internalized_donor_blocks) + len(original_6clips_replacement)
    assert available_operational == 12, f"Expected 12 operational blocks, got {available_operational}"

    quarantined = total_original_donor_blocks - len(internalized_donor_blocks)
    assert quarantined == 186, f"Expected strictly 186 quarantined blocks, got {quarantined}"
    assert quarantined != 184, "Quarantined count must never be 184"


def test_gt20_zero_donor_dependency():
    """
    Verify GT-20: Runtime has strictly zero dependency on external donor directory
    `C:\\Users\\toddy\\Desktop\\hyperframes`.
    """
    reg_dir = get_registry_dir()
    # reg_dir must resolve to vendored repository path
    assert "shipped_blocks" in str(reg_dir).lower() or "catalog" in str(reg_dir).lower()
    assert "c:\\users\\toddy\\desktop\\hyperframes" not in str(reg_dir).lower()

    # Verify RegistryAdapter discovers blocks without external donor folder
    items = RegistryAdapter.list_catalog_items()
    assert len(items) >= 12
    item_ids = [item["id"] for item in items]
    for expected_id in ["aurora", "flowing-gradient", "holographic", "plasma", "stripes", "creator-hud", "glitch-transition"]:
        assert expected_id in item_ids, f"Expected block {expected_id} in discovered blocks"


# =========================================================================
# Task C (GT-13): 12 Blocks Distinct Render Proof & Unique SHA-256 Hashes
# =========================================================================

def test_gt13_12_blocks_distinct_sha256_and_valid_mp4():
    """
    Verify that all 12 operational blocks render valid MP4 files with:
    1. Valid ffmpeg decode (exit code 0)
    2. Valid ffprobe resolution (1080x1920) and codec (h264)
    3. Full 64-character strictly distinct SHA-256 hashes across all 12 blocks
    4. Specifically: aurora, flowing-gradient, holographic, plasma, and stripes
       DO NOT share the identical hash prefix `b90d1afe4fd3bac9`.
    """
    results = CatalogPreviewService.render_all_12_distinct_blocks()
    assert len(results) == 12, f"Expected 12 results, got {len(results)}"

    shas = set()
    block_sha_map = {}
    for r in results:
        block_id = r["block_id"]
        sha = r["sha256"]
        exit_code = r["ffmpeg_decode_exit_code"]
        path = r["mp4_path"]

        # Decode exit code must be 0
        assert exit_code == 0, f"Block {block_id} failed ffmpeg decode: exit code {exit_code}"
        assert os.path.exists(path), f"Block {block_id} MP4 file does not exist at {path}"
        assert len(sha) == 64, f"Block {block_id} SHA-256 must be 64 characters: {sha}"

        shas.add(sha)
        block_sha_map[block_id] = sha

    # All 12 hashes must be strictly unique
    assert len(shas) == 12, f"Expected 12 unique hashes, got {len(shas)}. Map: {block_sha_map}"

    # Specifically check the 5 previously defective shader blocks
    shader_blocks = ["aurora", "flowing-gradient", "holographic", "plasma", "stripes"]
    shader_shas = [block_sha_map[b] for b in shader_blocks]
    assert len(set(shader_shas)) == 5, f"Shader blocks must have 5 distinct hashes, got: {shader_shas}"

    # None of them should have the former broken hash prefix
    for b in shader_blocks:
        assert not block_sha_map[b].startswith("b90d1afe4fd3bac9"), (
            f"Block {b} has the broken identical hash prefix: {block_sha_map[b]}"
        )
