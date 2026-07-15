"""Generate the 1200x630 Open Graph / LinkedIn preview card for the landing
page. Reuses the site's visual language (dark ground, teal = grounded,
amber = naive baseline) so the shared-link card matches the page it opens.

Run:  python scripts/generate_og_image.py
Output: public/og-image.png
"""

import os

from PIL import Image, ImageDraw, ImageFont

# --- palette (matches landing.html) ---
BG = (11, 18, 15)            # #0b120f
INK = (237, 245, 241)        # #edf5f1
INK_DIM = (147, 171, 162)    # #93aba2
INK_FAINT = (92, 113, 104)   # #5c7168
TEAL = (31, 209, 184)        # #1fd1b8
TEAL_DK = (14, 118, 106)     # #0e766a
AMBER = (234, 165, 63)       # #eaa53f
LINE = (40, 52, 47)          # subtle divider

W, H = 1200, 630
PAD = 72


def _font(candidates, size, index=0):
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size, index=index)
            except Exception:
                continue
    return ImageFont.load_default()


MONO = ["/System/Library/Fonts/SFNSMono.ttf", "/System/Library/Fonts/Menlo.ttc"]
MENLO = "/System/Library/Fonts/Menlo.ttc"
SANS_BOLD = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]

f_wordmark = _font(SANS_BOLD, 34)
f_eyebrow = _font(MONO, 21)
f_head = _font([MENLO], 46, index=1)          # Menlo Bold
f_label = _font(MONO, 20)
f_stat = _font([MENLO], 58, index=1)          # Menlo Bold, big numbers
f_unit = _font(MONO, 23)
f_foot = _font(MONO, 20)


def draw_logo(d, x, y, box=60):
    """Teal rounded square with three ascending bars, matching the nav mark."""
    d.rounded_rectangle([x, y, x + box, y + box], radius=14, fill=TEAL_DK)
    d.rounded_rectangle([x, y, x + box, y + box], radius=14, outline=TEAL, width=2)
    bar_w = 8
    gap = 7
    base_y = y + box - 15
    heights = [16, 26, 34]
    start_x = x + (box - (3 * bar_w + 2 * gap)) // 2
    for i, hgt in enumerate(heights):
        bx = start_x + i * (bar_w + gap)
        d.rounded_rectangle([bx, base_y - hgt, bx + bar_w, base_y], radius=2, fill=TEAL)


def main():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # top: logo + wordmark
    draw_logo(d, PAD, 56, box=58)
    d.text((PAD + 78, 68), "Ask Cortex Analyst", font=f_wordmark, fill=INK)

    # eyebrow with a short teal rule
    ey_y = 168
    d.line([PAD, ey_y + 12, PAD + 26, ey_y + 12], fill=TEAL, width=2)
    d.text((PAD + 38, ey_y), "A CONTROLLED EVALUATION OF LLM GROUNDING",
           font=f_eyebrow, fill=TEAL)

    # headline (two lines, monospace bold)
    d.text((PAD, 208), "Ground an LLM in a real semantic", font=f_head, fill=INK)
    d.text((PAD, 262), "model, and it stops guessing.", font=f_head, fill=INK)

    # the stat contrast: two columns
    col_l = PAD
    col_r = 640
    label_y = 372
    row1_y = 410
    row2_y = 480
    gap = 26  # gap between the big number and its unit label

    def num_width(s):
        b = d.textbbox((0, 0), s, font=f_stat)
        return b[2] - b[0]

    # place each column's unit labels clear of that column's widest number
    unit_x_l = col_l + max(num_width("100%"), num_width("0%")) + gap
    unit_x_r = col_r + max(num_width("65.3%"), num_width("16.7%")) + gap

    d.ellipse([col_l, label_y + 4, col_l + 11, label_y + 15], fill=TEAL)
    d.text((col_l + 22, label_y), "CORTEX ANALYST", font=f_label, fill=TEAL)
    d.ellipse([col_r, label_y + 4, col_r + 11, label_y + 15], fill=AMBER)
    d.text((col_r + 22, label_y), "NAIVE BASELINE", font=f_label, fill=AMBER)

    # left column (grounded)
    d.text((col_l, row1_y), "100%", font=f_stat, fill=TEAL)
    d.text((unit_x_l, row1_y + 22), "accuracy", font=f_unit, fill=INK_DIM)
    d.text((col_l, row2_y), "0%", font=f_stat, fill=TEAL)
    d.text((unit_x_l, row2_y + 22), "hallucination", font=f_unit, fill=INK_DIM)

    # right column (naive baseline)
    d.text((col_r, row1_y), "65.3%", font=f_stat, fill=AMBER)
    d.text((unit_x_r, row1_y + 22), "accuracy", font=f_unit, fill=INK_DIM)
    d.text((col_r, row2_y), "16.7%", font=f_stat, fill=AMBER)
    d.text((unit_x_r, row2_y + 22), "hallucination", font=f_unit, fill=INK_DIM)

    # footer
    d.line([PAD, 566, W - PAD, 566], fill=LINE, width=1)
    d.text((PAD, 584), "ask-cortex-analyst.onrender.com", font=f_foot, fill=INK_DIM)
    right_txt = "Snowflake  ·  Cortex Analyst  ·  dbt  ·  Chainlit"
    rb = d.textbbox((0, 0), right_txt, font=f_foot)
    d.text((W - PAD - (rb[2] - rb[0]), 584), right_txt, font=f_foot, fill=INK_FAINT)

    out = os.path.join(os.path.dirname(__file__), "..", "public", "og-image.png")
    img.save(out, "PNG")
    print("wrote", os.path.abspath(out), img.size)


if __name__ == "__main__":
    main()
