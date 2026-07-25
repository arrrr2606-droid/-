#!/usr/bin/env python3
"""Собирает номенклатуру, ТТХ и фото с сайтов UMG и ЗЗГТ в data/catalog.json."""

import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_ROOT = os.path.join(ROOT, "assets", "img", "machines")
DATA = os.path.join(ROOT, "data")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126 Safari/537.36"

UMG = "https://umg-sdm.com"
ZZGT = "https://zzgt.ru"

UMG_CATEGORIES = [
    ("gusenichnye-ekskavatory", "Гусеничные экскаваторы", "excavator-track"),
    ("kolesnye-ekskavatory", "Колёсные экскаваторы", "excavator-wheel"),
    ("frontalnykh-pogruzchikov", "Фронтальные погрузчики", "loader-front"),
    ("teleskopicheskie-pogruzchiki", "Телескопические погрузчики", "loader-telescopic"),
    ("ekskavatory-pogruzchiki", "Экскаваторы-погрузчики", "backhoe"),
    ("avtogreydery", "Автогрейдеры", "grader"),
    ("buldozery", "Бульдозеры", "dozer"),
]

ZZGT_MODELS = [
    "catalog/gaz-34039-snegobolotohod/",
    "catalog/Snegobolotohod_34039__Irbis____2023/",
    "catalog/snegobolotohod-gaz-34039-irbis/",
    "catalog/snegobolotohod-gaz-3409-bobr/",
    "catalog/elem178845/",
]

TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "c",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e",
    "ю": "yu", "я": "ya", "«": "", "»": "",
}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def slugify(text):
    text = text.lower().strip()
    out = "".join(TRANSLIT.get(ch, ch) for ch in text)
    out = re.sub(r"[^a-z0-9]+", "-", out).strip("-")
    return out or "item"


def fetch(url, referer=None, binary=False, retries=3):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept-Language": "ru-RU,ru;q=0.9",
        **({"Referer": referer} if referer else {}),
    })
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                raw = r.read()
            return raw if binary else raw.decode("utf-8", "replace")
        except urllib.error.HTTPError:
            raise  # 404 и прочие ответы сервера повтором не лечатся
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt == retries - 1:
                raise
            log(f"    retry {attempt + 1} {url}: {e}")
            time.sleep(2 * (attempt + 1))


# --- разбор HTML -------------------------------------------------------------

class TableParser(HTMLParser):
    """Собирает таблицы в список строк ячеек. wanted_class=None — берёт все."""

    def __init__(self, wanted_class=None):
        super().__init__(convert_charrefs=True)
        self.wanted = wanted_class
        self.tables = []
        self._depth = 0
        self._capture = 0
        self._rows = None
        self._row = None
        self._cell = None
        self._cell_attrs = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            self._depth += 1
            if not self._capture and (self.wanted is None or self.wanted in (a.get("class") or "")):
                self._capture = self._depth
                self._rows = []
            return
        if not self._capture:
            return
        if tag == "tr" and self._depth == self._capture:
            self._row = []
        elif tag in ("td", "th") and self._depth == self._capture:
            self._cell = []
            self._cell_attrs = a
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag):
        if tag == "table":
            if self._capture == self._depth:
                self.tables.append(self._rows)
                self._rows = None
                self._capture = 0
            self._depth = max(0, self._depth - 1)
            return
        if not self._capture:
            return
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            text = re.sub(r"\s+", " ", "".join(self._cell)).strip()
            self._row.append({
                "text": text,
                "colspan": int(self._cell_attrs.get("colspan") or 1),
                "rowspan": int(self._cell_attrs.get("rowspan") or 1),
                "style": self._cell_attrs.get("style") or "",
            })
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self._rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def parse_tables(markup, cls=None):
    p = TableParser(cls)
    p.feed(markup)
    return p.tables


def section(markup, div_id):
    """Кусок разметки от <div id="..."> до следующего такого же блока."""
    start = markup.find(f'id="{div_id}"')
    if start == -1:
        return ""
    end = markup.find('<div id="product-info', start + 10)
    return markup[start:end if end != -1 else len(markup)]


HEADER_HINTS = re.compile(r"технические характеристики|параметр|наименование|характеристик", re.I)
UNIT_HINTS = re.compile(r"ед\.?\s*изм", re.I)


def read_spec_table(rows, fallback_column):
    """Приводит таблицу любого вида к общему виду: колонки + строки с ячейками.

    У производителей встречаются три формата: «параметр / ед.изм. / значение»,
    «параметр / значение» и сравнение двух исполнений в соседних колонках.
    """
    if not rows:
        return [], [], False

    columns, body = [fallback_column], rows
    first = [c["text"] for c in rows[0]]
    if len(first) >= 2 and (HEADER_HINTS.search(first[0] or "") or UNIT_HINTS.search(first[1] or "")):
        columns = [c or fallback_column for c in first[1:]]
        body = rows[1:]

    has_unit = bool(len(columns) > 1 and UNIT_HINTS.search(columns[0] or ""))
    if has_unit:
        columns = columns[1:]

    out, pending = [], None
    for cells in body:
        texts = [re.sub(r"\s+", " ", c["text"]).strip() for c in cells]
        if len(cells) == 1 and cells[0]["colspan"] > 1:
            if texts[0]:
                out.append({"group": texts[0]})
            pending = None
            continue
        if cells[0]["rowspan"] > 1 and texts[0]:
            pending = texts[0]
        # Продолжение строки с rowspan: имя параметра осталось в предыдущей строке.
        if len(texts) < (2 + int(has_unit)) and pending:
            name, values = pending, texts
        else:
            name, values = texts[0], texts[1:]
        if not name or not any(values):
            continue
        out.append({"name": name.rstrip(":"), "cells": values})
    return columns, out, bool(has_unit)


LATIN_FOR = str.maketrans("АВСЕНКМОРТХаосерху", "ABCEHKMOPTXaocepxy")
TYPE_WORDS = re.compile(
    r"\b(гусеничный|колесный|колёсный|двухзвенный|полноповоротный|фронтальный|телескопический)?\s*"
    r"(экскаватор-погрузчик|экскаватор|погрузчик|бульдозер|автогрейдер|грейдер|снегоболотоход|"
    r"вездеход|тягач)\b", re.I)


def clean_model_name(title, brand):
    """Из заголовка страницы делает короткий индекс модели: «E225C», «ГАЗ-3409 «Бобр»»."""
    name = TYPE_WORDS.sub(" ", title)
    name = re.sub(r"\s+", " ", name).strip(" -—,")

    if brand == "zzgt":
        name = re.sub(r"^ГАЗ[\s-]*", "", name).strip()
        name = f"ГАЗ-{name}" if name and name[0].isdigit() else name
    else:
        name = name.replace("_", "-")
        # Индексы вроде «E160С_CT» и «Е225С LR» приходят с кириллическими двойниками
        # латинских букв. Правим только там, где латиница в индексе уже есть.
        if re.search(r"[A-Za-z]", name):
            name = name.translate(LATIN_FOR)
    return name or title


def strip_tags(markup):
    markup = re.sub(r"<(script|style|iframe)[^>]*>.*?</\1>", "", markup, flags=re.S | re.I)
    # На сайте ЗЗГТ знак градуса местами сохранён в битой кодировке.
    markup = re.sub(r"(?<=\d)\s*\?(?=\s*[СC])", "°", markup)
    markup = re.sub(r"<br\s*/?>", "\n", markup, flags=re.I)
    markup = re.sub(r"</(p|li|h\d|div|tr)>", "\n", markup, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", markup)
    text = html.unescape(text).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.split("\n")]
    return [ln for ln in lines if ln]


def h1_of(markup):
    m = re.search(r"<h1[^>]*>(.*?)</h1>", markup, re.S | re.I)
    return " ".join(strip_tags(m.group(1))) if m else ""


# --- фотографии --------------------------------------------------------------

def save_image(url, referer, out_dir, base_name):
    """Скачивает и уменьшает фото. Возвращает (большое, малое) относительные имена."""
    big = f"{base_name}.jpg"
    small = f"{base_name}-sm.jpg"
    big_path = os.path.join(out_dir, big)
    small_path = os.path.join(out_dir, small)
    if os.path.exists(big_path) and os.path.exists(small_path):
        return big, small

    raw = fetch(url, referer=referer, binary=True)
    if len(raw) < 2000:
        raise ValueError(f"слишком маленький файл ({len(raw)} б)")
    os.makedirs(out_dir, exist_ok=True)
    tmp = os.path.join(out_dir, f".{base_name}.src")
    with open(tmp, "wb") as f:
        f.write(raw)
    try:
        for out, width, quality in ((big_path, 1200, 50), (small_path, 640, 55)):
            subprocess.run(
                ["sips", "-Z", str(width), "-s", "format", "jpeg",
                 "-s", "formatOptions", str(quality), tmp, "--out", out],
                check=True, capture_output=True)
    finally:
        os.remove(tmp)
    return big, small


def collect_images(urls, referer, brand, model_slug):
    out_dir = os.path.join(IMG_ROOT, brand, model_slug)
    rel = f"assets/img/machines/{brand}/{model_slug}"
    photos = []
    for idx, url in enumerate(urls, 1):
        try:
            big, small = save_image(url, referer, out_dir, f"{model_slug}-{idx}")
            photos.append({"src": f"{rel}/{big}", "thumb": f"{rel}/{small}"})
        except Exception as e:  # одна битая картинка не должна валить прогон
            log(f"    ! фото {url}: {e}")
        time.sleep(0.3)
    return photos


# --- UMG ---------------------------------------------------------------------

def umg_model_urls(cat_slug):
    markup = fetch(f"{UMG}/catalog/{cat_slug}/")
    seen, urls = set(), []
    for m in re.finditer(rf'href="(/catalog/{re.escape(cat_slug)}/[^"?#]+)"', markup):
        path = m.group(1)
        if "/filter/" in path or path.rstrip("/").endswith(cat_slug):
            continue
        if path not in seen:
            seen.add(path)
            urls.append(UMG + path)
    return urls


def umg_description(markup):
    m = re.search(r'<div id="product-info1"[^>]*>(.*?)<div id="product-info', markup, re.S)
    if not m:
        return {}
    lines = strip_tags(m.group(1))
    sections, current = {}, None
    headings = {
        "назначение": "purpose", "преимущества": "advantages",
        "гарантия": "warranty", "оснащен": "equipment", "оснащён": "equipment",
        "комплектация": "equipment", "особенности": "advantages",
    }
    for line in lines:
        key = line.rstrip(":").lower()
        matched = next((v for k, v in headings.items() if k in key and len(line) < 90), None)
        if matched:
            current = matched
            sections.setdefault(current, [])
            continue
        if current is None:
            current = "purpose"
            sections.setdefault(current, [])
        sections[current].append(line)
    return {k: v for k, v in sections.items() if v}


def umg_specs(markup, model_name):
    tables = parse_tables(section(markup, "product-info2"))
    if not tables:
        return [], [], False
    return read_spec_table(tables[0], model_name)


def umg_photo_urls(markup):
    urls, seen = [], set()
    for m in re.finditer(r'src="(/upload/resize_cache/iblock/[^"]+?/(\d+)_(\d+)_\d+/([^"/]+\.(?:jpg|jpeg|png)))"', markup, re.I):
        cached, width, name = m.group(1), int(m.group(2)), m.group(4)
        if width < 400 or name in seen:
            continue
        seen.add(name)
        folder = re.match(r"(/upload/)resize_cache/(iblock/[0-9a-f]+/)", cached)
        original = f"{UMG}{folder.group(1)}{folder.group(2)}{name}" if folder else UMG + cached
        urls.append((original, UMG + cached))
    return urls


def scrape_umg():
    items = []
    for cat_slug, cat_title, cat_icon in UMG_CATEGORIES:
        log(f"[UMG] {cat_title}")
        for url in umg_model_urls(cat_slug):
            markup = fetch(url)
            title = h1_of(markup)
            if not title:
                log(f"  ! без заголовка: {url}")
                continue
            name = clean_model_name(title, "umg")
            slug = slugify(name)
            log(f"  · {name}")
            photos = []
            for original, cached in umg_photo_urls(markup):
                idx = len(photos) + 1
                out_dir = os.path.join(IMG_ROOT, "umg", slug)
                rel = f"assets/img/machines/umg/{slug}"
                for candidate in (original, cached):
                    try:
                        big, small = save_image(candidate, url, out_dir, f"{slug}-{idx}")
                        photos.append({"src": f"{rel}/{big}", "thumb": f"{rel}/{small}"})
                        break
                    except Exception as e:
                        log(f"    ! фото {candidate}: {e}")
                time.sleep(0.3)
            columns, specs, has_unit = umg_specs(markup, name)
            items.append({
                "brand": "umg",
                "category": cat_slug,
                "categoryTitle": cat_title,
                "categoryIcon": cat_icon,
                "slug": slug,
                "name": name,
                "title": title,
                "source": url,
                "specColumns": columns,
                "specUnitColumn": has_unit,
                "specs": specs,
                "description": umg_description(markup),
                "photos": photos,
            })
            time.sleep(1)
    return items


# --- ЗЗГТ --------------------------------------------------------------------

def zzgt_specs(markup, model_name):
    tables = parse_tables(markup, "info_table")
    if not tables:
        return [], [], False
    columns, rows, has_unit = read_spec_table(tables[0], model_name)
    # У ЗЗГТ первая ячейка шапки — описание комплектации, а не название колонки.
    columns = [model_name if len(c) > 40 else c for c in columns]
    return columns, rows, has_unit


def zzgt_description(markup):
    m = re.search(r"(Описание.*?)<table", markup, re.S)
    if not m:
        return {}
    lines = [ln for ln in strip_tags(m.group(1))
             if ln.lower().rstrip(":") not in ("описание", "характеристики")]
    return {"purpose": lines} if lines else {}


def scrape_zzgt():
    items = []
    log("[ЗЗГТ] Снегоболотоходы")
    for path in ZZGT_MODELS:
        url = f"{ZZGT}/{path}"
        markup = fetch(url)
        title = h1_of(markup) or path
        name = clean_model_name(title, "zzgt")
        slug = slugify(name)
        log(f"  · {name}")
        photo_urls, seen = [], set()
        for m in re.finditer(r'(?:src|href)="([^"]*images/catalog/[^"]*_image_big[^"]*\.(?:jpe?g|png))"', markup, re.I):
            # В разметке пути относительные, но лежат картинки в корне сайта.
            src = urllib.parse.urljoin(ZZGT + "/", m.group(1).lstrip("./"))
            if src not in seen:
                seen.add(src)
                photo_urls.append(src)
        columns, specs, has_unit = zzgt_specs(markup, name)
        items.append({
            "brand": "zzgt",
            "category": "snegobolotokhody",
            "categoryTitle": "Гусеничные снегоболотоходы",
            "categoryIcon": "atv",
            "slug": slug,
            "name": name,
            "title": title,
            "source": url,
            "specColumns": columns,
            "specUnitColumn": has_unit,
            "specs": specs,
            "description": zzgt_description(markup),
            "photos": collect_images(photo_urls, url, "zzgt", slug),
        })
        time.sleep(1)
    return items


def main():
    os.makedirs(DATA, exist_ok=True)
    items = scrape_umg() + scrape_zzgt()
    out = os.path.join(DATA, "catalog-raw.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    total_photos = sum(len(i["photos"]) for i in items)
    log(f"\nГотово: {len(items)} моделей, {total_photos} фото → {out}")
    for i in items:
        if not i["specs"] or not i["photos"]:
            log(f"  ВНИМАНИЕ {i['name']}: ТТХ={len(i['specs'])} фото={len(i['photos'])}")


if __name__ == "__main__":
    main()
