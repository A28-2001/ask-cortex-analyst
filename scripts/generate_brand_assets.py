"""Generates the app's logo, favicon, and per-author avatars programmatically
(no external design tool available) -- simple geometric marks only, no emoji,
no hand-drawn complex paths, consistent flat brand palette.

Palette:
  teal  #14B8A6 -- primary brand color, used for logo + Cortex Analyst avatar
  navy  #1E293B -- secondary, used for the Assistant avatar (visual contrast)
  white #FFFFFF -- mark foreground
"""
import os
from PIL import Image, ImageDraw

TEAL = (20, 184, 166, 255)
NAVY = (30, 41, 59, 255)
WHITE = (255, 255, 255, 255)

BASE = os.path.join(os.path.dirname(__file__), "..", "public")
AVATARS = os.path.join(BASE, "avatars")
os.makedirs(AVATARS, exist_ok=True)


def rounded_square(size, bg):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    radius = int(size * 0.22)
    draw.rounded_rectangle([(0, 0), (size - 1, size - 1)], radius=radius, fill=bg)
    return img, draw


def bar_chart_mark(size=512, bg=TEAL, fg=WHITE):
    """Three ascending bars centered on a rounded square -- the core brand mark."""
    img, draw = rounded_square(size, bg)
    bar_w = size * 0.11
    gap = size * 0.08
    heights = [0.28, 0.44, 0.60]
    total_w = bar_w * 3 + gap * 2
    start_x = (size - total_w) / 2
    base_y = size * 0.72
    for i, h_frac in enumerate(heights):
        x0 = start_x + i * (bar_w + gap)
        x1 = x0 + bar_w
        y1 = base_y
        y0 = base_y - size * h_frac
        draw.rounded_rectangle([(x0, y0), (x1, y1)], radius=bar_w * 0.25, fill=fg)
    return img


def dot_mark(size=512, bg=NAVY, fg=WHITE):
    """Three dots in a row -- distinct silhouette from the bar mark, same family."""
    img, draw = rounded_square(size, bg)
    r = size * 0.075
    cy = size * 0.5
    gap = size * 0.22
    start_x = size * 0.5 - gap
    for i in range(3):
        cx = start_x + i * gap
        draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=fg)
    return img


# Logo: bar-chart mark, same asset serves both light/dark themes since it's a
# filled square (no transparency reliance on page background).
logo = bar_chart_mark(512)
logo.save(os.path.join(BASE, "logo_dark.png"))
logo.save(os.path.join(BASE, "logo_light.png"))

# Favicon: smaller render of the same mark for crispness at small sizes.
favicon = bar_chart_mark(64)
favicon.save(os.path.join(BASE, "favicon.png"))
favicon.convert("RGB").save(os.path.join(BASE, "favicon.ico"), sizes=[(16, 16), (32, 32), (64, 64)])

# Avatars: the "Cortex Analyst" step gets the brand bar-chart mark (it *is*
# the analytics engine); the default message author gets the dot mark in
# navy for clear visual contrast. Chainlit looks up avatars by author name,
# lowercased with spaces -> underscores -- the default author is the app's
# [UI].name in config.toml ("Ask Cortex Analyst" -> ask_cortex_analyst.png).
bar_chart_mark(128).save(os.path.join(AVATARS, "cortex_analyst.png"))
dot_mark(128).save(os.path.join(AVATARS, "ask_cortex_analyst.png"))

print("Generated:", os.listdir(BASE), os.listdir(AVATARS))
