#!/usr/bin/env python3
"""Проверяет собранный сайт: битые внутренние ссылки, картинки, дубли title."""

import json
import os
import re
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {"_build", "data", "ФИРМЕННЫЙ СТИЛЬ ", ".git"}
ATTR = re.compile(r'(?:href|src)="([^"]+)"')


def base_path():
    """Подпапка деплоя из конфига — ссылки от корня сайта начинаются с неё."""
    with open(os.path.join(ROOT, "data", "site-config.json"), encoding="utf-8") as f:
        domain = json.load(f)["domain"]
    after_host = domain.split("//", 1)[-1].partition("/")[2].strip("/")
    return "/" + after_host if after_host else ""


def pages():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.endswith(".html"):
                yield os.path.join(dirpath, name)


def main():
    problems = []
    titles = {}
    checked = 0
    base = base_path()

    for path in pages():
        rel_page = os.path.relpath(path, ROOT)
        with open(path, encoding="utf-8") as f:
            markup = f.read()

        title = re.search(r"<title>(.*?)</title>", markup, re.S)
        if title:
            titles.setdefault(title.group(1).strip(), []).append(rel_page)

        for raw in set(ATTR.findall(markup)):
            if raw.startswith(("http://", "https://", "mailto:", "tel:", "data:", "#")):
                continue
            target = urllib.parse.unquote(raw.split("#")[0].split("?")[0])
            if not target:
                continue
            # 404.html ссылается от корня сайта, остальные страницы — относительно себя.
            if target.startswith("/"):
                if base and not target.startswith(base + "/"):
                    problems.append(f"{rel_page}: «{raw}» без префикса подпапки «{base}»")
                    continue
                anchor, target = ROOT, target[len(base):]
            else:
                anchor = os.path.dirname(path)
            resolved = os.path.normpath(os.path.join(anchor, target.lstrip("/")))
            checked += 1
            if not os.path.exists(resolved):
                problems.append(f"{rel_page}: не найдено «{raw}»")

    for title, where in titles.items():
        if len(where) > 1:
            problems.append(f"повторяющийся title «{title}»: {', '.join(where)}")

    total = len(list(pages()))
    print(f"Страниц: {total} · проверено ссылок: {checked}")
    if problems:
        print(f"\nПроблем: {len(problems)}")
        for p in problems[:40]:
            print("  ×", p)
        sys.exit(1)
    print("Битых ссылок и дублей title нет.")


if __name__ == "__main__":
    main()
