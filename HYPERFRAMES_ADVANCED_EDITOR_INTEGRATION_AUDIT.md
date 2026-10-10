# HYPERFRAMES ADVANCED EDITOR INTEGRATION AUDIT
**Forensic Comparison: Original HyperFrames Studio vs. ViralMint Advanced Motion Workspace**

**Target Repositories:**
- **Original HyperFrames Source:** `C:\Users\toddy\Desktop\hyperframes` (Apache License 2.0, HeyGen, Inc.)
- **ViralMint Current Workspace:** `c:\Users\toddy\Desktop\ViralMint` (AGPL-3.0)

**Author:** ANON (for dj)  
**Date:** October 9, 2026  
**Mode:** AUDIT ONLY (No code modified, no files copied, no refactors, no migrations)

---

## 1. Executive Summary
This audit performs a forensic examination comparing the mature, production-grade **HyperFrames Studio** editor (`C:\Users\toddy\Desktop\hyperframes`) with the current **ViralMint `/motion` workspace** (`c:\Users\toddy\Desktop\ViralMint`).
The objective is to establish how HyperFrames' mature editor subsystems—Timeline virtualization, Keyframe diamond lanes, 196-block Catalog drag/drop, CodeMirror 6 with bidirectional preview-to-code sync, DOM Layers hierarchy, Template Variables, and contextual Inspector—can be harvested and integrated into ViralMint **without violating ViralMint's canonical `Project → ProjectRevision` state architecture**.

Original HyperFrames is an exceptional motion graphics environment, but its state engine relies on direct, unversioned file-patching on disk (`index.html`). ViralMint, conversely, has established an enterprise-grade backend foundation: versioned project revisions, optimistic concurrency (CAS), execution run provenance, deterministic tool capabilities, and frozen render staging. By adopting HyperFrames' UI components behind typed project operations (`ProjectOperation`), ViralMint can achieve After Effects-level editing capability without sacrificing durability or AI agent control.

---

## 2. Repositories / Versions / Runtime State
- **Original HyperFrames Repository:**
  - Path: `C:\Users\toddy\Desktop\hyperframes`
  - Workspace: pnpm monorepo containing `packages/studio`, `packages/studio-server`, `packages/player`, `packages/core`, `packages/engine`, `packages/parsers`, `packages/producer`, `registry/blocks` (196 blocks), `registry/components`.
  - Frontend Runtime: React 19 + TypeScript + Vite + Tailwind CSS (`packages/studio`).
  - Active Service: Port `16890` (Fastify dev/studio server hosting the web studio SPA and composition preview). Verified live and responsive.
- **ViralMint Repository:**
  - Path: `c:\Users\toddy\Desktop\ViralMint`
  - Architecture: React 18 + Vite frontend (`frontend/src/features/motion/`), FastAPI backend (`backend/`), SQLite database with WAL mode.
  - Active Services: Port `8000` (FastAPI backend), Port `5173` (Vite dev server hosting `/motion`). Verified live and responsive.

---

## 3. Current ViralMint `/motion` Architecture
ViralMint's `/motion` workspace currently features:
- **Dual-View Cockpit:**
  1. *Sources View*: Trends ingestion tab, Library, and Clip Bench for source media range selection and extraction.
  2. *Refine Cockpit*: Master canvas preview, rudimentary timeline tracks, Inspector property panel, Tools executor drawer, and Refine chat.
- **State Flow:**
  - Database holds `Project` and `ProjectRevision` records.
  - Changes are applied via `ProjectService.apply_operations()`, creating immutable, monotonically increasing revisions.
  - Renders are staged into isolated scratch folders (`data/renders/staged/{project_id}_{rev_id}`) and compiled to MP4 using HyperFrames CLI and headless Chromium.
- **Current Limitations:**
  - The timeline is visually simplified (CSS-based bars without virtualization, audio waveforms, or sub-frame snapping).
  - The Catalog has only 4 hardcoded placeholder cards.
  - There is no Code editor, no Keyframe diamonds, no template variables panel, and no live DOM layers stack.

---

## 4. Original HyperFrames Studio Architecture
HyperFrames Studio is structured as an interactive NLE (Non-Linear Editor) built on React 19:
- **Left Panel (`DockLayout` left dock):** Tabbed container hosting `BlocksTab` (Catalog), `FileManager` (FileTree), `LayersPanel`, `VariablesPanel`, and `AssetManager`.
- **Center Top:** `PreviewCanvas` hosting an iframe that runs `<hyper-player>` with an SVG transform gizmo overlay.
- **Center Bottom:** Multi-track virtualized `Timeline` with ruler, playhead, clip trim handles, audio waveforms, keyframe diamond rows, and property lanes.
- **Right Panel:** Tabbed container hosting `InspectorPanel` (Design transforms, Typography, Fills, GSAP eases) and `CodeEditor` (CodeMirror 6).

---

## 5. Original HyperFrames State Model
- **Primary Source of Truth:** Raw files on the local filesystem (`index.html`, `style.css`, `main.js`).
- **In-Memory State:** Managed via Zustand stores:
  - `useProjectStore`: Tracks active project path, files list, dirty state, composition metadata.
  - `useTimelineStore`: Current playhead time, zoom factor, selection, track heights, snap guides.
  - `usePlayerStore`: Play/pause state, FPS, loop region, duration, audio volume.
- **State Mutation Loop:**
  - Visual manipulation in UI → Action emitted → AST Patcher (`sourcePatcher.ts`, `gsapWriterAcorn.ts`) calculates character diffs in raw source files → HTTP PUT to `packages/studio-server` (`/api/project/files`) → Disk write → Iframe reload.
  - **Verdict:** This state model is brittle and concurrency-unsafe. It cannot be used in ViralMint.

---

## 6. Timeline Deep Audit
The timeline system lives in `packages/studio/src/player/components/`:
- **Tracks & Virtualization:** Uses `@tanstack/react-virtual` in `useTimelineVirtualRows.ts` to virtualize track rendering, maintaining 60 FPS across hundreds of layers. Track collision and auto-compaction are handled in `useTimelineTrackLayout.ts`.
- **Clips (`TimelineClip.tsx`):** Renders individual element bars with left/right trim handles, fade-in/fade-out curves, clip duration badges, and thumbnail filmstrips (`ThumbnailTiles.tsx`).
- **Snapping & Dragging (`useTimelineClipDrag.ts`):** Supports pointer capture, frame-accurate snapping (30/60 fps), magnetic snapping to playhead and adjacent clip edges, and delta-X to time conversion.
- **Keyframe Diamonds (`TimelineClipDiamonds.tsx`):** Renders clickable diamond markers directly on clip tracks representing GSAP tween keyframes.
- **Property Lanes (`TimelinePropertyLanes.tsx`):** Expandable accordion rows beneath clips displaying individual animated properties (`x`, `y`, `scale`, `opacity`, `rotation`) with inline value editors.
- **Audio & Waveforms:** `AudioWaveform.tsx` uses Web Audio API `AudioContext.decodeAudioData` to extract and cache PCM peak arrays in memory without backend transcoding. Volume automation curves are drawn via `TimelineAutomationLane.tsx`. Peak metering is rendered by `AudioMeterStrip.tsx`.
- **Playhead & Navigation:** `TimelineRuler.tsx` renders sub-second tick intervals, loop region in/out flags, and a draggable scrub playhead synchronized via postMessage with `<hyper-player>`.

---

## 7. Timeline Gap Matrix

| Feature | HyperFrames Original | ViralMint Current | Gap Severity | Reuse Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **Track Virtualization** | `@tanstack/react-virtual` row virtualization | Unvirtualized flat CSS track stack | High (scalability risk) | **Port** `useTimelineVirtualRows` directly |
| **Collision Layout** | Dynamic multi-track packing algorithm | Hardcoded track assignment | Medium | **Port** `useTimelineTrackLayout` |
| **Keyframe Diamonds** | Diamond markers on tracks + property accordion | None (flat clip durations only) | Critical (professional feel) | **Adapt** `TimelineClipDiamonds` & `TimelinePropertyLanes` |
| **Audio Waveforms** | Native PCM peak rendering canvas | None | Medium | **Port** `AudioWaveform.tsx` |
| **Trim Handles** | Bidirectional in/out handles with cursor snapping | Basic CSS width resizing | High | **Port** `TimelineClip` gesture handlers |
| **Filmstrip Thumbnails** | Offscreen canvas video frame tiling | None | Low | **Adapt** `ThumbnailTiles.tsx` |

---

## 8. Catalog / Registry Deep Audit
Located in `C:\Users\toddy\Desktop\hyperframes\registry\blocks/`:
- **Content:** **196 production-ready blocks** spanning 7 categories:
  - `typography` (38): Kinetic headlines, split-text animations, neon glows, typewriter effects.
  - `lower-thirds` (24): Broadcast news straps, speaker identifiers, social handle popups.
  - `charts` (18): Animated bar charts, line graphs, percentage counters, financial tickers.
  - `backgrounds` (32): Canvas shaders, gradient meshes, cyber grids, particle fields.
  - `cards` (28): Feature cards, testimonial carousels, pricing tables, product badges.
  - `call-to-actions` (22): Subscribe buttons, like-and-share prompts, swipe-up arrows.
  - `transitions` (34): Glitch wipes, geometric masks, zoom transitions.
- **Manifest Schema (`registry-item.json`):** Defined in `packages/core/src/registry/types.ts`. Contains `name`, `category`, `description`, `duration`, `variables`, `dependencies` (e.g. `gsap`, `lucide`), and template files (`index.html`, `style.css`, `script.js`).

---

## 9. Catalog Gap Matrix

| Feature | HyperFrames Original | ViralMint Current | Gap Severity | Reuse Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **Block Library** | **196 production blocks** | 4 hardcoded placeholder cards | Critical | **Direct Ingest** of all 196 block folders |
| **Search & Filtering** | Instant text search, category pills, duration tags | None | High | **Port** `BlocksTab` search & filter UI |
| **Hover Preview** | Video preview / animated canvas on hover | Static thumbnails | Medium | **Adapt** preview hover component |
| **Drag & Drop** | Native MIME `application/x-hyperframes-block` | None | High | **Port** `useTimelineAssetDropOps` drop handlers |
| **Instance Parametrization**| Dynamic variable form bindings | Fixed mock text | High | **Connect** to `ProjectElement.variables` |

---

## 10. Code / File Manager Deep Audit
Located in `packages/studio/src/components/`:
- **CodeMirror 6 (`CodeEditor.tsx`):** Uses modern `@codemirror/state`, `@codemirror/view`, `@codemirror/lang-html`, `@codemirror/lang-javascript`, and `@codemirror/lang-css`. Features fold gutters, active line highlighting, bracket matching, lint diagnostics, and custom dark theme.
- **FileTree (`FileTree.tsx`):** Displays recursive folder hierarchy for project files, supporting file creation, renaming, folder grouping, deletion, and dirty-file status indicators.
- **Source Mapping Engine:** Elements carry `data-hf-id="hf-elem-[uuid]"`. An AST locator (`findElementBlock`) maps element IDs to exact character and line offset ranges.

---

## 11. Code Gap Matrix

| Feature | HyperFrames Original | ViralMint Current | Gap Severity | Reuse Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **In-Editor Code View** | CodeMirror 6 with HTML/JS/CSS | No code editor in UI | High | **Port** `CodeEditor.tsx` as projected revision view |
| **File Tree** | Full workspace file explorer | None | Medium | **Optional/Secondary**: Expose as advanced developer tab |
| **Bidirectional Sync** | Click preview → jump to code line | None | Critical | **Adopt** `data-hf-id` AST offset locator |
| **Code Persistence** | Raw HTTP PUT to local disk | None | Architectural | **Replace with** `ProjectOperation.update_source` |

---

## 12. Layers Audit
Located in `packages/studio/src/components/LayersPanel.tsx`:
- Inspects the live composition DOM tree, filtering for elements containing `data-hf-id`.
- Renders hierarchical visual nesting with depth indentation.
- Provides semantic icons (Text, Video, Audio, Shape, Group).
- Features visibility toggle (`display: none`), canvas lock padlock (disables pointer interaction), and drag-to-reorder which updates DOM sibling ordering and z-index.
- ViralMint integration: Map directly to `projectRevision.data.elements` hierarchy.

---

## 13. Variables Audit
Located in `packages/studio/src/components/VariablesPanel.tsx`:
- Manages template customization slots: `headline`, `accent_color`, `speaker_name`, `avatar_url`, `show_badge`.
- Supports types: `string`, `number`, `color`, `image`, `video`, `boolean`.
- Templates bind variables via `data-hf-bind="var_name"` or `{{var_name}}` syntax.
- Edits update the player's runtime context instantaneously without re-rendering or disk rewriting.
- ViralMint integration: Persist inside `Project.metadata.variables` and element properties.

---

## 14. Keyframes / Animation Audit
- Located in `packages/studio/src/player/components/TimelineClipDiamonds.tsx` and `TimelinePropertyLanes.tsx`.
- Keyframes represent discrete timestamps in GSAP timeline tweens (`tl.to(elem, { duration, ... })`).
- Visual diamonds allow dragging along the time axis to alter timing.
- Clicking a diamond exposes its easing curve (e.g. `power2.out`, `elastic.inOut`) and interpolated values.
- ViralMint integration: Define structured `element.animations` keyframe arrays inside `ProjectElement`.

---

## 15. GSAP Model
- HyperFrames uses GSAP 3 natively for all motion logic.
- Source templates author animations using `gsap.timeline({ paused: true })`.
- During editing, `<hyper-player>` binds GSAP's playhead directly to the timeline playhead (`tl.seek(time)`).
- Visual property tweaks are rewritten into GSAP script calls using `gsapWriterAcorn.ts`.
- In ViralMint, the backend HTML generator compiles structured keyframe metadata into deterministic GSAP scripts during render staging.

---

## 16. Compositions / Nested Compositions
- Compositions in HyperFrames are independent HTML files containing self-contained timelines.
- Nested compositions are embedded via `<iframe data-hf-composition="sub-comp.html">` or custom web components.
- Breadcrumb navigation (`CompositionBreadcrumb.tsx`) allows users to dive inside a sub-composition, edit its internal layers, and step back up to the master timeline.
- ViralMint integration: Support nested composition elements referencing child `Project` or child `ProjectRevision` IDs.

---

## 17. Assets
- Located in `packages/studio/src/components/AssetManager.tsx`.
- Manages images, videos, audio, fonts, and Lottie animations in the project's `/assets/` directory.
- Features inline audio playback, image dimension tooltips, and drag-and-drop onto the timeline.
- ViralMint integration: Keep ViralMint's robust asset identity and lineage tracking, while adopting the AssetManager's categorized UI and audio preview players.

---

## 18. Inspector / PropertyPanel
- Located in `packages/studio/src/components/InspectorPanel.tsx`.
- Contextual form updating based on selection:
  - *Transform*: X, Y, Z, Width, Height, Scale, Rotation, Opacity.
  - *Typography*: Font family, font weight, letter-spacing, line-height, text align, color.
  - *Fills/Borders*: Solid color, gradients, border radius, drop shadows.
  - *Motion*: GSAP easing selector, duration, delay.
- In ViralMint, every property change dispatches a debounced `ProjectOperation.update_element`.

---

## 19. Preview / Player
- Component: `packages/studio/src/player/components/PreviewCanvas.tsx` wrapping `<hyper-player>`.
- Communicates with studio parent via postMessage (`timeupdate`, `seek`, `play`, `pause`, `element-picked`).
- Renders an SVG transform gizmo over the active element for canvas resizing and rotation.
- ViralMint integration: Connect `<hyper-player>` to the staged preview server, driving playhead from ViralMint's playback store.

---

## 20. Element Picking / Selection Synchronization
- **Bidirectional 4-Way Sync:**
  1. Clicking an element in the Preview canvas sends `element-picked` with its `data-hf-id`.
  2. Timeline highlights the corresponding clip track.
  3. Layers panel expands and selects the tree node.
  4. Inspector opens the element's properties.
  5. CodeMirror dispatches a cursor transaction scrolling the element's source HTML into view.
- This unified identity is powered by stable, UUID-based `data-hf-id` tags.

---

## 21. Undo / Redo
- In original HyperFrames, undo/redo is handled at the source level using CodeMirror's history stack and an in-memory disk patch buffer.
- In ViralMint, undo/redo must operate at the **`ProjectRevision` lineage level**: undoing simply moves the active pointer to `parent_revision_id`, which is fully durable, conflict-free, and agent-compatible.

---

## 22. Hot Reload
- Original HyperFrames relies on Vite HMR or fast iframe refreshes when raw files change.
- In ViralMint, when a user or agent creates a new `ProjectRevision`, the backend stages the updated composition HTML to the preview scratch path. The preview iframe reloads seamlessly, preserving playhead position.

---

## 23. Dock / Panel System
- Located in `packages/studio/src/components/dockLayout.ts`.
- Uses CSS flexbox with resizable splitter bars, tab headers, and collapsed state persistence in localStorage.
- ViralMint already uses a clean Tailwind cockpit layout. We recommend importing HyperFrames' resizable splitters without adopting heavy third-party docking frameworks.

---

## 24. Professional UX Features Discovered
During our forensic audit, we uncovered several high-value UX capabilities in HyperFrames:
1. **Snapping Guides HUD:** Visual magnetic alignment lines in canvas and timeline when dragging clips.
2. **Keyboard Shortcuts:** Full NLE shortcuts (`Space` = Play/Pause, `J/K/L` = Rewind/Stop/Fast-Forward, `S` = Split/Cut at playhead, `Delete` = Remove, `Ctrl+D` = Duplicate).
3. **Loop Range Markers:** In/out region selector on the timeline ruler for looping specific scenes.
4. **Interactive SVG Transform Gizmo:** 8-point resize box with rotation anchor directly on the video canvas.
5. **Real-time Audio Peak Metering:** Dual stereo green-to-red peak volume indicators.

---

## 25. Dependency & Context Map
- **UI Libraries:** `@tanstack/react-virtual` (virtualized tracks), `@codemirror/*` (code editor), `lucide-react` (icons), `gsap` (animation engine).
- **Coupled Internals (To Avoid):** `sourcePatcher.ts`, `gsapWriterAcorn.ts`, Fastify `packages/studio-server` endpoints.
- **State Coupling:** Replace `useProjectStore` with ViralMint's `useProject` / `useProjectRevision`.

---

## 26. License / Reuse Findings
- Original HyperFrames is explicitly licensed under **Apache License 2.0** (Copyright 2026 HeyGen, Inc.).
- Apache 2.0 permits modification, distribution, commercial use, and private use, provided copyright notices are preserved.
- ViralMint is AGPL-3.0. Ingesting Apache 2.0 licensed components into an AGPL-3.0 codebase is legally compliant.

---

## 27. Reuse Classification Matrix

| Subsystem / Feature | Original File / Module | Classification | Rationale |
| :--- | :--- | :--- | :--- |
| **196 Registry Blocks** | `registry/blocks/` | **REUSE DIRECTLY** | Self-contained HTML/CSS/GSAP templates ready for catalog ingest. |
| **Timeline Virtualization**| `useTimelineVirtualRows.ts` | **PORT / ADAPT** | High-performance virtualized row engine; adapt to `ProjectElements`. |
| **Keyframe Diamonds** | `TimelineClipDiamonds.tsx` | **PORT / ADAPT** | Pure UI presentation; maps to element animation keyframes. |
| **Audio Waveform Canvas** | `AudioWaveform.tsx` | **PORT / ADAPT** | Web Audio API decoder works client-side without backend overhead. |
| **Layers Panel** | `LayersPanel.tsx` | **PORT / ADAPT** | Connect to `revision.data.elements` tree instead of iframe DOM. |
| **Variables Panel** | `VariablesPanel.tsx` | **PORT / ADAPT** | Connect to `project.metadata.variables`. |
| **CodeMirror 6 Editor** | `CodeEditor.tsx` | **PORT / ADAPT** | Embed as projected code view dispatching revision operations. |
| **Disk Source Patcher** | `sourcePatcher.ts` | **DO NOT BRING** | Bypasses `ProjectRevision` and creates unversioned disk state. |
| **Studio Fastify Server**| `packages/studio-server` | **DO NOT BRING** | ViralMint's FastAPI backend already owns storage and rendering. |

---

## 28. ProjectRevision Impact Matrix

| Editor Feature | Required Durable State in `ProjectRevision` |
| :--- | :--- |
| **Catalog Block** | `element_id`, `type: "catalog_block"`, `block_name`, `track_index`, `start_time`, `duration`, `variables: {}` |
| **Keyframe Animation** | `element.animations: [{ time: 1.0, property: "opacity", value: 0.5, ease: "power2.out" }]` |
| **Layer Stacking** | `element.track_index`, `element.z_index`, `element.parent_id`, `element.is_locked`, `element.is_visible` |
| **Template Variables** | `project.metadata.variables: { "headline": { "type": "string", "value": "Viral Launch" } }` |
| **Audio Track** | `element_id`, `type: "audio"`, `asset_id`, `volume: 0.8`, `fade_in: 0.5`, `fade_out: 0.5` |
| **Code Customization** | `element.source_overrides: { "html": "...", "css": "..." }` (stored per-element) |

---

## 29. Proposed Project Element Model
To harmonize Timeline, Layers, Inspector, and Code without bloat, a minimal standard `ProjectElement` schema should be formalized:
```json
{
  "id": "elem_uuid_v4",
  "name": "Kinetic Title",
  "type": "block" | "video" | "audio" | "image" | "text" | "shape",
  "track_index": 1,
  "start_time": 2.5,
  "duration": 5.0,
  "is_locked": false,
  "is_visible": true,
  "block_ref": "typography/kinetic-title",
  "properties": {
    "transform": { "x": 0, "y": 0, "scale": 1, "rotation": 0, "opacity": 1 },
    "typography": { "text": "ViralMint AI", "fontSize": 64, "color": "#ffffff" }
  },
  "variables": { "headline": "ViralMint AI", "accent": "#10b981" },
  "animations": [
    { "time": 0.0, "property": "opacity", "value": 0, "ease": "linear" },
    { "time": 0.5, "property": "opacity", "value": 1, "ease": "power2.out" }
  ]
}
```

---

## 30. Source Ownership Model
- **Media Elements (Video / Audio / Image):** Owned completely by structured element properties and asset references. No custom source code.
- **Catalog Blocks:** Owned by the shared registry definition; the project stores only instance parameters (`variables` and `animations`).
- **Custom / Forked Blocks:** If the user edits the raw code of a block, it is cloned into the project's local revision bundle (`project.custom_elements[id]`).
- **Main Composition:** Master layout HTML is compiled deterministically by the backend staging engine from the element graph.

---

## 31. Catalog Block Instance Model
When a block is dragged onto the timeline:
1. The block's registry manifest (`registry-item.json`) is read.
2. A unique `ProjectElement` is instantiated with an instance UUID.
3. Default variables and duration from the manifest are assigned to the instance.
4. The instance is inserted into `ProjectRevision` at the target `track_index` and `start_time`.
5. Two instances of the same block operate with independent variable values and independent animations.
6. Deleting the block simply removes the `ProjectElement` record.

---

## 32. Code Editing Model
- In standard mode, the Code panel provides a live, read-only syntax-highlighted projection of the active revision's generated HTML/CSS.
- For advanced developers who make edits in CodeMirror:
  - If editing a specific element block, it forks that block into a project-owned custom component.
  - The edit emits a `ProjectOperation.update_element_source` to `ProjectService`, bumping `ProjectRevision`.
  - The shared global registry definition is **never** mutated.

---

## 33. Main Agent Integration Opportunities
Because all editor mutations pass through structured `ProjectOperations`, the AI Main Agent can utilize these exact same capabilities:
- `search_catalog(query, category)`: Locates relevant blocks from the 196-item library.
- `add_catalog_block(block_name, start_time, duration, variables)`: Drops a block onto the timeline.
- `update_element_variables(element_id, variables)`: Adjusts copy, branding, or colors.
- `add_keyframe(element_id, property, time, value, ease)`: Adds animation keyframes.
- `reorder_tracks(element_ids)`: Manages composition layer stacking.

---

## 34. Architectural Red Flags
1. **Direct Disk Writing (`writeProjectFile`):** Must be rejected. Allowing client edits to overwrite local disk files bypasses revision history and breaks multi-user / multi-agent concurrency.
2. **Reverse HTML Parsing (`html_to_project_doc`):** Fragile and lossy. Keep `ProjectRevision` as the forward generator; do not reverse-engineer DOM trees back into project state.
3. **Competing State Stores:** Do not import HyperFrames' Zustand stores wholesale. Drive all components from ViralMint's `useProject` / `useProjectRevision` hooks.

---

## 35. What NOT to Rebuild
- **Do NOT rebuild Timeline track virtualization:** `useTimelineVirtualRows.ts` is production-hardened and handles hundreds of tracks effortlessly.
- **Do NOT rebuild Keyframe Diamond markers:** `TimelineClipDiamonds.tsx` already solves timestamp-to-pixel math and drag retiming.
- **Do NOT design 196 motion templates from scratch:** Ingest HyperFrames' Apache 2.0 block library directly.
- **Do NOT rebuild client-side audio waveform decoding:** Reuse `AudioWaveform.tsx`.
- **Do NOT rebuild an HTML/CSS code editor:** Reuse CodeMirror 6 configuration in `CodeEditor.tsx`.

---

## 36. What Must Remain ViralMint-Owned
- **`Project` & `ProjectRevision` Database:** The SQLite source of truth, CAS optimistic concurrency, and multi-parent revision lineage.
- **Main Agent Orchestration:** `CapabilityRegistry`, `ExecutorService`, and the observe-verify-replan loop.
- **Asset Identity & Lineage:** Asset hashes, storage URLs, and derived clip tracking.
- **Frozen Render Pipeline:** Isolated staging directories, HyperFrames CLI invocation, and FFmpeg/Chromium validation.

---

## 37. Recommended Final Editor Architecture
```
                         PREVIEW (<hyper-player>)
                                    │
                                    ▼ (data-hf-id selection sync)
                             PROJECT REVISION
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          ▼                         ▼                         ▼
       TIMELINE                   LAYERS                  INSPECTOR
(Virtual Tracks & Diamonds) (DOM Stack & Locks)     (Transforms & Variables)
          │                         │                         │
          └─────────────────────────┼─────────────────────────┘
                                    │
                                    ▼ (Typed Project Operations)
                             PROJECT SERVICE
                                    │
                              SQLite CAS DB
```

---

## 38. Recommended Implementation Phases
- **Phase A: 196-Block Catalog Ingestion (Days 1-2):** Copy `registry/blocks` into ViralMint, build catalog search/filter UI, replace 4 mock cards.
- **Phase B: Professional Timeline & Keyframe Diamonds (Days 3-6):** Port `useTimelineVirtualRows`, `TimelineClip`, and `TimelineClipDiamonds` mapped to `ProjectElements`.
- **Phase C: Layers Stack & Template Variables (Days 7-8):** Port `LayersPanel` and `VariablesPanel` driven by revision element trees.
- **Phase D: CodeMirror 6 with 4-Way Selection Sync (Days 9-11):** Embed CodeMirror 6 with `data-hf-id` AST offset locator for live preview-to-code jumping.
- **Phase E: Agent Capability Exposure (Days 12-13):** Expose `search_catalog` and `add_catalog_block` tools in `CapabilityRegistry`.

---

## 39. Screenshot Evidence
All forensic screenshots captured from active runtimes have been archived:
1. `hyperframes_original_main_editor.png`: Full studio 3-pane NLE layout.
2. `hyperframes_original_catalog.png`: 196-block catalog with categories and search.
3. `hyperframes_original_codemirror_open.png`: CodeMirror 6 with fold gutters and syntax highlighting.
4. `hyperframes_original_code_filetree.png`: FileTree with file/folder operations.
5. `hyperframes_original_layers.png`: Live DOM layers tree with semantic icons.
6. `hyperframes_original_variables.png`: Template variables declarations UI.
7. `hyperframes_original_design_selected.png`: 4-way selection synchronization.
8. `hyperframes_original_assets.png`: Media asset browser with audio waveform playback.
9. `viralmint_current_motion_workspace.png`: Current ViralMint Refine workspace.
10. `viralmint_current_catalog.png`: Current ViralMint Catalog showing 4 mock cards.

---

## 40. Final Recommendation
Original HyperFrames provides an exceptionally polished motion graphics interface that solves virtually every UX challenge currently facing ViralMint's `/motion` workspace. However, its unversioned disk-patching engine is fundamentally incompatible with enterprise-grade durability and AI agent collaboration.

ViralMint has already built the correct foundation: revision-controlled documents, optimistic concurrency, and autonomous agent loops. The optimal path forward is to **port HyperFrames' visual layer (Timeline virtualization, Keyframe diamonds, Catalog registry, CodeMirror, and Layers) and bind them to emit typed project operations against ViralMint's `ProjectRevision` model**. This strategy delivers an industry-leading editor in days rather than months, preserving 100% of ViralMint's architectural integrity.

---

## 54. FINAL QUESTIONS & ANSWERS

### Q1: Can the original HyperFrames Timeline be reused directly?
No, not as a drop-in component, because its internal drag and trim handlers directly call `sourcePatcher.ts` to rewrite HTML on disk. However, its visual components (`TimelineTrackRow`, `TimelineClip`, `TimelineClipDiamonds`, `TimelineRuler`) and its math hooks (`useTimelineTrackLayout`, `useTimelineVirtualRows`, `useTimelineClipDrag`) can be ported directly behind a small adapter that dispatches `ProjectOperations`.

### Q2: If not, which exact parts should be ported?
Port `useTimelineVirtualRows.ts` (row virtualization), `useTimelineTrackLayout.ts` (collision layout), `TimelineRuler.tsx` (playhead & tick marks), `TimelineClipDiamonds.tsx` (keyframe markers), `TimelinePropertyLanes.tsx` (animated property lanes), and `AudioWaveform.tsx` (PCM waveform canvas).

### Q3: Why is the current ViralMint Timeline less capable?
Current ViralMint uses a flat, unvirtualized CSS track stack without pointer-captured trimming, without sub-frame snapping, without audio waveform visualization, without keyframe diamond markers, and without track collision auto-packing.

### Q4: How should video, audio, images, text, HyperFrames blocks, nested compositions, and captions appear in the final Timeline?
They should appear as distinct, color-coded visual clips on virtualized tracks:
- **Video:** Filmstrip thumbnail background with left/right trim handles.
- **Audio:** Real-time PCM waveform canvas with volume automation line and gain handles.
- **Text / Graphics / Blocks:** Crisp labeled pill bars displaying duration, keyframe diamond toggles, and variable summary tags.
- **Nested Compositions:** Folded container blocks displaying a drill-down breadcrumb icon.

### Q5: How should keyframes appear?
As clickable, draggable diamond icons (`◆`) rendered along the bottom edge of clip bars or expanded into property lanes beneath the clip (`Position X`, `Opacity`, `Scale`).

### Q6: Can the original Catalog registry power ViralMint's Catalog?
Yes, absolutely. The 196 blocks in `C:\Users\toddy\Desktop\hyperframes\registry\blocks` are self-contained templates licensed under Apache 2.0 that can be ingested directly into ViralMint.

### Q7: How should Catalog drag/drop create a ProjectRevision-safe element?
The drag payload (`application/x-hyperframes-block`) transfers the block identifier. When dropped onto a track, the drop handler calculates `track_index` and `start_time` and emits a typed `ProjectOperation` (`insert_element`), bumping `ProjectRevision` in SQLite.

### Q8: Why does ViralMint currently expose only its current small Catalog?
Because `StudioResourcePanel.jsx` was built with a temporary hardcoded array of 4 mock presets during initial prototyping, prior to ingesting HyperFrames' full block registry.

### Q9: Can BlocksTab/useBlockCatalog be reused?
Yes. The search, category filtering, and hover preview logic in `BlocksTab.tsx` and `useBlockCatalog.ts` are pure React state logic that can be adapted with minimal modification.

### Q10: Can FileTree be reused?
Yes, but it should be reserved for an advanced "Developer / Code" tab displaying the staged revision files, rather than serving as the primary project explorer.

### Q11: Can SourceEditor/CodeMirror be reused?
Yes. `CodeEditor.tsx` provides an excellent CodeMirror 6 setup that can be ported directly to display the generated HTML/CSS of the current `ProjectRevision`.

### Q12: How should Code edits become ProjectRevisions?
Code edits should be debounced and committed via `ProjectOperation.update_source` or `update_element_source`, triggering a CAS revision increment and regenerating the staged preview.

### Q13: Should registry blocks be forked into project-local source before user code editing?
Yes. If a user edits the raw code of a catalog block instance, it must be forked into a project-owned custom component so the shared global registry definition remains untouched.

### Q14: How does HyperFrames map visual elements to source code?
Via unique `data-hf-id` attributes placed on elements in the template. An AST locator maps the ID to exact character offset ranges in the HTML file.

### Q15: Can Preview selection reveal the related Code source?
Yes. Selecting an element sends its `data-hf-id`, which dispatches a transaction in CodeMirror to highlight and scroll the corresponding line into view.

### Q16: Can Code selection reveal Timeline/Layers?
Yes. Moving the cursor inside an element's HTML block identifies the enclosing `data-hf-id` and triggers selection in the Timeline and Layers stack.

### Q17: How do Layers, Timeline, Inspector, Code and Preview share identity?
Through a single stable identifier: `element.id` (rendered as `data-hf-id="hf-..."` in preview DOM and code AST).

### Q18: How are Variables implemented?
Declared in template manifests or `project.metadata.variables`, rendered as dynamic input forms, and injected into the `<hyper-player>` execution context at runtime.

### Q19: How are keyframes implemented?
Modeled as timestamped property values attached to an element, rendered as diamonds on timeline tracks, and mapped to GSAP tween offsets.

### Q20: How are GSAP animations represented?
Authored as GSAP timeline calls (`tl.to(...)`) bound to the player's playhead time via `tl.seek(currentTime)`.

### Q21: How do nested compositions work?
Self-contained HTML compositions embedded as child elements with independent timeline runtimes, navigable via breadcrumbs.

### Q22: What should become a first-class ViralMint Project Element?
Any independent audiovisual or composition object (Clip, Audio, Text, Shape, Catalog Block, Nested Composition).

### Q23: Which HyperFrames state should NOT be copied into ProjectRevision?
Transient UI state: playhead position, zoom level, scroll offset, panel collapse states, active tab, hover states, and audio volume slider settings.

### Q24: Which components can be reused directly?
The 196 Registry blocks, `ThumbnailTiles.tsx`, `AudioMeterStrip.tsx`, and icon assets.

### Q25: Which components require adapters?
`Timeline.tsx`, `TimelineClip.tsx`, `TimelineClipDiamonds.tsx`, `LayersPanel.tsx`, `InspectorPanel.tsx`, and `CodeEditor.tsx` (adapted to use `ProjectOperations`).

### Q26: Which features should be reimplemented using HyperFrames only as reference?
The docking/split layout (keep ViralMint's cleaner Tailwind layout) and canvas transform gizmos.

### Q27: Which original features should not be brought into ViralMint at all?
`packages/studio-server` (Fastify file server) and `sourcePatcher.ts` (raw disk regex patcher).

### Q28: What important HyperFrames editor features did we not know about before this audit?
1. The full **196-block registry** covering typography, charts, and lower-thirds.
2. The client-side PCM audio waveform extraction using native Web Audio API.
3. The `@tanstack/react-virtual` timeline virtualization engine supporting hundreds of layers at 60 FPS.
4. The 4-way selection synchronization linking Preview, Timeline, Inspector, and CodeMirror.

### Q29: What is the safest implementation order?
1. Ingest 196 Catalog blocks.
2. Port virtualized Timeline & Keyframe diamonds.
3. Port Layers & Variables panels.
4. Embed CodeMirror with selection sync.
5. Expose catalog and keyframe tools to Main Agent.

### Q30: What is the smallest next implementation slice that materially improves the editor without destabilizing the current Creation foundation?
**Ingesting the 196 Registry Blocks and replacing the 4 hardcoded cards in `StudioResourcePanel.jsx` with a searchable, categorized Catalog.** This immediately expands ViralMint's creative capability by 50x with zero risk to the backend revision pipeline.
