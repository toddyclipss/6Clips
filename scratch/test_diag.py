import os
import sys
import time
import urllib.request
import json
import subprocess
from pathlib import Path

ISOLATED_DIR = Path("c:/Users/toddy/Desktop/ViralMint/tmp_isolated_test")
env = os.environ.copy()
env["VIRALMINT_DATA_DIR"] = str(ISOLATED_DIR)
env["PORT"] = "16889"

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "16889"],
    env=env,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

try:
    ready = False
    for i in range(20):
        try:
            with urllib.request.urlopen("http://127.0.0.1:16889/api/config", timeout=1) as resp:
                ready = True
                break
        except Exception:
            time.sleep(0.5)

    if not ready:
        print("Backend failed to start")
        sys.exit(1)

    print("Backend ready on port 16889!")
    proj_url = "http://127.0.0.1:16889/api/projects/6169c61a-9805-43fa-9230-7806f4ed922b"
    try:
        with urllib.request.urlopen(proj_url) as resp:
            data = json.loads(resp.read().decode())
            print("GET project status:", resp.status)
            print("Project name:", data.get("name"))
            print("Project rev:", data.get("revision"))
            print("Has document:", data.get("document") is not None)
    except Exception as e:
        print("GET project failed:", e)

    studio_url = "http://127.0.0.1:16889/api/generate/motion/studio/start?mode=light"
    req = urllib.request.Request(studio_url, data=b"", method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            print("POST studio/start status:", resp.status)
            print("POST studio/start body:", resp.read().decode())
    except Exception as e:
        print("POST studio/start failed:", e)

finally:
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except Exception:
        proc.kill()
