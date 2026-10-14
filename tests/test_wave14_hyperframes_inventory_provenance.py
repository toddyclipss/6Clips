#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Unit and Quality-Control Acceptance Test Suite for HyperFrames 196-Block
Forensic Inventory & Provenance (Wave 14 Stage 1).

Enforces:
1. Strict 196 original donor block count.
2. Exclusion of 6Clips-authored blocks (creator-hud, glitch-transition).
3. Exact 10 internalized donor blocks reconciliation with installed shipped blocks.
4. Exactly 186 unported donor blocks with truthful blockers/eligibility.
5. Permissive, copyleft, and proprietary license classifications.
6. Safe identifier regex and elimination of path traversal / private machine paths.
7. Upstream reconciliation: 196 disk dirs = 170 registry.json + 26 unbundled dirs;
   222 microcomponents; 8 examples.
8. Deterministic, idempotent scanner output.
"""

import json
import os
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "backend" / "catalog_inventory" / "hyperframes_196_inventory.json"
SHIPPED_BLOCKS_DIR = REPO_ROOT / "backend" / "catalog" / "shipped_blocks"
DONOR_PATH = Path(os.environ.get("HYPERFRAMES_DONOR_PATH", r"C:\Users\toddy\Desktop\hyperframes"))

EXPECTED_TEN_INTERNALIZED = {
    "aurora",
    "data-chart",
    "flowing-gradient",
    "holographic",
    "instagram-follow",
    "plasma",
    "stripes",
    "tiktok-follow",
    "weight-wave",
    "yt-lower-third",
}

EXPECTED_SIXCLIPS_AUTHORED = {
    "creator-hud",
    "glitch-transition",
}

EXPECTED_SEVENTEEN_ELIGIBLE = {
    "blob",
    "fractal-noise",
    "frost",
    "godrays",
    "goo",
    "lens-flare",
    "liquid-metal",
    "marble",
    "mesh-gradient",
    "nebula",
    "prism",
    "sine-wave",
    "strands",
    "swirl",
    "voronoi",
    "water",
    "waveform",
}

VALID_LICENSE_STATUSES = {
    "VERIFIED_PERMISSIVE",
    "VERIFIED_OTHER_OBLIGATIONS",
    "UNVERIFIED",
    "RESTRICTED",
}

VALID_INTEGRATION_STATUSES = {
    "INTERNALIZED",
    "ELIGIBLE_NOT_PORTED",
    "NEEDS_ADAPTATION",
    "BLOCKED_LICENSE",
    "BLOCKED_SECURITY",
    "BLOCKED_DEPENDENCY",
    "NOT_EVALUATED",
}


class TestWave14HyperFramesInventoryProvenance(unittest.TestCase):
    """Test suite for HyperFrames 196-block inventory and provenance manifest."""

    @classmethod
    def setUpClass(cls):
        if not MANIFEST_PATH.exists():
            raise FileNotFoundError(f"Inventory manifest not found at '{MANIFEST_PATH}'. Run scanner first.")
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            cls.manifest = json.load(f)
        cls.blocks = cls.manifest.get("blocks", [])

    def test_01_manifest_metadata_and_envelope(self):
        """Manifest envelope must follow v1 contract specification."""
        self.assertEqual(self.manifest.get("schema_version"), 1)
        self.assertEqual(self.manifest.get("source_inventory"), "HyperFrames")
        self.assertEqual(self.manifest.get("original_block_count"), 196)
        self.assertIsInstance(self.blocks, list)
        self.assertEqual(len(self.blocks), 196, "Manifest must contain precisely 196 block entries.")

    def test_02_no_duplicate_block_ids_and_safe_format(self):
        """Block IDs must be unique, non-empty, and match strict identifier regex."""
        ids = [b.get("id") for b in self.blocks]
        self.assertEqual(len(ids), 196)
        self.assertEqual(len(set(ids)), 196, "Block IDs must be strictly unique without collisions.")

        id_regex = re.compile(r"^[a-zA-Z0-9_\-]+$")
        for bid in ids:
            self.assertIsNotNone(bid)
            self.assertTrue(id_regex.match(bid), f"Invalid block identifier format: '{bid}'")
            self.assertNotIn("..", bid)
            self.assertNotIn("/", bid)
            self.assertNotIn("\\", bid)

    def test_03_strict_exclusion_of_6clips_blocks(self):
        """Original 6Clips-authored blocks must never count toward the 196 donor originals."""
        manifest_ids = {b.get("id") for b in self.blocks}
        for sc_id in EXPECTED_SIXCLIPS_AUTHORED:
            self.assertNotIn(
                sc_id,
                manifest_ids,
                f"Integrity error: 6Clips-authored block '{sc_id}' must NOT be in the 196 donor manifest.",
            )

    def test_04_reconciliation_of_ten_internalized_blocks(self):
        """Exactly 10 donor-original blocks must be marked INTERNALIZED and verified against shipped_blocks."""
        internalized = [b for b in self.blocks if b.get("integration_status") == "INTERNALIZED"]
        self.assertEqual(
            len(internalized),
            10,
            f"Expected exactly 10 INTERNALIZED blocks, found {len(internalized)}.",
        )

        internalized_ids = {b["id"] for b in internalized}
        self.assertEqual(
            internalized_ids,
            EXPECTED_TEN_INTERNALIZED,
            "Internalized block IDs do not match the canonical 10 donor blocks.",
        )

        for b in internalized:
            self.assertIsNone(b.get("blocker_reason"), f"Internalized block {b['id']} must have blocker_reason=None")
            # Verify physically present in backend/catalog/shipped_blocks
            shipped_dir = SHIPPED_BLOCKS_DIR / b["id"]
            self.assertTrue(
                shipped_dir.exists() and shipped_dir.is_dir(),
                f"Internalized block {b['id']} missing from shipped_blocks directory '{shipped_dir}'.",
            )
            # Must have valid license status
            self.assertIn(b["license_status"], ["VERIFIED_PERMISSIVE", "VERIFIED_OTHER_OBLIGATIONS"])

    def test_05_reconciliation_of_one_hundred_eighty_six_unported(self):
        """Exactly 186 donor-original blocks must have integration_status != INTERNALIZED."""
        unported = [b for b in self.blocks if b.get("integration_status") != "INTERNALIZED"]
        self.assertEqual(
            len(unported),
            186,
            f"Expected exactly 186 unported donor blocks, found {len(unported)}.",
        )

        # Count per status
        counts = {}
        for b in unported:
            stat = b["integration_status"]
            counts[stat] = counts.get(stat, 0) + 1
            if stat != "ELIGIBLE_NOT_PORTED":
                self.assertTrue(
                    b.get("blocker_reason"),
                    f"Blocked block '{b['id']}' must have a non-empty blocker_reason.",
                )

        self.assertIn("ELIGIBLE_NOT_PORTED", counts)
        self.assertIn("BLOCKED_DEPENDENCY", counts)
        self.assertIn("BLOCKED_LICENSE", counts)

    def test_06_seventeen_vetted_eligible_shader_candidates(self):
        """The 17 vetted self-contained WebGPU shader blocks must be marked ELIGIBLE_NOT_PORTED."""
        eligible = [b for b in self.blocks if b.get("integration_status") == "ELIGIBLE_NOT_PORTED"]
        self.assertEqual(
            len(eligible),
            17,
            f"Expected exactly 17 ELIGIBLE_NOT_PORTED candidates, found {len(eligible)}.",
        )

        eligible_ids = {b["id"] for b in eligible}
        self.assertEqual(
            eligible_ids,
            EXPECTED_SEVENTEEN_ELIGIBLE,
            "Eligible candidate IDs do not match vetted 17 shader blocks.",
        )

        for b in eligible:
            self.assertEqual(b["license_status"], "VERIFIED_PERMISSIVE")
            self.assertIsNone(b.get("blocker_reason"))
            # Must support 9:16 (responsive WebGPU viewport shader)
            self.assertIn("9:16", b["supported_aspects"])

    def test_07_valid_license_statuses(self):
        """All 196 blocks must have valid license status and non-empty license evidence."""
        for b in self.blocks:
            bid = b.get("id")
            lstat = b.get("license_status")
            self.assertIn(
                lstat,
                VALID_LICENSE_STATUSES,
                f"Block '{bid}' has invalid license_status: '{lstat}'",
            )
            evidence = b.get("license_evidence")
            self.assertTrue(
                evidence and isinstance(evidence, str) and len(evidence.strip()) > 0,
                f"Block '{bid}' has empty or invalid license_evidence.",
            )

    def test_08_valid_integration_statuses(self):
        """All 196 blocks must have valid integration status."""
        for b in self.blocks:
            bid = b.get("id")
            istat = b.get("integration_status")
            self.assertIn(
                istat,
                VALID_INTEGRATION_STATUSES,
                f"Block '{bid}' has invalid integration_status: '{istat}'",
            )

    def test_09_source_sha256_format_and_integrity(self):
        """All blocks must have deterministic 64-character hex source_sha256."""
        sha_regex = re.compile(r"^[0-9a-f]{64}$")
        for b in self.blocks:
            bid = b.get("id")
            sha = b.get("source_sha256")
            self.assertIsNotNone(sha)
            self.assertTrue(
                sha_regex.match(sha),
                f"Block '{bid}' has invalid source_sha256: '{sha}'",
            )

    def test_10_relative_source_paths_security_and_purity(self):
        """Relative source paths must start with 'registry/blocks/' and contain no machine paths."""
        for b in self.blocks:
            bid = b.get("id")
            rel_path = b.get("relative_source_path")
            self.assertEqual(rel_path, f"registry/blocks/{bid}")
            self.assertNotIn(":", rel_path)
            self.assertNotIn("\\", rel_path)
            self.assertNotIn("/Users/", rel_path)
            self.assertNotIn("Desktop", rel_path)

    def test_11_aspect_ratios_and_dimensions(self):
        """Dimensions and supported aspects must be populated and valid."""
        for b in self.blocks:
            bid = b.get("id")
            dims = b.get("dimensions", {})
            self.assertGreater(dims.get("width", 0), 0)
            self.assertGreater(dims.get("height", 0), 0)
            aspects = b.get("supported_aspects", [])
            self.assertIsInstance(aspects, list)
            self.assertGreater(len(aspects), 0, f"Block '{bid}' has empty supported_aspects")
            for asp in aspects:
                self.assertIn(asp, ["9:16", "16:9", "1:1", "4:5"])

    def test_12_evidence_refs_present(self):
        """Evidence references must be present and non-empty for every block."""
        for b in self.blocks:
            bid = b.get("id")
            refs = b.get("evidence_refs", [])
            self.assertIsInstance(refs, list)
            self.assertGreater(len(refs), 0, f"Block '{bid}' has no evidence_refs.")
            self.assertTrue(any(f"registry/blocks/{bid}" in r for r in refs))

    def test_13_upstream_census_reconciliation_math(self):
        """Reconciliation block must accurately reflect upstream inventory math."""
        reconc = self.manifest.get("reconciliation", {})
        self.assertEqual(reconc.get("historical_block_dirs"), 196)
        self.assertEqual(reconc.get("aggregate_manifest_blocks"), 170)
        self.assertEqual(reconc.get("unbundled_block_dirs"), 26)
        self.assertEqual(reconc.get("aggregate_components"), 222)
        self.assertEqual(reconc.get("aggregate_examples"), 8)
        self.assertEqual(
            reconc.get("aggregate_manifest_blocks") + reconc.get("unbundled_block_dirs"),
            196,
            "170 aggregated + 26 unbundled must equal 196 historical block directories.",
        )

    def test_14_scanner_verification_mode(self):
        """HyperFramesCensusScanner.verify_existing_manifest must pass on the active manifest."""
        from tools.wave14_hyperframes_inventory import HyperFramesCensusScanner
        scanner = HyperFramesCensusScanner(DONOR_PATH, REPO_ROOT)
        success, errors = scanner.verify_existing_manifest(MANIFEST_PATH)
        self.assertTrue(success, f"Scanner verification failed with errors: {errors}")
        self.assertEqual(len(errors), 0)


if __name__ == "__main__":
    unittest.main()
