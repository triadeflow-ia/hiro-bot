"""Add beautiful text overlays to promo images without ruining them."""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path

PROMOS_DIR = Path(__file__).parent.parent / "assets" / "promos"
OUTPUT_DIR = PROMOS_DIR  # overwrite originals (backups first)
BACKUP_DIR = PROMOS_DIR / "originals"

# Fonts
FONT_DIR = "C:/Windows/Fonts"
FONT_TITLE = f"{FONT_DIR}/impact.ttf"
FONT_PRICE = f"{FONT_DIR}/impact.ttf"
FONT_SUB = f"{FONT_DIR}/arialbd.ttf"
FONT_DAY = f"{FONT_DIR}/arialbd.ttf"

# Brand colors
RED = (219, 12, 20)
GREEN = (31, 183, 108)
WHITE = (255, 255, 255)
BLACK = (12, 5, 5)

PROMOS = [
    {
        "file": "segunda-samurai.png",
        "day": "SEGUNDA",
        "title": "SEGUNDA\nSAMURAI",
        "subtitle": "30 PECAS SORTIDAS",
        "price": "R$29,90",
    },
    {
        "file": "terca-crocante.png",
        "day": "TERCA",
        "title": "TERCA\nCROCANTE",
        "subtitle": "10 HOT ROLLS",
        "price": "R$19,90",
    },
    {
        "file": "quarta-maluca.png",
        "day": "QUARTA",
        "title": "QUARTA\nMALUCA",
        "subtitle": "40 PECAS VARIADAS",
        "price": "R$38,00",
    },
    {
        "file": "quinta-dragao.png",
        "day": "QUINTA",
        "title": "QUINTA\nDO DRAGAO",
        "subtitle": "2 TEMAKIS PREMIUM",
        "price": "R$34,90",
    },
    {
        "file": "sexta-familia.png",
        "day": "SEXTA",
        "title": "SEXTA\nFAMILIA",
        "subtitle": "60 PECAS PRA FAMILIA",
        "price": "R$54,90",
    },
    {
        "file": "sabado-shogun.png",
        "day": "SABADO",
        "title": "SABADO\nSHOGUN",
        "subtitle": "80 PECAS IMPERIAL",
        "price": "R$69,90",
    },
    {
        "file": "domingo-zen.png",
        "day": "DOMINGO",
        "title": "DOMINGO\nZEN",
        "subtitle": "FESTIVAL DE SASHIMI",
        "price": "R$44,90",
    },
]


def add_text_overlay(img_path: Path, promo: dict) -> None:
    """Add text overlay to a promo image."""
    img = Image.open(img_path).convert("RGBA")
    # Resize to 1080x1350 WITHOUT distortion: fill width, pad top/bottom with brand black
    target_w, target_h = 1080, 1350
    ratio = target_w / img.width
    new_h = int(img.height * ratio)
    img = img.resize((target_w, new_h), Image.LANCZOS)
    # Center on dark canvas
    canvas = Image.new("RGBA", (target_w, target_h), (12, 5, 5, 255))
    paste_y = (target_h - new_h) // 2
    canvas.paste(img, (0, paste_y))
    img = canvas
    w, h = img.size

    # Create overlay layer
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # --- Bottom gradient bar (for price + subtitle) ---
    bar_height = int(h * 0.22)
    bar_y = h - bar_height
    for i in range(bar_height):
        alpha = int(220 * (i / bar_height))  # gradient from transparent to opaque
        draw.rectangle([(0, bar_y + i), (w, bar_y + i + 1)], fill=(12, 5, 5, alpha))

    # --- Top-left title area (subtle dark overlay) ---
    title_area_h = int(h * 0.45)
    for i in range(title_area_h):
        alpha = int(160 * (1 - i / title_area_h))  # fade from top
        draw.rectangle([(0, i), (w, i + 1)], fill=(12, 5, 5, alpha))

    # Composite overlay onto image
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # --- Title (top-left) ---
    title_font = ImageFont.truetype(FONT_TITLE, size=int(h * 0.10))
    title_lines = promo["title"].split("\n")
    y_pos = int(h * 0.04)
    for line in title_lines:
        # Red shadow
        draw.text((int(w * 0.06) + 2, y_pos + 2), line, font=title_font, fill=(100, 0, 0, 200))
        # White text
        draw.text((int(w * 0.06), y_pos), line, font=title_font, fill=WHITE)
        bbox = title_font.getbbox(line)
        y_pos += bbox[3] - bbox[1] + int(h * 0.01)

    # --- Red accent line under title ---
    line_y = y_pos + int(h * 0.01)
    draw.rectangle(
        [(int(w * 0.06), line_y), (int(w * 0.35), line_y + 4)],
        fill=RED,
    )

    # --- "PROMO DO DIA" badge (top-right) ---
    badge_font = ImageFont.truetype(FONT_SUB, size=int(h * 0.028))
    badge_text = "PROMO DO DIA"
    badge_bbox = badge_font.getbbox(badge_text)
    badge_text_w = badge_bbox[2] - badge_bbox[0]
    badge_text_h = badge_bbox[3] - badge_bbox[1]
    badge_px = 20
    badge_py = 14
    badge_total_w = badge_text_w + badge_px * 2
    badge_total_h = badge_text_h + badge_py * 2
    badge_x = w - badge_total_w - int(w * 0.04)
    badge_y = int(h * 0.04)
    draw.rounded_rectangle(
        [(badge_x, badge_y), (badge_x + badge_total_w, badge_y + badge_total_h)],
        radius=8,
        fill=RED,
    )
    # Center text inside badge
    badge_text_x = badge_x + (badge_total_w - badge_text_w) // 2 - badge_bbox[0]
    badge_text_y = badge_y + (badge_total_h - badge_text_h) // 2 - badge_bbox[1]
    draw.text((badge_text_x, badge_text_y), badge_text, font=badge_font, fill=WHITE)

    # --- Subtitle (bottom area) ---
    sub_font = ImageFont.truetype(FONT_SUB, size=int(h * 0.035))
    sub_bbox = sub_font.getbbox(promo["subtitle"])
    sub_y = h - bar_height + int(bar_height * 0.15)
    draw.text((int(w * 0.06), sub_y), promo["subtitle"], font=sub_font, fill=(255, 255, 255, 220))

    # --- Price (bottom-right, big and bold) ---
    price_font = ImageFont.truetype(FONT_PRICE, size=int(h * 0.07))
    price_bbox = price_font.getbbox(promo["price"])
    price_text_w = price_bbox[2] - price_bbox[0]
    price_text_h = price_bbox[3] - price_bbox[1]

    # Red pill dimensions
    pill_px = 28
    pill_py = 20
    pill_w = price_text_w + pill_px * 2
    pill_h = price_text_h + pill_py * 2
    pill_x = w - pill_w - int(w * 0.05)
    pill_y = sub_y + int(h * 0.005)

    draw.rounded_rectangle(
        [(pill_x, pill_y), (pill_x + pill_w, pill_y + pill_h)],
        radius=12,
        fill=RED,
    )
    # Center text inside pill
    text_x = pill_x + (pill_w - price_text_w) // 2 - price_bbox[0]
    text_y = pill_y + (pill_h - price_text_h) // 2 - price_bbox[1]
    draw.text((text_x, text_y), promo["price"], font=price_font, fill=WHITE)

    # --- Logo (bottom-left, inside the bar) ---
    logo_path = PROMOS_DIR.parent / "logo-sushi-da-hora.png"
    if logo_path.exists():
        logo = Image.open(logo_path).convert("RGBA")
        logo_size = int(h * 0.07)
        logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
        logo_x = int(w * 0.04)
        logo_y = h - int(h * 0.05) - logo_size
        img.paste(logo, (logo_x, logo_y), logo)
        # Re-create draw after paste
        draw = ImageDraw.Draw(img)

    # --- "TODAS AS UNIDADES | 17h - 23h" watermark (bottom center) ---
    wm_font = ImageFont.truetype(FONT_SUB, size=int(h * 0.02))
    wm_text = "TODAS AS UNIDADES   |   17h - 23h"
    wm_bbox = wm_font.getbbox(wm_text)
    wm_w = wm_bbox[2] - wm_bbox[0]
    draw.text(
        ((w - wm_w) // 2, h - int(h * 0.035)),
        wm_text,
        font=wm_font,
        fill=(255, 255, 255, 140),
    )

    # Save (convert back to RGB for PNG)
    img_rgb = img.convert("RGB")
    img_rgb.save(img_path, "PNG", quality=95)


def main():
    # Backup originals
    BACKUP_DIR.mkdir(exist_ok=True)

    print("Adding text overlays to promo images...\n")

    for promo in PROMOS:
        filepath = PROMOS_DIR / promo["file"]
        if not filepath.exists():
            print(f"  SKIP {promo['file']} - not found")
            continue

        # Backup
        backup_path = BACKUP_DIR / promo["file"]
        if not backup_path.exists():
            import shutil
            shutil.copy2(filepath, backup_path)
            print(f"  Backup: {promo['file']} -> originals/")

        # Add overlay
        add_text_overlay(filepath, promo)
        print(f"  OK {promo['file']} - {promo['title'].replace(chr(10), ' ')} | {promo['price']}")

    print(f"\nDone! Images updated in: {PROMOS_DIR}")
    print(f"Originals backed up in: {BACKUP_DIR}")


if __name__ == "__main__":
    main()
