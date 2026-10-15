# SPDX-License-Identifier: AGPL-3.0-only
"""E2E Test Suite for Wave 17 Agent 4: Independent QA and Anti-Fake Acceptance."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
QA_SCRIPT = REPO_ROOT / "scripts" / "qa_wave17" / "adversarial_qa_harness_w17.py"
REPORT_FILE = REPO_ROOT / "scripts" / "qa_wave17" / "qa_adversarial_report.json"

def test_agent4_e2e_adversarial_qa_harness():
    """Verify that the independent adversarial QA harness runs to completion and produces valid report."""
    assert QA_SCRIPT.is_file(), f"Missing QA script: {QA_SCRIPT}"

    cmd = [
        sys.executable,
        str(QA_SCRIPT)
    ]
    env = dict(subprocess.os.environ)
    env["PYTHONPATH"] = f"C:\\Users\\toddy\\AppData\\Roaming\\Python\\Python314\\site-packages;{REPO_ROOT}"

    res = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=180)
    assert res.returncode == 0, f"QA script failed: {res.stderr}\nOutput: {res.stdout}"

    assert REPORT_FILE.exists(), f"Missing report output: {REPORT_FILE}"
    report = json.loads(REPORT_FILE.read_text(encoding="utf-8"))

    assert report["schema_version"] == 1
    assert report["wave"] == 17
    assert report["agent"] == "Agent 4 (N-Z HyperFrames Porting & Independent Anti-Fake QA)"
    assert report["execution_mode"] == "BASELINE_QA"
    assert report["integrated_candidate_status"] == "PENDING"

    summary = report["summary"]
    assert summary["w17_newly_ported_passed"] == "18/18"
    assert summary["w16_regression_passed"] == "14/14"
    assert summary["standin_audit_passed"] is True
    assert summary["negative_controls_passed"] is True

def test_agent4_standin_detector_catches_fake_duplicates():
    """Verify that the stand-in detector accurately flags identical duplicate frames."""
    from scripts.qa_wave17.adversarial_qa_harness_w17 import AdversarialQAHarnessW17

    harness = AdversarialQAHarnessW17(REPO_ROOT)
    fake_blocks = [
        {"block_id": "fake-a", "frame_hashes": ["hash_1", "hash_2"]},
        {"block_id": "fake-b", "frame_hashes": ["hash_1", "hash_3"]}, # duplicate first frame!
    ]
    res = harness.detect_standin_renders(fake_blocks)
    harness.shutdown()

    assert res["standin_audit_passed"] is False
    assert len(res["detected_identical_cross_block_renders"]) == 1
    assert res["detected_identical_cross_block_renders"][0] == ("fake-b", "fake-a")
