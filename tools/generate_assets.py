"""Generate the Book My Date brand assets.

Development-only helper. Requires Pillow. Run from the repository root:

    python tools/generate_assets.py
"""

from __future__ import annotations

import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "book_my_date" / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)

S = 4096
UNIT = S / 1024


def px(value: float) -> int:
    return int(round(value * UNIT))


def lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def vertical_gradient(size: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    image = Image.new("RGB", (1, size))
    for y in range(size):
        image.putpixel((0, y), lerp(top, bottom, y / max(1, size - 1)))
    return image.resize((size, size), Image.Resampling.BILINEAR)


def rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return mask


def draw_icon(size: int = S) -> Image.Image:
    u = size / 1024

    def p(value: float) -> int:
        return int(round(value * u))

    # Background gradient
    background = vertical_gradient(size, (99, 102, 241), (139, 92, 246)).convert("RGBA")
    highlight = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    hdraw = ImageDraw.Draw(highlight)
    hdraw.ellipse(
        (-p(280), -p(420), p(920), p(560)),
        fill=(255, 255, 255, 46),
    )
    highlight = highlight.filter(ImageFilter.GaussianBlur(p(60)))
    background.alpha_composite(highlight)
    background.putalpha(rounded_mask(size, int(p(226))))

    # Soft colored glow behind the calendar
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle(
        (p(214), p(310), p(810), p(822)),
        radius=p(90),
        fill=(49, 46, 129, 80),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(p(38)))
    background.alpha_composite(glow)

    draw = ImageDraw.Draw(background)

    # Calendar body
    body = (p(218), p(282), p(806), p(804))
    draw.rounded_rectangle(body, radius=p(78), fill=(255, 255, 255, 255))
    draw.rounded_rectangle(
        (p(232), p(296), p(792), p(790)),
        radius=p(64),
        outline=(255, 255, 255, 255),
        width=p(3),
    )

    # Header band (clipped to rounded top corners with a mask)
    header_height = p(156)
    header = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    hd = ImageDraw.Draw(header)
    hd.rounded_rectangle(
        (body[0], body[1], body[2], body[1] + header_height),
        radius=p(78),
        fill=(238, 239, 254, 255),
    )
    hd.rectangle(
        (body[0], body[1] + header_height - p(80), body[2], body[1] + header_height),
        fill=(238, 239, 254, 255),
    )
    background.alpha_composite(header)

    # Binder rings
    for center_x in (p(376), p(648)):
        draw.rounded_rectangle(
            (center_x - p(23), p(232), center_x + p(23), p(350)),
            radius=p(23),
            fill=(255, 255, 255, 255),
        )
        draw.rounded_rectangle(
            (center_x - p(11), p(252), center_x + p(11), p(338)),
            radius=p(11),
            fill=(109, 92, 246, 255),
        )

    # Header dots
    for index in range(3):
        cx = p(454) + index * p(58)
        draw.ellipse((cx - p(9), p(370) - p(9), cx + p(9), p(370) + p(9)), fill=(99, 102, 241, 255))

    # Accent check circle
    circle = (p(378), p(474), p(646), p(742))
    draw.ellipse(circle, fill=(91, 91, 214, 255))
    draw.ellipse(
        (circle[0] + p(20), circle[1] + p(20), circle[2] - p(20), circle[3] - p(20)),
        outline=(255, 255, 255, 55),
        width=p(6),
    )
    draw.line(
        [(p(452), p(606)), (p(510), p(664)), (p(590), p(560))],
        fill=(255, 255, 255, 255),
        width=p(46),
        joint="curve",
    )
    for point in ((p(452), p(606)), (p(510), p(664)), (p(590), p(560))):
        radius = p(23)
        draw.ellipse(
            (point[0] - radius, point[1] - radius, point[0] + radius, point[1] + radius),
            fill=(255, 255, 255, 255),
        )

    # Sparkle
    sparkle_center = (p(750), p(268))
    sparkle = [
        (sparkle_center[0], sparkle_center[1] - p(54)),
        (sparkle_center[0] + p(15), sparkle_center[1] - p(15)),
        (sparkle_center[0] + p(54), sparkle_center[1]),
        (sparkle_center[0] + p(15), sparkle_center[1] + p(15)),
        (sparkle_center[0], sparkle_center[1] + p(54)),
        (sparkle_center[0] - p(15), sparkle_center[1] + p(15)),
        (sparkle_center[0] - p(54), sparkle_center[1]),
        (sparkle_center[0] - p(15), sparkle_center[1] - p(15)),
    ]
    draw.polygon(sparkle, fill=(255, 255, 255, 235))

    return background


def write_icns(png_paths: dict[str, Path], destination: Path) -> None:
    type_map = {
        "16": b"icp4",
        "32": b"icp5",
        "64": b"icp6",
        "128": b"ic07",
        "256": b"ic08",
        "512": b"ic09",
        "1024": b"ic10",
    }
    chunks = b""
    for size, png in png_paths.items():
        data = png.read_bytes()
        chunk_type = type_map[size]
        chunk = chunk_type + struct.pack(">I", len(data) + 8) + data
        chunks += chunk
    destination.write_bytes(b"icns" + struct.pack(">I", len(chunks) + 8) + chunks)


def write_svg(destination: Path) -> None:
    destination.write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" role="img" aria-label="Book My Date">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#6366F1"/>
      <stop offset="1" stop-color="#8B5CF6"/>
    </linearGradient>
    <linearGradient id="check" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#6366F1"/>
      <stop offset="1" stop-color="#7C3AED"/>
    </linearGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="150%">
      <feDropShadow dx="0" dy="18" stdDeviation="26" flood-color="#312E81" flood-opacity=".28"/>
    </filter>
  </defs>
  <rect x="2" y="2" width="1020" height="1020" rx="226" fill="url(#bg)"/>
  <path d="M118 386c94-254 321-338 559-278 178 45 292 194 300 386-222 34-572 24-859-108z" fill="#fff" opacity=".06"/>
  <g filter="url(#shadow)">
    <rect x="218" y="282" width="588" height="522" rx="78" fill="#fff"/>
    <path d="M218 360c0-43 35-78 78-78h432c43 0 78 35 78 78v78H218z" fill="#EEEFFE"/>
    <rect x="353" y="232" width="46" height="118" rx="23" fill="#fff"/>
    <rect x="365" y="252" width="22" height="86" rx="11" fill="#6D5CF6"/>
    <rect x="625" y="232" width="46" height="118" rx="23" fill="#fff"/>
    <rect x="637" y="252" width="22" height="86" rx="11" fill="#6D5CF6"/>
    <circle cx="454" cy="370" r="9" fill="#6366F1"/>
    <circle cx="512" cy="370" r="9" fill="#6366F1"/>
    <circle cx="570" cy="370" r="9" fill="#6366F1"/>
    <circle cx="512" cy="608" r="134" fill="url(#check)"/>
    <circle cx="512" cy="608" r="122" fill="none" stroke="#fff" stroke-opacity=".22" stroke-width="6"/>
    <path d="M452 606l58 58 80-104" fill="none" stroke="#fff" stroke-width="46" stroke-linecap="round" stroke-linejoin="round"/>
  </g>
  <path d="M750 214l15 39 39 15-39 15-15 39-15-39-39-15 39-15z" fill="#fff" opacity=".92"/>
</svg>
""",
        encoding="utf-8",
    )


def main() -> None:
    icon = draw_icon()
    master = ASSETS / "app_icon.png"
    icon.resize((1024, 1024), Image.Resampling.LANCZOS).save(master, "PNG")
    icon.resize((512, 512), Image.Resampling.LANCZOS).save(ASSETS / "app_icon_512.png", "PNG")
    icon.resize((256, 256), Image.Resampling.LANCZOS).save(ASSETS / "app_icon_256.png", "PNG")
    icon.resize((128, 128), Image.Resampling.LANCZOS).save(ASSETS / "app_icon_128.png", "PNG")

    sizes = [16, 24, 32, 48, 64, 128, 256]
    frames = [icon.resize((size, size), Image.Resampling.LANCZOS) for size in sizes]
    frames[-1].save(ASSETS / "app.ico", format="ICO", sizes=[(s, s) for s in sizes])

    icns_sizes = [16, 32, 64, 128, 256, 512, 1024]
    icns_paths: dict[str, Path] = {}
    for size in icns_sizes:
        target = ASSETS / f".icns_{size}.png"
        icon.resize((size, size), Image.Resampling.LANCZOS).save(target, "PNG")
        icns_paths[str(size)] = target
    write_icns(icns_paths, ASSETS / "app.icns")
    for path in icns_paths.values():
        path.unlink()

    write_svg(ASSETS / "logo.svg")
    print(f"Wrote brand assets to {ASSETS}")


if __name__ == "__main__":
    main()
