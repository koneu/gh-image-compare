#!/usr/bin/env python3
"""Compare a candidate image against the current golden image.

Writes a GitHub Actions job summary (golden/candidate/diff inline as
base64 images) and sets step outputs: exceeds_threshold, diff_ratio,
mismatched_pixels, width, height.

Never fails on its own (exit code 0) so the summary always gets written;
the calling workflow step decides whether to fail the job based on the
exceeds_threshold output.
"""
import argparse
import base64
import os
from pathlib import Path

from PIL import Image


def b64_img(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def write_output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        print(f"{name}={value}")
        return
    with open(path, "a") as f:
        f.write(f"{name}={value}\n")


def write_summary(md: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        print(md)
        return
    with open(path, "a") as f:
        f.write(md)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--golden", help="path to golden image; omit if none exists yet")
    parser.add_argument("--diff-out", default="diff.png")
    parser.add_argument("--threshold", type=float, default=0.01, help="max allowed mismatch ratio (0-1)")
    args = parser.parse_args()

    candidate_path = Path(args.candidate)
    candidate = Image.open(candidate_path).convert("RGBA")

    if not args.golden or not Path(args.golden).exists():
        write_output("exceeds_threshold", "true")
        write_output("diff_ratio", "1.0")
        write_summary(
            "## Image comparison\n\n"
            "No golden image found yet — this run establishes the baseline.\n\n"
            f'<img src="data:image/png;base64,{b64_img(candidate_path)}" width="300" alt="candidate">\n\n'
            "If the promotion job is approved, this candidate becomes golden v1.\n"
        )
        return

    golden_path = Path(args.golden)
    golden = Image.open(golden_path).convert("RGBA")

    if golden.size != candidate.size:
        write_output("exceeds_threshold", "true")
        write_output("diff_ratio", "1.0")
        write_summary(
            "## Image comparison — FAIL (size mismatch)\n\n"
            f"Golden is {golden.size[0]}x{golden.size[1]}, "
            f"candidate is {candidate.size[0]}x{candidate.size[1]}.\n\n"
            "| Golden | Candidate |\n|:---:|:---:|\n"
            f'| <img src="data:image/png;base64,{b64_img(golden_path)}" width="300"> '
            f'| <img src="data:image/png;base64,{b64_img(candidate_path)}" width="300"> |\n'
        )
        return

    from pixelmatch.contrib.PIL import pixelmatch

    width, height = candidate.size
    diff_img = Image.new("RGBA", (width, height))
    mismatched = pixelmatch(golden, candidate, diff_img, includeAA=True)
    total = width * height
    ratio = mismatched / total
    exceeds = ratio > args.threshold

    diff_path = Path(args.diff_out)
    diff_img.save(diff_path)

    write_output("exceeds_threshold", "true" if exceeds else "false")
    write_output("diff_ratio", f"{ratio:.6f}")
    write_output("mismatched_pixels", str(mismatched))
    write_output("width", str(width))
    write_output("height", str(height))

    status = "FAIL" if exceeds else "PASS"
    write_summary(
        f"## Image comparison — {status}\n\n"
        f"- Mismatched pixels: **{mismatched}** / {total} ({ratio:.2%})\n"
        f"- Threshold: {args.threshold:.2%}\n\n"
        "| Golden | Candidate | Diff |\n|:---:|:---:|:---:|\n"
        f'| <img src="data:image/png;base64,{b64_img(golden_path)}" width="260"> '
        f'| <img src="data:image/png;base64,{b64_img(candidate_path)}" width="260"> '
        f'| <img src="data:image/png;base64,{b64_img(diff_path)}" width="260"> |\n'
    )


if __name__ == "__main__":
    main()
