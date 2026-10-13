# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Isolated backend server runner pointing strictly to tmp_isolated_test."""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ISOLATED_DIR = BASE_DIR / "tmp_isolated_test"

# Set environment before any backend module is imported
os.environ["VIRALMINT_DATA_DIR"] = str(ISOLATED_DIR)
os.environ["PORT"] = "16889"

# Add repo to sys.path
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.config import DATA_DIR, settings
print(f"ISOLATED RUNNER INITIALIZED:")
print(f"  DATA_DIR: {DATA_DIR}")
print(f"  DATABASE_URL: {settings.DATABASE_URL}")
print(f"  STORAGE_ROOT: {settings.STORAGE_ROOT}")

import uvicorn
from backend.main import app

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=16889, log_level="info")
