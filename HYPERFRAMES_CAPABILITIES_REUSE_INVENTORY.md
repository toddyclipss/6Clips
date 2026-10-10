# HyperFrames Capabilities, Prompts, and Skills Reuse Inventory

**Date:** 2026-10-10
**Target:** HyperFrames Ecosystem (`C:\Users\toddy\Desktop\hyperframes`) & ViralMint Core Integration
**License Compliance:** Apache 2.0 Permissive Open Source (`C:\Users\toddy\Desktop\hyperframes\LICENSE`)
**Architecture Constraint:** 1 Main Agent, 1 Global Chat. All capabilities adapt to canonical `ProjectService` and atomic `ProjectRevision` workflows without introducing separate chat personas or parallel agent hierarchies.

---

## 1. Executive Summary

A comprehensive inventory of `C:\Users\toddy\Desktop\hyperframes` reveals a mature, battle-tested suite of professional motion graphics tools, animation contracts, audio DSP processors, caption engines, and UI components. Rather than reimplementing motion primitives from scratch, ViralMint can directly leverage these proven assets.

All evaluated HyperFrames assets are licensed under the **Apache License 2.0**, allowing full commercial integration, modification, and bundling within ViralMint.

---

## 2. Pinned Registry Blocks (150+ Validated Motion Blocks)

Located in `C:\Users\toddy\Desktop\hyperframes\registry\blocks`. Each block contains a `registry-item.json` manifest, declarative TypeScript/React animation code, typed variable schemas, and CSS/WebGL shaders.

### 2.1 Categorized Block Catalog

| Category | Representative Block Names | Capabilities & Variables | Adaptation Complexity |
| :--- | :--- | :--- | :--- |
| **Lower Thirds & Identifiers** | `lt-accent-underline`, `lt-bold-block`, `lt-clean-bar`, `lt-color-block`, `lt-dark-card`, `lt-kicker-name`, `lt-mask-reveal`, `lt-neon-border`, `lt-soft-pill`, `lt-stack-bars`, `lower-third-bild`, `yt-lower-third` | Primary text, secondary kicker, accent color, position preset, duration scaling. | **Low** (Already supported via `RegistryAdapter`) |
| **Social & Platform Callouts** | `yt-comment-card`, `tiktok-follow`, `instagram-follow`, `x-post`, `reddit-post`, `slack-notification-ad`, `macos-notification`, `ios26-liquid-glass` | Avatar image, username, handle, verified badge, likes/reposts count, pop-in sound trigger. | **Low** (Input props map directly to timeline clip variables) |
| **UI Mockups & Code Highlighting** | `code-snippet-dark-modern`, `code-snippet-apple-terminal-pro`, `code-typing`, `code-diff`, `code-3d-extrude`, `chatgpt-exchange`, `claude-exchange`, `app-showcase` | Syntax theme, code strings, typing speed, cursor blink, diff additions/deletions. | **Medium** (Integrates with ViralMint's CodeMirror 6 engine) |
| **Data Visualization & Charts** | `data-chart`, `bar-chart-race`, `mk-line-graph`, `mk-progress-stat`, `split-flap-board`, `apple-money-count` | Series data JSON, metric labels, color ramps, easing curves, formatters (`$`, `%`). | **Medium** (Requires structured JSON variables in Inspector) |
| **Maps & Geospatial** | `world-map`, `us-map`, `us-map-bubble`, `us-map-flow`, `spain-map`, `nyc-paris-flight` | Pin coordinates, flight arc trajectory, camera zoom, country highlights. | **Medium** (Canvas/SVG path rendering) |
| **Transitions & Wipes** | `transitions-blur`, `transitions-cover`, `transitions-destruction`, `transitions-dissolve`, `transitions-distortion`, `transitions-light`, `whip-pan`, `cross-warp-morph`, `flash-through-white` | Dual-clip transition shaders, duration (0.3s–1.2s), direction vector. | **Medium** (Requires timeline clip overlap transition handle) |
| **VFX, Shaders & Backgrounds** | `mesh-gradient`, `flowing-gradient`, `aurora`, `liquid-glass`, `godrays`, `glitch`, `thermal-distortion`, `starfield`, `fractal-noise` | WebGL GLSL shaders, noise octaves, color palette stops, seed, speed multiplier. | **Low** (Standalone background blocks) |

---

## 3. Motion & Animation Skills (`skills/`)

HyperFrames implements 21 declarative motion skills (`C:\Users\toddy\Desktop\hyperframes\skills-manifest.json`). The most critical for ViralMint Refine are:

### 3.1 `hyperframes-keyframes` (2D/3D Pose Ladder & Keyframe Contract)
- **File:** `skills/hyperframes-keyframes/SKILL.md`
- **Core Principle:** Keyframes own visual motion (`scale`, `x`, `y`, `opacity`, `rotation`), NOT clip temporal assembly. Source trimming belongs to core timing (`data-start`, `data-duration`, `data-media-start`).
- **Validated Presets:**
  - *Punch-in / punch-out:* Non-timed visual/crop wrapper inside clip with scale + position tween.
  - *Ken Burns / Camera Pan:* Author wrapper translation plus scale with smooth easing ladder.
  - *Seek-Safe Contract:* Renders deterministic transforms at any given float timestamp `t`.
- **ViralMint Value:** **P0**. Maps directly to our proposed Timeline expandable property subtracks.

### 3.2 `hyperframes-audio` (DSP, Dynamic Ducking & FX Chains)
- **File:** `skills/hyperframes-audio/SKILL.md`
- **Core Principle:** Audio mixing is a relational contract.
- **Key Attributes:**
  - `data-fx-chain`: Ordered DSP processors (Gain, EQ, Compressor, Limiter, Noise Gate, Saturation, Delay, Reverb, Chorus, Phaser, Bitcrush).
  - `data-automation`: Envelope lanes for volume or effect parameter automation over time.
  - `data-fx-carve`: Automated sidechain ducking (e.g. music bed frequency-carves around voiceover narration without crushing master dynamics).
- **ViralMint Value:** **P0**. Provides the mathematical and declarative foundation for multi-track audio mixing and automated music ducking under voiceovers.

### 3.3 `embedded-captions` (35 Styled Subtitle Identities & Matting)
- **File:** `skills/embedded-captions/SKILL.md`
- **Core Principle:** Split into *Standard Rail* (clean lower-third verbatim text) and *Cinematic Embed* (composited behind the speaker's head via matting).
- **Themes:** 35 pre-styled identities (`ordnance`, `terminal`, `neonsign`, `stardust`, `stomp`, etc.).
- **ViralMint Value:** **P1**. ViralMint's current captions are flat text cards. Incorporating the 35 caption style presets elevates short-form video quality to top TikTok/Reels standards.

---

## 4. UI Components & NLE Architecture (`packages/studio/src`)

The HyperFrames Studio package contains verified UI patterns directly solving ViralMint's Refine bottlenecks:

### 4.1 Non-Destructive Asset & Block Previews
- **`packages/studio/src/components/nle/AssetPreviewOverlay.tsx`:**
  - CapCut-style floating media preview over canvas.
  - Intercepts clicks on un-added assets/blocks, previews audio/video/image without creating an undo entry or mutating the project document.
  - Dismissible via ESC, click outside, or playhead movement.
- **`packages/studio/src/components/sidebar/BlocksTab.tsx` (BlockCard Hover Preview):**
  - Features debounced (300ms) hover trigger (`onPreview?.({ videoUrl, posterUrl, title })`).
  - Automatically cancels pending hover preview on mouse leave.
- **`packages/studio/vite.thumbnail.ts`:**
  - Headless thumbnail generation using Puppeteer and `window.__player.seek(t)`.

### 4.2 Professional Timeline & Audio Meters
- **`packages/studio/src/components/nle/AudioMeterStrip.tsx`:**
  - Live stereo decibel meter (peak/RMS) for scrubbing and playback.
- **`packages/studio/src/components/nle/useCanvasZOrderTimelineMirror.ts`:**
  - Bi-directional synchronization between canvas layer z-order and timeline track stacking order.
- **`packages/studio/src/components/nle/zLaneGesture.ts`:**
  - Robust drag-to-reorder track gesture handling.

---

## 5. Agent Prompts & Context Synthesis

In `packages/studio/src/components/sidebar/BlocksTab.tsx` (Lines 209–268), `buildAgentPrompt()` implements a context-aware prompt generator:

```typescript
function buildAgentPrompt(title, name, description, category, blockType, context: CompositionContext) {
  // Synthesizes current playhead time, active composition, visible elements at time t,
  // and highest track index into a structured instruction for the agent.
}
```

### Adaptation into ViralMint Single-Agent Architecture
In ViralMint, we have **1 Main Agent and 1 Global Chat**. Instead of launching a modal that talks to a separate agent, clicking "Ask AI to Insert & Style" in the Catalog will:
1. Call this context builder to capture `{ playheadTime, activeElements, trackCount, blockName, variables }`.
2. Populate the prompt into ViralMint's global Chat input.
3. The Main Agent processes the instruction using existing `ProjectService` atomic timeline operations, keeping the entire chat history and project context unified.

---

## 6. Integration Roadmap & Value Matrix

| Asset | Source Path | ViralMint Target Destination | Priority | Complexity |
| :--- | :--- | :--- | :--- | :--- |
| **Catalog Manifest Cache** | `RegistryAdapter.py` | `backend/app/adapters/registry_adapter.py` | **P0** | Low (1 day) |
| **Hover Preview Overlay** | `AssetPreviewOverlay.tsx` | `frontend/src/components/motion/StudioPreviewStage.jsx` | **P0** | Low (1-2 days) |
| **Keyframe Subtrack Model** | `skills/hyperframes-keyframes` | `StudioTimelineWorkspace.jsx` | **P0** | Medium (3 days) |
| **Audio Ducking / FX Envelopes** | `skills/hyperframes-audio` | `backend/app/adapters/hyperframes_adapter.py` | **P1** | Medium (2-3 days) |
| **35 Caption Preset Styles** | `skills/embedded-captions` | `frontend/src/components/motion/MotionGraphics.jsx` | **P1** | Medium (2 days) |
| **Audio Peak Meter Strip** | `AudioMeterStrip.tsx` | `frontend/src/components/motion/StudioTimelineWorkspace.jsx` | **P2** | Low (1 day) |

---

## 7. Conclusion

The HyperFrames ecosystem provides production-ready solutions for every UX and architectural challenge identified in the Phase 9 audit. By directly adapting these Apache 2.0 components into ViralMint's single-agent, canonical `ProjectService` architecture, we avoid reinventing the wheel and accelerate the product roadmap toward commercial release.
