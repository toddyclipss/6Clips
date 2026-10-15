#!/usr/bin/env python3
import hashlib
from pathlib import Path

donor_cuboid = Path(r"C:\Users\toddy\Desktop\hyperframes\registry\blocks\cuboid-carousel\assets")
gsap_f = donor_cuboid / "gsap-3.14.2.min.js"
three_f = donor_cuboid / "three.core.min.js"

print("GSAP exists:", gsap_f.exists(), "size:", gsap_f.stat().st_size, "sha256:", hashlib.sha256(gsap_f.read_bytes()).hexdigest())
print("Three exists:", three_f.exists(), "size:", three_f.stat().st_size, "sha256:", hashlib.sha256(three_f.read_bytes()).hexdigest())
