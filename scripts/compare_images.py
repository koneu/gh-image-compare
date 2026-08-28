#!/usr/bin/env python3
"""Compute the structural similarity (SSIM) between a candidate image and
the current golden image.

SSIM is used instead of a raw pixel diff because rendered (e.g. OpenGL)
output varies slightly between GPUs/drivers — anti-aliasing, dithering,
float precision — without being a real regression. SSIM measures
structural/perceptual similarity rather than pixel-exact equality, so it
tolerates that noise while still catching real visual changes.

Sets step outputs: status (bootstrap|size_mismatch|compared),
exceeds_threshold, ssim_score, golden_size, candidate_size.
Writes a heatmap diff to --diff-out only when status is 'compared': the
grayscale candidate with red bleeding in proportional to local
dissimilarity, so both *where* and *how much* something changed is
visible at a glance.

Never fails on its own (exit code 0); the calling workflow step decides
whether to fail the job based on the exceeds_threshold output. Image
rendering is handled separately by render_summary.py, since it needs
externally-hosted URLs rather than local paths (GitHub strips data: URIs
from job-summary <img> tags).
"""
import argparse
import os
from pathlib import Path

import numpy as np
from PIL import Image


def write_output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        print(f"{name}={value}")
        return
    with open(path, "a") as f:
        f.write(f"{name}={value}\n")


def render_heatmap_diff(candidate_rgb: np.ndarray, ssim_map: np.ndarray) -> Image.Image:
    """Grayscale candidate with red bleeding in where SSIM is locally low."""
    dissimilarity = np.clip(1 - ssim_map, 0, 1).mean(axis=2)  # (H, W), 0=identical, 1=totally different
    base = np.array(Image.fromarray(candidate_rgb).convert("L")).astype(float)
    base_rgb = np.stack([base] * 3, axis=-1)
    red = np.array([255, 40, 40], dtype=float)
    heat = dissimilarity[..., None]
    blended = base_rgb * (1 - heat) + red * heat
    return Image.fromarray(np.clip(blended, 0, 255).astype(np.uint8))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--golden", help="path to golden image; omit if none exists yet")
    parser.add_argument("--diff-out", default="diff.png")
    parser.add_argument("--min-ssim", type=float, default=0.98, help="minimum acceptable SSIM score (0-1)")
    args = parser.parse_args()

    candidate_path = Path(args.candidate)
    candidate_img = Image.open(candidate_path).convert("RGB")
    write_output("candidate_size", f"{candidate_img.size[0]}x{candidate_img.size[1]}")

    if not args.golden or not Path(args.golden).exists():
        write_output("status", "bootstrap")
        write_output("exceeds_threshold", "true")
        write_output("ssim_score", "0.0")
        return

    golden_path = Path(args.golden)
    golden_img = Image.open(golden_path).convert("RGB")
    write_output("golden_size", f"{golden_img.size[0]}x{golden_img.size[1]}")

    if golden_img.size != candidate_img.size:
        write_output("status", "size_mismatch")
        write_output("exceeds_threshold", "true")
        write_output("ssim_score", "0.0")
        return

    from skimage.metrics import structural_similarity

    golden_arr = np.array(golden_img)
    candidate_arr = np.array(candidate_img)
    score, ssim_map = structural_similarity(golden_arr, candidate_arr, channel_axis=-1, full=True)
    exceeds = score < args.min_ssim

    render_heatmap_diff(candidate_arr, ssim_map).save(args.diff_out)

    write_output("status", "compared")
    write_output("exceeds_threshold", "true" if exceeds else "false")
    write_output("ssim_score", f"{score:.6f}")


if __name__ == "__main__":
    main()
