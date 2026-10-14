// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
/**
 * Cached and Deduplicated Model Registry API Client.
 * Prevents redundant /api/config/model_registry HTTP requests on every component mount,
 * route change, or StrictMode double-mount, thereby preventing cascading queries to local Ollama.
 */

import http from "./http.js"

const CACHE_TTL_MS = 5 * 60 * 1000 // 5 minutes cache lifetime

let _cachedRegistry = null
let _cachedAt = 0
let _pendingPromise = null

/**
 * Fetch model registry with in-memory caching and in-flight promise deduplication.
 *
 * @param {Object} options
 * @param {boolean} [options.force=false] Force refresh ignoring cache
 * @param {AbortSignal} [options.signal=null] Optional AbortSignal
 * @returns {Promise<Object>} Model registry dictionary
 */
export async function fetchModelRegistry({ force = false, signal = null } = {}) {
  const now = Date.now()

  // 1. Return fresh cached data immediately if available and not forced
  if (!force && _cachedRegistry && (now - _cachedAt < CACHE_TTL_MS)) {
    return _cachedRegistry
  }

  // 2. Deduplicate concurrent requests (e.g., StrictMode double-mount, multiple components)
  if (!force && _pendingPromise) {
    return _pendingPromise
  }

  // 3. Dispatch fresh request
  _pendingPromise = (async () => {
    try {
      const { data } = await http.get("/api/config/model_registry", { signal })
      const reg = data?.value || {}
      _cachedRegistry = reg
      _cachedAt = Date.now()
      return reg
    } finally {
      _pendingPromise = null
    }
  })()

  return _pendingPromise
}

/**
 * Invalidate cached registry so subsequent fetch reads fresh state from server.
 */
export function invalidateModelRegistryCache() {
  _cachedRegistry = null
  _cachedAt = 0
  _pendingPromise = null
}

/**
 * Synchronous read of currently cached registry without making any network call.
 */
export function getCachedModelRegistry() {
  return _cachedRegistry
}
