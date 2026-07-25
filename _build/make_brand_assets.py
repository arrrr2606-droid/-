#!/usr/bin/env python3
"""Вырезает логотип из макета брендбука с прозрачным фоном и делает фавиконки.

Pillow в системе нет, поэтому PNG читается и пишется через zlib вручную (pnglite).
"""

import os

import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pnglite as P

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "ФИРМЕННЫЙ СТИЛЬ ", "DB227B98-2113-45FF-B683-0D4B9D725E91.PNG")
OUT = os.path.join(ROOT, "assets", "img", "brand")

# Фон макета — однородный тёмно-синий; логотип занимает эту область.
BG = (16, 22, 33)
FULL = (341, 364, 798, 205)   # x, y, w, h — знак + надпись
MARK = (341, 364, 267, 205)   # только знак «А»
GRAPHITE = (26, 26, 26)


def keyed(img, box):
    """Вырезает область и делает фон прозрачным, убирая тёмную кайму с краёв."""
    x, y, w, h = box
    src = P.crop(img, x, y, w, h)
    out = bytearray(w * h * 4)
    px = src["px"]
    for i in range(w * h):
        r, g, b = px[i * 3], px[i * 3 + 1], px[i * 3 + 2]
        d = max(abs(r - BG[0]), abs(g - BG[1]), abs(b - BG[2]))
        a = min(1.0, max(0.0, (d - 5) / 14.0))
        if a <= 0:
            continue
        # снимаем подмешанный фон, чтобы кромка не была грязной на светлом фоне
        rr = min(255, max(0, round((r - (1 - a) * BG[0]) / a)))
        gg = min(255, max(0, round((g - (1 - a) * BG[1]) / a)))
        bb = min(255, max(0, round((b - (1 - a) * BG[2]) / a)))
        out[i * 4:i * 4 + 4] = bytes((rr, gg, bb, round(a * 255)))
    return {"w": w, "h": h, "ch": 4, "px": out}


def on_canvas(img, cw, chh, box_w, bg=GRAPHITE):
    """Вписывает картинку по центру полотна заданного цвета, ширина картинки box_w."""
    scale = box_w / img["w"]
    tw, th = max(1, round(img["w"] * scale)), max(1, round(img["h"] * scale))
    small = P.resize(img, tw, th)
    out = bytearray()
    for _ in range(cw * chh):
        out += bytes((*bg, 255))
    ox, oy = (cw - tw) // 2, (chh - th) // 2
    for y in range(th):
        for x in range(tw):
            s = (y * tw + x) * 4
            a = small["px"][s + 3] / 255
            if a <= 0:
                continue
            d = ((y + oy) * cw + (x + ox)) * 4
            for c in range(3):
                out[d + c] = round(small["px"][s + c] * a + out[d + c] * (1 - a))
    return {"w": cw, "h": chh, "ch": 4, "px": out}


def main():
    os.makedirs(OUT, exist_ok=True)
    img = P.read(SRC)

    full = keyed(img, FULL)
    mark = keyed(img, MARK)

    P.write(os.path.join(OUT, "logo.png"), full)
    P.write(os.path.join(OUT, "logo-mark.png"), mark)
    P.write(os.path.join(OUT, "favicon-32.png"), on_canvas(mark, 32, 32, 30))
    P.write(os.path.join(OUT, "favicon-180.png"), on_canvas(mark, 180, 180, 140))
    P.write(os.path.join(OUT, "og-image.png"), on_canvas(full, 1200, 630, 760))

    for name in ("logo.png", "logo-mark.png", "favicon-32.png", "favicon-180.png", "og-image.png"):
        path = os.path.join(OUT, name)
        print(f"  {name}: {os.path.getsize(path) // 1024} КБ")


if __name__ == "__main__":
    main()
