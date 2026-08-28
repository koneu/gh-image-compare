#!/usr/bin/env python3
"""Generate a test PNG for exercising the image-diff pipeline.

Usage:
    python3 generate_test_image.py --variant 0 --out baseline.png
    python3 generate_test_image.py --variant 1 --out changed.png

Everything about the image is derived from --variant, so bumping that
one number is enough to produce a visibly different but same-shaped
image (color, shape position, and label all shift with it).
"""
import argparse
import colorsys

from PIL import Image, ImageDraw


def generate(variant: int, size: tuple[int, int] = (400, 300)) -> Image.Image:
    width, height = size
    hue = (variant * 47 % 360) / 360
    bg = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(hue, 0.25, 1.0))
    fg = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(hue, 0.85, 0.85))

    img = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(img)

    # Shape position walks across the canvas as variant increases.
    cx = 60 + (variant * 37) % (width - 120)
    cy = 60 + (variant * 23) % (height - 120)
    draw.ellipse((cx - 50, cy - 50, cx + 50, cy + 50), fill=fg)
    draw.rectangle((10, 10, width - 10, height - 10), outline=fg, width=3)
    draw.text((20, height - 30), f"variant {variant}", fill=fg)

    return img


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", type=int, default=0, help="any integer; changes color/shape/label")
    parser.add_argument("--out", default="test-image.png", help="output PNG path")
    args = parser.parse_args()

    generate(args.variant).save(args.out)
    print(f"wrote {args.out} (variant={args.variant})")


if __name__ == "__main__":
    main()
