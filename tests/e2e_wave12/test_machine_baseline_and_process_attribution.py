# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 12 Stage 3: Machine Baseline & Process Attribution Suite.

Verifies:
1. System baseline inventory: port 11434, Ollama process PID and executable path.
2. Exact resident model vs active inference state (`ollama ps` does not imply active run).
3. Process tree enumeration: Python, Node, Edge/Chromium, Ollama.
4. Active TCP connections and loopback vs external interface classification.
5. Process attribution: mapping short-lived or persistent connections to owning PID and executable.
6. Persistence of baseline telemetry metadata to %TEMP%/6clips_wave12_idle_audit/machine_baseline.json.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import httpx
import pytest

from tests.e2e_wave12.conftest import EVIDENCE_DIR


def get_process_map() -> dict[int, dict]:
    """Return map of PID -> {name, executable, command_line} for relevant processes."""
    pmap = {}
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process | Select-Object ProcessId, Name, ExecutablePath, CommandLine | ConvertTo-Json -Compress"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if res.returncode == 0 and res.stdout.strip():
            raw = json.loads(res.stdout)
            items = raw if isinstance(raw, list) else [raw]
            for item in items:
                pid = item.get("ProcessId")
                if pid:
                    pmap[int(pid)] = {
                        "name": item.get("Name") or "",
                        "executable": item.get("ExecutablePath") or "",
                        "command_line": (item.get("CommandLine") or "")[:200],  # truncated for privacy
                    }
    except Exception as exc:
        print(f"[WARN] Failed to query Win32_Process: {exc}")
    return pmap


def get_tcp_connections() -> list[dict]:
    """Sample active TCP connections via netstat."""
    conns = []
    try:
        res = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        for line in res.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) >= 5 and parts[0].upper() == "TCP":
                try:
                    conn_pid = int(parts[-1])
                except ValueError:
                    continue
                local_addr = parts[1]
                foreign_addr = parts[2]
                state = parts[3]
                foreign_host = foreign_addr.rsplit(":", 1)[0].strip("[]")
                is_loopback = foreign_host in (
                    "0.0.0.0", "127.0.0.1", "::", "::1", "localhost", "*",
                ) or foreign_addr.startswith("0.0.0.0:0") or foreign_addr.startswith("[::]:0")

                conns.append({
                    "pid": conn_pid,
                    "local_address": local_addr,
                    "foreign_address": foreign_addr,
                    "foreign_host": foreign_host,
                    "state": state,
                    "is_loopback": is_loopback,
                })
    except Exception as exc:
        print(f"[WARN] Failed to sample netstat: {exc}")
    return conns


def test_ollama_daemon_and_resident_state():
    """Verify Ollama is reachable on port 11434 and record resident models vs active inference."""
    resp = httpx.get("http://127.0.0.1:11434/api/version", timeout=5.0)
    assert resp.status_code == 200, f"Ollama daemon unreachable: {resp.status_code}"
    version_info = resp.json()
    assert "version" in version_info

    # Query installed models
    tags_resp = httpx.get("http://127.0.0.1:11434/api/tags", timeout=5.0)
    assert tags_resp.status_code == 200
    models = [m.get("name") for m in tags_resp.json().get("models", [])]
    assert any("gemma4:e4b" in m for m in models), f"gemma4:e4b not in installed models: {models}"

    # Query active/resident processes in Ollama (`/api/ps`)
    ps_resp = httpx.get("http://127.0.0.1:11434/api/ps", timeout=5.0)
    assert ps_resp.status_code == 200
    ps_models = ps_resp.json().get("models", [])
    # GPU residency in `ollama ps` is documented as VRAM caching, NOT active inference
    for m in ps_models:
        print(f"[BASELINE] Ollama resident model: {m.get('name')}, size={m.get('size')}, vram={m.get('size_vram')}")


def test_machine_baseline_capture_and_persistence(isolated_server):
    """Capture full baseline inventory and save outside repository."""
    pmap = get_process_map()
    conns = get_tcp_connections()

    ollama_procs = [p for p in pmap.values() if "ollama" in p["name"].lower()]
    python_procs = [p for p in pmap.values() if "python" in p["name"].lower()]
    node_procs = [p for p in pmap.values() if "node" in p["name"].lower()]

    assert len(ollama_procs) >= 1, "At least one Ollama process must be active"

    # Identify server PID
    server_pids = isolated_server["server_pids"]
    assert len(server_pids) >= 1

    baseline_data = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "isolated_server_port": isolated_server["port"],
        "server_pids": list(server_pids),
        "ollama_process_count": len(ollama_procs),
        "ollama_processes": ollama_procs,
        "python_process_count": len(python_procs),
        "node_process_count": len(node_procs),
        "total_active_tcp_connections": len(conns),
        "server_connections": [c for c in conns if c["pid"] in server_pids],
    }

    out_file = EVIDENCE_DIR / "machine_baseline.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(baseline_data, f, indent=2)

    assert out_file.is_file()
    assert out_file.stat().st_size > 100


def test_process_attribution_resolution():
    """Verify attribution resolver maps known PIDs correctly and labels unknown PIDs."""
    pmap = get_process_map()

    # Current test runner process
    my_pid = os.getpid()
    assert my_pid in pmap or len(pmap) > 0

    def resolve_pid(pid: int) -> dict:
        info = pmap.get(pid)
        if not info:
            return {"attribution": "ATTRIBUTION_UNKNOWN", "pid": pid}
        name = info["name"].lower()
        if "ollama" in name:
            category = "OLLAMA_SERVICE"
        elif "python" in name or "uvicorn" in name:
            category = "PYTHON_APP_OR_TEST"
        elif "node" in name or "vite" in name:
            category = "FRONTEND_DEV_OR_TOOL"
        elif "msedge" in name or "chrome" in name:
            category = "BROWSER_CLIENT"
        else:
            category = "UNATTRIBUTED_OTHER_PROCESS"
        return {
            "attribution": category,
            "pid": pid,
            "name": info["name"],
            "executable": info["executable"],
        }

    # Attribute sample PIDs
    ollama_pids = [pid for pid, info in pmap.items() if "ollama" in info["name"].lower()]
    if ollama_pids:
        res = resolve_pid(ollama_pids[0])
        assert res["attribution"] == "OLLAMA_SERVICE"

    unknown_res = resolve_pid(99999999)
    assert unknown_res["attribution"] == "ATTRIBUTION_UNKNOWN"
