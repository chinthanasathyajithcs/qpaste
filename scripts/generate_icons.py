"""Generate Windows-friendly icon assets from the source SVG."""

from __future__ import annotations

import io
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image, ImageColor, ImageDraw


ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT / "assets"
SVG_PATH = ASSETS_DIR / "icon.svg"

PNG_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def parse_svg_colors(svg_path: Path) -> tuple[str, str, str]:
    tree = ET.parse(svg_path)
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    styles = tree.find("svg:defs/svg:style", namespace)
    if styles is None or styles.text is None:
        raise ValueError("SVG style block not found")

    css = styles.text

    def get_fill(class_name: str) -> str:
        marker = f".{class_name} {{"
        start = css.find(marker)
        if start == -1:
            raise ValueError(f"Class {class_name} not found in SVG styles")
        fill_marker = "fill:"
        fill_start = css.find(fill_marker, start)
        fill_end = css.find(";", fill_start)
        return css[fill_start + len(fill_marker):fill_end].strip()

    return get_fill("cls-1"), get_fill("cls-2"), "#231f20"


def build_master_icon(size: int, primary: str, secondary: str, outline: str) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    margin = max(6, round(size * 0.055))
    center = size / 2
    outer_box = (margin, margin, size - margin, size - margin)

    draw.ellipse(outer_box, fill=ImageColor.getrgb(primary))

    ring_inset = max(4, round(size * 0.11))
    ring_box = (
        margin + ring_inset,
        margin + ring_inset,
        size - margin - ring_inset,
        size - margin - ring_inset,
    )
    draw.ellipse(ring_box, fill=ImageColor.getrgb(secondary))

    inner_radius = size * 0.17
    stem_half_width = max(3, round(size * 0.055))
    stem_top = center - size * 0.16
    stem_bottom = center + size * 0.19
    draw.rounded_rectangle(
        (
            center - stem_half_width,
            stem_top,
            center + stem_half_width,
            stem_bottom,
        ),
        radius=stem_half_width,
        fill=ImageColor.getrgb(primary),
    )
    draw.ellipse(
        (
            center - inner_radius,
            center - inner_radius,
            center + inner_radius,
            center + inner_radius,
        ),
        fill=ImageColor.getrgb(primary),
    )

    notch_width = size * 0.16
    notch_height = size * 0.11
    notch_top = center + size * 0.015
    draw.rounded_rectangle(
        (
            center - notch_width / 2,
            notch_top,
            center + notch_width / 2,
            notch_top + notch_height,
        ),
        radius=max(2, round(size * 0.025)),
        fill=ImageColor.getrgb(secondary),
    )

    outline_width = max(1, round(size * 0.035))
    draw.ellipse(outer_box, outline=ImageColor.getrgb(outline), width=outline_width)

    if size <= 32:
        image = image.resize((size, size), Image.Resampling.LANCZOS)

    return image


def save_png(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")


def main() -> None:
    primary, secondary, outline = parse_svg_colors(SVG_PATH)
    master = build_master_icon(512, primary, secondary, outline)

    for size in PNG_SIZES:
        resized = master.resize((size, size), Image.Resampling.LANCZOS)
        suffix = "" if size == 256 else f"-{size}"
        save_png(resized, ASSETS_DIR / f"icon{suffix}.png")

    ico_frames = [master.resize((size, size), Image.Resampling.LANCZOS) for size in ICO_SIZES]
    ico_path = ASSETS_DIR / "icon.ico"
    ico_frames[0].save(
        ico_path,
        format="ICO",
        sizes=[(size, size) for size in ICO_SIZES],
        append_images=ico_frames[1:],
    )

    png_buffer = io.BytesIO()
    master.save(png_buffer, format="PNG")
    print(f"Generated {ico_path.relative_to(ROOT)} and {len(PNG_SIZES)} PNG assets")


if __name__ == "__main__":
    main()