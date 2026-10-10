# Motion Sources, Assets, and HyperFrames Catalog Preview Audit

**Date:** 2026-10-10
**Target:** ViralMint `/motion` Refine Workspace (`StudioResourcePanel.jsx`, `StudioPreviewStage.jsx`, `RegistryAdapter.py`, `ProjectService.py`)
**Baseline Commit:** `c9619f507c71d52eff8ad7049fd053f4eb3dbb05`
**Evidence Base:** Live browser audit, DOM element inspection, database schema inspection (`scout_results`, `library_items`), and source code tracing.

---

## 1. Executive Summary & Diagnostic Findings

The visual media inspection within the ViralMint `/motion` Refine workspace currently suffers from a fundamental disconnect: **rich visual metadata is captured by backend ingestion and storage pipelines, but the user interface completely discards this data and renders generic placeholder icons**.

Specifically:
1. **Contextual Trends & Sources:** The backend database table `scout_results` captures and stores provider `thumbnail_url` (e.g., YouTube `https://i.ytimg.com/vi/<id>/hqdefault.jpg`), media duration, platform tags, and embed URLs. However, `StudioResourcePanel.jsx` drops `thumbnail_url` entirely and renders a static `<IconTrendingUp />`.
2. **Library Assets:** The library API (`/api/library/items`) returns computed `thumb_url` paths (e.g., `/api/videos/{id}/thumbnail?v=...`) and media metadata. However, `StudioResourcePanel.jsx` ignores `thumb_url` and renders an opaque black `44x44px` box with a hardcoded `<IconVideo />`.
3. **HyperFrames Catalog Blocks:** Catalog cards render solely text metadata (name, category, variable count, duration chip) with zero visual preview or thumbnail poster. In addition, `RegistryAdapter.list_catalog_items` contains a severe architectural performance bottleneck: it computes synchronous SHA-256 hashes of all disk files on every catalog list request, stalling the backend for 5–10 seconds.
4. **Player Preview Absence:** There is currently no hover preview capability. Users must blind-insert blocks into their canonical project timeline and trigger a compilation cycle just to see what an animation looks like.

---

## 2. Audit of Sources (Discovery & Trend Ingestion)

### 2.1 Backend Schema & Ingestion Evidence
In `backend/app/db/database.py` and `backend/app/services/scout_service.py`, discovery providers (YouTube, TikTok, Instagram, Web) populate the `scout_results` SQLite/PostgreSQL entity:

```sql
CREATE TABLE scout_results (
    id TEXT PRIMARY KEY,
    query TEXT,
    title TEXT,
    url TEXT,
    thumbnail_url TEXT,
    duration_seconds REAL,
    platform TEXT,
    virality_score REAL,
    metadata_json TEXT,
    created_at TIMESTAMP
);
```

Live database queries verify that real video records contain valid, publicly resolvable poster frames:
- YouTube: `https://i.ytimg.com/vi/75tja_RxKn4/hqdefault.jpg`
- Duration: `45.0` seconds
- Platform: `youtube`

### 2.2 Frontend Discard in `StudioResourcePanel.jsx`
In `frontend/src/components/motion/StudioResourcePanel.jsx` (Lines 272–282):
```jsx
<Stack direction="row" spacing={1} alignItems="center">
  <IconTrendingUp size={16} color="#8b5cf6" style={{ marginTop: 2 }} />
  <Box sx={{ flex: 1, minWidth: 0 }}>
    <Typography variant="caption" sx={{ fontWeight: 700, color: "text.primary" }}>
      {trend.title || trend.query}
    </Typography>
    <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.68rem" }}>
      Score: {trend.virality_score || trend.traffic || "High"} • {trend.platform || "Web"}
    </Typography>
  </Box>
...
```

The component accepts `trend.thumbnail_url` from the API response payload, but never passes it to an `<img />` or `backgroundImage` element. The user is presented with a wall of purple trend arrows (`artifacts/audit/resource_panel_sources.png`).

### 2.3 Required Discovery Source Preview Architecture
To show recognizable thumbnails without triggering heavy video downloads or privacy leaks:
1. **Image Thumbnail Element:** Replace `<IconTrendingUp />` with a `48x36px` 16:9 thumbnail preview container:
   - If `trend.thumbnail_url` is present: render `<Box component="img" src={trend.thumbnail_url} loading="lazy" referrerPolicy="no-referrer" />`.
   - `referrerPolicy="no-referrer"` prevents provider hotlink blocking on YouTube and TikTok CDNs.
   - Fallback: If `trend.thumbnail_url` fails or is null, render a fallback badge with the platform icon (`<IconBrandYoutube />`, `<IconBrandTiktok />`) over a slate-800 background.
2. **Metadata Overlay:** Render a duration badge (`0:45`) in the lower-right corner of the thumbnail.
3. **No Autoplay on Hover:** Avoid firing background video downloads or iframe embeds on hover in the Source list. Hover should display an expanded tooltip containing title, channel name, and platform engagement score.

---

## 3. Audit of Assets (Project & Local Media Library)

### 3.1 Backend Library API
The `/api/library/items` endpoint returns stored video, audio, and graphic assets:
```json
{
  "id": "asset-video-001",
  "filename": "stock_finance_bg.mp4",
  "media_type": "video",
  "duration": 12.4,
  "thumb_url": "/api/videos/asset-video-001/thumbnail?v=1",
  "status": "ready"
}
```

### 3.2 Frontend Omission in `StudioResourcePanel.jsx`
In `frontend/src/components/motion/StudioResourcePanel.jsx` (Lines 193–208):
```jsx
<Box
  sx={{
    width: 44,
    height: 44,
    borderRadius: 1,
    bgcolor: "#0f172a",
    color: "#ffffff",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
    flexShrink: 0,
  }}
>
  <IconVideo size={20} />
</Box>
```

Every single asset—regardless of type, duration, or whether a thumbnail exists—renders an identical solid black square with a white film camera icon (`artifacts/audit/resource_panel_assets.png`).

### 3.3 Required Media Asset Preview Architecture
1. **Type-Specific Thumbnail Renderers:**
   - **Video Assets:** Render `<Box component="img" src={asset.thumb_url} />`. When the thumbnail endpoint returns 404 or pending, display a video badge with a subtle pulsing skeleton.
   - **Image Assets:** Render the image thumbnail directly with `object-fit: cover`.
   - **Audio Assets:** Render a stylized waveform badge with duration overlay (`03:14`), distinct from video/image assets.
2. **Thumbnail Generation Pipeline:**
   - Ensure `POST /api/videos/upload` generates a low-resolution WebP poster frame at `1.0s` (`ffmpeg -ss 00:00:01 -i input.mp4 -vframes 1 -vf "scale=160:90:force_original_aspect_ratio=decrease" thumb.webp`).
   - Store `thumb_path` in SQLite `library_items` and serve via `/api/videos/{id}/thumbnail` with `Cache-Control: public, max-age=86400`.

---

## 4. Audit of HyperFrames Catalog Blocks

### 4.1 Backend Registry Listing Bottleneck
In `backend/app/adapters/registry_adapter.py`, `list_catalog_items()` traverses `C:\Users\toddy\Desktop\hyperframes\registry\blocks` or the local registry directory:
```python
def list_catalog_items(self) -> Dict[str, Any]:
    # Synchronously calculates SHA-256 hash for every file in every block directory!
    for block_dir in blocks_path.iterdir():
        ...
        block_hash = self._compute_directory_hash(block_dir)
```
On a production registry with 50+ blocks containing source TSX, asset files, and manifests, this synchronous hash computation blocks the single-threaded asyncio event loop for **5.8 to 9.2 seconds** per request.
- **Immediate Fix:** Cache the catalog list in memory with an `mtime` watch or pre-computed manifest (`catalog-manifest.json`). SHA-256 verification should occur strictly when freezing a block or creating an immutable `RegistrySnapshot`, never during simple UI browsing.

### 4.2 Frontend Catalog Cards
In `StudioResourcePanel.jsx` (Lines 343–374):
- Catalog cards are text-only cards (`artifacts/audit/resource_panel_catalog.png`).
- Variable counts and categories are displayed, but there is no thumbnail, aspect ratio indicator, or animation preview.
- Furthermore, `StudioResourcePanel.jsx` contains an array handling bug:
  ```javascript
  const items = Array.isArray(res.data) ? res.data : []
  ```
  Because the backend returns `{ "items": [...], "count": ... }`, `Array.isArray(res.data)` evaluates to `false` and catalog blocks fail to load unless normalized to `res.data.items || res.data`.

---

## 5. Architectural Specification: Non-Destructive "Hover to Preview"

### 5.1 The Product Requirement
When a creator hovers their cursor over a HyperFrames Catalog item:
1. The main Motion player stage temporarily displays the animation of that block.
2. **Zero Project Mutation:** No clip is appended to the timeline, no `ProjectRevision` is written, no undo/redo history is created, and no database record is altered.
3. The existing project composition time, playhead position, and track selections are fully preserved.
4. On `mouseleave` or hover cancellation, the player instantly restores the original project preview.
5. On explicit insertion (clicking "+" or drag-dropping onto the timeline), a canonical `ProjectRevision` operation is dispatched through `ProjectService`.

### 5.2 Architectural Architecture & Isolation
The authoritative player stage is managed by `StudioPreviewStage.jsx`, which hosts a sandboxed iframe (`allow-scripts`, origin `null`) communicating via `postMessage`.

Replacing the project bundle inside the active preview iframe during a brief hover introduces state corruption risks, playback desync, and memory overhead. Instead, we implement a **Layered Ghost Preview Architecture**:

```
+-------------------------------------------------------------+
| StudioPreviewStage Container                                |
|                                                             |
|  +-------------------------------------------------------+  |
|  | Authoritative Project Preview iframe                  |  |
|  | (Paused at current playhead, state fully preserved)   |  |
|  +-------------------------------------------------------+  |
|                                                             |
|  +-------------------------------------------------------+  |
|  | Ghost Hover Preview Overlay (Absolute, z-index: 10)   |  |
|  | - Mounted ONLY while hovering catalog card            |  |
|  | - Loads standalone /preview/block/{block_name}        |  |
|  | - Autoplays looped block animation                    |  |
|  | - Semi-transparent badge: "Previewing [Block Name]"   |  |
|  | - Press ESC or mouseleave to dismiss                  |  |
|  +-------------------------------------------------------+  |
|                                                             |
+-------------------------------------------------------------+
```

### 5.3 Step-by-Step Implementation Flow

1. **State Ownership (`StudioTimelineWorkspace.jsx` / `MotionGraphics.jsx`):**
   - Introduce transient state: `const [hoverPreviewBlock, setHoverPreviewBlock] = useState(null);`
   - Debounce hover entry with a **180ms delay** (`useDebounce` or `setTimeout`) to prevent thrashing when the user rapidly scrolls through the catalog.
2. **Hover Trigger (`StudioResourcePanel.jsx`):**
   - Card events:
     ```jsx
     onMouseEnter={() => handleCatalogHover(item)}
     onMouseLeave={() => handleCatalogHoverEnd()}
     ```
   - If the user moves away before 180ms expires, the timer is cleared and no preview is launched.
3. **Stage Display (`StudioPreviewStage.jsx`):**
   - When `hoverPreviewBlock` is active:
     - Pause the authoritative project audio/video player.
     - Mount the `GhostPreviewOverlay` iframe pointed at `/api/motion/blocks/${hoverPreviewBlock.name}/preview-bundle`.
     - The ghost preview iframe operates under an isolated sandbox (`sandbox="allow-scripts"`).
   - When `hoverPreviewBlock` is null:
     - Unmount the `GhostPreviewOverlay` iframe completely, releasing all GPU and memory contexts.
     - Unpause or retain the authoritative player at its preserved playhead position.
4. **Permanent Insertion:**
   - When the user clicks "+" or drags the block onto a timeline track:
     - Clear `hoverPreviewBlock`.
     - Invoke `onInsertBlock(item, targetTrackId, playheadTime)` which calls `ProjectService.apply_atomic_operation("INSERT_CLIP", ...)`.
     - Generates an immutable `ProjectRevision` and updates the canonical document.

---

## 6. Catalog Performance, Caching & Poster Generation

To prevent sluggish catalog browsing:

| Resource Layer | Implementation Requirement |
| :--- | :--- |
| **Manifest Caching** | Cache `list_catalog_items()` in `RegistryAdapter`. Rebuild cache only on file change or explicit refresh endpoint (`POST /api/registry/refresh`). |
| **Static Posters** | For each block in the registry, generate a `poster.webp` snapshot at `t = duration / 2`. Serve at `/api/motion/blocks/{name}/poster`. |
| **Catalog Card Poster** | In `StudioResourcePanel.jsx`, render a `60x40px` static poster in the catalog card. Only mount the dynamic player on hover. |
| **Network Throttling** | If a block requires large remote fonts or 3D assets, defer loading until the 180ms hover threshold is satisfied. |
| **Stale Cancellation** | Use an `AbortController` or token identifier so that if Block B is hovered before Block A finishes loading, Block A is aborted immediately. |

---

## 7. Implementation Roadmap & Acceptance Gates

- **Gate 1 (Sources & Assets Visual Restoration):**
  - Fix `StudioResourcePanel.jsx` to render `trend.thumbnail_url` with `referrerPolicy="no-referrer"` and duration badges.
  - Fix `StudioResourcePanel.jsx` to render `asset.thumb_url` for videos and images, with audio waveform badges for audio files.
  - Verify visually in live browser.
- **Gate 2 (Catalog Performance & Poster Rendering):**
  - Remove synchronous SHA-256 hashing from `RegistryAdapter.list_catalog_items()`.
  - Fix response payload unwrapping (`res.data.items || res.data`).
  - Render static poster thumbnails in catalog cards.
- **Gate 3 (Ghost Hover Preview Stage):**
  - Implement debounced (180ms) `hoverPreviewBlock` state in `MotionGraphics.jsx`.
  - Render `GhostPreviewOverlay` in `StudioPreviewStage.jsx`.
  - Verify that hovering a catalog card shows the animated preview in the main player without modifying `project.json`, without creating revisions, and that leaving the card restores the exact prior stage state.
