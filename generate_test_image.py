#!/usr/bin/env python3
"""Generate a test PNG for exercising the image-diff pipeline.

Usage:
    python3 generate_test_image.py --variant 0 --out baseline.png
    python3 generate_test_image.py --variant 1 --out changed.png
    python3 generate_test_image.py --component button --variant 0 --out button.png
    python3 generate_test_image.py --component button --image hover --out button-hover.png

Everything about the image is derived from --variant, so bumping that
one number is enough to produce a visibly different but same-shaped
image (color, shape position, and label all shift with it).

--component picks a different base look per named component (so
multiple "component tests" can be simulated from this one script), and
--image lets one component produce more than one picture (e.g. several
states/screenshots from a single test) - both offset the variant with a
hash of their name. "output" and "default" are special-cased to offset
0 so this stays backward compatible with goldens generated before
--component/--image existed.
"""
import argparse
import colorsys
import hashlib

from PIL import Image, ImageDraw


def component_offset(component: str) -> int:
    if component == "output":
        return 0
    return int(hashlib.sha256(component.encode()).hexdigest(), 16) % 1000


def image_offset(image: str) -> int:
    if image == "default":
        return 0
    return int(hashlib.sha256(image.encode()).hexdigest(), 16) % 1000


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
    parser.add_argument("--component", default="output", help="component name; picks a distinct base look")
    parser.add_argument("--image", default="default", help="image name within the component; picks a distinct base look")
    parser.add_argument("--variant", type=int, default=0, help="any integer; changes color/shape/label")
    parser.add_argument("--out", default="test-image.png", help="output PNG path")
    args = parser.parse_args()

    effective_variant = component_offset(args.component) + image_offset(args.image) + args.variant
    generate(effective_variant).save(args.out)
    print(f"wrote {args.out} (component={args.component}, image={args.image}, variant={args.variant})")


if __name__ == "__main__":
    main()
