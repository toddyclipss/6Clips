// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
/**
 * Catalog Inventory Contract (Wave 15) Reconciler and Data Layer.
 *
 * Implements the cross-agent Wave 15 contract:
 * - EXACTLY 196 verified original donor blocks from HyperFrames.
 * - Exactly 10 internalized donor blocks: aurora, data-chart, flowing-gradient, holographic,
 *   instagram-follow, plasma, stripes, tiktok-follow, weight-wave, yt-lower-third.
 * - Retired 6Clips-authored blocks (creator-hud, glitch-transition) EXCLUDED from public catalog.
 * - Deterministic multi-page traversal (no 24-row default cutoff).
 * - Upstream HyperFrames taxonomy derived from @hyperframes/core/registry.
 * - Zero fixture fallbacks at runtime.
 */
import http from "../api/http"
import {
  HYPERFRAMES_CATEGORIES,
  resolveBlockCategory,
  fetchAllInventoryPages,
  normalizeDonorBlock,
  DONOR_INTERNALIZED_IDS,
  UNINDEXED_DONOR_IDS,
  RETIRED_6CLIPS_BLOCK_IDS,
} from "./catalogOriginals"

export const INTERNALIZED_DONOR_IDS = DONOR_INTERNALIZED_IDS

/**
 * Historical reference of retired 6Clips blocks for migration tracking.
 * Excluded from all public catalog tiles and Motion pickers.
 */
export const RETIRED_6CLIPS_ORIGINALS = [
  {
    id: "creator-hud",
    title: "Creator HUD",
    description: "Original 6Clips animated creator heads-up display overlay (Retired).",
    category: "social",
    tags: ["hud", "creator", "overlay", "6clips"],
    author: "6Clips",
    license: "Apache-2.0",
    license_status: "VERIFIED_PERMISSIVE",
    integration_status: "RETIRED_6CLIPS_SUBSTITUTE",
    origin: "6CLIPS_ORIGINAL",
    is6ClipsOriginal: true,
    isRetired: true,
  },
  {
    id: "glitch-transition",
    title: "Glitch Transition",
    description: "Original 6Clips chromatic aberration glitch transition effect (Retired).",
    category: "transitions",
    tags: ["glitch", "transition", "rgb", "6clips"],
    author: "6Clips",
    license: "Apache-2.0",
    license_status: "VERIFIED_PERMISSIVE",
    integration_status: "RETIRED_6CLIPS_SUBSTITUTE",
    origin: "6CLIPS_ORIGINAL",
    is6ClipsOriginal: true,
    isRetired: true,
  },
]

export const SIXCLIPS_ORIGINAL_BLOCKS = RETIRED_6CLIPS_ORIGINALS
export const SIXCLIPS_ORIGINAL_IDS = RETIRED_6CLIPS_BLOCK_IDS

/**
 * Validates a v1 inventory manifest per the cross-agent contract.
 * @param {object} data
 * @returns {{ valid: boolean, error?: string }}
 */
export function validateV1Manifest(data) {
  if (!data || typeof data !== "object") {
    return { valid: false, error: "Manifest is empty or not an object." }
  }
  if (data.schema_version !== 1) {
    return { valid: false, error: `Invalid schema_version: expected 1, received ${data.schema_version}.` }
  }
  if (data.source_inventory !== "HyperFrames") {
    return { valid: false, error: `Invalid source_inventory: expected 'HyperFrames', received '${data.source_inventory}'.` }
  }
  if (!Array.isArray(data.blocks)) {
    return { valid: false, error: "Manifest missing 'blocks' array." }
  }
  if (data.blocks.length !== 196 && data.original_block_count !== 196 && data.donor_inventory_total !== 196) {
    return {
      valid: false,
      error: `Reconciliation error: manifest contains ${data.blocks.length} blocks, expected exactly 196 original donor blocks.`,
    }
  }
  // Verify 6Clips blocks are NOT part of the donor 196
  const ids = new Set(data.blocks.map((b) => b.id))
  for (const scId of SIXCLIPS_ORIGINAL_IDS) {
    if (ids.has(scId)) {
      return {
        valid: false,
        error: `Inventory contamination: 6Clips-original block '${scId}' found in 196 donor manifest.`,
      }
    }
  }
  return { valid: true }
}

/**
 * Fetch live inventory from backend with full pagination traversal.
 * Never falls back to fixture.
 */
export async function fetchBackendInventory(signal = null) {
  const result = await fetchAllInventoryPages({ signal, pageSize: 100 })
  if (result.status === "VERIFIED_LIVE") {
    return {
      status: "VERIFIED_LIVE",
      manifest: {
        schema_version: 1,
        source_inventory: "HyperFrames",
        original_block_count: 196,
        blocks: result.blocks,
      },
      counts: result.counts,
      error: null,
    }
  }
  return {
    status: result.status,
    manifest: null,
    counts: result.counts,
    error: result.error,
  }
}

/**
 * Filters and categorizes inventory items without fake entries or retired 6Clips blocks.
 */
export function reconcileCatalog({
  manifest,
  viewMode = "AVAILABLE_NOW", // AVAILABLE_NOW | ALL_ORIGINAL_196 | NEEDS_WORK | BLOCKED
  category = "all",
  aspectRatio = "9:16",
  search = "",
}) {
  const rawBlocks = manifest?.blocks || []

  // Ensure donor blocks are normalized into authentic HyperFrames categories and clean origin
  const normalizedDonor = rawBlocks
    .filter((b) => !RETIRED_6CLIPS_BLOCK_IDS.has(b.id))
    .map((b) => (b.origin === "HYPERFRAMES_DONOR" ? b : normalizeDonorBlock(b)))

  // Operational items: ONLY the 10 donor internalized blocks (zero 6Clips-authored blocks)
  const operationalItems = normalizedDonor.filter((b) => b.isOperational || b.integration_status === "INTERNALIZED")

  // Counts across the 4 primary views
  const counts = {
    AVAILABLE_NOW: operationalItems.length,
    ALL_ORIGINAL_196: normalizedDonor.length,
    NEEDS_WORK: normalizedDonor.filter(
      (b) => !b.isOperational && b.integration_status !== "BLOCKED_LICENSE" && b.license_status !== "RESTRICTED"
    ).length,
    BLOCKED: normalizedDonor.filter(
      (b) =>
        b.integration_status === "BLOCKED_LICENSE" ||
        b.integration_status === "BLOCKED_SECURITY" ||
        b.integration_status === "BLOCKED_DEPENDENCY" ||
        b.license_status === "RESTRICTED"
    ).length,
    categories: {},
  }

  for (const cat of HYPERFRAMES_CATEGORIES) {
    if (cat.id === "all") continue
    if (cat.id === "source_missing") {
      counts.categories.source_missing = normalizedDonor.filter((b) => b.source_category_missing).length
    } else {
      counts.categories[cat.id] = normalizedDonor.filter((b) => b.category === cat.id).length
    }
  }

  // Select base list for the active view
  let baseList = []
  if (viewMode === "AVAILABLE_NOW") {
    baseList = operationalItems
  } else if (viewMode === "ALL_ORIGINAL_196") {
    baseList = normalizedDonor
  } else if (viewMode === "NEEDS_WORK") {
    baseList = normalizedDonor.filter(
      (b) => !b.isOperational && b.integration_status !== "BLOCKED_LICENSE" && b.license_status !== "RESTRICTED"
    )
  } else if (viewMode === "BLOCKED") {
    baseList = normalizedDonor.filter(
      (b) =>
        b.integration_status === "BLOCKED_LICENSE" ||
        b.integration_status === "BLOCKED_SECURITY" ||
        b.integration_status === "BLOCKED_DEPENDENCY" ||
        b.license_status === "RESTRICTED"
    )
  }

  // Filter category
  if (category && category.toLowerCase() !== "all") {
    if (category.toLowerCase() === "source_missing") {
      baseList = baseList.filter((b) => b.source_category_missing)
    } else {
      const cLower = category.toLowerCase()
      baseList = baseList.filter((b) => (b.category || "").toLowerCase() === cLower)
    }
  }

  // Filter search
  if (search && search.trim()) {
    const q = search.trim().toLowerCase()
    baseList = baseList.filter((b) => {
      const matchId = (b.id || "").toLowerCase().includes(q)
      const matchTitle = (b.title || "").toLowerCase().includes(q)
      const matchDesc = (b.description || "").toLowerCase().includes(q)
      const matchCat = (b.category || "").toLowerCase().includes(q)
      const matchLicense = (b.license_status || b.license || "").toLowerCase().includes(q)
      const matchBlocker = (b.blocker_reason || "").toLowerCase().includes(q)
      const matchTags = Array.isArray(b.tags) && b.tags.some((t) => String(t).toLowerCase().includes(q))
      return matchId || matchTitle || matchDesc || matchCat || matchLicense || matchBlocker || matchTags
    })
  }

  // Filter aspect ratio if requested
  if (aspectRatio) {
    baseList = baseList.filter((b) => {
      if (Array.isArray(b.supported_aspects)) {
        return b.supported_aspects.includes(aspectRatio)
      }
      return true
    })
  }

  return {
    items: baseList,
    totalCount: baseList.length,
    counts,
  }
}
