#!/usr/bin/env python3
"""Кладёт Montserrat и Inter локально: только кириллица и латиница, без CDN."""

import os
import re
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "fonts")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126 Safari/537.36"
WANTED = {"cyrillic", "latin"}

FAMILIES = [
    ("Montserrat", [700, 800]),
    ("Inter", [400, 500, 600]),
]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read()


def main():
    os.makedirs(OUT, exist_ok=True)
    css_parts = []
    for family, weights in FAMILIES:
        spec = f"{family}:wght@{';'.join(str(w) for w in weights)}"
        css = get(f"https://fonts.googleapis.com/css2?family={spec}&display=swap").decode()
        blocks = re.findall(r"/\* (\S+) \*/\s*(@font-face \{.*?\})", css, re.S)
        for subset, block in blocks:
            if subset not in WANTED:
                continue
            weight = re.search(r"font-weight: (\d+)", block).group(1)
            url = re.search(r"url\((https://[^)]+)\)", block).group(1)
            name = f"{family.lower()}-{weight}-{subset}.woff2"
            path = os.path.join(OUT, name)
            if not os.path.exists(path):
                with open(path, "wb") as f:
                    f.write(get(url))
            unicode_range = re.search(r"unicode-range: ([^;]+);", block).group(1)
            css_parts.append(
                f"@font-face{{font-family:'{family}';font-style:normal;font-weight:{weight};"
                f"font-display:swap;src:url('{name}') format('woff2');"
                f"unicode-range:{unicode_range}}}"
            )
            print(f"  {name}: {os.path.getsize(path) // 1024} КБ")

    with open(os.path.join(OUT, "fonts.css"), "w", encoding="utf-8") as f:
        f.write("\n".join(css_parts) + "\n")


if __name__ == "__main__":
    main()
