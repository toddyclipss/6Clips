# AGENT B: Integration Readiness Specification (`Production V1`)

**Agent:** AGENTE B (Exclusive Owner: Audiovisual Data Plane & Motion Review Experience)  
**Date:** 2026-10-13  
**Working Branch:** `agent-b` (Base commit: `f757754d91459cb71684619d1c0af171bdf0a6b9`)  
**Production DB Baseline Hash (SHA-256):** `A4DB2C5867F8B85FE2B35B383C9BBD3719DA5EE29DB7C4F9C68F9463DC48CE9E` (Verified Unchanged)  
**Readiness Gate:** `AGENT_B_READY_FOR_INTEGRATION: YES`

---

## 1. Executive Summary & Readiness Gate

All audiovisual data plane capabilities, physical media inspection, multi-clip narrative highlight selection, 9:16 vertical reframing, CAS project revision registration, and the Motion Review experience (`/motion`) are fully implemented, verified, and test-covered.

The live application router is mounted in `backend/main.py`. The standalone test suite executes 14 unit and integration tests across 3 dedicated files with a 100% pass rate.

Agent A is authorized to proceed with integration work in its isolated worktree.

---

## 2. Import & Initialization Specification

### 2.1 Python Service Import
```python
from backend.media_pipeline.producer_adapter import MediaProducerPort, get_media_producer
from backend.media_pipeline.models import (
    ProductionRequestV1,
    ProductionReportV1,
    SourceAssetV1,
    OutputSpecV1,
    DurationPolicy,
    BatchStatus,
    OutputState,
)
```

### 2.2 Initialization & Configuration
- **Singleton Producer:** `producer = get_media_producer()`
- **Custom Isolated Producer (e.g. for testing):**  
  `producer = MediaProducerPort(storage_dir=Path("/custom/storage/root"))`
- **Default Storage Location:** `DATA_DIR / "media_production"` (configurable via `backend.config.DATA_DIR`).
- **Worker Lifecycle & Durability:**
  - Jobs execute asynchronously via Python `asyncio.create_task()`.
  - Durability is currently in-memory (`self._jobs`). Process death/restart clears active job reports.
  - Idempotency is supported via request SHA-256 fingerprinting: identical requests return the existing `job_id` with `"idempotent_replay": True`.

### 2.3 Live FastAPI Router Mounting
The router is registered in `backend/main.py` before `media.router`:
```python
from backend.media_pipeline.api_router import router as media_production_router
app.include_router(media_production_router)
```
Live routes available:
- `POST /api/media/production/batch`: Submit a batch (accepts JSON request).
- `GET /api/media/production/batch/{job_id}`: Poll batch progress report.
- `POST /api/media/production/batch/{job_id}/cancel`: Cancel an active job.
- `GET /api/media/production/artifacts/{artifact_id}/stream`: Stream MP4 artifact with HTTP 206 Partial Content support.

---

## 3. Logical Contract Shapes & Type Compatibility

The adapter natively accepts either Pydantic `ProductionRequestV1` models or standard Python `dict` structures.

### 3.1 ProductionRequestV1 Specification
```json
{
  "schema_version": "production.v1",
  "run_id": "run_orchestration_101",
  "contract_id": "contract_6clips_v1",
  "contract_version": "1.0.0",
  "project_id": "proj_fortnite_gameplay",
  "user_id": "local",
  "source_assets": [
    {
      "asset_id": "asset_source_01",
      "editorial_role": "primary_footage",
      "permitted_uses": ["clip_extraction", "motion_review"],
      "acquisition_route": "authorized_fixture",
      "content_hash": "A3F8...",
      "local_path": "C:/path/to/source.mp4"
    }
  ],
  "outputs": [
    {
      "output_id": "clip_hook_1",
      "aspect_ratio": "9:16",
      "seconds": 60.0,
      "duration_policy": "TARGET",
      "tolerance_seconds": 3.0,
      "language": "en"
    },
    {
      "output_id": "clip_mid_2",
      "aspect_ratio": "9:16",
      "seconds": 60.0,
      "duration_policy": "TARGET",
      "tolerance_seconds": 3.0,
      "language": "en"
    },
    {
      "output_id": "clip_climax_3",
      "aspect_ratio": "9:16",
      "seconds": 60.0,
      "duration_policy": "TARGET",
      "tolerance_seconds": 3.0,
      "language": "en"
    }
  ],
  "execution_limits": {
    "max_attempts": 3,
    "stop_policy": "abort_on_rights_blocker"
  }
}
```

### 3.2 Duration Policy Compatibility (Agent A `TARGET` vs `EXACT` vs `MAX`)
- **`DurationPolicy.TARGET` (Default):** Accepts duration within $\pm (\text{tolerance\_seconds} + 0.8\text{s})$. Agent A using `TARGET` is supported out-of-the-box.
- **`DurationPolicy.EXACT`:** Enforces precise duration matching within $\pm 0.8\text{s}$.
- **`DurationPolicy.MAX`:** Guarantees duration does not exceed requested seconds $+ 0.5\text{s}$.

### 3.3 ProductionReportV1 Response Structure
```json
{
  "schema_version": "production.v1",
  "job_id": "job_prod_37fa128bc901",
  "run_id": "run_orchestration_101",
  "contract_version": "1.0.0",
  "status": "COMPLETE",
  "outputs": [
    {
      "output_id": "clip_hook_1",
      "project_revision_id": "1",
      "artifact_id": "artifact_clip_hook_1_e41b8a92",
      "snapshot_manifest_ref": "manifest://artifact_clip_hook_1_e41b8a92",
      "media_probe": {
        "width": 1080,
        "height": 1920,
        "duration_seconds": 59.8,
        "video_codec": "h264",
        "audio_codec": "aac",
        "fps": 30.0,
        "audio_channels": 2,
        "sample_rate": 48000,
        "content_hash": "D41D...",
        "is_silent": false,
        "is_black": false
      },
      "source_ranges": [
        {
          "asset_id": "asset_source_01",
          "start_seconds": 0.0,
          "end_seconds": 60.0,
          "duration_seconds": 60.0,
          "editorial_reason": "Hook & Early Engagement",
          "relevance_score": 9.0
        }
      ],
      "checks": {
        "technical": "PASS",
        "contract": "PASS",
        "editorial": "NOT_ASSESSED"
      },
      "preview_ref": "/api/media/production/artifacts/artifact_clip_hook_1_e41b8a92/stream",
      "warnings": [
        "Center crop 9:16 applied: verify HUD and reticle visibility in Motion Review."
      ],
      "state": "SUCCEEDED"
    }
  ],
  "blockers": [],
  "evidence_refs": [
    "artifact:artifact_clip_hook_1_e41b8a92"
  ],
  "step_events": [
    {
      "step_name": "render_output_clip_hook_1",
      "status": "succeeded",
      "timestamp": "2026-10-13T12:00:00Z",
      "detail": "Render complete"
    }
  ]
}
```

---

## 4. Status Truth Table & Orchestrator Presentation

| Batch Status | Output Checks (`tech` / `contract` / `editorial`) | What Orchestrator May Truthfully Display | Prohibited Claims |
|---|---|---|---|
| `RUNNING` | `NOT_RUN` / `NOT_RUN` / `NOT_ASSESSED` | "Rendering clips in background... (X of Y rendered)" | Never display "Clips ready" or render thumbnails. |
| `COMPLETE` | `PASS` / `PASS` / `NOT_ASSESSED` | "Clips rendered successfully. Ready for Motion Review." | Never claim "Creative approval complete" or publish automatically. |
| `PARTIAL` | Mixed (`PASS` / `FAIL`) | "X of Y clips rendered. Clip Z failed: [Reason]. Open Review to inspect valid clips." | Never claim total success or hide failed output. |
| `BLOCKED` | Empty or `FAIL` | "Media pipeline blocked: [Blocker Code] - [Reason]. Next action: [Next Action]." | Never show empty success state or retry without addressing blocker. |
| `CANCELLED` | `CANCELLED` | "Batch cancelled by user. Committed outputs: [IDs]." | Never display cancelled jobs as failures. |

---

## 5. Verification & Test Evidence

Total: **14 unit, integration, and E2E tests passing 100%**:

```
tests/test_media_production_pipeline.py ........                         [ 57%]
tests/test_motion_review_experience.py ...                               [ 78%]
tests/test_preview_render_parity_media.py ...                            [100%]
============================== 14 passed in 63.93s ==============================
```

### Coverage Matrix:
1. **Physical Byte Inspection:** Probes container, H.264 video, AAC audio, volume, SHA-256 (`test_physical_media_byte_inspection`).
2. **Negative Provenance Gating:** Unpermitted route or missing uses returns `BLOCKED` with `UNPERMITTED_ACQUISITION_ROUTE` (`test_provenance_and_rights_negative_gate`).
3. **Short Source Duration Guard:** Source shorter than required duration cleanly returns `INSUFFICIENT_SOURCE_DURATION` without loops or fillers (`test_three_segment_selection_and_duration_guard`).
4. **Three Distinct Outputs:** Renders 3 distinct MP4 files with non-overlapping source ranges and distinct SHA-256 hashes (`test_full_batch_production_and_independent_outputs`).
5. **Fault Isolation:** Simulated failure in clip 3 leaves clips 1 and 2 intact with aggregate status `PARTIAL` (`test_fault_tolerance_partial_failure`).
6. **Duration Policy Verification:** Tests `DurationPolicy.TARGET` with tolerance and `DurationPolicy.MAX` (`test_duration_policy_target_and_max_semantics`).
7. **Idempotency & Cancellation:** Repeated submission returns cached job; cancellation marks status `CANCELLED` (`test_idempotency_and_cancellation`).
8. **Live FastAPI TestClient Endpoint:** Verifies `/api/media/production/batch` and polling on live `backend.main.app` with raw dictionary payloads (`test_fastapi_endpoint_and_dict_payload`).
9. **HTTP 206 Range Streaming:** Verifies partial byte range requests without exposing internal `file://` paths (`test_preview_endpoint_http_range_support`).
10. **Motion Review UI Isolation:** 3 output cards, independent approval toggles, timeline refine jump (`tests/test_motion_review_experience.py`).

---

## 6. Heuristic Limitations & Editorial Boundaries

To maintain technical honesty:
- **Reframing:** The 16:9 to 9:16 reframe uses `scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920`. This is a centered crop, not an AI object tracker or adaptive facecam detector. The output warning flags this for human inspection.
- **Highlight Selection:** Segmentation divides footage into narrative zones (Hook, Mid-Game Action, Climax) using temporal spacing. It does not claim semantic gameplay comprehension or machine virality scoring.
- **Captions:** Whisper provides initial ASR timestamps. Manual edits made in the timeline override automatic transcriptions.

---

## 7. Integration Request for AGENTE A (`INTEGRATION_REQUEST`)

Agent A should integrate the media pipeline in its orchestration layer as follows:

```python
from backend.media_pipeline.producer_adapter import get_media_producer

# 1. Obtain singleton producer
producer = get_media_producer()

# 2. Submit batch using ProductionRequestV1 or dict
submission = await producer.submit_batch({
    "run_id": run_id,
    "contract_id": "contract_6clips_v1",
    "project_id": project_id,
    "user_id": user_id,
    "source_assets": [
        {
            "asset_id": asset_id,
            "editorial_role": "primary_footage",
            "permitted_uses": ["clip_extraction", "motion_review"],
            "acquisition_route": "authorized_fixture",  # or "local_upload"
            "local_path": local_video_path,
        }
    ],
    "outputs": [
        {"output_id": f"clip_{i+1}", "aspect_ratio": "9:16", "seconds": 60.0, "duration_policy": "TARGET", "tolerance_seconds": 3.0}
        for i in range(3)
    ],
})

# 3. Poll batch report until terminal status
job_id = submission["job_id"]
report = producer.get_batch(job_id)

# 4. Navigate user to Motion Review when report.status in (COMPLETE, PARTIAL)
# Frontend URL: /motion?jobId={job_id}&mode=review
```
