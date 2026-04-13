"""Generate rclone GUI.icns — run by the build workflow before PyInstaller."""
import os, subprocess, shutil
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = "icon.iconset"
os.makedirs(OUT_DIR, exist_ok=True)

SIZES  = [16, 32, 64, 128, 256, 512, 1024]
BG_TOP    = (232, 114, 10)
BG_BOT    = (180, 60,  0)
WHITE     = (255, 255, 255, 255)
OFF_WHITE = (255, 230, 200, 220)

def draw_arrow(draw, x1, y1, x2, y2, head, lw, color):
    draw.line([(x1, y1), (x2, y2)], fill=color, width=lw)
    if x2 > x1:
        draw.polygon([(x2, y2), (x2-head, y2-head//2), (x2-head, y2+head//2)], fill=color)
    else:
        draw.polygon([(x2, y2), (x2+head, y2-head//2), (x2+head, y2+head//2)], fill=color)

def make_icon(size):
    img  = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    radius = max(4, size // 5)

    for y in range(size):
        t = y / size
        r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
        draw.line([(0, y), (size, y)], fill=(r, g, b, 255))

    mask = Image.new('L', (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size-1, size-1], radius=radius, fill=255)
    img.putalpha(mask)
    draw = ImageDraw.Draw(img)

    pad  = size * 0.18
    mid  = size // 2
    lw   = max(1, size // 22)
    head = max(2, size // 12)
    gap  = size * 0.10

    draw_arrow(draw, int(pad), int(mid - gap), int(size - pad), int(mid - gap), head, lw, WHITE)
    draw_arrow(draw, int(size - pad), int(mid + gap), int(pad), int(mid + gap), head, lw, OFF_WHITE)

    if size >= 256:
        font_size = max(8, size // 11)
        font = None
        for path in ['/System/Library/Fonts/Helvetica.ttc',
                     '/System/Library/Fonts/SFNSDisplay.ttf',
                     '/Library/Fonts/Arial.ttf']:
            if os.path.exists(path):
                try:
                    font = ImageFont.truetype(path, font_size)
                    break
                except Exception:
                    pass
        if font:
            text = "rclone GUI"
            bbox = draw.textbbox((0, 0), text, font=font)
            tw   = bbox[2] - bbox[0]
            ty   = int(size * 0.80)
            tx   = (size - tw) // 2
            draw.text((tx, ty), text, font=font, fill=(255, 255, 255, 180))

    return img

for sz in SIZES:
    make_icon(sz).save(f"{OUT_DIR}/icon_{sz}x{sz}.png")
    if sz <= 512:
        make_icon(sz * 2).save(f"{OUT_DIR}/icon_{sz}x{sz}@2x.png")

subprocess.run(['iconutil', '-c', 'icns', OUT_DIR, '-o', 'appicon.icns'], check=True)
shutil.rmtree(OUT_DIR)
print("Created: appicon.icns")
