"""Generates the logo, favicons and avatars as simple geometric marks, in the
landing page's palette (ink, paper, one blue). Drawn at 4x and scaled down so
the edges stay clean at 16 px.

  brand mark   blue square, three ascending paper bars: logo, favicons, and
               the assistant's own avatar
  Cortex step  ink square, three lines of text: the question being read
  SQL step     ink square, a six-armed asterisk: the Snowflake query

Chainlit finds an avatar by author name, lower-cased with spaces turned into
underscores, so the step called "Snowflake query" uses snowflake_query.png.
"""
import math
import os

from PIL import Image, ImageDraw

INK = (20, 24, 27, 255)
PAPER = (238, 241, 244, 255)
BLUE = (36, 56, 224, 255)

BASE = os.path.join(os.path.dirname(__file__), "..", "public")
AVATARS = os.path.join(BASE, "avatars")
SCALE = 4


def canvas(size, bg):
    big = size * SCALE
    img = Image.new("RGBA", (big, big), bg)
    return img, ImageDraw.Draw(img), big


def finish(img, size):
    return img.resize((size, size), Image.LANCZOS)


def brand_mark(size):
    img, draw, s = canvas(size, BLUE)
    bar_w, gap = s * 0.13, s * 0.075
    start_x = (s - (bar_w * 3 + gap * 2)) / 2
    base_y = s * 0.76
    for i, h in enumerate((0.26, 0.40, 0.54)):
        x0 = start_x + i * (bar_w + gap)
        draw.rectangle([(x0, base_y - s * h), (x0 + bar_w, base_y)], fill=PAPER)
    return finish(img, size)


def text_lines_mark(size):
    img, draw, s = canvas(size, INK)
    thick = s * 0.11
    for y, w in ((0.30, 0.56), (0.50, 0.56), (0.70, 0.34)):
        x0 = s * 0.22
        draw.rectangle([(x0, s * y - thick / 2), (x0 + s * w, s * y + thick / 2)], fill=PAPER)
    return finish(img, size)


def asterisk_mark(size):
    img, draw, s = canvas(size, INK)
    c, r, w = s / 2, s * 0.30, int(s * 0.11)
    for k in range(3):
        a = math.radians(90 + k * 60)
        dx, dy = r * math.cos(a), r * math.sin(a)
        draw.line([(c - dx, c - dy), (c + dx, c + dy)], fill=PAPER, width=w)
    return finish(img, size)


if __name__ == "__main__":
    os.makedirs(AVATARS, exist_ok=True)

    logo = brand_mark(512)
    logo.save(os.path.join(BASE, "logo_light.png"))
    logo.save(os.path.join(BASE, "logo_dark.png"))
    brand_mark(64).save(os.path.join(BASE, "favicon.png"))
    brand_mark(180).convert("RGB").save(os.path.join(BASE, "apple-touch-icon.png"))
    brand_mark(64).save(os.path.join(BASE, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)])

    brand_mark(128).save(os.path.join(AVATARS, "ask_cortex_analyst.png"))
    text_lines_mark(128).save(os.path.join(AVATARS, "cortex_analyst.png"))
    asterisk_mark(128).save(os.path.join(AVATARS, "snowflake_query.png"))

    print("Generated:", sorted(os.listdir(BASE)), sorted(os.listdir(AVATARS)))
