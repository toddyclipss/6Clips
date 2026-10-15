#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
import os
import json
import re

def main():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    evidence_path = os.path.join(root, "tools", "wave18_a2", "preview_evidence_table.json")
    with open(evidence_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    passes = sorted([r["donor_slug"] for r in data["records"] if r["status"] == "LIVE_PREVIEW_PASS"])
    assert len(passes) == 149, f"Expected 149 passes, got {len(passes)}"

    catalog_path = os.path.join(root, "frontend", "src", "utils", "catalogOriginals.js")
    with open(catalog_path, "r", encoding="utf-8") as f:
        code = f.read()

    # Create the SHIPPED_OPERATIONAL_IDS set string
    shipped_slugs_code = "export const SHIPPED_OPERATIONAL_IDS = new Set([\n" + "\n".join(f"  '{s}'," for s in passes) + "\n])\n"

    # Replace DONOR_PACKAGED_IDS section
    old_packaged_block = re.search(r"export const DONOR_PACKAGED_IDS = new Set\(\[[^\]]*\]\)", code)
    if not old_packaged_block:
        raise ValueError("Could not find DONOR_PACKAGED_IDS block in catalogOriginals.js")

    new_packaged_block = (
        shipped_slugs_code + "\n"
        "/**\n"
        " * Packaged and operable donor blocks (149 active shipped blocks + 10 baseline internalized)\n"
        " */\n"
        "export const DONOR_PACKAGED_IDS = new Set([\n"
        "  ...SHIPPED_OPERATIONAL_IDS,\n"
        "  ...DONOR_INTERNALIZED_IDS,\n"
        "])"
    )

    code = code[:old_packaged_block.start()] + new_packaged_block + code[old_packaged_block.end():]

    # Update normalizeDonorBlock logic
    old_norm_snippet = """  const isOperational = isInternalized
  const isInsertable = isInternalized || Boolean(rawBlock.runtime_operable)"""

    new_norm_snippet = """  const isOperational = SHIPPED_OPERATIONAL_IDS.has(id) || isInternalized || Boolean(rawBlock.is_operational) || Boolean(rawBlock.isOperational)
  const isInsertable = isOperational"""

    if old_norm_snippet in code:
        code = code.replace(old_norm_snippet, new_norm_snippet)
    else:
        print("Warning: old_norm_snippet not found directly")

    # Update clean status calculation
    old_status_snippet = """  // Clean status calculation
  let statusLabel = 'NEEDS ADAPTATION'
  let integrationStatus = rawBlock.integration_status || 'NEEDS_ADAPTATION'
  let runtimeStatus = rawBlock.runtime_status || 'NEEDS_ADAPTATION'

  if (isInternalized) {
    statusLabel = 'OPERATIONAL'
    integrationStatus = 'INTERNALIZED'
    runtimeStatus = 'INTERNALIZED_WORKING'
  } else if (isShader) {
    statusLabel = 'PACKAGED SHADER'
    integrationStatus = 'SHIPPED_SHADER'
    runtimeStatus = 'PACKAGED_PORTED'
  } else if (isLowerThird) {
    statusLabel = 'PACKAGED LOWER-THIRD'
    integrationStatus = 'SHIPPED_LOWER_THIRD'
    runtimeStatus = 'PACKAGED_PORTED'
  } else if (isPackaged) {
    statusLabel = 'PACKAGED'
    integrationStatus = 'PACKAGED_PORTED'
    runtimeStatus = 'PACKAGED_PORTED'
  } else if (rawBlock.integration_status === 'BLOCKED_LICENSE' || rawBlock.license_status === 'RESTRICTED') {
    statusLabel = 'BLOCKED LICENSE'
    integrationStatus = 'BLOCKED_LICENSE'
    runtimeStatus = 'BLOCKED_LICENSE'
  } else if (rawBlock.integration_status === 'BLOCKED_DEPENDENCY') {
    statusLabel = 'BLOCKED DEPENDENCY'
    integrationStatus = 'BLOCKED_DEPENDENCY'
    runtimeStatus = 'BLOCKED_DEPENDENCY'
  }"""

    new_status_snippet = """  // Clean status calculation
  const isShipped = SHIPPED_OPERATIONAL_IDS.has(id)
  let statusLabel = isShipped ? 'OPERATIONAL' : 'STAGE 2 AWAITING PORT'
  let integrationStatus = isShipped ? 'SHIPPED_OPERATIONAL' : (rawBlock.integration_status || 'STAGE2_AWAITING_PORT')
  let runtimeStatus = isShipped ? 'OPERATIONAL' : (rawBlock.runtime_status || 'AWAITING_PORT')

  if (isShipped) {
    statusLabel = 'OPERATIONAL'
    integrationStatus = 'SHIPPED_OPERATIONAL'
    runtimeStatus = 'OPERATIONAL'
  } else if (isInternalized) {
    statusLabel = 'OPERATIONAL'
    integrationStatus = 'INTERNALIZED'
    runtimeStatus = 'INTERNALIZED_WORKING'
  } else if (rawBlock.integration_status === 'BLOCKED_LICENSE' || rawBlock.license_status === 'RESTRICTED') {
    statusLabel = 'BLOCKED LICENSE'
    integrationStatus = 'BLOCKED_LICENSE'
    runtimeStatus = 'BLOCKED_LICENSE'
  } else if (rawBlock.integration_status === 'BLOCKED_DEPENDENCY') {
    statusLabel = 'BLOCKED DEPENDENCY'
    integrationStatus = 'BLOCKED_DEPENDENCY'
    runtimeStatus = 'BLOCKED_DEPENDENCY'
  }"""

    if old_status_snippet in code:
        code = code.replace(old_status_snippet, new_status_snippet)
    else:
        print("Warning: old_status_snippet not found directly")

    with open(catalog_path, "w", encoding="utf-8") as f:
        f.write(code)

    print("Successfully updated catalogOriginals.js with 149 SHIPPED_OPERATIONAL_IDS!")

if __name__ == "__main__":
    main()
