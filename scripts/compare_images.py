#!/usr/bin/env python3
"""Compute the pixel diff between a candidate image and the current golden image.

Sets step outputs: status (bootstrap|size_mismatch|compared), exceeds_threshold,
diff_ratio, mismatched_pixels, total_pixels, golden_size, candidate_size.
Writes a diff image to --diff-out only when status is 'compared'.

Never fails on its own (exit code 0); the calling workflow step decides
whether to fail the job based on the exceeds_threshold output. Image
rendering is handled separately by render_summary.py, since it needs
externally-hosted URLs rather than local paths (GitHub strips data: URIs
from job-summary <img> tags).
"""
import argparse
import os
from pathlib import Path

from PIL import Image


def write_output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        print(f"{name}={value}")
        return
    with open(path, "a") as f:
        f.write(f"{name}={value}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--golden", help="path to golden image; omit if none exists yet")
    parser.add_argument("--diff-out", default="diff.png")
    parser.add_argument("--threshold", type=float, default=0.01, help="max allowed mismatch ratio (0-1)")
    args = parser.parse_args()

    candidate_path = Path(args.candidate)
    candidate = Image.open(candidate_path).convert("RGBA")
    write_output("candidate_size", f"{candidate.size[0]}x{candidate.size[1]}")

    if not args.golden or not Path(args.golden).exists():
        write_output("status", "bootstrap")
        write_output("exceeds_threshold", "true")
        write_output("diff_ratio", "1.0")
        return

    golden_path = Path(args.golden)
    golden = Image.open(golden_path).convert("RGBA")
    write_output("golden_size", f"{golden.size[0]}x{golden.size[1]}")

    if golden.size != candidate.size:
        write_output("status", "size_mismatch")
        write_output("exceeds_threshold", "true")
        write_output("diff_ratio", "1.0")
        return

    from pixelmatch.contrib.PIL import pixelmatch

    width, height = candidate.size
    diff_img = Image.new("RGBA", (width, height))
    mismatched = pixelmatch(golden, candidate, diff_img, includeAA=True)
    total = width * height
    ratio = mismatched / total
    exceeds = ratio > args.threshold

    diff_img.save(args.diff_out)

    write_output("status", "compared")
    write_output("exceeds_threshold", "true" if exceeds else "false")
    write_output("diff_ratio", f"{ratio:.6f}")
    write_output("mismatched_pixels", str(mismatched))
    write_output("total_pixels", str(total))


if __name__ == "__main__":
    main()
