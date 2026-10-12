# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
import asyncio
import json
import os
import sys
from pathlib import Path
from playwright.async_api import async_playwright
from backend.services.project_service import ProjectService
from backend.services.hyperframes_adapter import HyperFramesAdapter

async def run_audio_verification():
    print("=== STARTING LIVE AUDIBLE TIMELINE PLAYBACK VERIFICATION ===")
    
    # 1. Create a canonical test project with BGM and SFX audio tracks
    doc = {
        "schema_version": 2,
        "project_id": "proj_audio_verification_live",
        "aspect_ratio": "9:16",
        "duration": 10.0,
        "fps": 30,
        "timeline": {
            "tracks": [
                {
                    "id": "trk_bgm",
                    "type": "audio",
                    "name": "Background Music",
                    "volume": 0.8,
                    "muted": False,
                    "solo": False,
                    "clips": [
                        {
                            "id": "clip_bgm_1",
                            "name": "Lofi Chill Beat",
                            "asset_id": "trk:lofi_hiphop_groove.mp3",
                            "start_time": 0.0,
                            "duration": 10.0,
                            "offset": 0.0,
                            "volume": 0.8
                        }
                    ]
                },
                {
                    "id": "trk_sfx",
                    "type": "audio",
                    "name": "Sound Effects",
                    "volume": 1.0,
                    "muted": False,
                    "solo": False,
                    "clips": [
                        {
                            "id": "clip_sfx_1",
                            "name": "Camera Shutter Click",
                            "asset_id": "sfx:camera_shutter.mp3",
                            "start_time": 2.0,
                            "duration": 1.5,
                            "offset": 0.0,
                            "volume": 1.0
                        }
                    ]
                }
            ]
        }
    }
    
    # Ensure audio test files exist in storage
    storage_music = Path("storage/music")
    storage_music.mkdir(parents=True, exist_ok=True)
    bgm_path = storage_music / "lofi_hiphop_groove.mp3"
    if not bgm_path.exists():
        # Generate valid 10s audio sine wave using ffmpeg
        import subprocess
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=10", "-c:a", "libmp3lame", "-b:a", "128k", str(bgm_path)],
            check=True, capture_output=True
        )
    
    storage_sfx = Path("storage/sfx")
    storage_sfx.mkdir(parents=True, exist_ok=True)
    sfx_path = storage_sfx / "camera_shutter.mp3"
    if not sfx_path.exists():
        import subprocess
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=880:duration=1.5", "-c:a", "libmp3lame", "-b:a", "128k", str(sfx_path)],
            check=True, capture_output=True
        )
        
    # Materialize project workspace
    proj = await ProjectService.create_project(
        name="Live Audio Playback Verification",
        aspect_ratio="9:16",
        initial_document=doc
    )
    doc["project_id"] = proj.id
    sync_res = await HyperFramesAdapter.sync_project_to_studio(proj.id)
    preview_html_path = Path(sync_res["html_path"])
    workspace = preview_html_path.parent
    print(f"Materialized workspace at: {workspace}")
    print(f"Preview HTML exists: {preview_html_path.exists()}")
    
    # Verify staged assets
    assets_dir = workspace / "assets"
    print("Staged assets in workspace:", [f.name for f in assets_dir.iterdir() if f.is_file()])
    
    # 2. Launch headless browser with autoplay enabled
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--autoplay-policy=no-user-gesture-required",
                "--use-fake-ui-for-media-stream",
                "--enable-audio-service-sandbox"
            ]
        )
        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        page = await context.new_page()
        
        # Navigate directly to the preview endpoint
        preview_url = f"http://127.0.0.1:16888/api/projects/{doc['project_id']}/preview"
        print(f"Navigating to {preview_url}...")
        resp = await page.goto(preview_url, wait_until="load")
        print(f"Response status: {resp.status}")
        
        await page.wait_for_timeout(500)
        
        # Inspect audio elements in DOM
        audio_info = await page.evaluate("""() => {
            const els = Array.from(document.querySelectorAll('audio'));
            return els.map(a => ({
                id: a.id,
                src: a.src,
                paused: a.paused,
                muted: a.muted,
                volume: a.volume,
                currentTime: a.currentTime,
                duration: a.duration,
                readyState: a.readyState
            }));
        }""")
        print("Discovered audio elements in preview iframe:", json.dumps(audio_info, indent=2))
        assert len(audio_info) >= 1, "Expected at least 1 audio element in DOM"
        
        # 3. Setup Web Audio Analyser to monitor audio output signal
        analyser_setup = await page.evaluate("""() => {
            window.__audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const bgmEl = document.querySelector('audio');
            if (!bgmEl) return { error: "No audio element found" };
            
            // Connect to AnalyserNode
            try {
                window.__source = window.__audioContext.createMediaElementSource(bgmEl);
                window.__analyser = window.__audioContext.createAnalyser();
                window.__analyser.fftSize = 256;
                window.__source.connect(window.__analyser);
                window.__analyser.connect(window.__audioContext.destination);
                return { success: true, audioCtxState: window.__audioContext.state };
            } catch (err) {
                return { error: err.toString() };
            }
        }""")
        print("Web Audio Analyser setup:", analyser_setup)
        
        # 4. Trigger Playback
        print("Triggering Play via window.startPlayback()...")
        await page.evaluate("""() => {
            if (window.__audioContext && window.__audioContext.state === 'suspended') {
                window.__audioContext.resume();
            }
            if (typeof window.startPlayback === 'function') {
                window.startPlayback();
            } else {
                window.postMessage({ source: 'vm-parent', action: 'play' }, '*');
            }
        }""")
        
        # Let it play for 1 second
        await page.wait_for_timeout(1000)
        
        # Measure RMS Signal and play state
        play_metrics = await page.evaluate("""() => {
            const bgmEl = document.querySelector('audio');
            let rms = 0;
            if (window.__analyser) {
                const dataArray = new Uint8Array(window.__analyser.frequencyBinCount);
                window.__analyser.getByteTimeDomainData(dataArray);
                let sumSq = 0;
                for (let i = 0; i < dataArray.length; i++) {
                    const norm = (dataArray[i] - 128) / 128.0;
                    sumSq += norm * norm;
                }
                rms = Math.sqrt(sumSq / dataArray.length);
            }
            return {
                currentTime: bgmEl ? bgmEl.currentTime : 0,
                compTime: window.__currentTime || 0,
                paused: bgmEl ? bgmEl.paused : true,
                muted: bgmEl ? bgmEl.muted : true,
                volume: bgmEl ? bgmEl.volume : 0,
                analyserRms: rms
            };
        }""")
        print("Playback metrics (1.0s elapsed):", json.dumps(play_metrics, indent=2))
        assert not play_metrics["paused"], "Audio element should be playing (paused=False)"
        assert play_metrics["analyserRms"] > 0.0, f"Expected non-zero RMS signal, got {play_metrics['analyserRms']}"
        
        # 5. Test Seek to 4.5s
        print("Seeking composition to 4.5s...")
        await page.evaluate("""() => {
            if (typeof window.seekTo === 'function') {
                window.seekTo(4.5);
            } else {
                window.postMessage({ source: 'vm-parent', action: 'seek', time: 4.5 }, '*');
            }
        }""")
        await page.wait_for_timeout(400)
        seek_metrics = await page.evaluate("""() => {
            const bgmEl = document.querySelector('audio');
            return {
                currentTime: bgmEl ? bgmEl.currentTime : 0,
                compTime: window.__currentTime || 0
            };
        }""")
        print("Seek metrics (at 4.5s):", json.dumps(seek_metrics, indent=2))
        assert abs(seek_metrics["currentTime"] - 4.5) < 0.5, "Audio currentTime should track composition time within 500ms"
        
        # 6. Test Mute Toggle
        print("Muting audio track via postMessage...")
        await page.evaluate("""() => {
            window.postMessage({ source: 'vm-parent', action: 'mute', muted: true }, '*');
        }""")
        await page.wait_for_timeout(200)
        mute_metrics = await page.evaluate("""() => {
            const bgmEl = document.querySelector('audio');
            return { muted: bgmEl ? bgmEl.muted : false };
        }""")
        print("Mute metrics:", mute_metrics)
        assert mute_metrics["muted"] is True, "Audio element should be muted"
        
        # 7. Test Unmute
        print("Unmuting audio track via postMessage...")
        await page.evaluate("""() => {
            window.postMessage({ source: 'vm-parent', action: 'mute', muted: false }, '*');
        }""")
        await page.wait_for_timeout(200)
        unmute_metrics = await page.evaluate("""() => {
            const bgmEl = document.querySelector('audio');
            return { muted: bgmEl ? bgmEl.muted : true };
        }""")
        print("Unmute metrics:", unmute_metrics)
        assert unmute_metrics["muted"] is False, "Audio element should be unmuted"
        
        # 8. Test Pause
        print("Pausing composition via window.pausePlayback()...")
        await page.evaluate("""() => {
            if (typeof window.pausePlayback === 'function') {
                window.pausePlayback();
            } else {
                window.postMessage({ source: 'vm-parent', action: 'pause' }, '*');
            }
        }""")
        await page.wait_for_timeout(200)
        pause_metrics = await page.evaluate("""() => {
            const bgmEl = document.querySelector('audio');
            return { paused: bgmEl ? bgmEl.paused : false };
        }""")
        print("Pause metrics:", pause_metrics)
        assert pause_metrics["paused"] is True, "Audio element should be paused"
        
        print("=== ALL LIVE AUDIBLE TIMELINE PLAYBACK CHECKS PASSED SUCCESSFULLY ===")
        await browser.close()

if __name__ == '__main__':
    asyncio.run(run_audio_verification())
