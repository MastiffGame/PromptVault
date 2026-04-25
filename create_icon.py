"""Generates icon.ico for PromptVault."""
from PIL import Image, ImageDraw, ImageFont
import math, os

SIZE = 512
CYAN   = (0, 212, 255)
PURPLE = (167, 139, 250)
BG     = (6, 6, 15, 255)


def make_frame(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = size // 5

    # Background rounded rect
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=BG)

    # Outer cyan ring
    m = size // 16
    w = max(2, size // 28)
    d.arc([m, m, size - m - 1, size - m - 1], 0, 360, fill=(*CYAN, 220), width=w)

    # Inner purple ring (dashed feel via arcs)
    m2 = size // 7
    w2 = max(1, size // 50)
    for start in range(0, 360, 45):
        d.arc([m2, m2, size - m2 - 1, size - m2 - 1],
              start, start + 30, fill=(*PURPLE, 160), width=w2)

    # Corner dots
    dot = max(2, size // 40)
    ring_r = size // 2 - m
    for angle_deg in [45, 135, 225, 315]:
        a = math.radians(angle_deg)
        cx = size // 2 + int(ring_r * math.cos(a))
        cy = size // 2 + int(ring_r * math.sin(a))
        d.ellipse([cx - dot, cy - dot, cx + dot, cy + dot], fill=(*CYAN, 255))

    # Letters "P" and "V"
    font_size = size // 3
    font = None
    for path in [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/verdanab.ttf",
    ]:
        if os.path.exists(path):
            font = ImageFont.truetype(path, font_size)
            break
    if font is None:
        font = ImageFont.load_default()

    cx, cy = size // 2, size // 2
    d.text((cx - size // 8, cy + size // 30), "P",
           fill=(*CYAN, 255), anchor="mm", font=font)
    d.text((cx + size // 4 + size // 30, cy + size // 30), "V",
           fill=(*PURPLE, 255), anchor="mm", font=font)

    return img


if __name__ == "__main__":
    frames = [make_frame(s) for s in [256, 128, 64, 48, 32, 16]]
    frames[0].save(
        "icon.ico",
        format="ICO",
        append_images=frames[1:],
        sizes=[(f.width, f.height) for f in frames],
    )
    print("icon.ico created.")
