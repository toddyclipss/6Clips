# SPDX-License-Identifier: AGPL-3.0-only
import json

d = json.load(open("scripts/qa_wave16/qa_adversarial_report.json"))
for x in d["tested_groups"]["newly_ported_nz"]:
    print(f"{x['id']:30}: status={x['motion']['status']:18} delta={x['motion']['delta']:<8} b1={x['motion']['brightness_t1']} b2={x['motion']['brightness_t2']}")
