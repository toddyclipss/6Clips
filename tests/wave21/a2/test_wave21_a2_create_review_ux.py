"""
Wave 21 Agent 2: Comprehensive Test Suite for Minimal Create/Review Motion UX,
Single Player, Native Motion Adapter, and Real WebSocket Flow.
"""

import json
import subprocess
import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIR = REPO_ROOT / "frontend"
ADAPTER_PATH = FRONTEND_DIR / "src" / "utils" / "nativeMotionAdapter.js"
LAYOUT_PATH = FRONTEND_DIR / "src" / "components" / "Layout.jsx"
APP_PATH = FRONTEND_DIR / "src" / "App.jsx"
MOTION_PAGE_PATH = FRONTEND_DIR / "src" / "pages" / "MotionGraphics.jsx"
TOOLBAR_PATH = FRONTEND_DIR / "src" / "components" / "motion" / "StudioToolbar.jsx"
PREVIEW_STAGE_PATH = FRONTEND_DIR / "src" / "components" / "motion" / "StudioPreviewStage.jsx"
REVIEW_PANEL_PATH = FRONTEND_DIR / "src" / "components" / "motion" / "MotionReviewPanel.jsx"
WS_HOOK_PATH = FRONTEND_DIR / "src" / "hooks" / "useWebSocket.js"
APP_STORE_PATH = FRONTEND_DIR / "src" / "store" / "appStore.js"
RESOURCE_PANEL_PATH = FRONTEND_DIR / "src" / "components" / "motion" / "StudioResourcePanel.jsx"


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
        text=True,
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
            invalidTrack: Boolean(adapter.validateTrackDrop({ type: 'video' }, 'unknown_track').valid),
            lockedTrack: Boolean(adapter.validateTrackDrop({ type: 'video' }, { type: 'video', locked: true }).valid)
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
        assert results["lockedTrack"] is False

    def test_normalize_native_motion_v1_operators(self):
        """Verifies composition operators are canonicalized into standard player tracks."""
        code = """
        const project = {
            id: 'proj_native_1',
            document: {
                spec_version: 'native_motion_v1',
                aspect_ratio: '9:16',
                duration_seconds: 12.0,
                composition: {
                    operators: [
                        { id: 'op1', operator: 'kinetic_title', duration: 4.0, text: 'Hello OAAS' },
                        { id: 'op2', operator: 'audio', duration: 12.0, src: '/audio/bg.mp3' },
                        { id: 'op3', operator: 'caption', duration: 3.5, text: 'Subtitled Speech' },
                        { id: 'op4', operator: 'filter', duration: 12.0 }
                    ]
                }
            }
        };
        const normalized = adapter.normalizeProjectForPlayer(project);
        console.log(JSON.stringify({
            isNative: normalized.isNativeMotion,
            trackCount: normalized.tracks.length,
            duration: normalized.duration,
            aspect: normalized.aspectRatio,
            videoClips: (normalized.tracks.find(t => t.type === 'video') || {}).clips?.length,
            audioClips: (normalized.tracks.find(t => t.type === 'audio') || {}).clips?.length,
            captionClips: (normalized.tracks.find(t => t.type === 'captions') || {}).clips?.length,
            effectClips: (normalized.tracks.find(t => t.type === 'effects') || {}).clips?.length
        }));
        """
        out = json.loads(run_node_adapter(code))
        assert out["isNative"] is True
        assert out["trackCount"] == 5
        assert out["duration"] == 12.0
        assert out["aspect"] == "9:16"
        assert out["videoClips"] == 1
        assert out["audioClips"] == 1
        assert out["captionClips"] == 1
        assert out["effectClips"] == 1

    def test_normalize_native_motion_scenes_and_captions(self):
        """Verifies NativeMotionSpecContract (scenes & captions) unpacks into canonical player tracks."""
        code = """
        const project = {
            id: 'proj_scenes_1',
            document: {
                spec_version: 'native_motion_v1',
                title: 'Architecture Trends',
                aspect_ratio: '9:16',
                target_duration_sec: 15.0,
                scenes: [
                    {
                        scene_number: 1,
                        timecode_start: 0.0,
                        timecode_end: 5.0,
                        visual_description: 'Bold title hook',
                        elements: [
                            { element_id: 'el_title_1', element_type: 'kinetic_title', start_time: 0.0, duration: 5.0, properties: { title: 'Modern Arch' } },
                            { element_id: 'el_audio_1', element_type: 'voiceover', start_time: 0.0, duration: 5.0 }
                        ]
                    },
                    {
                        scene_number: 2,
                        timecode_start: 5.0,
                        timecode_end: 15.0,
                        visual_description: 'Kinetic showcase',
                        elements: [
                            { element_id: 'el_bg_2', element_type: 'shape', start_time: 0.0, duration: 10.0 }
                        ]
                    }
                ],
                captions: [
                    {
                        start_time: 0.5,
                        end_time: 4.5,
                        text: 'Welcome to the future of architecture',
                        words: [
                            { word: 'Welcome', start: 0.5, end: 1.0 },
                            { word: 'to', start: 1.0, end: 1.2 },
                            { word: 'the', start: 1.2, end: 1.4 },
                            { word: 'future', start: 1.4, end: 2.2 }
                        ]
                    }
                ]
            }
        };
        const normalized = adapter.normalizeProjectForPlayer(project);
        console.log(JSON.stringify({
            isNative: normalized.isNativeMotion,
            trackCount: normalized.tracks.length,
            duration: normalized.duration,
            aspect: normalized.aspectRatio,
            videoClips: (normalized.tracks.find(t => t.type === 'video') || {}).clips?.length,
            audioClips: (normalized.tracks.find(t => t.type === 'audio') || {}).clips?.length,
            captionClips: (normalized.tracks.find(t => t.type === 'captions') || {}).clips?.length
        }));
        """
        out = json.loads(run_node_adapter(code))
        assert out["isNative"] is True
        assert out["trackCount"] == 5
        assert out["duration"] == 15.0
        assert out["aspect"] == "9:16"
        assert out["videoClips"] == 2  # el_title_1 + el_bg_2
        assert out["audioClips"] == 1  # el_audio_1
        assert out["captionClips"] == 1  # doc.captions[0]


class TestMinimalOAASUIContracts:
    """Verifies structural invariants, accessibility, and stage contracts."""

    def test_sidebar_five_destinations_order(self):
        """Verifies Layout.jsx strictly renders the 5 primary destinations in exact order."""
        content = LAYOUT_PATH.read_text(encoding="utf-8")
        assert 'to: "/motion"' in content
        assert 'label: "Motion Graphics"' in content
        assert 'to: "/trends"' in content
        assert 'label: "Trends"' in content
        assert 'to: "/channels"' in content
        assert 'label: "My Channel"' in content
        assert 'to: "/videos"' in content
        assert 'label: "Library"' in content
        assert 'to: "/messaging"' in content
        assert 'label: "Messages"' in content

        # Check relative position in navItems array
        idx_motion = content.find('label: "Motion Graphics"')
        idx_trends = content.find('label: "Trends"')
        idx_channel = content.find('label: "My Channel"')
        idx_library = content.find('label: "Library"')
        idx_messaging = content.find('label: "Messages"')

        assert -1 < idx_motion < idx_trends < idx_channel < idx_library < idx_messaging, \
            "Sidebar navigation entries are not in the mandatory order"

        # Settings must be in bottom secondary list
        idx_bottom = content.find("const bottomItems")
        idx_settings = content.find('label: "Settings"')
        assert idx_bottom < idx_settings, "Settings must be rendered in secondary bottom items"

    def test_motion_graphics_stages_and_advanced_editing(self):
        """Verifies StudioToolbar renders strictly Create and Review stages, plus unobtrusive Advanced Editing."""
        content = TOOLBAR_PATH.read_text(encoding="utf-8")

        assert 'data-testid={`stage-tab-${lvl.id}`}' in content or 'stage-tab-' in content
        assert '{ id: "create", label: "Create" }' in content
        assert '{ id: "review", label: "Review" }' in content
        assert 'stage-tab-refine' not in content, "Refine must not exist as a primary tab"
        assert '{ id: "refine"' not in content, "Refine must not exist in stage list"

        # Aspect switcher strictly 9:16 and 16:9
        assert 'data-testid="aspect-ratio-btn-9-16"' in content
        assert 'data-testid="aspect-ratio-btn-16-9"' in content

        # Advanced Editing toggle button present
        assert 'data-testid="studio-toolbar-advanced-editing-btn"' in content

    def test_catalog_and_template_picker_eliminated(self):
        """Verifies StudioResourcePanel has zero catalog cards or block template pickers."""
        content = RESOURCE_PANEL_PATH.read_text(encoding="utf-8")

        # Strip comments to inspect code paths
        code_lines = [line for line in content.splitlines() if not line.strip().startswith(("//", "*", "/*"))]
        code_only = "\n".join(code_lines)

        assert "196" not in code_only
        assert "catalogInventory" not in code_only
        assert "Ask AI to insert block in chat" not in content
        assert "Add Block" not in content

        # Verify clean two-tab panel: Media Assets and Trends Sources
        assert "Media Assets" in content
        assert "Sources" in content or "Trends" in content

    def test_authentic_job_status_and_review_panel(self):
        """Verifies StudioPreviewStage displays authentic activeJob step without fake percentages, and ReviewPanel has honest publication status."""
        stage_content = PREVIEW_STAGE_PATH.read_text(encoding="utf-8")

        # Job status badge
        assert 'data-testid="studio-stage-job-status"' in stage_content
        assert 'activeJob.step || activeJob.message || "composing"' in stage_content
        assert "35%" not in stage_content and "78%" not in stage_content

        # Review Panel
        review_content = REVIEW_PANEL_PATH.read_text(encoding="utf-8")
        assert 'data-testid="review-deliverables-count"' in review_content
        assert 'data-testid="review-correction-guidance"' in review_content
        assert 'data-testid="review-publishing-status"' in review_content
        assert "NOT_CONNECTED / PENDING_CREDENTIALS" in review_content
        assert "editorial confirmation" in review_content

    def test_captions_overlay_in_preview_stage(self):
        """Verifies StudioPreviewStage includes professional captions overlay with word highlighting."""
        stage_content = PREVIEW_STAGE_PATH.read_text(encoding="utf-8")
        assert "CaptionsOverlay" in stage_content
        assert 'data-testid="studio-caption-overlay"' in stage_content
        assert "#facc15" in stage_content or "#ffd60a" in stage_content
        assert "activeCaptions" in stage_content

    def test_use_websocket_oaas_outcome_and_connection_handling(self):
        """Verifies useWebSocket handles _connection_state and oaas_outcome_update."""
        ws_content = WS_HOOK_PATH.read_text(encoding="utf-8")
        assert 'ws.on("_connection_state"' in ws_content
        assert 'ws.on("oaas_outcome_update"' in ws_content
        assert 'ws.on("project_created"' in ws_content
        assert "setWsConnected" in ws_content
        assert "setLatestOutcome" in ws_content
        assert "BLOCKED_RIGHTS" in ws_content
        assert "PENDING_CREDENTIALS" in ws_content

    def test_motion_graphics_outcome_synchronization(self):
        """Verifies MotionGraphics page subscribes to latestOutcome and attaches projects & Review mode."""
        motion_content = MOTION_PAGE_PATH.read_text(encoding="utf-8")
        assert "latestOutcome" in motion_content
        assert "deliverable_url" in motion_content
        assert 'setWorkspaceMode("review")' in motion_content
