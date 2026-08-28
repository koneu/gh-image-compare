#!/usr/bin/env python3
"""Render the image-comparison job summary from precomputed stats and
already-hosted image URLs.

GitHub strips data: URI images from job-summary <img> tags, so images
must be reachable over https to actually show up — the workflow uploads
candidate/diff previews to Cloudsmith and passes their URLs in here
rather than local file paths.
"""
import argparse
import os


def write_summary(md: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        print(md)
        return
    with open(path, "a") as f:
        f.write(md)


def img(url: str | None, label: str, width: int = 260) -> str:
    if not url:
        return f"*(no {label.lower()})*"
    return f'<img src="{url}" width="{width}" alt="{label}">'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", default="output")
    parser.add_argument("--status", required=True, choices=["bootstrap", "size_mismatch", "compared"])
    parser.add_argument("--golden-url")
    parser.add_argument("--candidate-url", required=True)
    parser.add_argument("--diff-url")
    parser.add_argument("--golden-size")
    parser.add_argument("--candidate-size")
    parser.add_argument("--ssim-score", type=float)
    parser.add_argument("--min-ssim", type=float, required=True)
    args = parser.parse_args()

    if args.status == "bootstrap":
        write_summary(
            f"## Image comparison: {args.component}\n\n"
            "No golden image found yet — this run establishes the baseline.\n\n"
            f"{img(args.candidate_url, 'Candidate')}\n\n"
            "If the promotion job is approved, this candidate becomes golden v1.\n"
        )
        return

    if args.status == "size_mismatch":
        write_summary(
            f"## Image comparison: {args.component} — FAIL (size mismatch)\n\n"
            f"Golden is {args.golden_size}, candidate is {args.candidate_size}.\n\n"
            "| Golden | Candidate |\n|:---:|:---:|\n"
            f"| {img(args.golden_url, 'Golden')} | {img(args.candidate_url, 'Candidate')} |\n"
        )
        return

    exceeds = args.ssim_score < args.min_ssim
    status_label = "FAIL" if exceeds else "PASS"
    write_summary(
        f"## Image comparison: {args.component} — {status_label}\n\n"
        f"- SSIM score: **{args.ssim_score:.4f}** (1.0 = identical)\n"
        f"- Minimum required: {args.min_ssim:.4f}\n\n"
        "| Golden | Candidate | Diff (red = structurally dissimilar) |\n|:---:|:---:|:---:|\n"
        f"| {img(args.golden_url, 'Golden')} | {img(args.candidate_url, 'Candidate')} | {img(args.diff_url, 'Diff')} |\n"
    )


if __name__ == "__main__":
    main()
