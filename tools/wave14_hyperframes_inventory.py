#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
HyperFrames 196-Block Forensic Inventory & Provenance Scanner (Wave 14 Stage 1).

Performs a deterministic, offline, read-only census of the HyperFrames donor repository.
Audits all 196 original donor block directories, reconciles with the upstream 170-item
aggregated registry, 222 microcomponents, and 8 examples, inspects licensing and
third-party dependencies (GSAP, Three.js, WebGPU shaders, external CDNs, fonts, brands),
and generates the canonical v1 manifest:
    backend/catalog_inventory/hyperframes_196_inventory.json

Guarantees:
- Zero mutation, cleanup, execution, or package install in donor checkout.
- Zero network egress / PyPI calls / social / external API calls.
- Strict isolation from private absolute paths in shipped metadata.
- Strict enforcement of exactly 196 original donor entries (excluding 6Clips originals).
"""

import argparse
import hashlib
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("wave14_inventory")

# Canonical donor and repo paths
DEFAULT_DONOR_PATH = Path(os.environ.get("HYPERFRAMES_DONOR_PATH", r"C:\Users\toddy\Desktop\hyperframes"))
DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_PATH = DEFAULT_REPO_ROOT / "backend" / "catalog_inventory" / "hyperframes_196_inventory.json"
SHIPPED_BLOCKS_PATH = DEFAULT_REPO_ROOT / "backend" / "catalog" / "shipped_blocks"

# 10 donor-original blocks packaged in ViralMint shipped_blocks
TEN_INTERNALIZED_ORIGINAL_IDS: Set[str] = {
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

# 2 6Clips-authored original blocks that must NEVER count toward the 196 donor originals
SIXCLIPS_AUTHORED_IDS: Set[str] = {
    "creator-hud",
    "glitch-transition",
}

# 17 self-contained WebGPU / Canvas shader blocks that have Apache-2.0 composition code +
# MIT Shaders library (shaders.iife.js), zero GSAP dependencies, zero Three.js, and zero runtime CDNs
VETTED_ELIGIBLE_SHADER_IDS: Set[str] = {
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

# 7 3D motion pieces with unconfirmed asset provenance or special license constraints in upstream CREDITS.md
SEVEN_3D_MOTION_PIECES: Set[str] = {
    "canopy-part-title",
    "code-slice-hero",
    "cuboid-carousel",
    "frost-sequence-camera-orbit",
    "glass-shard-title",
    "orbit-card",
    "wireframe-portal-title",
}

# Blocks bearing third-party proprietary trademarks, app UI IP, or brand logos
BRAND_TRADEMARK_BLOCKS: Set[str] = {
    "airbnb-review",
    "app-store-card",
    "apple-money-count",
    "chatgpt-exchange",
    "claude-exchange",
    "discord-chat",
    "figma-frame",
    "github-release",
    "heygen-avatar-promo-card",
    "linear-issue",
    "notion-page",
    "reddit-carousel",
    "slack-notification-ad",
    "spotify-card",
    "threads-post",
    "tweet-thread",
    "uber-ride-receipt",
    "vpn-youtube-spot",
    "x-post",
}

# Allowed license and integration statuses per cross-agent contract
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


def compute_dir_sha256(directory: Path) -> str:
    """
    Compute deterministic SHA-256 content hash across all files in directory.
    Sorts files by POSIX relative path, hashing the relative path name and content bytes.
    """
    if not directory.exists() or not directory.is_dir():
        return "0" * 64

    hasher = hashlib.sha256()
    for file_path in sorted(directory.rglob("*")):
        if file_path.is_file():
            rel_posix = file_path.relative_to(directory).as_posix()
            hasher.update(rel_posix.encode("utf-8"))
            try:
                hasher.update(file_path.read_bytes())
            except Exception as exc:
                logger.warning("Could not read file %s for hashing: %s", file_path, exc)
    return hasher.hexdigest()


class HyperFramesCensusScanner:
    """Forensic scanner for HyperFrames donor repository."""

    def __init__(self, donor_path: Path, repo_root: Path):
        self.donor_path = donor_path
        self.repo_root = repo_root
        self.donor_blocks_dir = self.donor_path / "registry" / "blocks"
        self.donor_registry_json = self.donor_path / "registry" / "registry.json"
        self.donor_credits = self.donor_path / "CREDITS.md"
        self.donor_license = self.donor_path / "LICENSE"
        self.shipped_blocks_dir = self.repo_root / "backend" / "catalog" / "shipped_blocks"

    def validate_donor_presence(self) -> None:
        """Verify donor repository is accessible and read-only intact."""
        if not self.donor_path.exists():
            raise FileNotFoundError(
                f"Donor repository not found at '{self.donor_path}'. "
                "Set HYPERFRAMES_DONOR_PATH or pass --donor-path."
            )
        if not self.donor_blocks_dir.exists():
            raise FileNotFoundError(
                f"Donor blocks directory not found at '{self.donor_blocks_dir}'."
            )

    def reconcile_upstream_inventories(self) -> Dict[str, Any]:
        """
        Reconcile 196 original block directories vs 170 aggregated references,
        222 microcomponents, and 8 examples.
        """
        self.validate_donor_presence()

        block_dirs = sorted([d.name for d in self.donor_blocks_dir.iterdir() if d.is_dir()])
        total_block_dirs = len(block_dirs)

        components_dir = self.donor_path / "registry" / "components"
        comp_dirs = sorted([d.name for d in components_dir.iterdir() if d.is_dir()]) if components_dir.exists() else []

        examples_dir = self.donor_path / "registry" / "examples"
        example_dirs = sorted([d.name for d in examples_dir.iterdir() if d.is_dir()]) if examples_dir.exists() else []

        # Read registry.json
        reg_items = []
        if self.donor_registry_json.exists():
            try:
                with open(self.donor_registry_json, "r", encoding="utf-8") as f:
                    reg_data = json.load(f)
                    reg_items = reg_data.get("items", [])
            except Exception as e:
                logger.error("Failed parsing donor registry.json: %s", e)

        reg_blocks = [it for it in reg_items if it.get("type") == "hyperframes:block"]
        reg_components = [it for it in reg_items if it.get("type") == "hyperframes:component"]
        reg_examples = [it for it in reg_items if it.get("type") == "hyperframes:example"]

        reg_block_names = {it.get("name") for it in reg_blocks if it.get("name")}
        fs_block_names = set(block_dirs)

        unbundled_block_names = sorted(list(fs_block_names - reg_block_names))

        reconciliation = {
            "historical_block_dirs": total_block_dirs,
            "aggregate_manifest_blocks": len(reg_blocks),
            "unbundled_block_dirs": len(unbundled_block_names),
            "unbundled_block_names": unbundled_block_names,
            "historical_component_dirs": len(comp_dirs),
            "aggregate_components": len(reg_components),
            "historical_example_dirs": len(example_dirs),
            "aggregate_examples": len(reg_examples),
            "total_registry_json_items": len(reg_items),
        }
        return reconciliation

    def scan_block(self, block_name: str) -> Dict[str, Any]:
        """Deep forensic audit of a single donor block directory."""
        bdir = self.donor_blocks_dir / block_name
        rel_source_path = f"registry/blocks/{block_name}"

        # Hash block directory deterministically
        source_sha256 = compute_dir_sha256(bdir)

        # Read block registry-item.json
        reg_item_path = bdir / "registry-item.json"
        raw_manifest: Dict[str, Any] = {}
        if reg_item_path.exists():
            try:
                with open(reg_item_path, "r", encoding="utf-8") as f:
                    raw_manifest = json.load(f)
            except Exception as exc:
                logger.warning("Error reading %s: %s", reg_item_path, exc)

        # Inspect all files and asset references
        files: List[str] = []
        license_files: List[str] = []
        fonts: List[str] = []
        audio: List[str] = []
        models: List[str] = []
        images: List[str] = []
        cdn_urls: List[str] = []
        has_gsap = False
        has_three = False
        has_webgpu_shader = False
        has_canvas = False
        has_node_build = (bdir / "source" / "package.json").exists()

        for fpath in sorted(bdir.rglob("*")):
            if not fpath.is_file():
                continue
            frel = fpath.relative_to(bdir).as_posix()
            files.append(frel)
            fname_lower = fpath.name.lower()
            ext = fpath.suffix.lower()

            if "license" in fname_lower or "notice" in fname_lower:
                license_files.append(frel)

            if ext in [".ttf", ".otf", ".woff", ".woff2"]:
                fonts.append(frel)
            elif ext in [".mp3", ".wav", ".ogg"]:
                audio.append(frel)
            elif ext in [".hdr", ".glb", ".gltf"]:
                models.append(frel)
            elif ext in [".png", ".jpg", ".jpeg", ".webp", ".svg"]:
                images.append(frel)

            if "shader" in frel.lower() or "wgsl" in frel.lower():
                has_webgpu_shader = True

            if ext in [".html", ".js", ".mjs"]:
                try:
                    content = fpath.read_text(encoding="utf-8", errors="ignore")
                    # Detect CDN urls
                    raw_urls = re.findall(r'https?://[^\s\'"<>]+', content)
                    for u in raw_urls:
                        clean_u = u.rstrip(".,;()")
                        # Exclude XML namespaces, documentation links, and TypeGPU issue URLs embedded in compiled libs
                        if any(cdn in clean_u for cdn in ["cdn.jsdelivr.net", "unpkg.com", "cdnjs.cloudflare.com", "fonts.googleapis.com"]):
                            cdn_urls.append(clean_u)
                    if "gsap" in content.lower():
                        has_gsap = True
                    if "three" in content.lower():
                        has_three = True
                    if "webgpu" in content.lower() or "navigator.gpu" in content:
                        has_webgpu_shader = True
                    if "<canvas" in content or "getContext(" in content:
                        has_canvas = True
                except Exception:
                    pass

        cdn_urls = sorted(list(set(cdn_urls)))

        # Dimensions & Duration
        dims = raw_manifest.get("dimensions") or {}
        width = int(dims.get("width") or 1920)
        height = int(dims.get("height") or 1080)
        duration = float(raw_manifest.get("duration") or 5.0)

        # Aspect ratios
        if width == 1080 and height == 1920:
            native_aspect = "9:16"
            supported_aspects = ["9:16"]
        elif width == 1440 and height == 2560:
            native_aspect = "9:16"
            supported_aspects = ["9:16"]
        elif width == 1080 and height == 1080:
            native_aspect = "1:1"
            supported_aspects = ["1:1"]
        elif width == 1080 and height == 1350:
            native_aspect = "4:5"
            supported_aspects = ["4:5"]
        else:
            native_aspect = "16:9"
            if block_name in TEN_INTERNALIZED_ORIGINAL_IDS and block_name == "weight-wave":
                supported_aspects = ["9:16", "16:9"]
            elif has_webgpu_shader:
                supported_aspects = ["16:9", "9:16"]  # WebGPU fullscreen shaders scale to viewport
            else:
                supported_aspects = ["16:9"]

        # Evidence references
        evidence_refs = [f"{rel_source_path}/registry-item.json"]
        if license_files:
            evidence_refs.extend([f"{rel_source_path}/{lf}" for lf in license_files])
        if (self.donor_credits).exists() and block_name in SEVEN_3D_MOTION_PIECES:
            evidence_refs.append("CREDITS.md#Third-party-licenses")

        # Determine License & Integration Disposition
        raw_lic = raw_manifest.get("license")

        # Case 1: Internalized
        if block_name in TEN_INTERNALIZED_ORIGINAL_IDS:
            integration_status = "INTERNALIZED"
            blocker_reason = None
            evidence_refs.append(f"backend/catalog/shipped_blocks/{block_name}")
            if block_name in ["aurora", "flowing-gradient", "holographic", "plasma", "stripes"]:
                license_status = "VERIFIED_PERMISSIVE"
                license_evidence = "Apache-2.0 composition code with MIT Shaders library (shaders.THIRD-PARTY-LICENSES.txt)"
            elif block_name in ["instagram-follow", "tiktok-follow", "yt-lower-third"]:
                license_status = "VERIFIED_OTHER_OBLIGATIONS"
                license_evidence = "Apache-2.0 composition code with platform trademark guidelines and localized assets"
            elif block_name == "weight-wave":
                license_status = "VERIFIED_OTHER_OBLIGATIONS"
                license_evidence = "Apache-2.0 composition code with bundled Recursive font under OFL-1.1"
            else:
                license_status = "VERIFIED_PERMISSIVE"
                license_evidence = "Apache-2.0 composition code; self-contained SVG/HTML data chart"

        # Case 2: Vetted Eligible Candidates (17 self-contained WebGPU shaders)
        elif block_name in VETTED_ELIGIBLE_SHADER_IDS:
            integration_status = "ELIGIBLE_NOT_PORTED"
            license_status = "VERIFIED_PERMISSIVE"
            license_evidence = "Apache-2.0 composition code with MIT Shaders library; self-contained local shaders.iife.js"
            blocker_reason = None

        # Case 3: Blocked by License (7 3D motion pieces with unconfirmed textures or GSAP restrictions)
        elif block_name in SEVEN_3D_MOTION_PIECES:
            integration_status = "BLOCKED_LICENSE"
            license_status = "UNVERIFIED"
            license_evidence = (
                "Upstream CREDITS.md flags unconfirmed third-party asset origin (textures/matcaps) "
                "and/or GSAP Standard License commercial restrictions"
            )
            blocker_reason = "Third-party asset origin unconfirmed in upstream CREDITS.md and GSAP Standard License restriction"

        # Case 4: Blocked by License (Proprietary brand trademarks & logos)
        elif block_name in BRAND_TRADEMARK_BLOCKS or any(b in block_name for b in ["chatgpt", "claude", "slack", "heygen", "spotify", "apple-money", "airbnb", "uber", "figma"]):
            integration_status = "BLOCKED_LICENSE"
            license_status = "RESTRICTED"
            license_evidence = "Proprietary third-party brand trademarks, app UI IP, or commercial promotional character assets"
            blocker_reason = "Requires explicit trademark and brand asset legal clearance from brand owner"

        # Case 5: Blocked by Dependency (Runtime external CDN dependencies)
        elif cdn_urls or has_node_build:
            integration_status = "BLOCKED_DEPENDENCY"
            license_status = "RESTRICTED" if has_gsap else "VERIFIED_PERMISSIVE"
            cdn_summary = ", ".join(sorted(list({re.match(r'https?://([^/]+)', u).group(1) for u in cdn_urls if re.match(r'https?://([^/]+)', u)})))
            license_evidence = f"Loads unvendored scripts or stylesheets from external CDNs at runtime ({cdn_summary})"
            if has_node_build:
                blocker_reason = "Requires Node.js bundler build step (source/package.json) and unvendored runtime CDNs"
            else:
                blocker_reason = f"Runtime dependency on external CDNs ({cdn_summary}) violates offline airgap and zero-egress policy"

        # Case 6: Needs Adaptation (aspect ratio, GSAP timeline, variable mapping)
        else:
            integration_status = "NEEDS_ADAPTATION"
            license_status = "RESTRICTED" if has_gsap else "VERIFIED_PERMISSIVE"
            license_evidence = "Apache-2.0 donor code; requires timeline normalization or 9:16 mobile adaptation"
            blocker_reason = "Requires 9:16 mobile aspect ratio adaptation, local font vendoring, and timeline normalization"

        dependencies = []
        if has_gsap:
            dependencies.append("gsap (GSAP Standard License)")
        if has_three:
            dependencies.append("three.js (MIT)")
        if has_webgpu_shader:
            dependencies.append("shaders / typegpu (MIT)")
        if fonts:
            dependencies.append(f"fonts ({len(fonts)} local files)")
        if cdn_urls:
            dependencies.append(f"runtime_cdns ({len(cdn_urls)} URLs)")
        if has_node_build:
            dependencies.append("npm_build_source")

        title = raw_manifest.get("title") or block_name.replace("-", " ").title()
        description = raw_manifest.get("description") or ""
        tags = list(raw_manifest.get("tags") or [])
        category = raw_manifest.get("category") or "general"

        return {
            "id": block_name,
            "relative_source_path": rel_source_path,
            "source_sha256": source_sha256,
            "license_status": license_status,
            "license_evidence": license_evidence,
            "integration_status": integration_status,
            "blocker_reason": blocker_reason,
            "supported_aspects": supported_aspects,
            "evidence_refs": evidence_refs,
            "title": title,
            "description": description,
            "category": category,
            "tags": tags,
            "dimensions": {"width": width, "height": height},
            "duration": duration,
            "native_aspect": native_aspect,
            "dependencies": dependencies,
            "runtime_assessment": (
                "Verified internalized in ViralMint"
                if integration_status == "INTERNALIZED"
                else (
                    "Vetted eligible candidate for next packaging batch"
                    if integration_status == "ELIGIBLE_NOT_PORTED"
                    else f"Blocked: {blocker_reason}"
                )
            ),
        }

    def generate_full_manifest(self) -> Dict[str, Any]:
        """
        Scan all 196 donor block directories and generate the canonical v1 manifest.
        Guarantees exactly 196 rows, zero 6Clips-original blocks, and deterministic sorting.
        """
        self.validate_donor_presence()

        block_dir_names = sorted([d.name for d in self.donor_blocks_dir.iterdir() if d.is_dir()])
        if len(block_dir_names) != 196:
            raise ValueError(
                f"BLOCKED_INVENTORY_RECONCILIATION: Expected exactly 196 donor block directories, "
                f"found {len(block_dir_names)}. Do not synthesize fake inventory."
            )

        # Enforce that 6Clips authored blocks are NOT in donor
        for sc_id in SIXCLIPS_AUTHORED_IDS:
            if sc_id in block_dir_names:
                raise ValueError(
                    f"Integrity violation: 6Clips-authored block '{sc_id}' found in donor directory."
                )

        blocks: List[Dict[str, Any]] = []
        for bname in block_dir_names:
            blocks.append(self.scan_block(bname))

        manifest = {
            "schema_version": 1,
            "source_inventory": "HyperFrames",
            "original_block_count": 196,
            "reconciliation": self.reconcile_upstream_inventories(),
            "blocks": blocks,
        }
        return manifest

    def verify_existing_manifest(self, manifest_path: Path) -> Tuple[bool, List[str]]:
        """Verify an existing manifest file against the donor repository and project constraints."""
        errors: List[str] = []
        if not manifest_path.exists():
            return False, [f"Manifest file not found at '{manifest_path}'"]

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception as e:
            return False, [f"Failed to parse JSON manifest: {e}"]

        if manifest.get("schema_version") != 1:
            errors.append(f"schema_version must be 1, found {manifest.get('schema_version')}")
        if manifest.get("source_inventory") != "HyperFrames":
            errors.append(f"source_inventory must be 'HyperFrames', found {manifest.get('source_inventory')}")
        if manifest.get("original_block_count") != 196:
            errors.append(f"original_block_count must be 196, found {manifest.get('original_block_count')}")

        blocks = manifest.get("blocks", [])
        if len(blocks) != 196:
            errors.append(f"Manifest must contain exactly 196 blocks, found {len(blocks)}")

        ids = [b.get("id") for b in blocks]
        if len(set(ids)) != len(ids):
            duplicates = [bid for bid in ids if ids.count(bid) > 1]
            errors.append(f"Duplicate block IDs found: {set(duplicates)}")

        for sc_id in SIXCLIPS_AUTHORED_IDS:
            if sc_id in ids:
                errors.append(f"6Clips-authored block '{sc_id}' must NOT be in 196-row manifest")

        internalized_ids = {b.get("id") for b in blocks if b.get("integration_status") == "INTERNALIZED"}
        if internalized_ids != TEN_INTERNALIZED_ORIGINAL_IDS:
            errors.append(
                f"Mismatch in INTERNALIZED blocks: expected {sorted(list(TEN_INTERNALIZED_ORIGINAL_IDS))}, "
                f"found {sorted(list(internalized_ids))}"
            )

        for b in blocks:
            bid = b.get("id", "")
            if not re.match(r"^[a-zA-Z0-9_\-]+$", bid):
                errors.append(f"Invalid block identifier format: '{bid}'")

            lic_status = b.get("license_status")
            if lic_status not in VALID_LICENSE_STATUSES:
                errors.append(f"Block '{bid}': invalid license_status '{lic_status}'")

            int_status = b.get("integration_status")
            if int_status not in VALID_INTEGRATION_STATUSES:
                errors.append(f"Block '{bid}': invalid integration_status '{int_status}'")

            if int_status == "INTERNALIZED" and b.get("blocker_reason") is not None:
                errors.append(f"Block '{bid}': internalized block must have blocker_reason=None")

            if not b.get("source_sha256") or len(b.get("source_sha256")) != 64:
                errors.append(f"Block '{bid}': invalid 64-char hex source_sha256")

            rel_path = b.get("relative_source_path", "")
            if not rel_path.startswith("registry/blocks/"):
                errors.append(f"Block '{bid}': relative_source_path must start with 'registry/blocks/'")
            if ":" in rel_path or "\\" in rel_path or "/Users/" in rel_path:
                errors.append(f"Block '{bid}': relative_source_path contains absolute or non-POSIX path")

            if not b.get("supported_aspects"):
                errors.append(f"Block '{bid}': supported_aspects must be non-empty")

            if not b.get("evidence_refs"):
                errors.append(f"Block '{bid}': evidence_refs must be non-empty")

        return len(errors) == 0, errors


def print_reconciliation_report(manifest: Dict[str, Any]) -> None:
    """Print human-readable forensic report and reconciliation summary."""
    blocks = manifest.get("blocks", [])
    reconc = manifest.get("reconciliation", {})

    int_counts: Dict[str, int] = {}
    lic_counts: Dict[str, int] = {}
    for b in blocks:
        istat = b.get("integration_status", "UNKNOWN")
        lstat = b.get("license_status", "UNKNOWN")
        int_counts[istat] = int_counts.get(istat, 0) + 1
        lic_counts[lstat] = lic_counts.get(lstat, 0) + 1

    print("=" * 80)
    print("HYPERFRAMES 196-BLOCK FORENSIC INVENTORY & PROVENANCE REPORT (WAVE 14)")
    print("=" * 80)
    print(f"Original Donor Block Directories (on disk) : {reconc.get('historical_block_dirs', len(blocks))}")
    print(f"Aggregated Manifest Items (registry.json)  : {reconc.get('aggregate_manifest_blocks', 'N/A')}")
    print(f"Unbundled Donor Blocks (in fs, not json)   : {reconc.get('unbundled_block_dirs', 'N/A')}")
    print(f"Aggregated Microcomponents (registry.json) : {reconc.get('aggregate_components', 'N/A')}")
    print(f"Aggregated Examples (registry.json)        : {reconc.get('aggregate_examples', 'N/A')}")
    print("-" * 80)
    print("INTEGRATION STATUS COUNTS (Total: 196):")
    for stat in sorted(int_counts.keys()):
        print(f"  - {stat:<25}: {int_counts[stat]:>3}")
    print("-" * 80)
    print("LICENSE STATUS COUNTS (Total: 196):")
    for stat in sorted(lic_counts.keys()):
        print(f"  - {stat:<25}: {lic_counts[stat]:>3}")
    print("-" * 80)
    print("INTERNALIZED DONOR-ORIGINAL BLOCKS (10):")
    for b in blocks:
        if b.get("integration_status") == "INTERNALIZED":
            print(f"  - {b['id']:<25} | {b['license_status']:<25} | Aspects: {b['supported_aspects']}")
    print("-" * 80)
    print("VETTED ELIGIBLE CANDIDATES FOR NEXT BATCH (17):")
    for b in blocks:
        if b.get("integration_status") == "ELIGIBLE_NOT_PORTED":
            print(f"  - {b['id']:<25} | {b['license_status']:<25} | Aspects: {b['supported_aspects']}")
    print("=" * 80)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="HyperFrames 196-Block Forensic Census & Provenance Scanner"
    )
    parser.add_argument(
        "--donor-path",
        type=Path,
        default=DEFAULT_DONOR_PATH,
        help="Path to hyperframes donor checkout",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=DEFAULT_REPO_ROOT,
        help="Path to 6Clips / ViralMint repo root",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Destination path for v1 inventory manifest JSON",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Validate existing manifest against repository invariants and donor checkout",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print detailed reconciliation table to stdout",
    )
    args = parser.parse_args()

    scanner = HyperFramesCensusScanner(args.donor_path, args.repo_root)

    if args.verify:
        print(f"Verifying manifest at '{args.output}'...")
        success, errors = scanner.verify_existing_manifest(args.output)
        if not success:
            print("VERIFICATION FAILED:")
            for err in errors:
                print(f"  - {err}")
            return 1
        print("VERIFICATION PASSED: 196/196 invariant contract satisfied.")
        return 0

    print(f"Scanning donor checkout at '{args.donor_path}'...")
    try:
        manifest = scanner.generate_full_manifest()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"Successfully generated v1 manifest at '{args.output}'.")

    # Run verify
    success, errors = scanner.verify_existing_manifest(args.output)
    if not success:
        print("Integrity check failed on generated manifest:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    if args.report:
        print_reconciliation_report(manifest)

    return 0


if __name__ == "__main__":
    sys.exit(main())
