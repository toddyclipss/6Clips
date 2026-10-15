# SPDX-License-Identifier: AGPL-3.0-only
from pathlib import Path
from backend.catalog_runtime.core.registry_engine import UniversalRuntimeRegistry

shipped = Path("backend/catalog/shipped_blocks")
targets = [
    "news-ticker", "notification-cascade", "organic-light-leak-overlay",
    "split-flap-board", "thread-message-stack", "week-in-merges",
    "whip-pan", "ripple-waves", "sdf-iris", "ridged-burn", "thermal-distortion",
    "transitions-push", "transitions-dissolve", "transitions-radial"
]

all_valid = True
for t in targets:
    bdir = shipped / t
    res = UniversalRuntimeRegistry.validate_vendored_block_integrity(t, bdir)
    is_v = res["is_valid"]
    if not is_v:
        all_valid = False
    print(f"{t:30} is_valid={is_v} blocker={res.get('blocker_code')} license={res.get('license_status')}")

print(f"\nALL 14 VALID: {all_valid}")
assert all_valid, "Integrity check failed!"
