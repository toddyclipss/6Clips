import asyncio
import copy
import json
import re
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest

from backend.services.hyperframes_adapter import HyperFramesAdapter
from backend.services.project_service import ProjectService


@pytest.mark.asyncio
async def test_staging_asset_name_collision():
    """Verify that assets with identical basenames (e.g. video.mp4) across different directories
    do not collide in staging: both files are preserved and manifest maintains distinct identities."""
    with tempfile.TemporaryDirectory(prefix="vm-test-assets-") as temp:
        root = Path(temp)
        paths = {}
        for aid in ["asset_alpha", "asset_beta"]:
            p = root / aid / "video.mp4"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(f"bytes_of_{aid}".encode())
            paths[aid] = p

        doc = {
            "timeline": {
                "duration_seconds": 20,
                "tracks": [
                    {
                        "type": "video",
                        "clips": [
                            {"id": "c1", "asset_id": "asset_alpha", "start_seconds": 0, "duration_seconds": 10},
                            {"id": "c2", "asset_id": "asset_beta", "start_seconds": 10, "duration_seconds": 10, "trim_start": 3},
                        ],
                    }
                ],
            }
        }

        async def mock_resolve(aid, **kwargs):
            return paths[aid]

        with patch.object(ProjectService, "freeze_for_render", AsyncMock(return_value=(1, copy.deepcopy(doc)))), \
             patch.object(HyperFramesAdapter, "_resolve_asset_path", mock_resolve):
            rev, dest = await HyperFramesAdapter.stage_project_for_render("proj_test", dest_dir=root / "render_test")

        manifest = json.loads((dest / "assets_manifest.json").read_text(encoding="utf-8"))
        assert len(manifest) == 2, f"Expected 2 manifest entries, got {len(manifest)}"

        alpha_key = [k for k, v in manifest.items() if v["asset_id"] == "asset_alpha"][0]
        beta_key = [k for k, v in manifest.items() if v["asset_id"] == "asset_beta"][0]

        assert alpha_key != beta_key
        assert (dest / "assets" / alpha_key).read_bytes() == b"bytes_of_asset_alpha"
        assert (dest / "assets" / beta_key).read_bytes() == b"bytes_of_asset_beta"


@pytest.mark.asyncio
async def test_preview_bridge_timeline_scheduling():
    """Verify that the generated preview bridge script respects timeline scheduling,
    clip trim offsets, and reports composition duration rather than media duration."""
    doc = {
        "timeline": {
            "duration_seconds": 20,
            "tracks": [
                {
                    "type": "video",
                    "clips": [
                        {"id": "c1", "file": "vid1.mp4", "start_seconds": 0, "duration_seconds": 10},
                        {"id": "c2", "file": "vid2.mp4", "start_seconds": 10, "duration_seconds": 10, "trim_start": 3},
                    ],
                }
            ],
        }
    }
    html = HyperFramesAdapter.project_doc_to_html(doc)
    match = re.search(r'<script id="vm-preview-bridge">(.*?)</script>', html, re.S)
    assert match is not None, "vm-preview-bridge script tag missing from HTML"
    bridge = match.group(1)

    node_code = """
const vm = require("node:vm");
let listener, tick, report;
const media = [0, 10].map(start => ({
    dataset: { start: String(start), duration: '10', mediaStart: start ? '3' : '0' },
    currentTime: 0,
    duration: 30,
    paused: true,
    play() { this.paused = false; return Promise.resolve(); },
    pause() { this.paused = true; }
}));
const ctx = {
    window: {
        addEventListener: (n, cb) => { listener = cb; },
        parent: { postMessage: r => { report = r; } }
    },
    document: {
        querySelectorAll: () => media,
        querySelector: () => media[0]
    },
    setInterval: cb => { tick = cb; },
    Date: Date
};
vm.runInNewContext(process.argv[1], ctx);

// 1. Play at t=0
listener({ data: { source: 'vm-parent', action: 'play' } });
const clip0PlayingAtZero = !media[0].paused;
const clip1PausedAtZero = media[1].paused;

// 2. Seek to t=12
listener({ data: { source: 'vm-parent', action: 'seek', time: 12 } });
// media[1] start=10, trim_start=3 -> local time = 3 + (12 - 10) = 5
if (media[1].currentTime !== 5) {
    throw new Error('Expected media[1].currentTime === 5, got ' + media[1].currentTime);
}
const clip0PausedAtTwelve = media[0].paused;
const clip1PlayingAtTwelve = !media[1].paused;

// 3. Tick runtime report
tick();
if (report.duration !== 20) {
    throw new Error('Expected reported duration === 20, got ' + report.duration);
}
if (report.currentTime !== 12) {
    throw new Error('Expected reported currentTime === 12, got ' + report.currentTime);
}

console.log(JSON.stringify({
    clip0PlayingAtZero,
    clip1PausedAtZero,
    clip0PausedAtTwelve,
    clip1PlayingAtTwelve,
    secondClipTimeAtTwelve: media[1].currentTime,
    reportedDuration: report.duration,
    reportedTime: report.currentTime
}));
"""
    result = subprocess.run(["node", "-e", node_code, bridge], capture_output=True, text=True, check=True)
    out = json.loads(result.stdout.strip())
    assert out["clip0PlayingAtZero"] is True
    assert out["clip1PausedAtZero"] is True
    assert out["clip0PausedAtTwelve"] is True
    assert out["clip1PlayingAtTwelve"] is True
    assert out["secondClipTimeAtTwelve"] == 5
    assert out["reportedDuration"] == 20
    assert out["reportedTime"] == 12


@pytest.mark.asyncio
async def test_preview_html_scaling_and_subcomp_mounting():
    """Requirement 39 & 15: Automated regression verifying stage responsive scaling
    and eager subcomposition iframe mounting for catalog blocks in 9:16 and 16:9."""
    # 9:16 Vertical
    doc_916 = {
        "title": "Regression 9:16",
        "aspect_ratio": "9:16",
        "timeline": {
            "duration_seconds": 10.0,
            "tracks": [
                {
                    "type": "video",
                    "clips": [
                        {
                            "id": "block_elem_1",
                            "type": "block",
                            "block_id": "lower-third-bild",
                            "start_seconds": 0.0,
                            "duration_seconds": 5.0,
                            "variables": {"TXT_MAIN_1_Line": "REGRESSION PROOF"}
                        }
                    ]
                }
            ]
        }
    }
    html_916 = HyperFramesAdapter.project_doc_to_html(doc_916)
    assert 'data-width="1080"' in html_916
    assert 'data-height="1920"' in html_916
    assert 'id="vm-stage-scale"' in html_916
    assert 'fitStage()' in html_916
    assert '<iframe class="subcomp-frame" src="compositions/block_elem_1.html"' in html_916
    assert 'syncFrames' in html_916

    # 16:9 Landscape
    doc_169 = {
        "title": "Regression 16:9",
        "aspect_ratio": "16:9",
        "timeline": {
            "duration_seconds": 10.0,
            "tracks": [
                {
                    "type": "video",
                    "clips": [
                        {
                            "id": "block_elem_2",
                            "type": "block",
                            "block_id": "lower-third-bild",
                            "start_seconds": 0.0,
                            "duration_seconds": 5.0,
                        }
                    ]
                }
            ]
        }
    }
    html_169 = HyperFramesAdapter.project_doc_to_html(doc_169)
    assert 'data-width="1920"' in html_169
    assert 'data-height="1080"' in html_169
    assert '<iframe class="subcomp-frame" src="compositions/block_elem_2.html"' in html_169


@pytest.mark.asyncio
async def test_project_default_aspect_ratio_is_9x16():
    """Requirement 14 & 40: Automated regression verifying default new Project format is 9:16."""
    from backend.database import init_db
    await init_db()
    proj = await ProjectService.create_project(name="Default Aspect Check")
    assert proj.aspect_ratio == "9:16", f"Expected default 9:16, got {proj.aspect_ratio}"
    doc = json.loads(proj.document_json)
    assert doc.get("aspect_ratio") == "9:16", f"Expected doc aspect_ratio 9:16, got {doc.get('aspect_ratio')}"

