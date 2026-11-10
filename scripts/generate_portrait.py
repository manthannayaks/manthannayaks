#!/usr/bin/env python3
"""Generate assets/portrait-src.png (halftone portrait) from assets/portrait.png.

Processes the original photo with background removal, tone mapping,
and high-resolution halftone dot screening, quantizing the result into a clean
monochrome 4-bit PNG suitable for profile_card.py.
"""
import math
import os
import sys
from PIL import Image, ImageDraw, ImageEnhance, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_PATH = os.path.join(ROOT, "assets", "portrait.png")
OUT_PATH = os.path.join(ROOT, "assets", "portrait-src.png")


def remove_background(img: Image.Image) -> Image.Image:
    """Isolate subject using rembg u2netp model, with fallback."""
    try:
        from rembg import new_session, remove
        session = new_session("u2netp")
        nobg = remove(img, session=session)
        return nobg
    except Exception as exc:
        print(f"rembg not available or failed ({exc}); using fallback alpha mask", file=sys.stderr)
        # Fallback: estimate subject mask by contrast & central region
        rgba = img.convert("RGBA")
        gray = img.convert("L")
        w, h = img.size
        mask = Image.new("L", (w, h), 0)
        mask_draw = ImageDraw.Draw(mask)
        # Elliptical mask focusing on center subject
        mask_draw.ellipse([w * 0.05, h * 0.05, w * 0.95, h * 0.98], fill=255)
        rgba.putalpha(mask)
        return rgba


def clean_artifacts(img: Image.Image) -> Image.Image:
    """Clean any top background artifact above the hair."""
    pixels = img.load()
    w, h = img.size
    for y in range(min(65, h)):
        for x in range(w):
            if y < 45 or x < 160 or x > 340:
                pixels[x, y] = (0, 0, 0, 0)
    return img


def generate_halftone(src_path: str = SRC_PATH, out_path: str = OUT_PATH,
                      target_w: int = 720, target_h: int = 864,
                      cell_size: int = 4):
    if not os.path.exists(src_path):
        raise FileNotFoundError(f"Source portrait not found: {src_path}")

    raw = Image.open(src_path)
    nobg = remove_background(raw).convert("RGBA")
    nobg = clean_artifacts(nobg)

    bbox = nobg.getbbox()
    if not bbox:
        bbox = (0, 0, nobg.width, nobg.height)

    w, h = nobg.size
    desired_ratio = target_w / target_h

    # Framing around head and upper torso
    head_top = bbox[1]
    margin_top = 28
    crop_top = max(0, head_top - margin_top)
    crop_height = int((bbox[2] - bbox[0]) / desired_ratio * 1.05)
    crop_bottom = min(h, crop_top + crop_height)
    crop_width = int((crop_bottom - crop_top) * desired_ratio)

    crop_center_x = (bbox[0] + bbox[2]) // 2
    crop_left = max(0, crop_center_x - crop_width // 2)
    crop_right = crop_left + crop_width
    if crop_right > w:
        crop_right = w
        crop_left = max(0, w - crop_width)

    cropped = nobg.crop((crop_left, crop_top, crop_right, crop_bottom))
    resized = cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)

    # Composite on pure white canvas
    canvas = Image.new("RGBA", (target_w, target_h), (255, 255, 255, 255))
    canvas.paste(resized, (0, 0), resized)

    rgb = canvas.convert("RGB")
    alpha = canvas.split()[3]
    gray = rgb.convert("L")

    # Tone mapping: lift midtones so face details/eyes pop while preserving hair/mustache
    lut = [int(math.pow(i / 255.0, 0.72) * 255) for i in range(256)]
    bright_gray = gray.point(lut)

    enhancer = ImageEnhance.Contrast(bright_gray)
    enhanced = enhancer.enhance(1.4)
    enhancer2 = ImageEnhance.Sharpness(enhanced)
    sharp = enhancer2.enhance(2.2)

    cols = target_w // cell_size
    rows = target_h // cell_size

    scale_factor = 3
    hi_w, hi_h = target_w * scale_factor, target_h * scale_factor
    hi_img = Image.new("RGB", (hi_w, hi_h), "#ffffff")
    hi_draw = ImageDraw.Draw(hi_img)
    hi_cell = cell_size * scale_factor

    pixels_sharp = sharp.load()
    pixels_alpha = alpha.load()

    for r in range(rows):
        for c in range(cols):
            x0, y0 = c * cell_size, r * cell_size
            val_sum = 0
            alpha_sum = 0
            for dy in range(cell_size):
                for dx in range(cell_size):
                    val_sum += pixels_sharp[x0 + dx, y0 + dy]
                    alpha_sum += pixels_alpha[x0 + dx, y0 + dy]

            avg_alpha = alpha_sum / (cell_size * cell_size)
            if avg_alpha < 25:
                continue

            avg_val = val_sum / (cell_size * cell_size)
            darkness = (1.0 - (avg_val / 255.0)) * (avg_alpha / 255.0)

            # S-curve for crisp contrast
            if darkness > 0.55:
                darkness = min(1.0, darkness * 1.18)
            else:
                darkness = max(0.0, darkness * 0.85)

            max_r = (hi_cell / 2.0) * 1.10
            r_px = max_r * math.sqrt(darkness)

            if r_px > 0.45:
                cx = (c * hi_cell) + (hi_cell / 2.0)
                cy = (r * hi_cell) + (hi_cell / 2.0)
                hi_draw.ellipse([cx - r_px, cy - r_px, cx + r_px, cy + r_px], fill="#0d1117")

    final_img = hi_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
    # Quantize to 16 colors (adaptive grayscale)
    final_p = final_img.convert("P", palette=Image.Palette.ADAPTIVE, colors=16)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    final_p.save(out_path)
    print(f"Halftone portrait generated: {out_path} ({target_w}x{target_h})")


if __name__ == "__main__":
    generate_halftone()

