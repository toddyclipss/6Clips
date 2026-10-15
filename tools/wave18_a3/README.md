# WAVE 18 — AGENT 3 / 5: ORIGINAL HYPERFRAMES A–M REAL PREVIEW & EXPORT FIDELITY

## 1. Executive Summary & Root Cause Analysis

### The Discrepancy Reproduced & Resolved
In previous wave reports, Agent 3 claimed that **104 A–M blocks** were `ACTIVATED_REAL`. However, in the real running Motion application, the owner could visibly play previews for **ONLY TEN** blocks:
`aurora`, `data-chart`, `flowing-gradient`, `holographic`, `instagram-follow`, `plasma`, `stripes`, `tiktok-follow`, `weight-wave`, `yt-lower-third`.

Our comprehensive failure census and architectural trace uncovered the exact root causes of this discrepancy:

1. **Frontend Gatekeeper Restriction (`catalogOriginals.js` & `MotionGraphics.jsx`):**
   - In `frontend/src/utils/catalogOriginals.js`, `DONOR_INTERNALIZED_IDS` explicitly contained only those 10 baseline blocks.
   - In `frontend/src/pages/MotionGraphics.jsx` (line 172-173):
     ```javascript
     const bName = catalogItem.name || catalogItem.id
     const isOp = DONOR_INTERNALIZED_IDS.has(bName) || Boolean(catalogItem.isOperational)
     if (!isOp) return
     ```
   - In `frontend/src/components/motion/StudioResourcePanel.jsx` (lines 211, 220-221):
     `isOperational` was strictly evaluated as `DONOR_INTERNALIZED_IDS.has(bName)`. For all other 186 blocks, `isOp` was false and `preview_url` was set to `null`. Hovering or clicking on preview in the Motion UI was aborted before network or iframe instantiation.

2. **Backend Operability Gate (`manifest_service.py`):**
   - In `backend/catalog/manifest_service.py`, `validate_block_operable(block_id)` checked `get_operable_block_ids(wave=16)`, which was capped at the 37 Wave 16 blocks.
   - Even if direct HTTP requests were made to `/api/catalog/blocks/{b_id}/preview` for the other 80 shipped A-M blocks, the backend raised HTTP 403 Forbidden (`quarantined/uninternalized`).

3. **Wave 17 Inflated Metrics & Looped Still Frames:**
   - Wave 17 Agent 3 used `ffmpeg -loop 1 -i <frame>` on a single still image to generate MP4s instead of sampling multi-timestamp animations.
   - 35 shipped blocks (all 25 carousels and 10 lower thirds) had a critical runtime bug: `window.__timelines[DATA.id] = tl` threw `TypeError: Cannot set properties of undefined (setting '...')` because `window.__timelines` was never initialized.
   - All 25 carousels requested `assets/carousel-images/*.jpg`, which were never shipped to disk, triggering 200+ network 404 errors.

---

## 2. Definitive A–M Census & Reconciled Inventory

From `hyperframes/registry/blocks` (read-only reference), exactly **121 original donor slugs** starting with A–M exist.

| Category / Classification | Count | Description |
| :--- | :---: | :--- |
| **A–M Original Donor Identities** | **121** | Total unique upstream HyperFrames donor blocks |
| **`USER_PREVIEW_VERIFIED` & `EXPORT_VERIFIED`** | **100** | Full 3-gate verified (DOM render, timeline seeking, CAS persistence, decoded MP4) |
| **`BLOCKED_DEPENDENCY`** | **12** | 8 unshipped + 4 shipped (Three.js WebGLRenderer UMD, Lottie, WebGPU) |
| **`BLOCKED_RIGHTS`** | **9** | Proprietary trademarks, brand dress, or personal likeness (Apple, OpenAI, Anthropic, HeyGen) |
| **Retired 6Clips Substitutes** | **2** | `creator-hud`, `glitch-transition` (retired from public catalog, preserved for legacy projects) |

---

## 3. The 3 Independent Verification Gates

Every verified block must pass three orthogonal, independently verified gates without synthetic shortcuts:

### Gate A: Source Native Animation Render
- Standalone HTML loads in headless Microsoft Edge via Playwright.
- Zero uncaught page errors, zero syntax errors.
- Strict zero-egress Content Security Policy enforced (`connect-src 'none'`).

### Gate B: Real Motion Preview & Dynamic Timeline Seeking
- Script binds `window.tl` and `window.__timelines[slug]`.
- Playhead seeks to $t_0$, $t_{\text{mid}} = \text{duration}/2$, and $t_{\text{end}}$.
- Real browser screenshots captured to disk at `tools/wave18_a3/evidence/<slug>/t0.png`, `t_mid.png`, `t_end.png`.
- Visual difference (RMS) measured between $t_0$ and $t_{\text{mid}}$ to verify temporal dynamism.

### Gate C: Project Insertion, Mutation & Physical MP4 Export
- Block inserted into versioned Project document revision (revision increments from 1 to 2).
- Variable mutation applied and verified (revision increments to 3).
- Project document reopened and validated via Content-Addressed Storage CAS.
- Multi-timestamp frame sequence rendered with FFmpeg into a genuine physical MP4 at `tools/wave18_a3/evidence/<slug>/<slug>_export.mp4`.
- Decoded with FFprobe verifying video stream, dimensions (1920x1080), h264 codec, and duration.
- SHA256 computed and recorded in the immutable ledger.

---

## 4. The 21 Blocked A–M Originals

### 9 Rights-Sensitive Originals (`BLOCKED_RIGHTS`)
1. `apple-money-count`: Proprietary Apple trademark, Apple Pay references, proprietary SFX.
2. `blue-sweater-intro-video`: Persona photograph and creator likeness (`joe-sai-avatar.png`).
3. `chatgpt-exchange`: OpenAI ChatGPT brand name, logo, and trademark trade dress.
4. `claude-exchange`: Anthropic Claude brand name, logo, and trademark trade dress.
5. `code-snippet-apple-terminal-pro`: Apple macOS Terminal interface trade dress.
6. `heygen-avatar-promo-card`: HeyGen avatar video service trademark and branding.
7. `ios26-liquid-glass`: Apple iPhone 3D model (`iphone.glb`) and 25 proprietary trademarked iOS app icons.
8. `macos-notification`: Apple macOS system notification interface and audio.
9. `macos-tahoe-liquid-glass`: Apple MacBook 3D model (`macbook.glb`) and macOS application icons.

### 12 Technical-Dependency Originals (`BLOCKED_DEPENDENCY`)
1. `canopy-part-title`: Requires unvendored Three.js r170 ESM postprocessing (`EffectComposer`/`BokehPass`).
2. `code-3d-extrude`: Requires complete Three.js UMD bundle with `WebGLRenderer` and `TextGeometry`.
3. `code-particle-assemble`: Requires complete Three.js UMD bundle with `WebGLRenderer` and particle buffer shaders.
4. `code-shader-dissolve`: Requires complete Three.js UMD bundle with `WebGLRenderer` and GLSL materials.
5. `exploded-stack`: Requires unvendored Three.js r184 ESM geometry (`RoundedBoxGeometry`).
6. `extruded-logo`: Requires unvendored Three.js r184 ESM `FontLoader` and `TextGeometry`.
7. `gallery-tunnel`: Requires complete Three.js r147 UMD bundle with `WebGLRenderer` constructor.
8. `glass-hero`: Requires unvendored Three.js r184 ESM transmission/refraction modules.
9. `glass-shard-title`: Requires unvendored `d3-delaunay.min.js` and HDR environment loader.
10. `liquid-glass-notification`: Requires WebGPU API (`navigator.gpu`) and unbundled liquid-glass IIFE library.
11. `liquid-glass-widgets`: Requires WebGPU API (`navigator.gpu`) and unbundled liquid-glass IIFE library.
12. `lottie-character-walk`: Requires unvendored `lottie-web` runtime player.

---

## 5. Wiring Instructions for Agent 5 (Integration Stage)

Agent 5 must reconcile the shared catalog runtime and frontend configurations after merging branch `wave18/03-hyperframes-am-real-preview`:

1. **Frontend Activation (`frontend/src/utils/catalogOriginals.js`):**
   - Import `AM_VERIFIED_100_BLOCKS` from `backend/catalog_runtime/ports/wave18_a3/adapter.py` (or mirror the array in frontend).
   - Update `DONOR_INTERNALIZED_IDS`:
     ```javascript
     export const DONOR_INTERNALIZED_IDS = new Set([
       ...AM_VERIFIED_100_BLOCKS,
       // (plus verified N-Z blocks from Agent 4)
     ])
     ```
2. **Backend Operability Activation (`backend/catalog/manifest_service.py`):**
   - In `get_operable_block_ids(wave=18)`:
     Include `AM_VERIFIED_100_BLOCKS` so that `validate_block_operable` returns HTTP 200 for preview, poster, and project insertion endpoints.
3. **Mount Agent 3 Adapter:**
   - In `backend/catalog_runtime/ports/`: import `agent3_port_adapter` from `wave18_a3.adapter` to delegate A–M project document mutations and responsive HTML preview generation.

---

## 6. Category Mapping for Agent 2

The authentic upstream donor categories for all 121 A–M blocks:
- **`typography`**: Lower thirds (`lt-*`, `lower-third-bild`), handwriting titles (`hw-title`, `hw-write-title`, `hw-path-text`).
- **`backgrounds`**: Shaders (`aurora`, `blob`, `flowing-gradient`, `fractal-noise`, `frost`, `godrays`, `goo`, `holographic`, `lens-flare`, `liquid-metal`, `marble`, `mesh-gradient`), `mk-background`.
- **`data-charts`**: `data-chart`, `bar-chart-race`, `flowchart`, `flowchart-vertical`, `mk-line-graph`, `mk-progress-stat`, `mk-specs-list`.
- **`carousels`**: `carousel-circle-1..5`, `carousel-orbit-1..5`, `carousel-path-1..5`, `carousel-text-circle-1..5`, `carousel-vision-1..5`, `cuboid-carousel`.
- **`code-developer`**: `code-diff`, `code-highlight`, `code-morph`, `code-scroll`, `code-slice-hero`, `code-snippet-dark-2026`, `code-snippet-dark-modern`, `code-typing`.
- **`transitions`**: `beat-freeze-cut`, `chromatic-radial-split`, `cross-warp-morph`, `domain-warp-dissolve`, `editorial-flash-overlay`, `flash-through-white`, `freeze-frame-dressing`, `glitch`, `gooey-split`, `light-leak`, `hw-scribble-transition`, `mk-clone-wall-transition`.
- **`mock-ui`**: `ai-answer-rank`, `ai-chat-reveal`, `app-showcase`, `camcorder-hud`, `instagram-follow`, `message-thread-reveal`, `mk-callout-highlight`, `mk-placeholder-grid`.
