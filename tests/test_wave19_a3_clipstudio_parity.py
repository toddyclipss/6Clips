import asyncio
import json
from pathlib import Path
import pytest

from backend.clipstudio_native.adapter import clipstudio_native_adapter
from backend.clipstudio_native.models import (
    ClipRange,
    ClipStudioActionType,
    ExtractClipsParams,
    SuggestClipsParams,
)
from backend.core.exceptions import ProjectNotFoundError
from backend.database import AsyncSessionLocal, init_db
from backend.models.project import Project
from backend.services.project_service import ProjectService

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools" / "wave19_a3"
CSV_PATH = TOOLS_DIR / "clipstudio_legacy_vs_current.csv"
JSON_PATH = TOOLS_DIR / "clipstudio_legacy_vs_current.json"
LEDGER_PATH = TOOLS_DIR / "clipstudio_evidence_ledger.json"
READY_PATH = TOOLS_DIR / "READY.json"


def test_capability_inventory_census():
    """Verify that all 34 legacy Clip Studio capabilities are enumerated and disjoint."""
    assert CSV_PATH.exists(), f"CSV ledger missing at {CSV_PATH}"
    assert JSON_PATH.exists(), f"JSON ledger missing at {JSON_PATH}"

    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    meta = data.get("metadata", {})
    assert meta.get("total_capabilities") == 34
    assert meta.get("verified_capabilities") == 34
    assert meta.get("blocked_capabilities") == 0

    caps = data.get("capabilities", [])
    assert len(caps) == 34

    cap_names = {c["name"] for c in caps}
    assert len(cap_names) == 34, "Duplicate capability name detected in census"

    # Verify key workflows exist
    required_workflows = {
        "source_select",
        "source_preview",
        "speech_transcribe",
        "suggest_clips_ai",
        "bench_range_set",
        "bench_range_snap",
        "extract_clips_ai",
        "extract_clips_manual",
        "silence_remove",
        "reframe_vertical",
        "captions_burn",
        "virality_score_breakdown",
        "thumbnail_regenerate",
        "timeline_project_map",
        "project_reopen",
        "project_export_mp4",
    }
    assert required_workflows.issubset(cap_names)


def test_suggest_clips_contract():
    """Verify suggest_clips returns typed, scored, and bounded clip ranges."""
    async def _test():
        await init_db()
        params = SuggestClipsParams(
            source_id="mock_source_media.mp4",
            max_clips=4,
            min_duration=10,
            max_duration=30,
            target_platform="reels",
            genre="podcast",
            user_query="main argument",
        )
        ranges = await clipstudio_native_adapter.suggest_clips(params)
        assert len(ranges) == 4
        for r in ranges:
            assert isinstance(r, ClipRange)
            assert r.score is not None and 1.0 <= r.score <= 10.0
            assert r.hook_score is not None and 1.0 <= r.hook_score <= 10.0
            assert r.hook_type in ("question", "bold_claim", "story_opener", "surprising_stat", "visual_disruption")
            assert (r.end - r.start) >= 3.0
            assert "hook" in r.score_breakdown
            assert "flow" in r.score_breakdown

    asyncio.run(_test())


def test_extract_clips_to_project_cas_lifecycle():
    """Verify atomic CAS project revision lifecycle during clip extraction."""
    async def _test():
        await init_db()
        proj_id = f"test_proj_unit_{int(asyncio.get_event_loop().time() * 1000)}"
        async with AsyncSessionLocal() as db:
            p = Project(
                id=proj_id,
                name="Unit Test Project",
                user_id="local",
                revision=1,
                aspect_ratio="16:9",
                document_json=json.dumps({
                    "schema_version": 2,
                    "timeline": {"fps": 30, "duration_seconds": 0.0, "tracks": []},
                    "assets": [],
                    "bench_ranges": {},
                }),
            )
            db.add(p)
            await db.commit()

        params = ExtractClipsParams(
            source_id="dummy_source.mp4",
            mode="ai",
            max_clips=2,
            force_vertical=True,
            caption_style="viral",
        )
        res = await clipstudio_native_adapter.extract_clips_to_project(proj_id, params)
        assert res.status == "SUCCESS"
        assert res.base_revision == 1
        assert res.resulting_revision == 6

        # Verify Project document contents
        updated = await ProjectService.get_project(proj_id)
        assert updated.revision == 6
        doc = json.loads(updated.document_json)
        assert doc.get("aspect_ratio") == "9:16"

        # Verify tracks
        tracks = doc.get("timeline", {}).get("tracks", [])
        assert len(tracks) >= 2  # media track and captions track
        video_track = next((t for t in tracks if t.get("id") == "track_video_main"), None)
        assert video_track is not None
        assert len(video_track.get("clips", [])) == 1

        captions_track = next((t for t in tracks if t.get("id") == "track_captions"), None)
        assert captions_track is not None
        assert len(captions_track.get("clips", [])) >= 1

    asyncio.run(_test())


def test_reframe_and_burn_captions():
    """Verify reframing and captions mutation over project revision."""
    async def _test():
        await init_db()
        proj_id = f"test_proj_reframe_{int(asyncio.get_event_loop().time() * 1000)}"
        async with AsyncSessionLocal() as db:
            p = Project(
                id=proj_id,
                name="Reframe Test",
                user_id="local",
                revision=1,
                aspect_ratio="16:9",
                document_json=json.dumps({
                    "schema_version": 2,
                    "timeline": {"fps": 30, "duration_seconds": 10.0, "tracks": []},
                    "assets": [],
                    "bench_ranges": {},
                }),
            )
            db.add(p)
            await db.commit()

        # Reframe
        ref_res = await clipstudio_native_adapter.reframe_clip_project(proj_id, aspect_ratio="9:16")
        assert ref_res.status == "SUCCESS"
        assert ref_res.resulting_revision == 2

        # Burn captions
        caps = [
            {"start": 0.0, "end": 4.0, "text": "Testing native captions"},
            {"start": 4.0, "end": 8.0, "text": "High impact typography"},
        ]
        cap_res = await clipstudio_native_adapter.burn_captions_to_project(proj_id, caps, style="beast")
        assert cap_res.status == "SUCCESS"
        assert cap_res.resulting_revision == 3

    asyncio.run(_test())


def test_project_reopen_and_schema_version_2():
    """Verify reopening project ensures schema_version 2 and preserves all clips/tracks."""
    async def _test():
        await init_db()
        proj_id = f"test_proj_reopen_{int(asyncio.get_event_loop().time() * 1000)}"
        async with AsyncSessionLocal() as db:
            p = Project(
                id=proj_id,
                name="Reopen Integrity Test",
                user_id="local",
                revision=1,
                aspect_ratio="9:16",
                document_json=json.dumps({
                    "schema_version": 2,
                    "timeline": {
                        "fps": 30,
                        "duration_seconds": 12.0,
                        "tracks": [
                            {"id": "t1", "type": "video", "clips": [{"id": "c1", "start_seconds": 0.0, "duration_seconds": 12.0}]},
                        ],
                    },
                    "assets": [{"id": "a1", "name": "source.mp4"}],
                    "bench_ranges": {"a1": [{"start": 0.0, "end": 12.0, "label": "Full"}]},
                }),
            )
            db.add(p)
            await db.commit()

        reopen = await clipstudio_native_adapter.reopen_clip_project(proj_id)
        assert reopen["status"] == "VALID"
        assert reopen["schema_version"] == 2
        assert reopen["total_tracks"] == 1
        assert reopen["total_clips"] == 1
        assert reopen["bench_ranges_count"] == 1

    asyncio.run(_test())


def test_negative_validation_cases():
    """Verify validation boundaries and exception handling."""
    # Negative 1: ClipRange end <= start
    with pytest.raises(ValueError, match="must be greater than start"):
        ClipRange(start=10.0, end=5.0)

    # Negative 2: ClipRange duration < 3.0s
    with pytest.raises(ValueError, match="must be at least 3.0 seconds"):
        ClipRange(start=10.0, end=11.5)

    # Negative 3: Nonexistent project lookup
    async def _test_lookup():
        await init_db()
        await clipstudio_native_adapter.reopen_clip_project("non_existent_project_9999")

    with pytest.raises(ProjectNotFoundError):
        asyncio.run(_test_lookup())

def test_evidence_ledger_and_ready_marker():
    """Verify evidence ledger and ready marker structure and non-regression."""
    assert LEDGER_PATH.exists(), f"Ledger missing at {LEDGER_PATH}"
    ledger_data = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))

    meta = ledger_data.get("metadata", {})
    assert meta.get("wave") == 19
    assert meta.get("total_capabilities") == 34
    assert meta.get("verified_capabilities") == 34
    assert meta.get("blocked_capabilities") == 0

    deliverables = ledger_data.get("deliverables", [])
    assert len(deliverables) >= 3, "Expected at least 3 verified physical media deliverables"

    for d in deliverables:
        assert Path(d["video_path"]).exists()
        assert d["ffprobe_meta"].get("width") == 1080
        assert d["ffprobe_meta"].get("height") == 1920
        assert d["ffprobe_meta"].get("video_codec") == "h264"
        assert len(d["sha256"]) == 64

    # Verify READY.json
    assert READY_PATH.exists()
    ready_data = json.loads(READY_PATH.read_text(encoding="utf-8"))
    assert ready_data.get("status") == "READY_FOR_INTEGRATION_REVIEW"
    assert ready_data.get("base_sha") == "5103a363b9b8514a486ffe83ef289f47eb67a782"
    assert ready_data.get("verified_capabilities") == 34
