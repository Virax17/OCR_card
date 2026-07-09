"""Generate CardScan PWA icon PNGs (regular + maskable) into static/icons/."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

INK = (20, 33, 61, 255)
TEAL = (15, 118, 110, 255)
AMBER = (234, 115, 23, 255)
OUT_DIR = Path(__file__).resolve().parent.parent / "static" / "icons"


def gradient_tile(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), INK)
    top_left, bottom_right = TEAL, AMBER
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * size)
            r = int(top_left[0] + (bottom_right[0] - top_left[0]) * t)
            g = int(top_left[1] + (bottom_right[1] - top_left[1]) * t)
            b = int(top_left[2] + (bottom_right[2] - top_left[2]) * t)
            img.putpixel((x, y), (r, g, b, 255))
    return img


def rounded_mask(size: int, radius_ratio: float) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    radius = int(size * radius_ratio)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return mask


def draw_cs(img: Image.Image, size: int, scale: float) -> None:
    draw = ImageDraw.Draw(img)
    font_size = int(size * scale)
    try:
        font = ImageFont.truetype("arialbd.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()
    text = "CS"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1]), text, font=font, fill=(255, 255, 255, 255))


def make_icon(size: int, maskable: bool) -> Image.Image:
    if maskable:
        # Safe zone: keep artwork within the inner ~80% for maskable icons.
        canvas = Image.new("RGBA", (size, size), INK)
        inner_size = int(size * 0.8)
        tile = gradient_tile(inner_size)
        draw_cs(tile, inner_size, 0.42)
        offset = (size - inner_size) // 2
        canvas.paste(tile, (offset, offset))
        return canvas
    tile = gradient_tile(size)
    mask = rounded_mask(size, 0.22)
    draw_cs(tile, size, 0.42)
    rounded = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    rounded.paste(tile, (0, 0), mask)
    return rounded


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        make_icon(size, maskable=False).save(OUT_DIR / f"icon-{size}.png")
        make_icon(size, maskable=True).save(OUT_DIR / f"icon-{size}-maskable.png")
    print(f"Icons written to {OUT_DIR}")


if __name__ == "__main__":
    main()
