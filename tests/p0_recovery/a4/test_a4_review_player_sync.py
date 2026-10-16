"""
P0 Recovery Squad - Agent 4: Review UI, Single Artifact Player Sync, No Social Gate.
Comprehensive Unit and Component Acceptance Tests.
"""

import json
import subprocess
import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIR = REPO_ROOT / "frontend"
ADAPTER_PATH = FRONTEND_DIR / "src" / "utils" / "nativeMotionAdapter.js"
MOTION_PAGE_PATH = FRONTEND_DIR / "src" / "pages" / "MotionGraphics.jsx"
PREVIEW_STAGE_PATH = FRONTEND_DIR / "src" / "components" / "motion" / "StudioPreviewStage.jsx"
REVIEW_PANEL_PATH = FRONTEND_DIR / "src" / "components" / "motion" / "MotionReviewPanel.jsx"


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


class TestNativeMotionAdapterDurationSync:
    """Tests that nativeMotionAdapter does not impose hardcoded 15.00s fallback durations."""

    def test_respects_probe_duration(self):
        code = """
        const project = {
            id: 'proj_probe_test',
            media_probe: { duration_seconds: 8.0 },
            document: {
                spec_version: 'native_motion_v1',
                aspect_ratio: '9:16',
                duration_seconds: 12.0
            }
        };
        const normalized = adapter.normalizeProjectForPlayer(project);
        console.log(JSON.stringify({ duration: normalized.duration }));
        """
        out = json.loads(run_node_adapter(code))
        assert out["duration"] == 8.0

    def test_respects_document_duration_when_no_probe(self):
        code = """
        const project = {
            id: 'proj_doc_test',
            document: {
                spec_version: 'native_motion_v1',
                aspect_ratio: '9:16',
                duration_seconds: 9.8
            }
        };
        const normalized = adapter.normalizeProjectForPlayer(project);
        console.log(JSON.stringify({ duration: normalized.duration }));
        """
        out = json.loads(run_node_adapter(code))
        assert out["duration"] == 9.8

    def test_defaults_to_zero_not_fifteen(self):
        code = """
        const project = {
            id: 'proj_empty',
            document: {}
        };
        const normalized = adapter.normalizeProjectForPlayer(project);
        console.log(JSON.stringify({ duration: normalized.duration }));
        """
        out = json.loads(run_node_adapter(code))
        assert out["duration"] == 0


class TestMotionReviewPanelContracts:
    """Verifies MotionReviewPanel handles publication gate and duration accurately."""

    def test_no_hardcoded_social_gate_for_edit_only(self):
        panel_src = REVIEW_PANEL_PATH.read_text(encoding="utf-8")

        # Must guard review-publishing-status with isExplicitPublicationRequested
        assert "isExplicitPublicationRequested" in panel_src
        assert "NOT_CONNECTED / PENDING_CREDENTIALS" not in panel_src
        assert "isExplicitPublicationRequested = (clip)" in panel_src
        assert "outputs.some(isExplicitPublicationRequested)" in panel_src

    def test_review_panel_uses_probe_duration(self):
        panel_src = REVIEW_PANEL_PATH.read_text(encoding="utf-8")
        assert "probe.duration_seconds ?? out.duration_seconds" in panel_src
        assert "15.00s" not in panel_src
        assert "duration_seconds ?? 15" not in panel_src
        assert "duration ?? 15" not in panel_src

    def test_review_panel_keys_by_unique_artifact_id(self):
        panel_src = REVIEW_PANEL_PATH.read_text(encoding="utf-8")
        assert "out.artifact_id || out.sha256 || out.output_id" in panel_src


class TestStudioPreviewStageContracts:
    """Verifies StudioPreviewStage single player and video element synchronization."""

    def test_preview_stage_no_15s_default_prop(self):
        stage_src = PREVIEW_STAGE_PATH.read_text(encoding="utf-8")
        assert "duration = 15" not in stage_src
        assert "duration = 0" in stage_src

    def test_preview_stage_syncs_with_video_metadata(self):
        stage_src = PREVIEW_STAGE_PATH.read_text(encoding="utf-8")
        assert "onLoadedMetadata=" in stage_src
        assert "setMediaDuration(realDur)" in stage_src
        assert "onDurationChange(realDur)" in stage_src

    def test_preview_stage_remounts_on_artifact_change(self):
        stage_src = PREVIEW_STAGE_PATH.read_text(encoding="utf-8")
        # Video keying ensures clean DOM remount when artifact changes
        assert "key={renderedVideo.artifact_id || renderedVideo.sha256 || renderedVideo.output_id" in stage_src

    def test_preview_stage_resets_time_on_video_change(self):
        stage_src = PREVIEW_STAGE_PATH.read_text(encoding="utf-8")
        assert "videoRef.current.currentTime = 0" in stage_src


class TestMotionGraphicsOrchestrationContracts:
    """Verifies MotionGraphics.jsx handles outcome sync, failures, and export URL."""

    def test_sync_outcome_invalidates_stale_deliverable_on_failure(self):
        mg_src = MOTION_PAGE_PATH.read_text(encoding="utf-8")
        assert 'FAILED_TERMINAL' in mg_src
        assert 'BLOCKED_UNAUTHORIZED_BACKGROUND_AI' in mg_src
        # When terminal failure occurs, renderedVideo and productionBatch must be cleared
        assert 'setRenderedVideo(null)' in mg_src
        assert 'setProductionBatch(null)' in mg_src

    def test_motion_graphics_passes_real_duration_and_on_duration_change(self):
        mg_src = MOTION_PAGE_PATH.read_text(encoding="utf-8")
        assert "onDurationChange=" in mg_src
        # StudioPreviewStage duration prop does not fall back to 15
        assert "duration_seconds || 15" not in mg_src

    def test_export_output_uses_download_url_and_canonical_id(self):
        mg_src = MOTION_PAGE_PATH.read_text(encoding="utf-8")
        assert "const url = output.download_url || output.preview_ref || output.video_url" in mg_src
        assert "${output.output_id || output.artifact_id || \"clip\"}.mp4" in mg_src

    def test_source_vs_output_duration_lineage_preserves_probe_duration(self):
        """Verifies that when source duration is 19.0s and output probe duration is 8.00s, output probe is preserved."""
        code = """
        const projectWithSource = {
            id: 'proj_source_edit',
            source_video_duration: 19.0,
            media_probe: { duration_seconds: 8.0, width: 1080, height: 1920 },
            document: {
                spec_version: 'native_motion_v1',
                aspect_ratio: '9:16',
                duration_seconds: 8.0
            }
        };
        const normalized = adapter.normalizeProjectForPlayer(projectWithSource);
        console.log(JSON.stringify({
            duration: normalized.duration,
            isOutputDuration: normalized.duration === 8.0
        }));
        """
        out = json.loads(run_node_adapter(code))
        assert out["duration"] == 8.0
        assert out["isOutputDuration"] is True

    def test_atomic_replacement_on_new_revision(self):
        """Verifies syncOutcome updates targetRev to new revision and canonicalizes incoming deliverable."""
        mg_src = MOTION_PAGE_PATH.read_text(encoding="utf-8")
        assert "targetRev = outcomeRev || detail.data.revision || 1" in mg_src
        assert "canonicalDeliverable =" in mg_src
        assert "setRenderedVideo(canonicalDeliverable)" in mg_src
        assert "setSelectedOutputIndex(0)" in mg_src
