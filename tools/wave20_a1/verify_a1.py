# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 20 Agent 1 Automated Verification Script.
Runs all Agent 1 test suites, verifies code integrity, and outputs structured status.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys


def run_command(cmd, cwd=None):
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    return res.returncode, res.stdout, res.stderr


def main():
    root = Path(__file__).resolve().parents[2]
    print(f"=== Wave 20 Agent 1 Verification === Root: {root}")

    # Check git branch and SHA
    rc, out_branch, _ = run_command("git rev-parse --abbrev-ref HEAD", cwd=root)
    branch = out_branch.strip()

    rc, out_sha, _ = run_command("git rev-parse HEAD", cwd=root)
    current_sha = out_sha.strip()

    rc, out_status, _ = run_command("git status --porcelain", cwd=root)
    git_status = out_status.strip()

    print(f"Branch: {branch} | HEAD: {current_sha}")

    # Run pytest
    test_cmd = f"pytest {root / 'tests' / 'wave20' / 'a1'} -v"
    print(f"Executing: {test_cmd}")
    rc_test, test_stdout, test_stderr = run_command(test_cmd, cwd=root)

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "branch": branch,
        "head_sha": current_sha,
        "git_status_clean": len(git_status) == 0,
        "test_exit_code": rc_test,
        "test_passed": rc_test == 0,
        "test_output": test_stdout,
        "test_stderr": test_stderr,
    }

    report_path = root / "tools" / "wave20_a1" / "verification_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Verification report written to {report_path}")
    print(f"Pytest result: {'PASS' if rc_test == 0 else 'FAIL'} (exit code {rc_test})")

    if rc_test != 0:
        print(test_stderr)
        print(test_stdout)
        sys.exit(rc_test)


if __name__ == "__main__":
    main()
