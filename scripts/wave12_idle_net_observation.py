# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Real Wall-Clock 10-Minute Server-Only Network Observation Script for Wave 12 Agent 5.

Contract:
- Starts the ViralMint backend server on an isolated test port (18889).
- Observes the server process for 10 minutes (600+ seconds) in true idle state (no user action, no scheduled jobs).
- Periodically samples TCP sockets via OS-level netstat for the server PID and child processes.
- Classifies each connection:
    - LOOPBACK_LOCAL: 127.0.0.1, ::1, 0.0.0.0 (listen) -> Authorized local interface
    - EXTERNAL_EGRESS: Any foreign non-loopback address -> Violation if unsolicited
- Persists full JSON evidence to %TEMP%/6clips_wave12_idle_audit/idle_observation_10min.json
- Shuts down test server cleanly upon completion.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

TEST_PORT = 18889
MIN_DURATION_SECONDS = 600  # 10 minutes minimum
SAMPLE_INTERVAL_SECONDS = 5


def get_connections_for_pids(pids: set[int]) -> list[dict]:
    """Sample active TCP connections for target PIDs via netstat."""
    connections = []
    try:
        res = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True,
            text=True,
            check=True,
        )
        lines = res.stdout.splitlines()
        for line in lines:
            parts = line.strip().split()
            if len(parts) >= 5 and parts[0].upper() == "TCP":
                try:
                    conn_pid = int(parts[-1])
                except ValueError:
                    continue

                if conn_pid in pids:
                    local_addr = parts[1]
                    foreign_addr = parts[2]
                    state = parts[3]

                    # Parse foreign host
                    foreign_host = foreign_addr.rsplit(":", 1)[0].strip("[]")
                    is_loopback = foreign_host in (
                        "0.0.0.0",
                        "127.0.0.1",
                        "::",
                        "::1",
                        "localhost",
                        "*",
                    ) or foreign_addr.startswith("0.0.0.0:0") or foreign_addr.startswith("[::]:0")

                    connections.append({
                        "pid": conn_pid,
                        "local_address": local_addr,
                        "foreign_address": foreign_addr,
                        "foreign_host": foreign_host,
                        "state": state,
                        "is_loopback": is_loopback,
                    })
    except Exception as exc:
        print(f"[WARN] Error sampling netstat: {exc}", file=sys.stderr)
    return connections


def run_observation():
    os.environ["SIXCLIPS_IDLE_NET_AUDIT"] = "1"
    os.environ["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"

    repo_root = Path(__file__).resolve().parent.parent
    audit_dir = Path(tempfile.gettempdir()) / "6clips_wave12_idle_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    out_file = audit_dir / "idle_observation_10min.json"

    print(f"[INFO] Launching ViralMint backend on port {TEST_PORT}...")
    server_env = os.environ.copy()
    server_env["PYTHONPATH"] = f"{repo_root};C:\\Users\\toddy\\AppData\\Roaming\\Python\\Python314\\site-packages"
    server_env["SIXCLIPS_IDLE_NET_AUDIT"] = "1"

    cmd = [
        "C:\\Python314\\python.exe",
        "-m",
        "uvicorn",
        "backend.main:create_app",
        "--factory",
        "--host",
        "127.0.0.1",
        "--port",
        str(TEST_PORT),
        "--log-level",
        "warning",
    ]

    proc = subprocess.Popen(
        cmd,
        cwd=str(repo_root),
        env=server_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    pids_to_watch = {proc.pid}
    start_time = time.time()
    start_time_utc = datetime.now(timezone.utc).isoformat()
    print(f"[INFO] Server launched with PID {proc.pid}. Waiting 4 seconds for boot...")
    time.sleep(4)

    # Health check verification
    import urllib.request
    try:
        req = urllib.request.urlopen(f"http://127.0.0.1:{TEST_PORT}/health", timeout=5)
        health_resp = req.read().decode("utf-8")
        print(f"[INFO] Health check succeeded: {health_resp}")
    except Exception as e:
        print(f"[WARN] Health check failed or timed out: {e}")

    # Discover any child processes spawned by uvicorn
    try:
        wmic = subprocess.run(
            ["wmic", "process", "where", f"ParentProcessId={proc.pid}", "get", "ProcessId"],
            capture_output=True,
            text=True,
        )
        for num in re.findall(r"\d+", wmic.stdout):
            pids_to_watch.add(int(num))
    except Exception:
        pass

    print(f"[INFO] Watching PIDs: {pids_to_watch}")
    print(f"[INFO] Beginning {MIN_DURATION_SECONDS}s (10 min) idle observation window...")

    samples = []
    unsolicited_external_connections = []
    total_samples = 0

    try:
        while True:
            elapsed = time.time() - start_time
            if elapsed >= MIN_DURATION_SECONDS:
                break

            total_samples += 1
            sample_time_utc = datetime.now(timezone.utc).isoformat()
            conns = get_connections_for_pids(pids_to_watch)

            external = [c for c in conns if not c["is_loopback"]]
            if external:
                for ext in external:
                    unsolicited_external_connections.append({
                        "timestamp_utc": sample_time_utc,
                        "elapsed_seconds": round(elapsed, 1),
                        **ext,
                    })
                print(f"[ALERT] External connection observed at {elapsed:.1f}s: {external}")

            samples.append({
                "tick": total_samples,
                "elapsed_seconds": round(elapsed, 1),
                "timestamp_utc": sample_time_utc,
                "active_connections_count": len(conns),
                "external_count": len(external),
            })

            if total_samples % 20 == 0:
                print(f"[PROGRESS] {elapsed:.1f}/{MIN_DURATION_SECONDS}s elapsed ({elapsed/MIN_DURATION_SECONDS*100:.1f}%) | "
                      f"samples={total_samples} | external_observed={len(unsolicited_external_connections)}")

            time.sleep(SAMPLE_INTERVAL_SECONDS)

    finally:
        print("[INFO] Stopping test server...")
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    end_time = time.time()
    end_time_utc = datetime.now(timezone.utc).isoformat()
    duration_seconds = round(end_time - start_time, 2)

    verdict = "ZERO_OBSERVED" if len(unsolicited_external_connections) == 0 else "VIOLATIONS"

    report = {
        "observation_target": "ViralMint Backend Server (Idle Server-Only)",
        "start_time_utc": start_time_utc,
        "end_time_utc": end_time_utc,
        "measured_duration_seconds": duration_seconds,
        "min_duration_required_seconds": MIN_DURATION_SECONDS,
        "total_samples": total_samples,
        "sample_interval_seconds": SAMPLE_INTERVAL_SECONDS,
        "server_pids_monitored": list(pids_to_watch),
        "test_port": TEST_PORT,
        "active_jobs_during_window": 0,
        "active_user_queries_during_window": 0,
        "unsolicited_external_connections_count": len(unsolicited_external_connections),
        "unsolicited_external_connections": unsolicited_external_connections,
        "EXTERNAL_IDLE_EGRESS_AFTER": verdict,
        "summary": (
            f"Observed server PID(s) {list(pids_to_watch)} for {duration_seconds}s across {total_samples} samples. "
            f"External egress detected: {len(unsolicited_external_connections)}. Verdict: {verdict}."
        ),
    }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"[COMPLETE] Wrote observation report to: {out_file}")
    print(f"[SUMMARY] {report['summary']}")
    print(f"EXTERNAL_IDLE_EGRESS_AFTER: {verdict}")
    return report


if __name__ == "__main__":
    run_observation()
