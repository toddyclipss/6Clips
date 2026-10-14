// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
/**
 * Catalog Inventory Contract (Version 1) Reconciler and Data Layer.
 *
 * Implements the cross-agent v1 contract:
 * - 196 verified original donor blocks in hyperframes_196_inventory.json.
 * - Exactly 10 internalized donor blocks: aurora, data-chart, flowing-gradient, holographic,
 *   instagram-follow, plasma, stripes, tiktok-follow, weight-wave, yt-lower-third.
 * - Exactly 2 6Clips-authored blocks: creator-hud, glitch-transition (NOT part of the 196 originals).
 * - Total operational blocks: 12.
 * - Total unported donor blocks: 186.
 * - 4 primary views: AVAILABLE_NOW (12), ALL_ORIGINAL_196 (196), NEEDS_WORK, BLOCKED.
 * - If backend manifest cannot be established, exposes honest status rather than fabricating 196.
 */
import http from "../api/http"
import fixtureData from "../fixtures/hyperframes_196_fixture.json"

export const INTERNALIZED_DONOR_IDS = new Set([
  "aurora",
  "data-chart",
  "flowing-gradient",
  "holographic",
  "instagram-follow",
  "plasma",
  "stripes",
  "tiktok-follow",
  "weight-wave",
  "yt-lower-third",
])

export const SIXCLIPS_ORIGINAL_BLOCKS = [
  {
    id: "creator-hud",
    title: "Creator HUD",
    description: "Original 6Clips animated creator heads-up display overlay.",
    category: "mock-ui",
    tags: ["hud", "creator", "overlay", "6clips"],
    author: "6Clips",
    license: "Apache-2.0",
    license_status: "VERIFIED_PERMISSIVE",
    license_evidence: "6Clips repository original work (Apache-2.0).",
    integration_status: "INTERNALIZED",
    origin: "6CLIPS_ORIGINAL",
    is6ClipsOriginal: true,
    blocker_reason: null,
    supported_aspects: ["9:16", "16:9"],
    aspect_9_16: "NATIVE",
    aspect_16_9: "NATIVE",
    duration: 5.0,
    variables_count: 4,
    variables: [
      { name: "handle", default: "@creator", description: "Creator handle" },
      { name: "followers", default: "128K", description: "Follower count" },
      { name: "status", default: "LIVE", description: "Status badge" },
      { name: "accent_color", default: "#6366f1", description: "Accent color hex" },
    ],
  },
  {
    id: "glitch-transition",
    title: "Glitch Transition",
    description: "Original 6Clips chromatic aberration glitch transition effect.",
    category: "transitions",
    tags: ["glitch", "transition", "rgb", "6clips"],
    author: "6Clips",
    license: "Apache-2.0",
    license_status: "VERIFIED_PERMISSIVE",
    license_evidence: "6Clips repository original work (Apache-2.0).",
    integration_status: "INTERNALIZED",
    origin: "6CLIPS_ORIGINAL",
    is6ClipsOriginal: true,
    blocker_reason: null,
    supported_aspects: ["9:16", "16:9"],
    aspect_9_16: "NATIVE",
    aspect_16_9: "NATIVE",
    duration: 1.5,
    variables_count: 2,
    variables: [
      { name: "intensity", default: "medium", description: "Glitch intensity (subtle, medium, extreme)" },
      { name: "color_shift", default: "cyan-magenta", description: "Color split mode" },
    ],
  },
]

export const SIXCLIPS_ORIGINAL_IDS = new Set(SIXCLIPS_ORIGINAL_BLOCKS.map((b) => b.id))

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
  if (data.blocks.length !== 196 || data.original_block_count !== 196) {
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
 * Fetch live inventory from backend with contract verification.
 */
export async function fetchBackendInventory(signal = null) {
  try {
    const res = await http.get("/api/catalog/inventory", { signal })
    const validation = validateV1Manifest(res.data)
    if (!validation.valid) {
      return {
        status: "BLOCKED_INVENTORY_RECONCILIATION",
        error: validation.error,
        manifest: null,
      }
    }
    return {
      status: "VERIFIED_LIVE",
      manifest: res.data,
      error: null,
    }
  } catch (err) {
    if (signal?.aborted) throw err
    const isOffline = typeof navigator !== "undefined" && !navigator.onLine
    if (isOffline) {
      return {
        status: "OFFLINE_BLOCKED",
        error: "Network connection is offline. Please check your connectivity.",
        manifest: null,
      }
    }
    // Backend endpoint pending Agent 1 merge or returning 404
    return {
      status: "UNAVAILABLE_BACKEND_PENDING",
      error: "Backend inventory endpoint (/api/catalog/inventory) is not yet available (pending Agent 1 integration merge).",
      manifest: null,
      fixtureAvailable: true,
    }
  }
}

/**
 * Loads the explicitly labeled Stage 1 test fixture.
 */
export function getStage1Fixture() {
  const validation = validateV1Manifest(fixtureData)
  if (!validation.valid) {
    return {
      status: "BLOCKED_INVENTORY_RECONCILIATION",
      error: validation.error,
      manifest: null,
    }
  }
  return {
    status: "STAGE1_FIXTURE",
    manifest: fixtureData,
    error: null,
    disclosure: "Stage 1 Test Fixture (Simulated Agent 1 v1 Manifest — Live Backend Pending Agent 1 Merge)",
  }
}

/**
 * Filters and categorizes inventory items.
 */
export function reconcileCatalog({
  manifest,
  viewMode = "AVAILABLE_NOW", // AVAILABLE_NOW | ALL_ORIGINAL_196 | NEEDS_WORK | BLOCKED
  category = "all",
  aspectRatio = "9:16",
  search = "",
}) {
  const donorBlocks = manifest?.blocks || []

  // Ensure donor blocks have origin set
  const normalizedDonor = donorBlocks.map((b) => ({
    ...b,
    origin: "HYPERFRAMES_DONOR",
    isOperational: b.integration_status === "INTERNALIZED",
  }))

  // Operational items: 10 donor internalized + 2 6Clips original = 12 total
  const operationalItems = [
    ...normalizedDonor.filter((b) => b.integration_status === "INTERNALIZED"),
    ...SIXCLIPS_ORIGINAL_BLOCKS.map((b) => ({
      ...b,
      isOperational: true,
    })),
  ]

  // Counts across the 4 primary views
  const counts = {
    AVAILABLE_NOW: operationalItems.length,
    ALL_ORIGINAL_196: normalizedDonor.length,
    NEEDS_WORK: normalizedDonor.filter(
      (b) => b.integration_status === "NEEDS_ADAPTATION" || b.integration_status === "ELIGIBLE_NOT_PORTED"
    ).length,
    BLOCKED: normalizedDonor.filter(
      (b) =>
        b.integration_status === "BLOCKED_LICENSE" ||
        b.integration_status === "BLOCKED_SECURITY" ||
        b.integration_status === "BLOCKED_DEPENDENCY" ||
        b.license_status === "RESTRICTED"
    ).length,
  }

  // Select base list for the active view
  let baseList = []
  if (viewMode === "AVAILABLE_NOW") {
    baseList = operationalItems
  } else if (viewMode === "ALL_ORIGINAL_196") {
    baseList = normalizedDonor
  } else if (viewMode === "NEEDS_WORK") {
    baseList = normalizedDonor.filter(
      (b) => b.integration_status === "NEEDS_ADAPTATION" || b.integration_status === "ELIGIBLE_NOT_PORTED"
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
    const cLower = category.toLowerCase()
    baseList = baseList.filter((b) => (b.category || "").toLowerCase() === cLower)
  }

  // Filter search
  if (search && search.trim()) {
    const q = search.trim().toLowerCase()
    baseList = baseList.filter((b) => {
      const matchId = (b.id || "").toLowerCase().includes(q)
      const matchTitle = (b.title || "").toLowerCase().includes(q)
      const matchDesc = (b.description || "").toLowerCase().includes(q)
      const matchLicense = (b.license_status || b.license || "").toLowerCase().includes(q)
      const matchBlocker = (b.blocker_reason || "").toLowerCase().includes(q)
      const matchTags = Array.isArray(b.tags) && b.tags.some((t) => String(t).toLowerCase().includes(q))
      return matchId || matchTitle || matchDesc || matchLicense || matchBlocker || matchTags
    })
  }

  // Filter aspect ratio if requested
  if (aspectRatio) {
    const is9x16 = aspectRatio === "9:16"
    baseList = baseList.filter((b) => {
      if (Array.isArray(b.supported_aspects)) {
        return b.supported_aspects.includes(aspectRatio)
      }
      if (is9x16) {
        return b.aspect_9_16 !== "UNSUPPORTED"
      } else {
        return b.aspect_16_9 !== "UNSUPPORTED"
      }
    })
  }

  return {
    items: baseList,
    totalCount: baseList.length,
    counts,
  }
}
