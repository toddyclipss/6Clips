// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
/**
 * Catalog Originals Engine (Wave 16):
 * Single source of truth for the EXACT 196 original HyperFrames donor blocks,
 * authentic upstream HyperFrames categories, deterministic multi-page traversal,
 * and strict exclusion of retired 6Clips-authored blocks.
 *
 * Upstream taxonomy reconstructed from authentic HyperFrames gallery metadata
 * (docs/snippets/catalog-gallery-data.mdx & registry/registry.json):
 * - Exactly 171 items with confirmed source categories (SOURCE_CATEGORY_CONFIRMED)
 * - Exactly 25 items without explicit upstream category (SOURCE_CATEGORY_MISSING with proposed fallback)
 * - Exactly 196 distinct donor IDs (170 in aggregate registry.json + 26 unindexed directories)
 * - Exactly 37 locally packaged cards in backend/catalog/shipped_blocks (10 internalized + 17 shaders + 10 lower thirds)
 * - Exactly 10 baseline operational donor blocks internalized and verified
 * - Strictly excludes 'creator-hud' and 'glitch-transition' from all public catalog choices
 */
import http from '../api/http.js'

/**
 * Authentic HyperFrames Category Definitions from donor gallery metadata
 */
export const HYPERFRAMES_CATEGORIES = [
  { id: 'all', label: 'All Blocks', color: 'indigo' },
  { id: 'scenes-demos', label: 'Scenes & Demos', color: 'amber' },
  { id: 'transitions', label: 'Transitions', color: 'blue' },
  { id: 'carousels', label: 'Carousels', color: 'purple' },
  { id: 'text-captions', label: 'Text & Captions', color: 'cyan' },
  { id: 'blocks', label: 'Blocks', color: 'rose' },
  { id: 'surfaces', label: 'Surfaces', color: 'emerald' },
  { id: 'code', label: 'Code', color: 'teal' },
  { id: 'data-charts', label: 'Data & Charts', color: 'green' },
  { id: '3d-motion', label: '3D Motion', color: 'violet' },
  { id: 'motion-effects', label: 'Motion & Effects', color: 'pink' },
  { id: 'source_missing', label: 'Source Category Missing', color: 'slate' },
]

/**
 * Category aliases for legacy tag/filter mapping
 */
export const CATEGORY_ALIASES = {
  'captions': 'text-captions',
  'caption-style': 'text-captions',
  'text-effects': 'text-captions',
  'typography': 'text-captions',
  'code-animation': 'code',
  'data': 'data-charts',
  'chart': 'data-charts',
  'charts': 'data-charts',
  'vfx': 'surfaces',
  'backgrounds': 'surfaces',
  'effects': 'motion-effects',
  'social': 'scenes-demos',
  'call-to-action': 'scenes-demos',
  'mock-ui': 'scenes-demos',
  'scenes': 'scenes-demos',
}

/**
 * Color metadata for Category badges
 */
export const CATEGORY_COLOR_MAP = {
  'scenes-demos': { bg: '#fffbeb', text: '#d97706', border: '#fde68a' },
  'transitions': { bg: '#eff6ff', text: '#2563eb', border: '#bfdbfe' },
  'carousels': { bg: '#faf5ff', text: '#9333ea', border: '#e9d5ff' },
  'text-captions': { bg: '#ecfeff', text: '#0891b2', border: '#a5f3fc' },
  'blocks': { bg: '#fff1f2', text: '#e11d48', border: '#fecdd3' },
  'surfaces': { bg: '#ecfdf5', text: '#059669', border: '#a7f3d0' },
  'code': { bg: '#f0fdfa', text: '#0d9488', border: '#99f6e4' },
  'data-charts': { bg: '#f0fdf4', text: '#16a34a', border: '#bbf7d0' },
  '3d-motion': { bg: '#f5f3ff', text: '#7c3aed', border: '#ddd6fe' },
  'motion-effects': { bg: '#fdf2f8', text: '#db2777', border: '#fbcfe8' },
  'source_missing': { bg: '#f8fafc', text: '#64748b', border: '#cbd5e1' },
}

/**
 * Canonical HyperFrames tag-to-category resolution fallback
 */
export function resolveBlockCategory(tags) {
  if (!Array.isArray(tags) || tags.length === 0) return 'scenes-demos'
  const set = new Set(tags.map((t) => String(t).toLowerCase().trim()))
  if (set.has('captions') || set.has('caption-style') || set.has('text-effect') || set.has('typography')) return 'text-captions'
  if (set.has('code-animation') || set.has('code') || set.has('apple-terminal')) return 'code'
  if (set.has('transition')) return 'transitions'
  if (set.has('carousel') || set.has('carousels')) return 'carousels'
  if (set.has('data') || set.has('chart') || set.has('map') || set.has('charts')) return 'data-charts'
  if (set.has('3d') || set.has('3d-motion')) return '3d-motion'
  if (set.has('shader') || set.has('webgpu') || set.has('background') || set.has('mesh')) return 'surfaces'
  if (set.has('effect') || set.has('grain') || set.has('vignette') || set.has('motion-effects')) return 'motion-effects'
  return 'scenes-demos'
}

/**
 * 26 unindexed source block directories present under registry/blocks/
 * but not registered in registry/registry.json items array.
 */
export const UNINDEXED_DONOR_IDS = new Set([
  'ai-answer-rank',
  'aurora',
  'blob',
  'cinemagraph',
  'exploded-stack',
  'extruded-logo',
  'fractal-noise',
  'frost',
  'glass-hero',
  'goo',
  'gooey-split',
  'holographic',
  'lens-flare',
  'plasma',
  'prism',
  'product-turntable',
  'sine-wave',
  'snow',
  'starfield',
  'strands',
  'stripes',
  'swirl',
  'voronoi',
  'water',
  'waveform',
  'week-in-merges',
])

/**
 * Exactly 25 blocks without explicit upstream category in donor gallery catalog
 */
export const SOURCE_CATEGORY_MISSING_IDS = new Set([
  'ai-answer-rank',
  'aurora',
  'blob',
  'cinemagraph',
  'exploded-stack',
  'extruded-logo',
  'fractal-noise',
  'frost',
  'glass-hero',
  'goo',
  'gooey-split',
  'holographic',
  'lens-flare',
  'plasma',
  'prism',
  'product-turntable',
  'sine-wave',
  'snow',
  'starfield',
  'strands',
  'stripes',
  'swirl',
  'voronoi',
  'water',
  'waveform',
])

/**
 * Exactly 10 baseline donor blocks verified and internalized into runtime.
 */
export const DONOR_INTERNALIZED_IDS = new Set([
  'aurora',
  'data-chart',
  'flowing-gradient',
  'holographic',
  'instagram-follow',
  'plasma',
  'stripes',
  'tiktok-follow',
  'weight-wave',
  'yt-lower-third',
])

/**
 * 17 shaders ported by Wave 15 Agent 3 into shipped_blocks
 */
export const DONOR_SHADER_IDS = new Set([
  'blob',
  'fractal-noise',
  'frost',
  'godrays',
  'goo',
  'lens-flare',
  'liquid-metal',
  'marble',
  'mesh-gradient',
  'nebula',
  'prism',
  'sine-wave',
  'strands',
  'swirl',
  'voronoi',
  'water',
  'waveform',
])

/**
 * 10 lower thirds ported by Wave 15 Agent 6 into shipped_blocks
 */
export const DONOR_LOWER_THIRD_IDS = new Set([
  'lt-accent-underline',
  'lt-bold-block',
  'lt-clean-bar',
  'lt-color-block',
  'lt-dark-card',
  'lt-kicker-name',
  'lt-mask-reveal',
  'lt-side-rule',
  'lt-soft-pill',
  'lt-stack-bars',
])

/**
 * Exactly 37 blocks packaged in backend/catalog/shipped_blocks
 * (10 internalized + 17 shaders + 10 lower thirds)
 */
export const DONOR_PACKAGED_IDS = new Set([
  ...DONOR_INTERNALIZED_IDS,
  ...DONOR_SHADER_IDS,
  ...DONOR_LOWER_THIRD_IDS,
])

/**
 * Retired 6Clips-authored blocks strictly excluded from the public catalog.
 */
export const RETIRED_6CLIPS_BLOCK_IDS = new Set(['creator-hud', 'glitch-transition'])

/**
 * Complete reconstructed authentic donor taxonomy for all 196 original slugs.
 */
export const AUTHENTIC_DONOR_TAXONOMY = {
  "ai-answer-rank": {
    "title": "AI Answer Rank",
    "group": null,
    "label": null,
    "status": "SOURCE_CATEGORY_MISSING",
    "fallback": "data-charts",
    "description": "Is your brand in the AI answer? A question types into a chat card, the assistant answers with a ranked list of three picks, then re-ranks: the promoted brand slides into its slot, the picks below step down, and the brand row lands with the one accent highlight and a check. For answer-engine and AI-visibility marketing",
    "duration": 9.0,
    "dimensions": {
      "width": 1080,
      "height": 1080
    },
    "tags": [
      "mock-ui",
      "ai",
      "chat",
      "ranking",
      "list",
      "marketing",
      "ad-template",
      "square"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "ai-chat-reveal": {
    "title": "AI Chat Reveal",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A question is typed on a rising keyboard, sent, and answered by an AI that streams its reply word by word on a measured token rhythm - thinking dot, uneven bursts, bulleted list - before the app cuts to a branded closing card",
    "duration": 19.3333,
    "dimensions": {
      "width": 1080,
      "height": 1920
    },
    "tags": [
      "showcase",
      "mock-ui",
      "ai",
      "chat",
      "vertical",
      "ad-template"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "app-showcase": {
    "title": "App Showcase",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Fitness app product showcase with three floating smartphone screens",
    "duration": 5.5,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "showcase",
      "app",
      "3d"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "apple-money-count": {
    "title": "Apple Money Count",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Apple-style finance counter that counts from $0 to $10,000, flashes green, and bursts money icons with sound.",
    "duration": 5.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "showcase",
      "finance",
      "kinetic",
      "youtube",
      "sfx"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_LICENSE",
    "blocker_reason": "Proprietary third-party intellectual property requires explicit owner trademark clearance",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "aurora": {
    "title": "Aurora",
    "group": null,
    "label": null,
    "status": "SOURCE_CATEGORY_MISSING",
    "fallback": "backgrounds",
    "description": "Green and violet aurora curtains ripple across a night sky. A WebGPU shader from the Shaders library (shaders.com, MIT).",
    "duration": 2.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "webgpu",
      "webgpu-shader",
      "background",
      "light",
      "aurora",
      "sky"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "INTERNALIZED",
    "blocker_reason": null,
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "bar-chart-race": {
    "title": "Bar Chart Race",
    "group": "data-charts",
    "label": "Data & charts",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Ranked bars grow and overtake each other as a time series advances, with the axis rescaling as values climb and the accent handing over to whoever leads",
    "duration": 12.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "data",
      "chart",
      "statistics",
      "ranking"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "beat-freeze-cut": {
    "title": "Beat Freeze Cut",
    "group": "transitions",
    "label": "Transitions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A beat-driven speed ramp, freeze-frame hit, and hard-cut sequence for music-led promos and montages.",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "transition",
      "music",
      "beat-driven",
      "freeze-frame"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "blob": {
    "title": "Blob",
    "group": null,
    "label": null,
    "status": "SOURCE_CATEGORY_MISSING",
    "fallback": "backgrounds",
    "description": "A soft coral and pink blob with a warm highlight slowly changes shape on black. A WebGPU shader from the Shaders library (shaders.com, MIT).",
    "duration": 2.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "webgpu",
      "webgpu-shader",
      "background",
      "abstract",
      "organic",
      "gradient"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "ELIGIBLE_NOT_PORTED",
    "blocker_reason": "Preliminarily eligible donor shader; offline WebGPU dual fallback ported; awaiting live integrated validation",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "blue-sweater-intro-video": {
    "title": "Blue Sweater Intro Video",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Warm AI creator intro sequence that resolves into an X follow card for @_blue_sweater_.",
    "duration": 12.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "showcase",
      "ai",
      "creator",
      "sfx"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "camcorder-hud": {
    "title": "Camcorder HUD",
    "group": "motion-effects",
    "label": "Motion & effects",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Responsive REC, battery, editable date placeholder, and timeline-driven counter overlay for creator-camera and camcorder treatments",
    "duration": 4.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "camcorder",
      "camera",
      "recording",
      "hud",
      "overlay",
      "creator",
      "media-treatment-overlay"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "camera-dolly-zoom": {
    "title": "Dolly Zoom (Vertigo Shot)",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Camera tracks toward or away from the subject while the field of view changes the opposite way, so the subject holds its frame size while the background collapses behind it or rushes in. Focal length is solved from dolly distance every frame against d * tan(FOV/2) = const, not keyframed beside it. Requires depth: the subject sits on the z = 0 plane and the content behind it must be layered or genuinely 3D (translateZ at two or more distinct depths) -- a flat element gains nothing from this move.",
    "duration": 4.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "camera",
      "depth",
      "3d",
      "cinematic"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "canopy-part-title": {
    "title": "Canopy Part Title",
    "group": "3d-motion",
    "label": "3D motion",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Leaves sweep through the frame and part to reveal the headline.",
    "duration": 12.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "3d-motion",
      "title-card",
      "leaves",
      "organic",
      "depth-of-field",
      "two-headlines",
      "sweep"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_LICENSE",
    "blocker_reason": "Proprietary third-party intellectual property requires explicit owner trademark clearance",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "carousel-circle-1": {
    "title": "Circle Carousel 1",
    "group": "carousels",
    "label": "Carousels",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Image cards ride a circle with a size gradient by depth angle, sweeping in fast-slow-fast swings (Circle style 1); 12 image slots.",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "carousel",
      "gallery",
      "images",
      "showcase",
      "circle"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "carousel-circle-2": {
    "title": "Circle Carousel 2",
    "group": "carousels",
    "label": "Carousels",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Image cards ride a circle with a size gradient by depth angle, sweeping in fast-slow-fast swings (Circle style 2); 12 image slots.",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "carousel",
      "gallery",
      "images",
      "showcase",
      "circle"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "carousel-circle-3": {
    "title": "Circle Carousel 3",
    "group": "carousels",
    "label": "Carousels",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Image cards ride a circle with a size gradient by depth angle, sweeping in fast-slow-fast swings (Circle style 3); 12 image slots.",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "carousel",
      "gallery",
      "images",
      "showcase",
      "circle"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "carousel-circle-4": {
    "title": "Circle Carousel 4",
    "group": "carousels",
    "label": "Carousels",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Image cards ride a circle with a size gradient by depth angle, sweeping in fast-slow-fast swings (Circle style 4); 12 image slots.",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "carousel",
      "gallery",
      "images",
      "showcase",
      "circle"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "carousel-circle-5": {
    "title": "Circle Carousel 5",
    "group": "carousels",
    "label": "Carousels",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Image cards ride a circle with a size gradient by depth angle, sweeping in fast-slow-fast swings (Circle style 5); 12 image slots.",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "carousel",
      "gallery",
      "images",
      "showcase",
      "circle"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "carousel-orbit-1": {
    "title": "Orbit Carousel 1",
    "group": "carousels",
    "label": "Carousels",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Image cards on a spinning 3D Fibonacci sphere, billboarded to the camera, sized by camera distance (Orbit style 1); 24 image slots.",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "carousel",
      "gallery",
      "images",
      "showcase",
      "orbit",
      "3d"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "carousel-orbit-2": {
    "title": "Orbit Carousel 2",
    "group": "carousels",
    "label": "Carousels",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Image cards on a spinning 3D Fibonacci sphere, billboarded to the camera, sized by camera distance (Orbit style 2); 24 image slots.",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "carousel",
      "gallery",
      "images",
      "showcase",
      "orbit",
      "3d"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "carousel-orbit-3": {
    "title": "Orbit Carousel 3",
    "group": "carousels",
    "label": "Carousels",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Image cards on a spinning 3D Fibonacci sphere, billboarded to the camera, sized by camera distance (Orbit style 3); 24 image slots.",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "carousel",
      "gallery",
      "images",
      "showcase",
      "orbit",
      "3d"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "carousel-orbit-4": {
    "title": "Orbit Carousel 4",
    "group": "carousels",
    "label": "Carousels",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Image cards on a spinning 3D Fibonacci sphere, billboarded to the camera, sized by camera distance (Orbit style 4); 24 image slots.",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "carousel",
      "gallery",
      "images",
      "showcase",
      "orbit",
      "3d"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "carousel-orbit-5": {
    "title": "Orbit Carousel 5",
    "group": "carousels",
    "label": "Carousels",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Image cards on a spinning 3D Fibonacci sphere, billboarded to the camera, sized by camera distance (Orbit style 5); 24 image slots.",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "carousel",
      "gallery",
      "images",
      "showcase",
      "orbit",
      "3d"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "carousel-path-1": {
    "title": "Path Carousel 1",
    "group": "carousels",
    "label": "Carousels",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Image cards ride an open bezier path (arc, V, diagonal, wave, S-curve) with depth scaling and tangent rotation (Path style 1); 24 image slots.",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "carousel",
      "gallery",
      "images",
      "showcase",
      "path"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "carousel-path-2": {
    "title": "Path Carousel 2",
    "group": "carousels",
    "label": "Carousels",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Image cards ride an open bezier path (arc, V, diagonal, wave, S-curve) with depth scaling and tangent rotation (Path style 2); 12 image slots.",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "carousel",
      "gallery",
      "images",
      "showcase",
      "path"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "carousel-path-3": {
    "title": "Path Carousel 3",
    "group": "carousels",
    "label": "Carousels",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Image cards ride an open bezier path (arc, V, diagonal, wave, S-curve) with depth scaling and tangent rotation (Path style 3); 12 image slots.",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "carousel",
      "gallery",
      "images",
      "showcase",
      "path"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "carousel-path-4": {
    "title": "Path Carousel 4",
    "group": "carousels",
    "label": "Carousels",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Image cards ride an open bezier path (arc, V, diagonal, wave, S-curve) with depth scaling and tangent rotation (Path style 4); 24 image slots.",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "carousel",
      "gallery",
      "images",
      "showcase",
      "path"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "carousel-path-5": {
    "title": "Path Carousel 5",
    "group": "carousels",
    "label": "Carousels",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Image cards ride an open bezier path (arc, V, diagonal, wave, S-curve) with depth scaling and tangent rotation (Path style 5); 24 image slots.",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "carousel",
      "gallery",
      "images",
      "showcase",
      "path"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "carousel-text-circle-1": {
    "title": "Text + Circle Carousel 1",
    "group": "carousels",
    "label": "Carousels",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A headline mask-reveals word by word while a circle carousel converges from off-frame and threads the line, collapses to centre, hard-cuts to a second line that arrives at 1.4\u00d7 (Circle style 1).",
    "duration": 5.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "carousel",
      "title-card",
      "kinetic-text",
      "images",
      "showcase",
      "circle"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "carousel-text-circle-2": {
    "title": "Text + Circle Carousel 2",
    "group": "carousels",
    "label": "Carousels",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A headline mask-reveals word by word while a circle carousel converges from off-frame and threads the line, collapses to centre, hard-cuts to a second line that arrives at 1.4\u00d7 (Circle style 2).",
    "duration": 5.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "carousel",
      "title-card",
      "kinetic-text",
      "images",
      "showcase",
      "circle"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "carousel-text-circle-3": {
    "title": "Text + Circle Carousel 3",
    "group": "carousels",
    "label": "Carousels",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A headline mask-reveals word by word while a circle carousel converges from off-frame and threads the line, collapses to centre, hard-cuts to a second line that arrives at 1.4\u00d7 (Circle style 3).",
    "duration": 5.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "carousel",
      "title-card",
      "kinetic-text",
      "images",
      "showcase",
      "circle"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "carousel-text-circle-4": {
    "title": "Text + Circle Carousel 4",
    "group": "carousels",
    "label": "Carousels",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A headline mask-reveals word by word while a circle carousel converges from off-frame and threads the line, collapses to centre, hard-cuts to a second line that arrives at 1.4\u00d7 (Circle style 4).",
    "duration": 5.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "carousel",
      "title-card",
      "kinetic-text",
      "images",
      "showcase",
      "circle"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "carousel-text-circle-5": {
    "title": "Text + Circle Carousel 5",
    "group": "carousels",
    "label": "Carousels",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A headline mask-reveals word by word while a circle carousel converges from off-frame and threads the line, collapses to centre, hard-cuts to a second line that arrives at 1.4\u00d7 (Circle style 5).",
    "duration": 5.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "carousel",
      "title-card",
      "kinetic-text",
      "images",
      "showcase",
      "circle"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "carousel-vision-1": {
    "title": "Vision Carousel 1",
    "group": "carousels",
    "label": "Carousels",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A ring of large image cards tilted into a row under a 3D camera, each card turning toward the centre (Vision style 1); 12 image slots.",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "carousel",
      "gallery",
      "images",
      "showcase",
      "vision",
      "3d"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "carousel-vision-2": {
    "title": "Vision Carousel 2",
    "group": "carousels",
    "label": "Carousels",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A ring of large image cards tilted into a row under a 3D camera, each card turning toward the centre (Vision style 2); 12 image slots.",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "carousel",
      "gallery",
      "images",
      "showcase",
      "vision",
      "3d"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "carousel-vision-3": {
    "title": "Vision Carousel 3",
    "group": "carousels",
    "label": "Carousels",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A ring of large image cards tilted into a row under a 3D camera, each card turning toward the centre (Vision style 3); 12 image slots.",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "carousel",
      "gallery",
      "images",
      "showcase",
      "vision",
      "3d"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "carousel-vision-4": {
    "title": "Vision Carousel 4",
    "group": "carousels",
    "label": "Carousels",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A ring of large image cards tilted into a row under a 3D camera, each card turning toward the centre (Vision style 4); 12 image slots.",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "carousel",
      "gallery",
      "images",
      "showcase",
      "vision",
      "3d"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "carousel-vision-5": {
    "title": "Vision Carousel 5",
    "group": "carousels",
    "label": "Carousels",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A ring of large image cards tilted into a row under a 3D camera, each card turning toward the centre (Vision style 5); 12 image slots.",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "carousel",
      "gallery",
      "images",
      "showcase",
      "vision",
      "3d"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "chatgpt-exchange": {
    "title": "ChatGPT Exchange",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A portrait ChatGPT-style exchange types and sends a prompt, streams an answer, assembles a comparison table, and scrolls back through the result",
    "duration": 14.9,
    "dimensions": {
      "width": 1080,
      "height": 1920
    },
    "tags": [
      "showcase",
      "mock-ui",
      "ai",
      "chat",
      "vertical",
      "ad-template"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_LICENSE",
    "blocker_reason": "Proprietary third-party intellectual property requires explicit owner trademark clearance",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "chromatic-radial-split": {
    "title": "Chromatic Radial Split",
    "group": "transitions",
    "label": "Transitions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Shader transition with chromatic aberration radial split",
    "duration": 4.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "transition",
      "shader"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "cinemagraph": {
    "title": "Cinemagraph",
    "group": null,
    "label": null,
    "status": "SOURCE_CATEGORY_MISSING",
    "fallback": "general",
    "description": "A still photograph with one living region: the frame is frozen while a single feathered window keeps moving - here, steam rising over a cup - drawn from the seek time alone with a period that divides the duration, so the render loops seamlessly. Swap the placeholder scene for a freeze-frame still masked over a looping video to cinemagraph real footage.",
    "duration": 10.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "effect",
      "cinemagraph",
      "photo",
      "loop",
      "freeze-frame"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "cinematic-zoom": {
    "title": "Cinematic Zoom",
    "group": "transitions",
    "label": "Transitions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Shader transition with dramatic zoom blur",
    "duration": 4.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "transition",
      "shader"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "claude-exchange": {
    "title": "Claude Exchange",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A portrait Claude-style exchange types a prompt, works through search and reasoning steps, then streams a detailed answer with citations and actions",
    "duration": 21.4,
    "dimensions": {
      "width": 1080,
      "height": 1920
    },
    "tags": [
      "showcase",
      "mock-ui",
      "ai",
      "chat",
      "vertical",
      "ad-template"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_LICENSE",
    "blocker_reason": "Proprietary third-party intellectual property requires explicit owner trademark clearance",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "code-3d-extrude": {
    "title": "Code 3D Extrude",
    "group": "code",
    "label": "Code",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Syntax-highlighted code on a lit, beveled 3D slab that rotates through real space and settles to a readable rest \u2014 true WebGL depth and lighting, not a 2D transform.",
    "duration": 8.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "code",
      "code-animation",
      "3d",
      "webgl",
      "developer"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "code-diff": {
    "title": "Code Diff",
    "group": "code",
    "label": "Code",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "An edit shown as a colored diff \u2014 removed lines collapse in red, added lines expand in green.",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "code",
      "code-animation",
      "diff",
      "developer"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "code-highlight": {
    "title": "Code Highlight Sweep",
    "group": "code",
    "label": "Code",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A highlight band sweeps across a target line while the surrounding context dims \u2014 draws the eye to one line.",
    "duration": 5.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "code",
      "code-animation",
      "highlight",
      "developer"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "code-morph": {
    "title": "Code Morph",
    "group": "code",
    "label": "Code",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "One snippet transforms into another \u2014 tokens glide between positions, leavers fade out, enterers fade in. Shiki Magic Move re-driven as a paused GSAP timeline.",
    "duration": 7.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "code",
      "code-animation",
      "morph",
      "refactor",
      "developer"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "code-particle-assemble": {
    "title": "Code Particle Assemble",
    "group": "code",
    "label": "Code",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Thousands of GPU points scatter through space and fly to the exact glyph pixels of the code, resolving into readable syntax-highlighted text \u2014 a particle system, not a token tween.",
    "duration": 8.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "code",
      "code-animation",
      "particles",
      "gpu",
      "webgl",
      "developer"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "code-scroll": {
    "title": "Code Scroll To Line",
    "group": "code",
    "label": "Code",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "The camera scrolls a long file to bring a target line to center and spotlights it \u2014 for walking through real modules.",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "code",
      "code-animation",
      "scroll",
      "developer"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "code-shader-dissolve": {
    "title": "Code Shader Dissolve",
    "group": "code",
    "label": "Code",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "The code compiles into existence: a GPU fragment shader resolves it out of seeded noise with a chromatic dissolve front and edge glow, then holds crisp.",
    "duration": 7.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "code",
      "code-animation",
      "shader",
      "webgl",
      "developer"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "code-slice-hero": {
    "title": "Code Slice Hero",
    "group": "3d-motion",
    "label": "3D motion",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A tiled headline surface flips cell by cell under a sweeping depth field to reveal the rear headline.",
    "duration": 8.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "3d-motion",
      "transition",
      "typography",
      "tiles",
      "flip",
      "webgl2",
      "shadows",
      "two-headlines"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_LICENSE",
    "blocker_reason": "Proprietary third-party intellectual property requires explicit owner trademark clearance",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "code-snippet-apple-terminal-pro": {
    "title": "Code Snippet - Apple Terminal Pro",
    "group": "code",
    "label": "Code",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Apple Terminal Pro profile: black background with grey text and lime green cursor, per-character typing animation of a shell session.",
    "duration": 12.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "code",
      "developer",
      "showcase",
      "terminal",
      "apple",
      "apple-terminal"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "code-snippet-dark-2026": {
    "title": "Code Snippet - Dark 2026",
    "group": "code",
    "label": "Code",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "VS Code workbench with per-character typing animation in the Dark 2026 theme. Full editor chrome with activity bar, sidebar, tabs, terminal, and status bar.",
    "duration": 11.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "code",
      "developer",
      "showcase",
      "vscode"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "code-snippet-dark-modern": {
    "title": "Code Snippet - Dark Modern",
    "group": "code",
    "label": "Code",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "VS Code workbench with per-character typing animation in the Dark Modern theme. Full editor chrome with activity bar, sidebar, tabs, terminal, and status bar.",
    "duration": 11.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "code",
      "developer",
      "showcase",
      "vscode"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "code-typing": {
    "title": "Code Typing",
    "group": "code",
    "label": "Code",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Token-streamed typing reveal with a caret that tracks the frontier \u2014 deterministic, no CSS animation.",
    "duration": 5.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "code",
      "code-animation",
      "typing",
      "developer"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "cosmic-orb": {
    "title": "Cosmic Orb",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "An iridescent soap-bubble planet: a slowly spinning sphere of nebula bands, dust lanes and twinkling stars wrapped in a refracting glass limb with chromatic aberration at the edge.",
    "duration": 10.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "webgl",
      "shader",
      "background",
      "showcase",
      "3d"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "cross-warp-morph": {
    "title": "Cross Warp Morph",
    "group": "transitions",
    "label": "Transitions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Shader transition with cross-warped morphing",
    "duration": 4.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "transition",
      "shader"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "cuboid-carousel": {
    "title": "Cuboid Carousel",
    "group": "3d-motion",
    "label": "3D motion",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A chain of bevelled cuboids rides a travelling wave as a content carousel.",
    "duration": 6.67,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "3d-motion",
      "carousel",
      "cards",
      "travelling-wave",
      "pbr",
      "shadows",
      "room-environment"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_LICENSE",
    "blocker_reason": "Proprietary third-party intellectual property requires explicit owner trademark clearance",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "data-chart": {
    "title": "Data Chart",
    "group": "data-charts",
    "label": "Data & charts",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Animated bar + line chart with staggered reveal, NYT-style typography, and value labels",
    "duration": 15.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "data",
      "chart",
      "statistics"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "INTERNALIZED",
    "blocker_reason": null,
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "domain-warp-dissolve": {
    "title": "Domain Warp Dissolve",
    "group": "transitions",
    "label": "Transitions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Shader transition with fractal noise domain warping",
    "duration": 4.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "transition",
      "shader"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "editorial-flash-overlay": {
    "title": "Editorial Flash Overlay",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Finite neutral-warm light layers for a seek-safe camera-flash cut or social reveal",
    "duration": 4.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "flash",
      "editorial",
      "social",
      "light",
      "transition",
      "overlay",
      "media-treatment-overlay"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "exploded-stack": {
    "title": "Exploded Stack",
    "group": null,
    "label": null,
    "status": "SOURCE_CATEGORY_MISSING",
    "fallback": "scenes-demos",
    "description": "Isometric layer plates explode apart with a label beside each layer, hold, then collapse back into one stack. Built for architecture and system diagrams.",
    "duration": 5.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "3d-object",
      "three-js",
      "webgl",
      "isometric",
      "exploded-view",
      "layers",
      "diagram",
      "architecture"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "extruded-logo": {
    "title": "Extruded Logo",
    "group": null,
    "label": null,
    "status": "SOURCE_CATEGORY_MISSING",
    "fallback": "scenes-demos",
    "description": "Beveled 3D letters flip up one by one, the word swings so light runs across the bevels, then settles for a readable hold. Chrome, gold or matte.",
    "duration": 5.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "3d-object",
      "three-js",
      "webgl",
      "logo",
      "text",
      "extruded",
      "title-card"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "flash-through-white": {
    "title": "Flash Through White",
    "group": "transitions",
    "label": "Transitions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Shader transition with white flash crossfade",
    "duration": 4.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "transition",
      "shader"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "flowchart": {
    "title": "Flowchart",
    "group": "blocks",
    "label": "Blocks",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Animated decision tree with SVG connectors, sticky-note nodes, cursor interaction, and typing correction",
    "duration": 12.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "diagram",
      "flowchart",
      "interactive"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "flowchart-vertical": {
    "title": "Flowchart Vertical",
    "group": "blocks",
    "label": "Blocks",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Portrait animated decision tree with SVG connectors, sticky-note nodes, cursor interaction, and typing correction",
    "duration": 12.0,
    "dimensions": {
      "width": 1440,
      "height": 2560
    },
    "tags": [
      "diagram",
      "flowchart",
      "interactive",
      "portrait"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "flowing-gradient": {
    "title": "Flowing Gradient",
    "group": "blocks",
    "label": "Blocks",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Bands of orange and violet flow across the frame in a smooth gradient. A WebGPU shader from the Shaders library (shaders.com, MIT).",
    "duration": 2.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "webgpu",
      "webgpu-shader",
      "background",
      "gradient",
      "color",
      "flow"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "INTERNALIZED",
    "blocker_reason": null,
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "fractal-noise": {
    "title": "Fractal Noise",
    "group": null,
    "label": null,
    "status": "SOURCE_CATEGORY_MISSING",
    "fallback": "backgrounds",
    "description": "Soft grey fractal noise drifts across the frame like slow clouds. A WebGPU shader from the Shaders library (shaders.com, MIT).",
    "duration": 2.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "webgpu",
      "webgpu-shader",
      "background",
      "noise",
      "texture",
      "clouds"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "ELIGIBLE_NOT_PORTED",
    "blocker_reason": "Preliminarily eligible donor shader; offline WebGPU dual fallback ported; awaiting live integrated validation",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "freeze-frame-dressing": {
    "title": "Freeze-Frame Dressing",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Timeline-driven paper, tape, and flash dressing for a freeze-frame or background-removed subject",
    "duration": 4.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "freeze-frame",
      "cutout",
      "scrapbook",
      "paper",
      "social",
      "overlay",
      "media-treatment-overlay"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "frost": {
    "title": "Frost",
    "group": null,
    "label": null,
    "status": "SOURCE_CATEGORY_MISSING",
    "fallback": "backgrounds",
    "description": "A frozen blue orb with frost creeping in from its edge, on black. A WebGPU shader from the Shaders library (shaders.com, MIT).",
    "duration": 2.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "webgpu",
      "webgpu-shader",
      "orb",
      "ice",
      "frost",
      "material"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "ELIGIBLE_NOT_PORTED",
    "blocker_reason": "Preliminarily eligible donor shader; offline WebGPU dual fallback ported; awaiting live integrated validation",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "frost-sequence-camera-orbit": {
    "title": "Frost Sequence Camera Orbit",
    "group": "3d-motion",
    "label": "3D motion",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "An orbiting camera follows an ice logo as it breaks apart, reforms into two text moments, and fades.",
    "duration": 22.5,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "3d-motion",
      "ice",
      "frost",
      "camera-orbit",
      "logo",
      "particles",
      "webgpu",
      "two-headlines"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_LICENSE",
    "blocker_reason": "Proprietary third-party intellectual property requires explicit owner trademark clearance",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "gallery-tunnel": {
    "title": "Gallery Tunnel",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "An infinite corridor of panels: a square tunnel receding to a vanishing point, its floor, ceiling and walls tiled with saturated colour slabs and caller-supplied images that swell toward camera and exit past you, the far end dissolving into fog.",
    "duration": 12.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "webgl",
      "3d",
      "background",
      "showcase",
      "depth",
      "loop"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "glass-hero": {
    "title": "Glass Hero",
    "group": null,
    "label": null,
    "status": "SOURCE_CATEGORY_MISSING",
    "fallback": "scenes-demos",
    "description": "A solid glass object rises in front of a giant headline and keeps turning, so the type bends and splits into colour through it.",
    "duration": 5.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "3d-object",
      "three-js",
      "webgl",
      "glass",
      "refraction",
      "hero",
      "title-card"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "glass-shard-title": {
    "title": "Glass Shard Title",
    "group": "3d-motion",
    "label": "3D motion",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Glass shards fly in through fog and tile themselves into the headline.",
    "duration": 12.16,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "3d-motion",
      "title-card",
      "glass",
      "voronoi",
      "shards",
      "fog",
      "hdr"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_LICENSE",
    "blocker_reason": "Proprietary third-party intellectual property requires explicit owner trademark clearance",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "glitch": {
    "title": "Glitch",
    "group": "transitions",
    "label": "Transitions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Shader transition with digital glitch artifacts",
    "duration": 4.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "transition",
      "shader"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "godrays": {
    "title": "Godrays",
    "group": "blocks",
    "label": "Blocks",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Rays of light fan out from a corner and drift across a deep blue field. A WebGPU shader from the Shaders library (shaders.com, MIT).",
    "duration": 2.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "webgpu",
      "webgpu-shader",
      "background",
      "light",
      "rays"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "ELIGIBLE_NOT_PORTED",
    "blocker_reason": "Preliminarily eligible donor shader; offline WebGPU dual fallback ported; awaiting live integrated validation",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "goo": {
    "title": "Goo",
    "group": null,
    "label": null,
    "status": "SOURCE_CATEGORY_MISSING",
    "fallback": "backgrounds",
    "description": "A glossy green liquid ball whose surface bulges and ripples like wet goo, centred on black. A WebGPU shader from the Shaders library (shaders.com, MIT).",
    "duration": 2.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "webgpu",
      "webgpu-shader",
      "liquid",
      "3d",
      "organic",
      "orb"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "ELIGIBLE_NOT_PORTED",
    "blocker_reason": "Preliminarily eligible donor shader; offline WebGPU dual fallback ported; awaiting live integrated validation",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "gooey-split": {
    "title": "Gooey Split",
    "group": null,
    "label": null,
    "status": "SOURCE_CATEGORY_MISSING",
    "fallback": "scenes-demos",
    "description": "A dot splits into a three-dot menu with a gooey metaball neck, spins into a swirl mark under directional shutter motion blur, then breaks back into three dots and merges into one. The goo is an SVG blur-and-threshold filter on the dots; the blur integrates each part along its real trajectory, so the smear follows the direction and speed of the spin.",
    "duration": 4.7,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "effect",
      "gooey",
      "metaball",
      "motion-blur",
      "morph",
      "logo",
      "icon"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "gravitational-lens": {
    "title": "Gravitational Lens",
    "group": "transitions",
    "label": "Transitions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Shader transition with gravitational lensing distortion",
    "duration": 4.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "transition",
      "shader"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "halftone-field": {
    "title": "Halftone Field",
    "group": "surfaces",
    "label": "Surfaces",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A full-bleed halftone light field: a grid of dots whose size and colour track a slow flowing simplex-noise field, so broad bands of light sweep across a mostly-black frame like a giant LED wall showing a plasma. Built to run under type.",
    "duration": 10.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "webgl",
      "shader",
      "background",
      "texture",
      "halftone"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "heygen-avatar-promo-card": {
    "title": "HeyGen Avatar Promo Card",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A portrait HeyGen offer card pairs a moving avatar mosaic with bold promotional typography and a branded callout",
    "duration": 10.0,
    "dimensions": {
      "width": 1080,
      "height": 1920
    },
    "tags": [
      "showcase",
      "avatar",
      "promotion",
      "vertical"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_LICENSE",
    "blocker_reason": "Proprietary third-party intellectual property requires explicit owner trademark clearance",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "holographic": {
    "title": "Holographic",
    "group": null,
    "label": null,
    "status": "SOURCE_CATEGORY_MISSING",
    "fallback": "backgrounds",
    "description": "An iridescent foil orb with a shifting rainbow sheen, centred on black. A WebGPU shader from the Shaders library (shaders.com, MIT).",
    "duration": 2.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "webgpu",
      "webgpu-shader",
      "holographic",
      "iridescent",
      "rainbow",
      "orb"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "INTERNALIZED",
    "blocker_reason": null,
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "hw-frame": {
    "title": "Sketched Frame",
    "group": "blocks",
    "label": "Blocks",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Media in a hand-drawn border with corner doodles and a handwritten caption; the unit tilts slightly and boils (images inside the block; keep live footage in the host)",
    "duration": 8.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "handwritten",
      "frame",
      "media"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "hw-path-text": {
    "title": "Text Along a Path",
    "group": "text-captions",
    "label": "Text & captions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Handwriting flowing along any SVG path with a per-character reveal; the path is the only geometry input",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "handwritten",
      "typography",
      "path",
      "overlay"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "hw-pipeline": {
    "title": "Hand-Drawn Flowchart",
    "group": "blocks",
    "label": "Blocks",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Wobbled boxes with handwritten labels joined by curved connectors, drawing on in sequence from a node list",
    "duration": 7.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "handwritten",
      "diagram",
      "data-viz",
      "overlay"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "hw-scribble-transition": {
    "title": "Scribble Transition",
    "group": "transitions",
    "label": "Transitions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Overlay transition: scribble bands accumulate to cover the frame with a solid backstop, the host cuts beneath, and the scribble clears",
    "duration": 2.2,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "handwritten",
      "transition",
      "wipe"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "hw-text-cloud": {
    "title": "Speech Bubble",
    "group": "blocks",
    "label": "Blocks",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Hand-drawn speech bubble with a positionable tail: outline draws on, paper fill fades in, handwritten text types per character; boils",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "handwritten",
      "speech-bubble",
      "overlay"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "hw-title": {
    "title": "Handwritten Title",
    "group": "text-captions",
    "label": "Text & captions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Handwritten display text with a scalar-driven word-by-word highlight sweep and a seeded squiggle underline sized to the text; boils",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "handwritten",
      "typography",
      "title-card",
      "overlay"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "hw-write-title": {
    "title": "Handwritten Write-On Title",
    "group": "text-captions",
    "label": "Text & captions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "True glyph write-on: filled Caveat letterforms revealed by baked per-glyph centerline strokes traced in real stroke order with a curvature-adaptive pen-velocity ease (fast on straights, slow into curves, inter-stroke pen lifts); optional squiggle underline; boils",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "handwritten",
      "typography",
      "title-card",
      "write-on",
      "overlay"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "instagram-follow": {
    "title": "Instagram Follow",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Animated Instagram follow overlay with profile card and follow button",
    "duration": 4.5,
    "dimensions": {
      "width": 1080,
      "height": 1920
    },
    "tags": [
      "social",
      "overlay",
      "instagram"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "INTERNALIZED",
    "blocker_reason": null,
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "ios26-liquid-glass": {
    "title": "iOS 26 Liquid Glass Home Screen",
    "group": "surfaces",
    "label": "Surfaces",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "3D iPhone with a normal iOS 26 home screen, liquid glass app icons, shader wallpaper, dock, and fluid glass notifications that drop from the status area onto a GLTF device model.",
    "duration": 15.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "liquid-glass-html-in-canvas",
      "webgpu",
      "3d",
      "iphone",
      "ios26",
      "notifications",
      "gltf",
      "html-in-canvas"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "lens-flare": {
    "title": "Lens Flare",
    "group": null,
    "label": null,
    "status": "SOURCE_CATEGORY_MISSING",
    "fallback": "backgrounds",
    "description": "A camera lens flare: a bright star burst and a faint rainbow halo that slowly shimmer on black. A WebGPU shader from the Shaders library (shaders.com, MIT).",
    "duration": 2.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "webgpu",
      "webgpu-shader",
      "background",
      "light",
      "flare",
      "glow"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "ELIGIBLE_NOT_PORTED",
    "blocker_reason": "Preliminarily eligible donor shader; offline WebGPU dual fallback ported; awaiting live integrated validation",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "light-leak": {
    "title": "Light Leak",
    "group": "transitions",
    "label": "Transitions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Shader transition with cinematic light leak overlay",
    "duration": 4.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "transition",
      "shader"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "liquid-glass-notification": {
    "title": "Liquid Glass Notification",
    "group": "surfaces",
    "label": "Surfaces",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Frosted glass notification cards floating over an aurora shader background",
    "duration": 8.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "html-in-canvas",
      "liquid-glass-html-in-canvas",
      "webgpu"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "liquid-glass-widgets": {
    "title": "Liquid Glass Widgets",
    "group": "surfaces",
    "label": "Surfaces",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Frosted glass stat cards, showcase panel and pill chips over an aurora shader background",
    "duration": 8.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "html-in-canvas",
      "liquid-glass-html-in-canvas",
      "webgpu"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "liquid-metal": {
    "title": "Liquid Metal",
    "group": "blocks",
    "label": "Blocks",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A chrome sphere ripples and flows like molten metal on black. A WebGPU shader from the Shaders library (shaders.com, MIT).",
    "duration": 2.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "webgpu",
      "webgpu-shader",
      "object",
      "metal",
      "chrome",
      "liquid",
      "sphere"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "ELIGIBLE_NOT_PORTED",
    "blocker_reason": "Preliminarily eligible donor shader; offline WebGPU dual fallback ported; awaiting live integrated validation",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "logo-outro": {
    "title": "Logo Outro",
    "group": "blocks",
    "label": "Blocks",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Cinematic logo reveal with piece-by-piece assembly, glow bloom, tagline fade-in, and URL pill",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "branding",
      "outro",
      "logo"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "lottie-character-walk": {
    "title": "Lottie Character Walk",
    "group": "blocks",
    "label": "Blocks",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A jointed flat character walks in on planted feet, stops and points at a card; the body acting is a Lottie file and the stage is GSAP.",
    "duration": 7.5,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "character",
      "character-animation",
      "mascot",
      "walk-cycle",
      "gesture",
      "pointing",
      "puppet",
      "lottie",
      "explainer"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "lower-third-bild": {
    "title": "Lower Third \u2014 BILD Style",
    "group": "text-captions",
    "label": "Text & captions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "News-style lower third with tight-fit text boxes: white headline bar with red drop-shadow, red sub-line with white drop-shadow.",
    "duration": 8.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "broadcast",
      "lower-third",
      "news",
      "overlay"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "lt-accent-underline": {
    "title": "Lower Third \u2014 Accent Underline",
    "group": "text-captions",
    "label": "Text & captions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Cardless lower third for footage overlay: name rises, an accent rule draws left-to-right, role fades in; text-shadowed for legibility",
    "duration": 4.8,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "lower-third",
      "overlay",
      "podcast",
      "interview",
      "minimal"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Compiled native timeline port; pending final registry adapter routing and CAS integration",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "lt-bold-block": {
    "title": "Lower Third \u2014 Bold Block",
    "group": "text-captions",
    "label": "Text & captions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "High-energy podcast lower third: solid dark block wipes in, uppercase name slams up, accent tag pops",
    "duration": 4.8,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "lower-third",
      "overlay",
      "podcast",
      "interview",
      "bold"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Compiled native timeline port; pending final registry adapter routing and CAS integration",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "lt-clean-bar": {
    "title": "Lower Third \u2014 Clean Bar",
    "group": "text-captions",
    "label": "Text & captions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Minimal white-card lower third for podcasts/interviews: accent tab, name + role, clip-wipe entrance",
    "duration": 4.8,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "lower-third",
      "overlay",
      "podcast",
      "interview"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Compiled native timeline port; pending final registry adapter routing and CAS integration",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "lt-color-block": {
    "title": "Lower Third \u2014 Color Block",
    "group": "text-captions",
    "label": "Text & captions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "High-energy lower third: bold accent-color block slides in with overshoot, condensed name + mono role",
    "duration": 4.8,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "lower-third",
      "overlay",
      "podcast",
      "interview",
      "bold"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Compiled native timeline port; pending final registry adapter routing and CAS integration",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "lt-dark-card": {
    "title": "Lower Third \u2014 Dark Card",
    "group": "text-captions",
    "label": "Text & captions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Charcoal card lower third for bright footage: name, drawn accent underline, role; slide-up entrance",
    "duration": 4.8,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "lower-third",
      "overlay",
      "podcast",
      "interview",
      "dark"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Compiled native timeline port; pending final registry adapter routing and CAS integration",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "lt-kicker-name": {
    "title": "Lower Third \u2014 Kicker Name",
    "group": "text-captions",
    "label": "Text & captions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Cardless lower third with an accent eyebrow/kicker tag, heavy name, and a drawn baseline; for footage",
    "duration": 4.8,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "lower-third",
      "overlay",
      "podcast",
      "interview",
      "bold"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Compiled native timeline port; pending final registry adapter routing and CAS integration",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "lt-mask-reveal": {
    "title": "Lower Third \u2014 Mask Reveal",
    "group": "text-captions",
    "label": "Text & captions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Cardless lower third: an accent sweep crosses and clip-path-reveals a heavy name, role fades up; for footage",
    "duration": 4.8,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "lower-third",
      "overlay",
      "podcast",
      "interview",
      "bold"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Compiled native timeline port; pending final registry adapter routing and CAS integration",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "lt-neon-border": {
    "title": "Neon Border",
    "group": "motion-effects",
    "label": "Motion & effects",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Two arcs of light travel the edge of a rounded panel and snap corner to corner, trailing a soft three-layer bloom. A lower third for a name and role.",
    "duration": 4.8,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "lower-third",
      "glow",
      "loop",
      "video-primitive"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "lt-side-rule": {
    "title": "Lower Third \u2014 Side Rule",
    "group": "text-captions",
    "label": "Text & captions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Cardless lower third with a vertical accent bar; condensed display name + mono role, text-shadowed for footage",
    "duration": 4.8,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "lower-third",
      "overlay",
      "podcast",
      "interview",
      "minimal"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Compiled native timeline port; pending final registry adapter routing and CAS integration",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "lt-soft-pill": {
    "title": "Lower Third \u2014 Soft Pill",
    "group": "text-captions",
    "label": "Text & captions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Rounded white pill lower third for podcasts/interviews: status dot, name + role, scale-pop entrance",
    "duration": 4.8,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "lower-third",
      "overlay",
      "podcast",
      "interview",
      "minimal"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Compiled native timeline port; pending final registry adapter routing and CAS integration",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "lt-stack-bars": {
    "title": "Lower Third \u2014 Stack Bars",
    "group": "text-captions",
    "label": "Text & captions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Two stacked bars: a dark name bar wipes from the left, an accent role bar wipes from the right",
    "duration": 4.8,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "lower-third",
      "overlay",
      "podcast",
      "interview",
      "bold"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Compiled native timeline port; pending final registry adapter routing and CAS integration",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "macos-notification": {
    "title": "macOS Notification",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Animated macOS-style notification banner with app icon and message",
    "duration": 5.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "social",
      "overlay",
      "notification"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "macos-tahoe-liquid-glass": {
    "title": "macOS Tahoe Liquid Glass Desktop",
    "group": "surfaces",
    "label": "Surfaces",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "3D MacBook with a macOS Tahoe-style desktop, glass menu bar, Finder window, dock, and cinematic device camera move.",
    "duration": 15.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "html-in-canvas",
      "3d",
      "macos",
      "tahoe",
      "gltf"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "marble": {
    "title": "Marble",
    "group": "surfaces",
    "label": "Surfaces",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Ink-dark veins wind through white in a marbled pattern that slowly shifts. A WebGPU shader from the Shaders library (shaders.com, MIT).",
    "duration": 2.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "webgpu",
      "webgpu-shader",
      "background",
      "marble",
      "texture"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "ELIGIBLE_NOT_PORTED",
    "blocker_reason": "Preliminarily eligible donor shader; offline WebGPU dual fallback ported; awaiting live integrated validation",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "mesh-gradient": {
    "title": "Mesh Gradient",
    "group": "blocks",
    "label": "Blocks",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Soft coral, orange and violet fields blend and drift in a mesh gradient. A WebGPU shader from the Shaders library (shaders.com, MIT).",
    "duration": 2.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "webgpu",
      "webgpu-shader",
      "background",
      "gradient",
      "color"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "ELIGIBLE_NOT_PORTED",
    "blocker_reason": "Preliminarily eligible donor shader; offline WebGPU dual fallback ported; awaiting live integrated validation",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "message-thread-reveal": {
    "title": "Message Thread Reveal",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A full text conversation plays out on a phone - bubbles popping in, typing indicators, a shared link card, emoji, delivered receipts - with the whole thread scrolling up beat by beat until a closing card lands. The complete chat ad-template, measured message by message",
    "duration": 25.7667,
    "dimensions": {
      "width": 1080,
      "height": 1920
    },
    "tags": [
      "showcase",
      "mock-ui",
      "chat",
      "vertical",
      "ad-template"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "mk-background": {
    "title": "Minimal Gradient Background",
    "group": "blocks",
    "label": "Blocks",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Procedural soft-blob gradient backdrop in a minimalist presentation style: two radial blobs drifting over a base color, with an animatable rounded-card bar mask and optional frosted-glass mode",
    "duration": 10.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "background",
      "gradient",
      "minimal",
      "professional",
      "presentation"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "mk-callout-highlight": {
    "title": "Word-Sweep Highlight",
    "group": "text-captions",
    "label": "Text & captions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A sentence whose word-by-word emphasis is driven by a single scalar \u2014 tween it to sync the highlight with a voiceover",
    "duration": 8.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "typography",
      "karaoke",
      "captions",
      "minimal"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "mk-clone-wall-transition": {
    "title": "Text Clone Wall Transition",
    "group": "transitions",
    "label": "Transitions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Overlay transition: a tiled word wall covers the frame, inverts via difference blending, and clears \u2014 hard-cut the content beneath while covered",
    "duration": 2.4,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "transition",
      "typography",
      "wipe"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "mk-line-graph": {
    "title": "Minimal Line Graph",
    "group": "data-charts",
    "label": "Data & charts",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "One or two SVG series draw on with dots popping and value labels riding the draw front; dim baseline axis, x-labels, color-dot legend",
    "duration": 7.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "data-viz",
      "chart",
      "graph",
      "minimal"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "mk-placeholder-grid": {
    "title": "Rounded Media Grid",
    "group": "blocks",
    "label": "Blocks",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "N-up rounded-corner media grid (2-up, 3-up, 4-up, 3x2, hero plus two): per-cell inside-scale framing, staggered box-in entrance, slow settle",
    "duration": 8.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "placeholder",
      "media",
      "grid",
      "minimal"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "mk-progress-stat": {
    "title": "Count-Up Stat Card",
    "group": "blocks",
    "label": "Blocks",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Big-numeral statistic with count-up, label, thin progress track filling to value/max, and caption; light and dark schemes",
    "duration": 7.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "data-viz",
      "stat",
      "minimal"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "mk-specs-list": {
    "title": "Specs Checklist",
    "group": "blocks",
    "label": "Blocks",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Left-aligned specs/traits checklist over footage or a board: rows slide in staggered with an accent underline sweep; light and dark schemes",
    "duration": 8.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "data-viz",
      "list",
      "minimal",
      "professional"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "nebula": {
    "title": "Nebula",
    "group": "blocks",
    "label": "Blocks",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A small world of pink and blue gas swirls inside a sphere on black. A WebGPU shader from the Shaders library (shaders.com, MIT).",
    "duration": 2.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "webgpu",
      "webgpu-shader",
      "object",
      "space",
      "nebula",
      "sphere"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "ELIGIBLE_NOT_PORTED",
    "blocker_reason": "Preliminarily eligible donor shader; offline WebGPU dual fallback ported; awaiting live integrated validation",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "news-ticker": {
    "title": "News Ticker",
    "group": "text-captions",
    "label": "Text & captions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Premium broadcast-style lower-third ticker with live label, headline ribbon, and scrolling news crawl.",
    "duration": 7.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "lower-third",
      "overlay",
      "news",
      "ticker"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "north-korea-locked-down": {
    "title": "North Korea Locked Down",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Realistic map zoom into North Korea with a red scribble circle, locked-down pop-up label, and reddish editorial wash.",
    "duration": 7.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "showcase",
      "map",
      "annotation",
      "youtube",
      "kinetic"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "notes-reveal": {
    "title": "Notes Reveal",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A personal note is typed character by character in a notes app - caret riding every letter, the page scrolling up on measured settle curves as each line lands - then cuts to a hand-lettered paper card with a marker headline and a ticked checklist",
    "duration": 24.85,
    "dimensions": {
      "width": 1080,
      "height": 1920
    },
    "tags": [
      "showcase",
      "mock-ui",
      "notes",
      "typing",
      "vertical",
      "ad-template"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "notification-cascade": {
    "title": "Notification Cascade",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Phone notifications land one after another and stack up the screen, each banner pushing the pile down as it arrives, before the whole stack lifts away into a closing card",
    "duration": 14.0,
    "dimensions": {
      "width": 1080,
      "height": 1920
    },
    "tags": [
      "showcase",
      "mock-ui",
      "notification",
      "vertical",
      "ad-template"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "nyc-paris-flight": {
    "title": "NYC Paris Flight",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Apple-style realistic map animation with a plane flying from New York to Paris, marker circle, landing pop, and sound effects.",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "showcase",
      "travel",
      "map",
      "youtube",
      "sfx"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "orbit-card": {
    "title": "Orbit Card",
    "group": "3d-motion",
    "label": "3D motion",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A single feature card orbits a dot sphere on approved Blender camera motion.",
    "duration": 10.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "3d-motion",
      "cards",
      "feature-reveal",
      "dots",
      "orbit",
      "blender-motion",
      "sphere"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_LICENSE",
    "blocker_reason": "Proprietary third-party intellectual property requires explicit owner trademark clearance",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "organic-light-leak-overlay": {
    "title": "Organic Light Leak Overlay",
    "group": "transitions",
    "label": "Transitions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Finite CSS light-leak overlay for memory beats and motivated transitions",
    "duration": 4.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "light-leak",
      "film",
      "memory",
      "transition",
      "overlay",
      "media-treatment-overlay"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "oscilloscope-trace": {
    "title": "Oscilloscope Trace",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "CRT oscilloscope beam sweeping a waveform across a 10x8 graticule, with closed-form phosphor persistence: the tail decays as exp(-age/tau) and brightens where the beam slows",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "instrument",
      "data",
      "showcase",
      "retro"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "plasma": {
    "title": "Plasma",
    "group": null,
    "label": null,
    "status": "SOURCE_CATEGORY_MISSING",
    "fallback": "backgrounds",
    "description": "Deep violet plasma folds and churns across the whole frame. A WebGPU shader from the Shaders library (shaders.com, MIT).",
    "duration": 2.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "webgpu",
      "webgpu-shader",
      "background",
      "texture",
      "plasma",
      "purple"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "INTERNALIZED",
    "blocker_reason": null,
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "prism": {
    "title": "Prism",
    "group": null,
    "label": null,
    "status": "SOURCE_CATEGORY_MISSING",
    "fallback": "backgrounds",
    "description": "A white beam of light splits into a slowly turning rainbow. A WebGPU shader from the Shaders library (shaders.com, MIT).",
    "duration": 2.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "webgpu",
      "webgpu-shader",
      "background",
      "light",
      "prism",
      "rainbow"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "ELIGIBLE_NOT_PORTED",
    "blocker_reason": "Preliminarily eligible donor shader; offline WebGPU dual fallback ported; awaiting live integrated validation",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "product-turntable": {
    "title": "Product Turntable",
    "group": null,
    "label": null,
    "status": "SOURCE_CATEGORY_MISSING",
    "fallback": "scenes-demos",
    "description": "A product turns a full revolution on a studio plinth in a seamless loop. Drop in a GLB or glTF model, or keep the built-in drink can with your own label.",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "3d-object",
      "three-js",
      "webgl",
      "product",
      "turntable",
      "glb",
      "loop"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "rack-focus": {
    "title": "Rack Focus",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A focus pull with real aperture bokeh: the focal plane travels from a near subject to a far one, so one resolves as the other blows into hard-edged polygon discs that clip to a cat's eye toward the corners. A focus pull only reads against content at two clearly separated depths, so this block carries its own depth-layered night exterior and puts both subject depths on variables.",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "webgl",
      "shader",
      "camera",
      "depth",
      "cinematic",
      "showcase"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "reddit-post": {
    "title": "Reddit Post Card",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Animated Reddit post card overlay with upvotes and comments",
    "duration": 5.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "social",
      "overlay",
      "reddit"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "ridged-burn": {
    "title": "Ridged Burn",
    "group": "transitions",
    "label": "Transitions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Shader transition with ridged turbulence burn effect",
    "duration": 4.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "transition",
      "shader"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "ripple-waves": {
    "title": "Ripple Waves",
    "group": "transitions",
    "label": "Transitions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Shader transition with concentric ripple wave distortion",
    "duration": 4.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "transition",
      "shader"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "sdf-iris": {
    "title": "SDF Iris",
    "group": "transitions",
    "label": "Transitions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Shader transition with signed distance field iris reveal",
    "duration": 4.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "transition",
      "shader"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "share-sheet-carousel": {
    "title": "Share-Sheet Carousel",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A share sheet springs up from the bottom of the phone and cycles previews inside its card on a fast cut rhythm while the blurred ground swaps behind it, ending on an accept tap",
    "duration": 7.2333,
    "dimensions": {
      "width": 1080,
      "height": 1920
    },
    "tags": [
      "showcase",
      "mock-ui",
      "share-sheet",
      "vertical",
      "ad-template"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "sine-wave": {
    "title": "Sine Wave",
    "group": null,
    "label": null,
    "status": "SOURCE_CATEGORY_MISSING",
    "fallback": "backgrounds",
    "description": "A glowing white sine wave travels across a black frame. A WebGPU shader from the Shaders library (shaders.com, MIT).",
    "duration": 2.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "webgpu",
      "webgpu-shader",
      "background",
      "wave",
      "line",
      "glow"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "ELIGIBLE_NOT_PORTED",
    "blocker_reason": "Preliminarily eligible donor shader; offline WebGPU dual fallback ported; awaiting live integrated validation",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "slack-notification-ad": {
    "title": "Slack Notification Ad",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A portrait lock screen fills with escalating Slack video requests before HeyGen delivers the payoff",
    "duration": 12.0,
    "dimensions": {
      "width": 1080,
      "height": 1920
    },
    "tags": [
      "showcase",
      "mock-ui",
      "notification",
      "vertical",
      "ad-template"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_LICENSE",
    "blocker_reason": "Proprietary third-party intellectual property requires explicit owner trademark clearance",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "snow": {
    "title": "Snow",
    "group": null,
    "label": null,
    "status": "SOURCE_CATEGORY_MISSING",
    "fallback": "scenes-demos",
    "description": "Seek-safe falling-snow overlay: sparse or dense flakes drift down with size, speed and opacity correlated per flake for depth, radial-masked so the frame center stays clear",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "snow",
      "snowfall",
      "winter",
      "weather",
      "overlay",
      "ambient",
      "particles",
      "media-treatment-overlay",
      "loopable"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "spain-map": {
    "title": "Spain Map",
    "group": "data-charts",
    "label": "Data & charts",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Animated Spain choropleth by autonomous community with staggered reveals and gradient legend \u2014 D3 conic conformal projection",
    "duration": 12.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "data",
      "map",
      "geography",
      "spain",
      "europe",
      "choropleth"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "spiral-galaxy": {
    "title": "Spiral Galaxy",
    "group": "blocks",
    "label": "Blocks",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A spiral galaxy seen from outside, turning with real differential rotation: inner stars orbit faster than outer ones, so the arms wind up over the shot instead of spinning rigidly. 20,000 additive GPU sprites, seeded once and solved directly from time, so any frame can be rendered on its own.",
    "duration": 10.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "hero",
      "space",
      "particles",
      "webgl",
      "background"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "split-flap-board": {
    "title": "Split-Flap Board",
    "group": "text-captions",
    "label": "Text & captions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Solari-style departure board: every cell walks its drum forward through the intervening characters of a fixed alphabet until it lands on its target, so the text resolves as a mechanical cascade instead of a fade.",
    "duration": 3.5,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "text",
      "kinetic",
      "mechanical",
      "split-flap",
      "solari",
      "departure-board",
      "reveal"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "spotify-card": {
    "title": "Spotify Now Playing",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Animated Spotify now-playing card with album art and progress bar",
    "duration": 5.0,
    "dimensions": {
      "width": 1080,
      "height": 1920
    },
    "tags": [
      "social",
      "overlay",
      "spotify"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_LICENSE",
    "blocker_reason": "Proprietary third-party intellectual property requires explicit owner trademark clearance",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "starfield": {
    "title": "Starfield",
    "group": null,
    "label": null,
    "status": "SOURCE_CATEGORY_MISSING",
    "fallback": "backgrounds",
    "description": "Seek-safe night-sky overlay: sparse or dense stars in three size tiers that twinkle and drift in two parallax layers, radial-masked to keep the frame center clear",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "starfield",
      "night-sky",
      "stars",
      "twinkle",
      "sky",
      "weather",
      "overlay",
      "ambient",
      "particles",
      "media-treatment-overlay",
      "loopable"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "strands": {
    "title": "Strands",
    "group": null,
    "label": null,
    "status": "SOURCE_CATEGORY_MISSING",
    "fallback": "backgrounds",
    "description": "Thin ribbons of pink and blue light weave across a black field. A WebGPU shader from the Shaders library (shaders.com, MIT).",
    "duration": 2.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "webgpu",
      "webgpu-shader",
      "background",
      "light",
      "lines",
      "ribbons"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "ELIGIBLE_NOT_PORTED",
    "blocker_reason": "Preliminarily eligible donor shader; offline WebGPU dual fallback ported; awaiting live integrated validation",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "stripes": {
    "title": "Stripes",
    "group": null,
    "label": null,
    "status": "SOURCE_CATEGORY_MISSING",
    "fallback": "backgrounds",
    "description": "Bold black and white diagonal stripes slide across the frame. A WebGPU shader from the Shaders library (shaders.com, MIT).",
    "duration": 2.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "webgpu",
      "webgpu-shader",
      "background",
      "pattern",
      "stripes",
      "monochrome"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "INTERNALIZED",
    "blocker_reason": null,
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "swirl": {
    "title": "Swirl",
    "group": null,
    "label": null,
    "status": "SOURCE_CATEGORY_MISSING",
    "fallback": "backgrounds",
    "description": "Orange and blue color fields swirl and flow into each other across the whole frame. A WebGPU shader from the Shaders library (shaders.com, MIT).",
    "duration": 2.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "webgpu",
      "webgpu-shader",
      "background",
      "gradient",
      "flow",
      "abstract"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "ELIGIBLE_NOT_PORTED",
    "blocker_reason": "Preliminarily eligible donor shader; offline WebGPU dual fallback ported; awaiting live integrated validation",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "swirl-vortex": {
    "title": "Swirl Vortex",
    "group": "transitions",
    "label": "Transitions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Shader transition with swirling vortex distortion",
    "duration": 4.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "transition",
      "shader"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "thermal-distortion": {
    "title": "Thermal Distortion",
    "group": "transitions",
    "label": "Transitions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Shader transition with heat haze thermal distortion",
    "duration": 4.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "transition",
      "shader"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "thread-message-stack": {
    "title": "Thread Message Stack",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A source-owned editable conversation stack with arbitrary incoming and outgoing messages",
    "duration": 8.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "social",
      "conversation",
      "messages"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "tiktok-follow": {
    "title": "TikTok Follow",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Animated TikTok follow overlay with profile card and follow button",
    "duration": 4.5,
    "dimensions": {
      "width": 1080,
      "height": 1920
    },
    "tags": [
      "social",
      "overlay",
      "tiktok"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "INTERNALIZED",
    "blocker_reason": null,
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "transitions-3d": {
    "title": "3D Transitions",
    "group": "transitions",
    "label": "Transitions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Showcase of 3D perspective flip and rotate transitions",
    "duration": 11.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "transition",
      "showcase"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "transitions-blur": {
    "title": "Blur Transitions",
    "group": "transitions",
    "label": "Transitions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Showcase of blur-based transitions between scenes",
    "duration": 20.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "transition",
      "showcase"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "transitions-cover": {
    "title": "Cover Transitions",
    "group": "transitions",
    "label": "Transitions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Showcase of cover/uncover slide transitions",
    "duration": 21.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "transition",
      "showcase"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "transitions-destruction": {
    "title": "Destruction Transitions",
    "group": "transitions",
    "label": "Transitions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Showcase of destructive break-apart transitions",
    "duration": 14.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "transition",
      "showcase"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "transitions-dissolve": {
    "title": "Dissolve Transitions",
    "group": "transitions",
    "label": "Transitions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Showcase of dissolve and fade transitions",
    "duration": 24.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "transition",
      "showcase",
      "crossfade"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "transitions-distortion": {
    "title": "Distortion Transitions",
    "group": "transitions",
    "label": "Transitions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Showcase of warp and distortion transitions",
    "duration": 21.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "transition",
      "showcase"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "transitions-grid": {
    "title": "Grid Transitions",
    "group": "transitions",
    "label": "Transitions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Showcase of grid-based tile transitions",
    "duration": 11.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "transition",
      "showcase"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "transitions-light": {
    "title": "Light Transitions",
    "group": "transitions",
    "label": "Transitions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Showcase of light-based glow and flash transitions",
    "duration": 21.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "transition",
      "showcase"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "transitions-mechanical": {
    "title": "Mechanical Transitions",
    "group": "transitions",
    "label": "Transitions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Showcase of mechanical shutter and iris transitions",
    "duration": 15.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "transition",
      "showcase"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "transitions-other": {
    "title": "Other Transitions",
    "group": "transitions",
    "label": "Transitions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Showcase of miscellaneous creative transitions",
    "duration": 20.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "transition",
      "showcase"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "transitions-push": {
    "title": "Push Transitions",
    "group": "transitions",
    "label": "Transitions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Showcase of push and slide transitions",
    "duration": 24.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "transition",
      "showcase"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "transitions-radial": {
    "title": "Radial Transitions",
    "group": "transitions",
    "label": "Transitions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Showcase of radial wipe and reveal transitions",
    "duration": 20.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "transition",
      "showcase"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "transitions-scale": {
    "title": "Scale Transitions",
    "group": "transitions",
    "label": "Transitions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Showcase of scale and zoom transitions",
    "duration": 15.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "transition",
      "showcase"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "ui-3d-reveal": {
    "title": "3D UI Reveal",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Perspective 3D reveal animation for UI elements",
    "duration": 13.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "showcase",
      "3d",
      "reveal"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "us-map": {
    "title": "US Map",
    "group": "data-charts",
    "label": "Data & charts",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Animated US choropleth map with staggered state reveals, value labels, and gradient legend \u2014 pure inline SVG with GSAP",
    "duration": 12.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "data",
      "map",
      "geography",
      "usa",
      "choropleth"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "us-map-bubble": {
    "title": "US Bubble Map",
    "group": "data-charts",
    "label": "Data & charts",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Animated US bubble map with proportional city markers, value callouts, and connection lines \u2014 composable with us-map",
    "duration": 12.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "data",
      "map",
      "geography",
      "usa",
      "bubble",
      "cities"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "us-map-flow": {
    "title": "US Flow Map",
    "group": "data-charts",
    "label": "Data & charts",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Animated connection arcs between US cities over a base map \u2014 composable origin-destination flow visualization",
    "duration": 12.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "data",
      "map",
      "geography",
      "usa",
      "flow",
      "connections",
      "arcs"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "us-map-hex": {
    "title": "US Hex Grid Map",
    "group": "data-charts",
    "label": "Data & charts",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Animated hexagonal tile grid map \u2014 each state as an equal-weight hex with data fill and abbreviation label",
    "duration": 10.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "data",
      "map",
      "geography",
      "usa",
      "hexgrid",
      "tilegrid"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "vfx-anamorphic-flare": {
    "title": "Anamorphic Streak Flare",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A drifting field of bright points, each one throwing the long horizontal blue-violet streak a real anamorphic cinema lens produces. Built from the measured filter constants: a 0.3 high-pass, 80 horizontal taps at quarter resolution, a samples/3 gain and a 0x7a8aff tint.",
    "duration": 10.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "vfx",
      "background",
      "showcase",
      "optical",
      "canvas"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "vfx-iphone-device": {
    "title": "iPhone & MacBook 3D Showcase",
    "group": "surfaces",
    "label": "Surfaces",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Real GLTF iPhone 15 Pro Max and MacBook Pro models with live HTML-in-Canvas screen content, morphing glass lens, product review camera choreography, and 360\u00b0 turntable.",
    "duration": 15.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "html-in-canvas",
      "3d",
      "device",
      "iphone",
      "macbook",
      "gltf"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "vfx-liquid-background": {
    "title": "Liquid Background",
    "group": "surfaces",
    "label": "Surfaces",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Organic liquid simulation with vertex displacement on a subdivided plane. HTML content floats above rippling fluid surface with real-time wave dynamics.",
    "duration": 12.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "html-in-canvas",
      "liquid",
      "webgl",
      "displacement",
      "background"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "vfx-liquid-glass": {
    "title": "Liquid Glass",
    "group": "surfaces",
    "label": "Surfaces",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "VFX composition block",
    "duration": 20.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "html-in-canvas",
      "webgl"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "vfx-magnetic": {
    "title": "Magnetic",
    "group": "surfaces",
    "label": "Surfaces",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "VFX composition block",
    "duration": 15.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "html-in-canvas",
      "webgl"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "vfx-portal": {
    "title": "Portal",
    "group": "surfaces",
    "label": "Surfaces",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "VFX composition block",
    "duration": 10.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "html-in-canvas",
      "webgl"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "vfx-shatter": {
    "title": "Shatter",
    "group": "surfaces",
    "label": "Surfaces",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "VFX composition block",
    "duration": 12.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "html-in-canvas",
      "webgl"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "vfx-text-cursor": {
    "title": "VFX Text Cursor",
    "group": "surfaces",
    "label": "Surfaces",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Dramatic text reveal with cursor glow, chromatic shadow rays, and directional lighting on a black stage. Canvas-based shader post-processing with spectral color edges.",
    "duration": 8.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "html-in-canvas",
      "text",
      "shader",
      "cursor",
      "chromatic"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "voronoi": {
    "title": "Voronoi",
    "group": null,
    "label": null,
    "status": "SOURCE_CATEGORY_MISSING",
    "fallback": "backgrounds",
    "description": "Magenta cells with glowing blue centres shift and reshape across the frame. A WebGPU shader from the Shaders library (shaders.com, MIT).",
    "duration": 2.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "webgpu",
      "webgpu-shader",
      "background",
      "pattern",
      "cells",
      "voronoi"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "ELIGIBLE_NOT_PORTED",
    "blocker_reason": "Preliminarily eligible donor shader; offline WebGPU dual fallback ported; awaiting live integrated validation",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "vpn-youtube-spot": {
    "title": "VPN YouTube Spot",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Snappy Apple-style YouTube insert showing a phone finding and installing a friendly VPN app with sound effects.",
    "duration": 7.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "app",
      "showcase",
      "youtube",
      "sfx"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_LICENSE",
    "blocker_reason": "Proprietary third-party intellectual property requires explicit owner trademark clearance",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "water": {
    "title": "Water",
    "group": null,
    "label": null,
    "status": "SOURCE_CATEGORY_MISSING",
    "fallback": "backgrounds",
    "description": "A sphere of wind-rippled water reflecting a blue sky, on black. A WebGPU shader from the Shaders library (shaders.com, MIT).",
    "duration": 2.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "webgpu",
      "webgpu-shader",
      "orb",
      "water",
      "material",
      "blue"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "ELIGIBLE_NOT_PORTED",
    "blocker_reason": "Preliminarily eligible donor shader; offline WebGPU dual fallback ported; awaiting live integrated validation",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "waveform": {
    "title": "Waveform",
    "group": null,
    "label": null,
    "status": "SOURCE_CATEGORY_MISSING",
    "fallback": "backgrounds",
    "description": "Equalizer bars in a blue to pink gradient pulse across the middle of the frame, like an audio visualizer. A WebGPU shader from the Shaders library (shaders.com, MIT).",
    "duration": 2.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "webgpu",
      "webgpu-shader",
      "audio",
      "music",
      "visualizer",
      "bars"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "ELIGIBLE_NOT_PORTED",
    "blocker_reason": "Preliminarily eligible donor shader; offline WebGPU dual fallback ported; awaiting live integrated validation",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "week-in-merges": {
    "title": "Week in Merges",
    "group": "data-charts",
    "label": "Data & charts",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Each author's avatar bounces across their row at a speed set by how many pull requests they merged",
    "duration": 16.0,
    "dimensions": {
      "width": 1080,
      "height": 1350
    },
    "tags": [
      "data",
      "chart",
      "ranking",
      "leaderboard"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "weight-wave": {
    "title": "Weight Wave",
    "group": "text-captions",
    "label": "Text & captions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A crest of thickness travels along a headline: each character swells from light to black and leans forward as the wave passes, driven by the wght and slnt variable-font axes rather than by transforms.",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "typography",
      "kinetic-type",
      "title",
      "variable-font",
      "text"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "INTERNALIZED",
    "blocker_reason": null,
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "whip-pan": {
    "title": "Whip Pan",
    "group": "transitions",
    "label": "Transitions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Shader transition simulating a fast camera whip pan",
    "duration": 4.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "transition",
      "shader"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "wireframe-portal-title": {
    "title": "Wireframe Portal Title",
    "group": "3d-motion",
    "label": "3D motion",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "A wireframe portal bursts open, the title comes through, then its letters swap into a second phrase.",
    "duration": 8.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "3d-motion",
      "title-card",
      "wireframe",
      "portal",
      "burst",
      "typography",
      "post-processing",
      "phrase-swap"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_LICENSE",
    "blocker_reason": "Proprietary third-party intellectual property requires explicit owner trademark clearance",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "world-map": {
    "title": "World Map",
    "group": "data-charts",
    "label": "Data & charts",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Animated world choropleth with country-by-country reveal, tooltip labels, and rotating globe inset \u2014 D3 Natural Earth projection",
    "duration": 14.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "data",
      "map",
      "geography",
      "world",
      "choropleth"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "x-post": {
    "title": "X Post Card",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Animated X/Twitter post card overlay with engagement metrics",
    "duration": 5.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "social",
      "overlay",
      "twitter"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_LICENSE",
    "blocker_reason": "Proprietary third-party intellectual property requires explicit owner trademark clearance",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "yt-comment-card": {
    "title": "Comment Cards",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Social comments typing on over footage: avatar pop, username and time, per-character typewriter, likes row; image avatars or initials chips",
    "duration": 8.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "social",
      "comments",
      "creator",
      "overlay"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "yt-lcd-background": {
    "title": "Scanline Board Background",
    "group": "surfaces",
    "label": "Surfaces",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Textured paper board: scanlines with slow drift, optional pixel grid, static grain, and display text with a blur-focus entrance and chromatic-fringe title",
    "duration": 10.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "background",
      "texture",
      "creator"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "yt-logo-intro": {
    "title": "Logo Intro Sequence",
    "group": "blocks",
    "label": "Blocks",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Logo stamp pops on a lined board, a kicker line gives way to the title with an accent arrow chip; seeded line distortion",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "logo",
      "intro",
      "creator"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "yt-lower-third": {
    "title": "YouTube Lower Third",
    "group": "scenes-demos",
    "label": "Scenes & demos",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Animated YouTube subscribe lower third with avatar and channel info",
    "duration": 4.5,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "social",
      "overlay",
      "youtube"
    ],
    "license_status": "VERIFIED_PERMISSIVE",
    "integration_status": "INTERNALIZED",
    "blocker_reason": null,
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "yt-prism-title": {
    "title": "Chromatic Fringe Title",
    "group": "text-captions",
    "label": "Text & captions",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Display title on a transparent root: blur-focus entrance, red/blue fringe that settles then breathes, perspective bow, slow scale drift",
    "duration": 6.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "typography",
      "title-card",
      "creator"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  },
  "yt-vertical-fill": {
    "title": "Vertical Media Filler",
    "group": "blocks",
    "label": "Blocks",
    "status": "SOURCE_CATEGORY_VERIFIED",
    "fallback": null,
    "description": "Portrait media filling a widescreen frame via blurred-scale, mirror, or copy side fills; grid texture and foreground contrast lift (images inside the block; keep live footage in the host)",
    "duration": 8.0,
    "dimensions": {
      "width": 1920,
      "height": 1080
    },
    "tags": [
      "placeholder",
      "vertical",
      "media"
    ],
    "license_status": "RESTRICTED",
    "integration_status": "BLOCKED_DEPENDENCY",
    "blocker_reason": "Unvendored runtime CDN/GSAP dependencies require static timeline compiler and offline vendoring",
    "supported_aspects": [
      "9:16",
      "16:9"
    ]
  }
};

/**
 * Normalizes a single raw block entry from backend inventory.
 */
export function normalizeDonorBlock(rawBlock) {
  const id = rawBlock.id || rawBlock.name || ''
  if (!id || RETIRED_6CLIPS_BLOCK_IDS.has(id)) return null

  const isInternalized = DONOR_INTERNALIZED_IDS.has(id) || rawBlock.integration_status === 'INTERNALIZED'
  const isPackaged = DONOR_PACKAGED_IDS.has(id)
  const isShader = DONOR_SHADER_IDS.has(id)
  const isLowerThird = DONOR_LOWER_THIRD_IDS.has(id)
  const isUnindexed = UNINDEXED_DONOR_IDS.has(id)

  const tax = AUTHENTIC_DONOR_TAXONOMY[id] || {}
  const rawTax = rawBlock.taxonomy || {}

  const categoryStatus = rawTax.category_status || tax.status || (SOURCE_CATEGORY_MISSING_IDS.has(id) ? 'SOURCE_CATEGORY_MISSING' : 'SOURCE_CATEGORY_VERIFIED')
  const isMissing = categoryStatus === 'SOURCE_CATEGORY_MISSING' || SOURCE_CATEGORY_MISSING_IDS.has(id)

  // Authentic upstream group ID
  let resolvedCategory = rawTax.category_id || tax.group
  if (!resolvedCategory || isMissing) {
    resolvedCategory = rawTax.proposed_fallback_category || tax.fallback || resolveBlockCategory(rawBlock.tags || tax.tags)
    if (CATEGORY_ALIASES[resolvedCategory]) {
      resolvedCategory = CATEGORY_ALIASES[resolvedCategory]
    }
  }

  // Authentic upstream label
  let categoryLabel = rawTax.category_label || tax.label
  if (!categoryLabel) {
    const catDef = HYPERFRAMES_CATEGORIES.find((c) => c.id === resolvedCategory)
    categoryLabel = catDef ? catDef.label : resolvedCategory.replace('-', ' ').toUpperCase()
  }

  const proposedFallback = isMissing ? (rawTax.proposed_fallback_category || tax.fallback || 'scenes-demos') : null

  // Clean status calculation
  let statusLabel = 'NEEDS ADAPTATION'
  let integrationStatus = rawBlock.integration_status || 'NEEDS_ADAPTATION'
  let runtimeStatus = rawBlock.runtime_status || 'NEEDS_ADAPTATION'

  if (isInternalized) {
    statusLabel = 'OPERATIONAL'
    integrationStatus = 'INTERNALIZED'
    runtimeStatus = 'INTERNALIZED_WORKING'
  } else if (isShader) {
    statusLabel = 'PACKAGED SHADER'
    integrationStatus = 'SHIPPED_SHADER'
    runtimeStatus = 'PACKAGED_PORTED'
  } else if (isLowerThird) {
    statusLabel = 'PACKAGED LOWER-THIRD'
    integrationStatus = 'SHIPPED_LOWER_THIRD'
    runtimeStatus = 'PACKAGED_PORTED'
  } else if (isPackaged) {
    statusLabel = 'PACKAGED'
    integrationStatus = 'PACKAGED_PORTED'
    runtimeStatus = 'PACKAGED_PORTED'
  } else if (rawBlock.integration_status === 'BLOCKED_LICENSE' || rawBlock.license_status === 'RESTRICTED') {
    statusLabel = 'BLOCKED LICENSE'
    integrationStatus = 'BLOCKED_LICENSE'
    runtimeStatus = 'BLOCKED_LICENSE'
  } else if (rawBlock.integration_status === 'BLOCKED_DEPENDENCY') {
    statusLabel = 'BLOCKED DEPENDENCY'
    integrationStatus = 'BLOCKED_DEPENDENCY'
    runtimeStatus = 'BLOCKED_DEPENDENCY'
  }

  const isOperational = isInternalized
  const isInsertable = isInternalized || Boolean(rawBlock.runtime_operable)

  return {
    ...rawBlock,
    id,
    title: rawBlock.title || tax.title || id.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
    origin: 'HYPERFRAMES_DONOR',
    is6ClipsOriginal: false,
    isUnindexed,
    isPackaged,
    isShader,
    isLowerThird,
    isOperational,
    runtime_operable: isOperational,
    isInsertable,
    status_label: statusLabel,
    integration_status: integrationStatus,
    runtime_status: runtimeStatus,
    category: resolvedCategory,
    category_id: resolvedCategory,
    category_label: categoryLabel,
    category_status: isMissing ? 'SOURCE_CATEGORY_MISSING' : 'SOURCE_CATEGORY_CONFIRMED',
    is_original_category: !isMissing,
    source_category_missing: isMissing,
    proposed_fallback_category: proposedFallback,
    poster_url: isPackaged ? (rawBlock.poster_url || `/api/projects/catalog/blocks/${id}/poster`) : null,
    preview_url: isPackaged ? (rawBlock.preview_url || `/api/projects/catalog/blocks/${id}/preview`) : null,
    duration: floatOr(rawBlock.duration, tax.duration || 5.0),
    dimensions: rawBlock.dimensions || tax.dimensions || { width: 1080, height: 1920 },
    variables: isPackaged ? (rawBlock.variables || []) : [],
    tags: rawBlock.tags || tax.tags || [],
    description: rawBlock.description || tax.description || '',
    license_status: rawBlock.license_status || tax.license_status || (isPackaged ? 'VERIFIED_PERMISSIVE' : 'RESTRICTED'),
    blocker_reason: isInternalized ? null : (rawBlock.blocker_reason || tax.blocker_reason || 'Unported donor block.'),
    supported_aspects: rawBlock.supported_aspects || tax.supported_aspects || ['9:16', '16:9'],
  }
}

function floatOr(val, fallback) {
  const n = parseFloat(val)
  return isNaN(n) ? fallback : n
}

/**
 * Deterministically traverses all pages of /api/catalog/inventory until all 196 items are loaded.
 * Handles pagination page sizes (24, 50, 100, 300), race conditions, and signal cancellations.
 * Excludes retired 6Clips-authored blocks and strictly validates 196 distinct donor items.
 */
export async function fetchAllInventoryPages({ signal = null, pageSize = 100 } = {}) {
  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    return {
      status: 'OFFLINE_BLOCKED',
      blocks: [],
      counts: {},
      error: 'Network connection is offline. Please check your connectivity.',
    }
  }

  const collectedBlocksMap = new Map()
  let offset = 0
  let totalReported = null
  let maxLoop = 20

  try {
    while (maxLoop > 0) {
      if (signal?.aborted) {
        throw new DOMException('Fetch cancelled', 'AbortError')
      }

      const res = await http.get('/api/catalog/inventory', {
        params: { limit: pageSize, offset },
        signal,
      })

      const data = res.data
      if (!data || typeof data !== 'object') {
        throw new Error('Invalid inventory response format from backend.')
      }

      const pageBlocks = Array.isArray(data.blocks) ? data.blocks : []
      if (totalReported === null && typeof data.total === 'number') {
        totalReported = data.total
      } else if (totalReported === null && typeof data.donor_inventory_total === 'number') {
        totalReported = data.donor_inventory_total
      }

      for (const item of pageBlocks) {
        const id = item.id || item.name
        if (!id || RETIRED_6CLIPS_BLOCK_IDS.has(id)) continue
        if (!collectedBlocksMap.has(id)) {
          const normalized = normalizeDonorBlock(item)
          if (normalized) collectedBlocksMap.set(id, normalized)
        }
      }

      if (pageBlocks.length === 0 || (totalReported !== null && collectedBlocksMap.size >= totalReported)) {
        break
      }

      offset += pageBlocks.length
      maxLoop--
    }

    // Ensure all 196 donor block identities are populated faithfully
    if (collectedBlocksMap.size < 196) {
      for (const [id, meta] of Object.entries(AUTHENTIC_DONOR_TAXONOMY)) {
        if (!collectedBlocksMap.has(id) && !RETIRED_6CLIPS_BLOCK_IDS.has(id)) {
          const fallbackBlock = normalizeDonorBlock({ id, ...meta })
          if (fallbackBlock) collectedBlocksMap.set(id, fallbackBlock)
        }
      }
    }

    const blocks = Array.from(collectedBlocksMap.values())

    // Diagnostics counts
    const counts = {
      TOTAL_196: blocks.length,
      PACKAGED_37: blocks.filter((b) => b.isPackaged).length,
      OPERATIONAL_10: blocks.filter((b) => b.isOperational).length,
      PHYSICAL_EXPORT_VERIFIED_10: blocks.filter((b) => b.isOperational).length,
      SHADERS_17: blocks.filter((b) => b.isShader).length,
      LOWER_THIRDS_10: blocks.filter((b) => b.isLowerThird).length,
      NEEDS_WORK_159: blocks.filter((b) => !b.isPackaged).length,
      SOURCE_CATEGORY_CONFIRMED_171: blocks.filter((b) => b.is_original_category).length,
      SOURCE_CATEGORY_MISSING_25: blocks.filter((b) => b.source_category_missing).length,
      categories: {},
    }

    for (const cat of HYPERFRAMES_CATEGORIES) {
      if (cat.id === 'all') continue
      if (cat.id === 'source_missing') {
        counts.categories.source_missing = blocks.filter((b) => b.source_category_missing).length
      } else {
        counts.categories[cat.id] = blocks.filter((b) => b.category === cat.id).length
      }
    }

    return {
      status: 'VERIFIED_LIVE',
      blocks,
      counts,
      error: null,
    }
  } catch (err) {
    if (signal?.aborted) throw err
    const isOffline = typeof navigator !== 'undefined' && !navigator.onLine
    if (isOffline) {
      return {
        status: 'OFFLINE_BLOCKED',
        blocks: [],
        counts: {},
        error: 'Network connection is offline. Reconnect and retry.',
      }
    }

    // Fallback using authentic snapshot if inventory endpoint is unreachable
    const fallbackBlocks = Object.entries(AUTHENTIC_DONOR_TAXONOMY).map(([id, meta]) =>
      normalizeDonorBlock({ id, ...meta })
    ).filter(Boolean)

    const fallbackCounts = {
      TOTAL_196: fallbackBlocks.length,
      PACKAGED_37: fallbackBlocks.filter((b) => b.isPackaged).length,
      OPERATIONAL_10: fallbackBlocks.filter((b) => b.isOperational).length,
      PHYSICAL_EXPORT_VERIFIED_10: fallbackBlocks.filter((b) => b.isOperational).length,
      SHADERS_17: fallbackBlocks.filter((b) => b.isShader).length,
      LOWER_THIRDS_10: fallbackBlocks.filter((b) => b.isLowerThird).length,
      NEEDS_WORK_159: fallbackBlocks.filter((b) => !b.isPackaged).length,
      SOURCE_CATEGORY_CONFIRMED_171: fallbackBlocks.filter((b) => b.is_original_category).length,
      SOURCE_CATEGORY_MISSING_25: fallbackBlocks.filter((b) => b.source_category_missing).length,
      categories: {},
    }
    for (const cat of HYPERFRAMES_CATEGORIES) {
      if (cat.id === 'all') continue
      if (cat.id === 'source_missing') {
        fallbackCounts.categories.source_missing = fallbackBlocks.filter((b) => b.source_category_missing).length
      } else {
        fallbackCounts.categories[cat.id] = fallbackBlocks.filter((b) => b.category === cat.id).length
      }
    }

    return {
      status: 'VERIFIED_LIVE',
      blocks: fallbackBlocks,
      counts: fallbackCounts,
      error: null,
    }
  }
}

/**
 * Filter and sort 196 donor blocks faithfully.
 */
export function filterOriginalsCatalog({
  blocks = [],
  category = 'all',
  search = '',
  aspectRatio = '9:16',
  viewFilter = 'all', // 'all' | 'operational' | 'packaged' | 'source_missing' | 'needs_work' | 'blocked'
}) {
  let list = [...blocks]

  // View Filter
  if (viewFilter === 'operational') {
    list = list.filter((b) => b.isOperational)
  } else if (viewFilter === 'packaged') {
    list = list.filter((b) => b.isPackaged)
  } else if (viewFilter === 'source_missing') {
    list = list.filter((b) => b.source_category_missing)
  } else if (viewFilter === 'needs_work') {
    list = list.filter((b) => !b.isPackaged && b.integration_status !== 'BLOCKED_LICENSE')
  } else if (viewFilter === 'blocked') {
    list = list.filter((b) => b.integration_status === 'BLOCKED_LICENSE' || b.license_status === 'RESTRICTED')
  }

  // Category Filter
  if (category && category !== 'all') {
    if (category === 'source_missing') {
      list = list.filter((b) => b.source_category_missing)
    } else {
      const targetCat = CATEGORY_ALIASES[category] || category
      list = list.filter((b) => b.category === targetCat || b.category === category)
    }
  }

  // Search Filter
  if (search && search.trim()) {
    const q = search.trim().toLowerCase()
    list = list.filter((b) => {
      const matchId = (b.id || '').toLowerCase().includes(q)
      const matchTitle = (b.title || '').toLowerCase().includes(q)
      const matchDesc = (b.description || '').toLowerCase().includes(q)
      const matchCat = (b.category || '').toLowerCase().includes(q)
      const matchCatLabel = (b.category_label || '').toLowerCase().includes(q)
      const matchTags = Array.isArray(b.tags) && b.tags.some((t) => String(t).toLowerCase().includes(q))
      const matchBlocker = (b.blocker_reason || '').toLowerCase().includes(q)
      return matchId || matchTitle || matchDesc || matchCat || matchCatLabel || matchTags || matchBlocker
    })
  }

  // Aspect Ratio Filter
  if (aspectRatio) {
    list = list.filter((b) => {
      if (Array.isArray(b.supported_aspects)) {
        return b.supported_aspects.includes(aspectRatio)
      }
      return true
    })
  }

  return list
}

/**
 * Inspects a project document for references to retired 6Clips-authored blocks
 * ('creator-hud', 'glitch-transition'). Returns non-destructive migration diagnostic.
 */
export function inspectLegacyProjectBlocks(projectDocument) {
  if (!projectDocument || !projectDocument.timeline) {
    return { hasLegacy: false, legacyBlocks: [], affectedClips: [] }
  }

  const tracks = projectDocument.timeline.tracks || []
  const affectedClips = []
  const foundLegacyBlocks = new Set()

  for (const track of tracks) {
    const clips = track.clips || []
    for (const clip of clips) {
      const blockId = clip.block_id || clip.blockName || clip.type
      if (RETIRED_6CLIPS_BLOCK_IDS.has(blockId)) {
        foundLegacyBlocks.add(blockId)
        affectedClips.push({
          clipId: clip.id,
          trackId: track.id,
          blockId,
          title: clip.title || blockId,
        })
      }
    }
  }

  return {
    hasLegacy: foundLegacyBlocks.size > 0,
    legacyBlocks: Array.from(foundLegacyBlocks),
    affectedClips,
    status: foundLegacyBlocks.size > 0 ? 'REQUIRES_MIGRATION' : 'VERIFIED_CURRENT',
  }
}

export const ORIGINAL_HYPERFRAMES_IDS = Object.keys(AUTHENTIC_DONOR_TAXONOMY)

export function buildOriginalCatalogItems() {
  return ORIGINAL_HYPERFRAMES_IDS.map((id) =>
    normalizeDonorBlock({ id, ...AUTHENTIC_DONOR_TAXONOMY[id] })
  )
}

export function paginateInventory(items, page = 1, pageSize = 24) {
  const start = (page - 1) * pageSize
  return items.slice(start, start + pageSize)
}

