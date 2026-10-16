"""
Wave 20 Agent 2: Test Suite for Minimal Motion Design OAAS UX.
Verifies all contract constraints, drop boundaries, typed adapter logic, and UI structural invariants.
"""

import json
import subprocess
import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIR = REPO_ROOT / "frontend"
ADAPTER_PATH = FRONTEND_DIR / "src" / "utils" / "nativeMotionAdapter.js"

def run_node_adapter(code_snippet: str):
    """Executes a short node snippet that imports nativeMotionAdapter.js."""
    adapter_file_uri = ADAPTER_PATH.as_uri()
    full_script = f"""
    import * as adapter from "{adapter_file_uri}";
    {code_snippet}
    """
    res = subprocess.run(
        ["node", "--input-type=module", "-e", full_script],
        capture_output=True,
        text=True
    )
    if res.returncode != 0:
        raise RuntimeError(f"Node execution failed: {res.stderr}\nCode:\n{full_script}")
    return res.stdout.strip()

class TestNativeMotionAdapter:
    """Tests the typed native_motion_v1 adapter and content-safe drop boundaries."""

    def test_adapter_exports_and_canonical_tracks(self):
        code = """
        console.log(JSON.stringify({
            version: adapter.NATIVE_MOTION_SCHEMA_VERSION,
            trackTypes: adapter.CANONICAL_TRACK_TYPES,
            hasIsNative: typeof adapter.isNativeMotionV1 === 'function',
            hasValidateDrop: typeof adapter.validateTrackDrop === 'function',
            hasNormalize: typeof adapter.normalizeProjectForPlayer === 'function'
        }));
        """
        out = json.loads(run_node_adapter(code))
        assert out["version"] == "native_motion_v1"
        assert out["trackTypes"] == ["video", "audio", "captions", "effects", "transitions"]
        assert out["hasIsNative"] is True
        assert out["hasValidateDrop"] is True
        assert out["hasNormalize"] is True

    def test_content_safe_drop_boundaries(self):
        """Verifies that cross-category drops are strictly rejected."""
        code = """
        const checks = {
            // Valid drops
            validVideo: Boolean(adapter.validateTrackDrop({ type: 'video' }, 'video').valid),
            validBroll: Boolean(adapter.validateTrackDrop({ type: 'broll' }, 'video').valid),
            validAudio: Boolean(adapter.validateTrackDrop({ type: 'audio' }, 'audio').valid),
            validVoiceover: Boolean(adapter.validateTrackDrop({ type: 'voiceover' }, 'audio').valid),
            validCaption: Boolean(adapter.validateTrackDrop({ type: 'caption' }, 'captions').valid),
            validText: Boolean(adapter.validateTrackDrop({ type: 'text' }, 'captions').valid),
            validEffect: Boolean(adapter.validateTrackDrop({ type: 'effect' }, 'effects').valid),
            validTransition: Boolean(adapter.validateTrackDrop({ type: 'transition' }, 'transitions').valid),
            
            // Illegal cross-category drops (must be false)
            captionToAudio: Boolean(adapter.validateTrackDrop({ type: 'caption' }, 'audio').valid),
            audioToCaptions: Boolean(adapter.validateTrackDrop({ type: 'audio' }, 'captions').valid),
            videoToAudio: Boolean(adapter.validateTrackDrop({ type: 'video' }, 'audio').valid),
            audioToVideo: Boolean(adapter.validateTrackDrop({ type: 'audio' }, 'video').valid),
            captionToVideo: Boolean(adapter.validateTrackDrop({ type: 'caption' }, 'video').valid),
            effectToCaptions: Boolean(adapter.validateTrackDrop({ type: 'effect' }, 'captions').valid),
            transitionToCaptions: Boolean(adapter.validateTrackDrop({ type: 'transition' }, 'captions').valid),
            invalidTrack: Boolean(adapter.validateTrackDrop({ type: 'video' }, 'unknown_track').valid)
        };
        console.log(JSON.stringify(checks));
        """
        results = json.loads(run_node_adapter(code))
        
        # Valid drops must pass
        assert results["validVideo"] is True
        assert results["validBroll"] is True
        assert results["validAudio"] is True
        assert results["validVoiceover"] is True
        assert results["validCaption"] is True
        assert results["validText"] is True
        assert results["validEffect"] is True
        assert results["validTransition"] is True

        # Content safety violations must fail
        assert results["captionToAudio"] is False
        assert results["audioToCaptions"] is False
        assert results["videoToAudio"] is False
        assert results["audioToVideo"] is False
        assert results["captionToVideo"] is False
        assert results["effectToCaptions"] is False
        assert results["transitionToCaptions"] is False
        assert results["invalidTrack"] is False

    def test_normalize_native_motion_v1_operators(self):
        """Verifies composition operators are canonicalized into standard player tracks."""
        code = """
        const spec = {
            schema_version: "native_motion_v1",
            duration: 15.0,
            aspect_ratio: "9:16",
            operators: [
                { id: "op_v1", type: "clip", start_time: 0, duration: 5.0, src: "/media/v1.mp4" },
                { id: "op_a1", type: "speech", start_time: 0, duration: 5.0, src: "/media/a1.mp3" },
                { id: "op_c1", type: "text", start_time: 0.5, duration: 3.0, text: "Hook Header" },
                { id: "op_e1", type: "effect", start_time: 2.0, duration: 1.0, effect_type: "zoom_blur" },
                { id: "op_t1", type: "transition", start_time: 4.5, duration: 0.5, transition_type: "whip_pan" }
            ]
        };
        const normalized = adapter.normalizeProjectForPlayer(spec);
        console.log(JSON.stringify(normalized));
        """
        data = json.loads(run_node_adapter(code))
        assert data["duration"] == 15.0
        assert data["aspect_ratio"] == "9:16"
        assert len(data["tracks"]) == 5
        
        track_map = {t["id"]: t for t in data["tracks"]}
        assert len(track_map["track-video"]["clips"]) == 1
        assert track_map["track-video"]["clips"][0]["src"] == "/media/v1.mp4"
        
        assert len(track_map["track-audio"]["clips"]) == 1
        assert track_map["track-audio"]["clips"][0]["src"] == "/media/a1.mp3"
        
        assert len(track_map["track-captions"]["clips"]) == 1
        assert track_map["track-captions"]["clips"][0]["text"] == "Hook Header"
        
        assert len(track_map["track-effects"]["clips"]) == 1
        assert len(track_map["track-transitions"]["clips"]) == 1

class TestMinimalOAASUIContracts:
    """Verifies UI structural invariants without requiring browser execution."""

    def test_sidebar_five_destinations_order(self):
        layout_file = FRONTEND_DIR / "src" / "components" / "Layout.jsx"
        content = layout_file.read_text(encoding="utf-8")
        
        order = ["Motion Graphics", "Trends", "My Channel", "Library", "Messages"]
        indices = [content.index(f'label: "{item}"') for item in order]
        assert indices == sorted(indices), "Sidebar destinations must strictly follow the 5-item order"

    def test_motion_graphics_stages_and_advanced_editing(self):
        toolbar_file = FRONTEND_DIR / "src" / "components" / "motion" / "StudioToolbar.jsx"
        content = toolbar_file.read_text(encoding="utf-8")

        # Refine is not in the primary stage switcher
        assert 'value="refine"' not in content
        assert '{ id: "refine"' not in content
        assert '{ id: "create"' in content
        assert '{ id: "review"' in content
        
        # Advanced Editing toggle exists
        assert 'data-testid="studio-toolbar-advanced-editing-btn"' in content

    def test_catalog_and_template_picker_eliminated(self):
        panel_file = FRONTEND_DIR / "src" / "components" / "motion" / "StudioResourcePanel.jsx"
        stage_file = FRONTEND_DIR / "src" / "components" / "motion" / "StudioPreviewStage.jsx"

        p_content = panel_file.read_text(encoding="utf-8")
        s_content = stage_file.read_text(encoding="utf-8")

        # No Catalog tab
        assert 'label="Catalog"' not in p_content
        assert 'Tab 2: Catalog' not in p_content
        assert "catalogInventory" not in p_content
        assert "Ask AI to insert block in chat" not in p_content

        # No Ghost preview frame in stage
        assert "studio-ghost-preview-stage" not in s_content
        assert "onProceedToRefine" not in s_content

    def test_authentic_job_status_and_review_panel(self):
        stage_file = FRONTEND_DIR / "src" / "components" / "motion" / "StudioPreviewStage.jsx"
        review_file = FRONTEND_DIR / "src" / "components" / "motion" / "MotionReviewPanel.jsx"

        s_content = stage_file.read_text(encoding="utf-8")
        r_content = review_file.read_text(encoding="utf-8")

        # Job status pill
        assert 'data-testid="studio-stage-job-status"' in s_content
        assert "activeJob.step || activeJob.message" in s_content

        # Review deliverables & correction hint & truthful publishing
        assert 'data-testid="review-deliverables-count"' in r_content
        assert 'data-testid="review-correction-guidance"' in r_content
        assert "NOT_CONNECTED / PENDING_CREDENTIALS" in r_content
