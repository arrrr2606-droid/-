#!/usr/bin/env python3
"""Собирает статический сайт из data/catalog-raw.json и data/site-config.json."""

import html
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pnglite as P

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

BRANDS = {
    "umg": {
        "name": "UMG",
        "full": "UMG (АО «ЭКСМАШ»)",
        "note": "Российский производитель строительно-дорожной техники: экскаваторы, "
                "погрузчики, автогрейдеры и бульдозеры.",
        "site": "https://umg-sdm.com/",
    },
    "zzgt": {
        "name": "ВПК (ЗЗГТ)",
        "full": "ВПК — Заволжский завод гусеничных тягачей",
        "note": "Гусеничные снегоболотоходы для работы вне дорог: нефтегаз, геологоразведка, "
                "энергетика, Крайний Север.",
        "site": "https://zzgt.ru/",
    },
}

NAV = [
    ("Главная", "index.html"),
    ("Каталог", "catalog/index.html"),
    ("Запчасти", "parts.html"),
    ("Сервис", "service.html"),
    ("Лизинг", "financing.html"),
    ("О компании", "about.html"),
    ("Контакты", "contacts.html"),
]

# Как достать ключевые параметры из таблицы ТТХ производителя.
SPEC_KEYS = {
    "mass": [r"эксплуатационн\w* масс", r"масса снаряж", r"полная масса"],
    "power": [r"мощность двигател", r"^(номинальная\s+)?мощность\b"],
    "bucket": [r"вместимость ковша", r"объ[её]м ковша", r"ковш"],
    "depth": [r"глубина копания"],
    "capacity": [r"грузоподъ[её]мность"],
    "blade": [r"грейдерный отвал, длина", r"длина отвала", r"отвал, ширина", r"отвал"],
    "speed": [r"по шоссе", r"максимальная скорость"],
}

# Третий показатель в карточке — свой для каждой категории.
CARD_THIRD = {
    "gusenichnye-ekskavatory": ("depth", "Глубина копания"),
    "kolesnye-ekskavatory": ("depth", "Глубина копания"),
    "ekskavatory-pogruzchiki": ("depth", "Глубина копания"),
    "frontalnykh-pogruzchikov": ("capacity", "Грузоподъёмность"),
    "teleskopicheskie-pogruzchiki": ("capacity", "Грузоподъёмность"),
    "avtogreydery": ("blade", "Длина отвала"),
    "buldozery": ("blade", "Отвал"),
    "snegobolotokhody": ("capacity", "Грузоподъёмность"),
}

CATEGORY_BLURB = {
    "gusenichnye-ekskavatory": "Полноповоротные гидравлические экскаваторы для земляных работ, "
                              "карьеров и промышленного строительства.",
    "kolesnye-ekskavatory": "Мобильные экскаваторы для городского строительства, ЖКХ и "
                           "обслуживания дорог — переезжают между объектами своим ходом.",
    "frontalnykh-pogruzchikov": "Погрузочно-разгрузочные и земляные работы, склады сыпучих "
                               "материалов, карьеры.",
    "teleskopicheskie-pogruzchiki": "Подъём и перемещение грузов на высоту со сменным рабочим "
                                   "оборудованием.",
    "ekskavatory-pogruzchiki": "Универсальные машины «два в одном» для коммунальных, дорожных "
                              "и благоустроительных работ.",
    "avtogreydery": "Планировка и профилирование земляного полотна при строительстве дорог, "
                   "аэродромов и площадок.",
    "buldozery": "Разработка и перемещение грунта в дорожном и промышленном строительстве.",
    "snegobolotokhody": "Плавающие гусеничные вездеходы для перевозки людей и грузов по бездорожью "
                       "при температурах от +40 °C до −50 °C.",
}

SERVICE_ITEMS = [
    ("Гарантийный ремонт", "Обслуживаем технику UMG и ЗЗГТ в течение гарантийного срока — "
     "с сохранением гарантии производителя."),
    ("Плановое ТО", "Регламентные работы по наработке моточасов: масла, фильтры, регулировки, "
     "диагностика по контрольным точкам."),
    ("Выездные бригады", "Ремонт на объекте заказчика — не нужно снимать машину с работы и везти "
     "её на площадку сервиса."),
    ("Гидравлика", "Диагностика и ремонт насосов, гидромоторов, распределителей и гидроцилиндров, "
     "замер давления в контурах."),
    ("Ходовая часть", "Ремонт и замена гусеничных цепей, катков, натяжителей, бортовых редукторов "
     "и направляющих колёс."),
    ("Двигатель и трансмиссия", "Ремонт дизелей ЯМЗ и Д-245, коробок передач, мостов и "
     "раздаточных коробок."),
]

PARTS_GROUPS = [
    ("Двигатель", "Фильтры, поршневая группа, топливная аппаратура, турбокомпрессоры, "
     "прокладки и ремкомплекты для ЯМЗ и Д-245."),
    ("Гидравлика", "Насосы, гидромоторы, распределители, гидроцилиндры, РВД, уплотнения "
     "и ремкомплекты."),
    ("Ходовая часть", "Гусеничные цепи, башмаки, опорные и поддерживающие катки, "
     "направляющие колёса, натяжные механизмы."),
    ("Трансмиссия", "Коробки передач, бортовые редукторы, мосты, карданные валы, "
     "муфты и фрикционы."),
    ("Электрооборудование", "Генераторы, стартеры, жгуты, датчики, приборные панели, "
     "аккумуляторные батареи."),
    ("Рабочее оборудование", "Ковши, зубья и коронки, отвалы, рыхлители, быстросъёмы, "
     "гидромолоты и грейферы."),
]

ADVANTAGES = [
    ("Официальный дилер", "Прямые поставки с заводов UMG и ЗЗГТ. Заводская гарантия и "
     "оригинальная документация на каждую машину."),
    ("Склад запчастей", "Расходники и узлы под технику обоих производителей — "
     "простой машины стоит дороже детали."),
    ("Собственный сервис", "Гарантийный и постгарантийный ремонт, выездные бригады, "
     "плановое обслуживание по наработке."),
    ("Лизинг и trade-in", "Подбираем схему финансирования под ваш парк, принимаем "
     "технику в зачёт."),
]

FINANCING_STEPS = [
    ("Заявка", "Присылаете модель и желаемые условия — аванс, срок, график платежей."),
    ("Расчёт", "Готовим предложения от лизинговых компаний и сравниваем удорожание."),
    ("Документы", "Собираем пакет: устав, бухгалтерская отчётность, паспорт руководителя."),
    ("Договор", "Подписываем договор лизинга и поставки, вносите аванс."),
    ("Передача", "Отгружаем технику, передаём ПСМ и документы, ставим на учёт."),
]

ICONS = {
    "excavator": "<path d='M3 30h30M7 30v-5h9v5M16 25l-3-9 5-2 4 8M22 14l8-4 5 8-6 3'/>"
                 "<circle cx='11' cy='33' r='3'/><circle cx='22' cy='33' r='3'/>",
    "parts": "<circle cx='18' cy='18' r='5'/><circle cx='18' cy='18' r='11'/>"
             "<path d='M18 4v3m0 22v3M4 18h3m22 0h3M9 9l2.2 2.2m13.6 13.6L27 27M27 9l-2.2 2.2"
             "M11.2 24.8 9 27'/>",
    "service": "<path d='M24 6a8 8 0 0 0-9.5 10.4L6 25l5 5 8.6-8.5A8 8 0 0 0 30 12l-4.5 4.5-4-4z'/>",
    "shield": "<path d='M18 4l12 5v9c0 8-5 13-12 16-7-3-12-8-12-16V9z'/><path d='M13 18l4 4 8-8'/>",
    "truck": "<path d='M3 10h17v14H3zM20 15h6l5 5v4h-11z'/><circle cx='9' cy='27' r='3'/>"
             "<circle cx='25' cy='27' r='3'/>",
    "doc": "<path d='M9 4h13l7 7v21H9z'/><path d='M22 4v7h7M14 19h12M14 25h12'/>",
    "clock": "<circle cx='18' cy='18' r='14'/><path d='M18 9v9l6 4'/>",
    "handshake": "<path d='M4 14l6-5 8 3 8-3 6 5v9l-6 5-6-5-4 3-4-3-8-4z'/>",
    "hydraulics": "<path d='M6 12h9l4-4h11v10H19l-4-4H6z'/><path d='M6 8v16M25 18v10M19 24h12'/>",
    "gearbox": "<circle cx='13' cy='14' r='6'/><circle cx='24' cy='23' r='5'/>"
                "<path d='M13 4v4m0 12v4M4 14h4m10 0h4M24 14v4m0 10v4M15 23h4m10 0h3'/>",
    "electric": "<path d='M20 3 8 20h9l-3 13 14-18h-9z'/>",
    "bucket": "<path d='M6 10h24l-3 14a3 3 0 0 1-3 2H12a3 3 0 0 1-3-2z'/>"
              "<path d='M6 10 4 4M30 10l2-6M14 16v6m8-6v6'/>",
}


def esc(text):
    return html.escape(str(text), quote=True)


UNITS = (r"кг|т|мм|см|км/ч|л/мин|л|кВт|л\.с\.|см³|м³|м²|м|%|град|шт|В|А|Ач|кПа|МПа|"
         r"Н\*м|Н·м|Нм|кгс|кН|об/мин")
# Единицу измерения заводы пишут где придётся: «Грузоподъемность, кг.»,
# «мощность нетто по SAE (кВт) / при оборотах, об/мин», «Масса (без груза) кг.».
# Берём то вхождение, которое встречается в названии раньше остальных.
UNIT_PATTERNS = [
    # «…нетто при оборотах кВт / об/мин» — единица величины идёт первой в паре.
    re.compile(rf"\b({UNITS})\s*/\s*(?:{UNITS})(?![\wа-я])", re.I),
    re.compile(rf",\s*({UNITS})\.?(?![\wа-я])", re.I),
    re.compile(rf"\(\s*({UNITS})\s*\)", re.I),
    re.compile(rf"[,)\s]\s*({UNITS})\.?\s*$", re.I),
]
FIRST_NUMBER = re.compile(r"\d[\d   ]*(?:[.,]\d+)?")


def unit_from_name(name):
    hits = [m for m in (p.search(name) for p in UNIT_PATTERNS) if m]
    return min(hits, key=lambda m: m.start()).group(1) if hits else ""


def find_spec(item, key):
    """Ищет строку ТТХ по названию параметра и возвращает значение с единицей."""
    for pattern in SPEC_KEYS[key]:
        for row in item["specs"]:
            name = row.get("name")
            if not name or not re.search(pattern, name, re.I):
                continue
            if item["specUnitColumn"] and len(row["cells"]) > 1:
                unit = row["cells"][0]
                values = row["cells"][1:]
            else:
                unit, values = unit_from_name(name), row["cells"]
            # Строки без чисел — это подзаголовки исполнений, а не значения.
            value = next((c for c in values if re.search(r"\d", c)), "")
            if value:
                unit = re.sub(r"\s*\([^)]*\)", "", unit)
                return {"unit": unit.strip(" ."), "value": value.strip(), "name": name}
    return None


def spec_number(row, to_kg=False):
    """Первое число из значения ТТХ — для сортировки каталога.

    Массу заводы пишут то в килограммах, то в тоннах, поэтому для сортировки
    приводим её к одной единице.
    """
    short = short_value(row)
    if not short:
        return 0.0
    value = float(re.sub(r"[^\d.]", "", short["value"].replace(",", ".")) or 0)
    if to_kg and short["unit"].lower().startswith("т"):
        value *= 1000
    return value


def short_value(row):
    """Ужимает значение до одного числа с единицей — для плиток и карточек.

    В таблицах встречается «92 (125) / 2000» (кВт, л.с. и обороты в одной ячейке)
    и «132 (180)» при единице «кВт/л.с.» — показываем только первую величину.
    """
    if not row:
        return None
    m = FIRST_NUMBER.search(re.sub(r"\s+", " ", row["value"]))
    if not m:
        return None
    value = m.group(0).strip()
    unit = row["unit"].replace("&nbsp;", "").strip()
    if "/" in unit and unit.lower() not in ("км/ч", "л/мин", "об/мин", "кг/см²"):
        unit = unit.split("/")[0].strip()
    return {"value": value, "unit": unit}


def rel(depth):
    return "../" * depth


def full_address(cfg):
    """Город и улица через запятую; пока улица не заполнена — только город."""
    return ", ".join(part for part in (cfg["city"], cfg["address"]) if part.strip())


TONE_CACHE = os.path.join(DATA, "photo-tone.json")


def is_cutout(path, cache):
    """Фото на белой подложке? Такие снимки заводы снимают в студии, и на тёмном
    фоне они выглядят белым прямоугольником — им нужна светлая подложка."""
    if path in cache:
        return cache[path]
    full = os.path.join(ROOT, path)
    tmp = os.path.join(DATA, ".tone.png")
    try:
        subprocess.run(["sips", "-z", "8", "8", "-s", "format", "png", full, "--out", tmp],
                       check=True, capture_output=True)
        img = P.read(tmp)
        corners = [P.pixel(img, x, y) for x, y in ((0, 0), (7, 0), (0, 7), (7, 7))]
        light = sum(1 for c in corners if min(c[:3]) > 205)
        cache[path] = light >= 3
    except Exception:
        cache[path] = False
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return cache[path]


# --- HTML-блоки --------------------------------------------------------------

def head(cfg, depth, title, description, canonical, extra=""):
    base = rel(depth)
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(cfg['domain'] + '/' + canonical)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{esc(cfg['company'])}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:image" content="{esc(cfg['domain'])}/assets/img/brand/og-image.png">
<meta property="og:url" content="{esc(cfg['domain'] + '/' + canonical)}">
<link rel="icon" type="image/png" sizes="32x32" href="{base}assets/img/brand/favicon-32.png">
<link rel="apple-touch-icon" href="{base}assets/img/brand/favicon-180.png">
<link rel="stylesheet" href="{base}assets/css/main.css">
{extra}</head>
<body>
"""


def header(cfg, depth, current, megamenu_html):
    base = rel(depth)
    links = []
    for label, href in NAV:
        cls = "nav__link"
        if href == current:
            cls += " is-current"
        if label == "Каталог":
            links.append(
                f'<button type="button" class="{cls}" data-megamenu '
                f'aria-controls="megamenu" aria-expanded="false">Каталог'
                f'<span class="nav__caret" aria-hidden="true"></span></button>'
                f'<a class="visually-hidden" href="{base}catalog/index.html">Открыть каталог</a>'
                + megamenu_html)
        else:
            links.append(f'<a class="{cls}" href="{base}{href}">{esc(label)}</a>')

    return f"""<header class="header">
<div class="shell header__bar">
<a class="header__logo" href="{base}index.html" aria-label="{esc(cfg['company'])} — на главную">
<img src="{base}assets/img/brand/logo.png" alt="{esc(cfg['company'])}" width="798" height="205">
</a>
<nav class="nav" aria-label="Основная навигация">
{chr(10).join(links)}
</nav>
<div class="header__contact">
<a class="header__phone" href="tel:{esc(cfg['phoneHref'])}">{esc(cfg['phone'])}</a>
<span class="header__hours">{esc(cfg['hours'])}</span>
</div>
<button type="button" class="burger" aria-label="Меню" aria-expanded="false"><span></span></button>
</div>
</header>
"""


def build_megamenu(depth, categories):
    base = rel(depth)
    columns = []
    for brand_key, brand in BRANDS.items():
        rows = []
        for cat in categories:
            if cat["brand"] != brand_key:
                continue
            rows.append(
                f'<li><a href="{base}catalog/{brand_key}/{cat["slug"]}/index.html">'
                f'{esc(cat["title"])}<span class="megamenu__count">{len(cat["items"])}</span></a></li>')
        columns.append(
            f'<div><p class="megamenu__brand">{esc(brand["name"])}</p>'
            f'<ul class="megamenu__list">{"".join(rows)}</ul></div>')

    columns.append(
        f'<div><p class="megamenu__brand">Ещё</p><ul class="megamenu__list">'
        f'<li><a href="{base}catalog/index.html">Весь каталог</a></li>'
        f'<li><a href="{base}parts.html">Запчасти</a></li>'
        f'<li><a href="{base}service.html">Сервис</a></li>'
        f'<li><a href="{base}financing.html">Лизинг</a></li></ul></div>')

    return (f'<div class="megamenu" id="megamenu"><div class="shell">'
            f'<div class="megamenu__grid">{"".join(columns)}</div></div></div>')


def breadcrumbs(cfg, depth, trail):
    base = rel(depth)
    items, ld = [], []
    for i, (label, href) in enumerate(trail):
        if href is None:
            items.append(f'<li><span aria-current="page">{esc(label)}</span></li>')
            url = cfg["domain"]
        else:
            items.append(f'<li><a href="{base}{href}">{esc(label)}</a></li>')
            url = f"{cfg['domain']}/{href}"
        ld.append({"@type": "ListItem", "position": i + 1, "name": label, "item": url})

    schema = json.dumps(
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": ld},
        ensure_ascii=False)
    return (f'<nav class="breadcrumbs" aria-label="Хлебные крошки"><div class="shell">'
            f'<ol>{"".join(items)}</ol></div></nav>'
            f'<script type="application/ld+json">{schema}</script>')


def footer(cfg, depth, categories):
    base = rel(depth)
    cat_links = "".join(
        f'<li><a href="{base}catalog/{c["brand"]}/{c["slug"]}/index.html">{esc(c["title"])}</a></li>'
        for c in categories[:7])
    page_links = "".join(
        f'<li><a href="{base}{href}">{esc(label)}</a></li>' for label, href in NAV[1:])

    return f"""<footer class="footer">
<div class="shell">
<div class="footer__grid">
<div>
<div class="footer__logo"><img src="{base}assets/img/brand/logo.png" alt="{esc(cfg['company'])}" width="798" height="205"></div>
<p class="footer__about">Официальный дилер UMG и ВПК (ЗЗГТ). Продажа спецтехники, поставка
оригинальных запчастей и сервисное обслуживание.</p>
</div>
<div>
<p class="footer__title">Каталог</p>
<ul class="footer__list">{cat_links}</ul>
</div>
<div>
<p class="footer__title">Разделы</p>
<ul class="footer__list">{page_links}</ul>
</div>
<div>
<p class="footer__title">Контакты</p>
<ul class="footer__list">
<li><a href="tel:{esc(cfg['phoneHref'])}">{esc(cfg['phone'])}</a></li>
<li><a href="mailto:{esc(cfg['email'])}">{esc(cfg['email'])}</a></li>
<li>{esc(cfg['hours'])}</li>
<li>{esc(full_address(cfg))}</li>
</ul>
</div>
</div>
<div class="footer__bottom">
<p>© 2020–2026 {esc(cfg['legalName'])}</p>
<p>{esc(cfg['tagline'])}</p>
<p class="footer__disclaimer">Технические характеристики и фотографии приведены по данным
производителей UMG и ЗЗГТ и не являются публичной офертой. Комплектация и параметры
могут быть изменены заводом-изготовителем.</p>
</div>
</div>
</footer>
<script src="{base}assets/js/config.js"></script>
<script src="{base}assets/js/site.js"></script>
</body>
</html>
"""


def request_form(cfg, form_id, subject, hidden=None, compact=False):
    hidden_html = "".join(
        f'<input type="hidden" name="{esc(k)}" value="{esc(v)}">' for k, v in (hidden or {}).items())
    message = "" if compact else f"""
<div class="field">
<label for="{form_id}-msg">Комментарий</label>
<textarea id="{form_id}-msg" name="Комментарий" rows="4" placeholder="Модель техники, регион работы, сроки"></textarea>
</div>"""

    return f"""<form class="form" data-form data-subject="{esc(subject)}" novalidate>
{hidden_html}
<input type="hidden" name="_subject" value="{esc(subject)}">
<div class="form__row">
<div class="field">
<label for="{form_id}-name">Ваше имя <span aria-hidden="true">*</span></label>
<input id="{form_id}-name" name="Имя" type="text" required autocomplete="name" placeholder="Иван Иванов">
<span class="field__error"></span>
</div>
<div class="field">
<label for="{form_id}-tel">Телефон <span aria-hidden="true">*</span></label>
<input id="{form_id}-tel" name="Телефон" type="tel" required autocomplete="tel" placeholder="+7 (___) ___-__-__">
<span class="field__error"></span>
</div>
</div>
<div class="field">
<label for="{form_id}-mail">Email</label>
<input id="{form_id}-mail" name="Email" type="email" autocomplete="email" placeholder="you@company.ru">
<span class="field__error"></span>
</div>{message}
<label class="form__consent">
<input type="checkbox" required>
<span>Согласен на обработку персональных данных <span aria-hidden="true">*</span>
<span class="field__error"></span></span>
</label>
<button type="submit" class="btn btn--wide">Отправить заявку</button>
<p class="form__status" role="status" hidden></p>
</form>"""


def machine_card(cfg, depth, item):
    base = rel(depth)
    href = f"{base}catalog/{item['brand']}/{item['category']}/{item['slug']}.html"
    photo = item["photos"][0] if item["photos"] else None
    media = (f'<img src="{base}{esc(photo["thumb"])}" alt="{esc(item["name"])}" loading="lazy" '
             f'width="640" height="480">'
             if photo else '<span class="gallery__empty">Фото уточняется</span>')
    cutout = " is-cutout" if photo and photo["cutout"] else ""

    rows = []
    for key, label in (("mass", "Масса"), ("power", "Мощность")):
        value = short_value(item["key"].get(key))
        if value:
            rows.append(f'<li><span>{label}</span><strong>{esc(value["value"])} '
                        f'{esc(value["unit"])}</strong></li>')
    third_key, third_label = CARD_THIRD.get(item["category"], (None, None))
    third = short_value(item["key"].get(third_key)) if third_key else None
    if third:
        rows.append(f'<li><span>{esc(third_label)}</span><strong>{esc(third["value"])} '
                    f'{esc(third["unit"])}</strong></li>')

    return f"""<article class="machine-card" data-name="{esc(item['name'])}"
 data-category="{esc(item['category'])}" data-brand="{esc(item['brand'])}"
 data-mass="{item['sort']['mass']}" data-power="{item['sort']['power']}">
<a class="machine-card__media{cutout}" href="{href}" tabindex="-1" aria-hidden="true">
<span class="machine-card__brand">{esc(BRANDS[item['brand']]['name'])}</span>
{media}
</a>
<div class="machine-card__body">
<h3 class="machine-card__title"><a href="{href}">{esc(item['name'])}</a></h3>
<p class="machine-card__cat">{esc(item['categoryTitle'])}</p>
<ul class="machine-card__specs">{"".join(rows)}</ul>
<a class="link-arrow" href="{href}">Характеристики</a>
</div>
</article>"""


def prose_from(description):
    titles = {
        "purpose": "Назначение и область применения",
        "advantages": "Преимущества",
        "equipment": "Комплектация и оснащение",
        "warranty": "Гарантия",
    }
    out = []
    for key in ("purpose", "advantages", "warranty", "equipment"):
        lines = description.get(key)
        if not lines:
            continue
        out.append(f"<h3>{titles[key]}</h3>")
        lead, body = "", lines
        # Строка с двоеточием — это подводка к перечислению, а не пункт списка.
        if len(lines) > 1 and lines[0].rstrip().endswith(":"):
            lead, body = lines[0], lines[1:]
            out.append(f"<p>{esc(lead)}</p>")
        if len(body) == 1 or (not lead and sum(len(l) for l in body) / len(body) > 220):
            out += [f"<p>{esc(l)}</p>" for l in body]
        else:
            out.append("<ul>" + "".join(f"<li>{esc(l)}</li>" for l in body) + "</ul>")
    return "".join(p for p in out if p)


def spec_table(item):
    """Таблица ТТХ. Колонок может быть больше одной — заводы сравнивают исполнения."""
    headers = (["Ед. изм."] if item["specUnitColumn"] else []) + item["specColumns"]
    width = len(headers) + 1
    rows = []
    for row in item["specs"]:
        if "group" in row:
            rows.append(f'<tr class="spec-group"><th colspan="{width}">{esc(row["group"])}</th></tr>')
            continue
        cells = (row["cells"] + [""] * width)[:width - 1]
        rows.append(f"<tr><td>{esc(row['name'])}</td>"
                    + "".join(f"<td>{esc(c)}</td>" for c in cells) + "</tr>")
    if not rows:
        return ('<p class="catalog-empty">Завод не публикует таблицу характеристик для этой '
                'модели — пришлём её вместе с коммерческим предложением.</p>')
    head_html = "".join(f"<th>{esc(h)}</th>" for h in headers)
    return (f'<div class="spec-table-wrap"><table class="spec-table">'
            f'<caption class="visually-hidden">Технические характеристики {esc(item["name"])}</caption>'
            f'<thead><tr><th>Параметр</th>{head_html}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def icon_card(icon, title, text):
    return (f'<div class="card"><div class="card__icon" aria-hidden="true">'
            f'<svg viewBox="0 0 36 36">{ICONS[icon]}</svg></div>'
            f'<h3>{esc(title)}</h3><p>{esc(text)}</p></div>')


def cta_block(cfg, form_id, subject, title, text):
    return f"""<section class="section section--panel">
<div class="shell">
<div class="cta hex-bg">
<div class="cta__grid">
<div>
<p class="eyebrow">Обратная связь</p>
<h2>{esc(title)}</h2>
<p>{esc(text)}</p>
<ul class="contact-list">
<li><div><p class="contact-list__label">Телефон</p>
<a class="contact-list__value" href="tel:{esc(cfg['phoneHref'])}">{esc(cfg['phone'])}</a></div></li>
<li><div><p class="contact-list__label">Почта</p>
<a class="contact-list__value" href="mailto:{esc(cfg['email'])}">{esc(cfg['email'])}</a></div></li>
</ul>
</div>
<div>{request_form(cfg, form_id, subject)}</div>
</div>
</div>
</div>
</section>"""


# --- Страницы ----------------------------------------------------------------

class Site:
    def __init__(self, cfg, items):
        self.cfg = cfg
        self.items = items
        self.categories = []
        seen = {}
        for item in items:
            key = (item["brand"], item["category"])
            if key not in seen:
                seen[key] = {
                    "brand": item["brand"],
                    "slug": item["category"],
                    "title": item["categoryTitle"],
                    "blurb": CATEGORY_BLURB.get(item["category"], ""),
                    "items": [],
                }
                self.categories.append(seen[key])
            seen[key]["items"].append(item)
        self.pages = []

    def write(self, path, markup):
        full = os.path.join(ROOT, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(markup)
        self.pages.append(path)

    def page(self, path, depth, title, description, current, body, extra_head=""):
        cfg = self.cfg
        markup = (head(cfg, depth, title, description, path.replace("index.html", ""), extra_head)
                  + header(cfg, depth, current, build_megamenu(depth, self.categories))
                  + body
                  + footer(cfg, depth, self.categories))
        self.write(path, markup)

    # --- главная ---

    def build_home(self):
        cfg = self.cfg
        # В герое нужен живой кадр, а не студийная вырезка на белом.
        hero_photo, hero_item = None, None
        for candidate in ([i for i in self.items if i["slug"] == "e225c"] + self.items):
            hero_photo = next((p for p in candidate["photos"] if not p["cutout"]), None)
            if hero_photo:
                hero_item = candidate
                break
        hero_img = (f'<img src="{esc(hero_photo["src"])}" alt="{esc(hero_item["name"])}" '
                    f'width="1200" height="900" fetchpriority="high">' if hero_photo else "")

        tiles = "".join(self.category_tile(0, c) for c in self.categories)
        popular = [i for i in self.items if i["photos"]][:6]
        cards = "".join(machine_card(cfg, 0, i) for i in popular)
        advantages = "".join(
            icon_card(icon, title, text)
            for (title, text), icon in zip(ADVANTAGES, ["shield", "parts", "service", "handshake"]))

        org = json.dumps({
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": cfg["legalName"],
            "alternateName": cfg["company"],
            "url": cfg["domain"],
            "logo": cfg["domain"] + "/assets/img/brand/logo.png",
            "telephone": cfg["phone"],
            "email": cfg["email"],
            "address": {k: v for k, v in {
                "@type": "PostalAddress", "addressLocality": cfg["city"],
                "streetAddress": cfg["address"], "addressCountry": "RU"}.items() if v},
            "description": "Официальный дилер UMG и ВПК (ЗЗГТ): продажа спецтехники, "
                           "запчасти и сервисное обслуживание.",
        }, ensure_ascii=False)

        body = f"""<main>
<section class="hero hex-bg">
<span class="diag-accent" style="right:12%"></span>
<div class="shell hero__grid">
<div>
<p class="eyebrow">Официальный дилер UMG и ВПК (ЗЗГТ)</p>
<h1>Спецтехника,<br>которая <em>работает</em></h1>
<p class="hero__lead">Продаём экскаваторы, погрузчики, автогрейдеры, бульдозеры и гусеничные
снегоболотоходы напрямую с заводов. Держим склад запчастей и обслуживаем технику весь срок службы.</p>
<div class="hero__actions">
<a class="btn" href="catalog/index.html">Каталог техники</a>
<a class="btn btn--ghost" href="#zayavka">Запросить цену</a>
</div>
<div class="hero__badges">
<span class="badge badge--green">{esc(cfg['tagline'])}</span>
<span class="badge badge--outline">Заводская гарантия</span>
<span class="badge badge--outline">Лизинг и trade-in</span>
</div>
</div>
<div class="hero__media">{hero_img}</div>
</div>
</section>

<section class="section section--deep" style="padding-top:0;padding-bottom:0">
<div class="shell" style="padding:0">
<div class="stats">
<div class="stats__item"><p class="stats__value">2</p><p class="stats__label">завода-производителя, чью технику мы поставляем напрямую</p></div>
<div class="stats__item"><p class="stats__value">{len(self.items)}</p><p class="stats__label">моделей техники в каталоге с полными характеристиками</p></div>
<div class="stats__item"><p class="stats__value">{len(self.categories)}</p><p class="stats__label">категорий: от мини-погрузчиков до снегоболотоходов</p></div>
<div class="stats__item"><p class="stats__value">24/7</p><p class="stats__label">приём заявок на сервис и подбор запчастей</p></div>
</div>
</div>
</section>

<section class="section">
<div class="shell">
<div class="section__head">
<p class="eyebrow">Каталог</p>
<h2>Техника по категориям</h2>
<p>Проваливайтесь в категорию, чтобы сравнить модели, или сразу открывайте карточку —
там полная таблица характеристик производителя и фотографии.</p>
</div>
<div class="grid grid--3">{tiles}</div>
</div>
</section>

<section class="section section--panel">
<div class="shell">
<div class="section__head">
<p class="eyebrow">Популярные модели</p>
<h2>Чаще всего спрашивают</h2>
</div>
<div class="grid grid--3">{cards}</div>
<p style="margin-top:28px"><a class="link-arrow" href="catalog/index.html">Смотреть весь каталог</a></p>
</div>
</section>

<section class="section">
<div class="shell">
<div class="section__head">
<p class="eyebrow">Направления</p>
<h2>Техника. Сервис. Запчасти.</h2>
</div>
<div class="grid grid--3">
<div class="card">
<div class="card__icon" aria-hidden="true"><svg viewBox="0 0 36 36">{ICONS['excavator']}</svg></div>
<h3>Продажа техники</h3>
<p>Экскаваторы, погрузчики, грейдеры, бульдозеры UMG и снегоболотоходы ЗЗГТ.
Подбираем модель под грунт, объём работ и бюджет.</p>
<p style="margin-top:14px"><a class="link-arrow" href="catalog/index.html">В каталог</a></p>
</div>
<div class="card">
<div class="card__icon" aria-hidden="true"><svg viewBox="0 0 36 36">{ICONS['parts']}</svg></div>
<h3>Запчасти</h3>
<p>Оригинальные детали по узлам: двигатель, гидравлика, ходовая, трансмиссия.
Подбираем по серийному номеру машины.</p>
<p style="margin-top:14px"><a class="link-arrow" href="parts.html">Подобрать запчасть</a></p>
</div>
<div class="card">
<div class="card__icon" aria-hidden="true"><svg viewBox="0 0 36 36">{ICONS['service']}</svg></div>
<h3>Сервис</h3>
<p>Гарантийный и постгарантийный ремонт, плановое ТО, выездные бригады
и диагностика на объекте заказчика.</p>
<p style="margin-top:14px"><a class="link-arrow" href="service.html">Условия сервиса</a></p>
</div>
</div>
</div>
</section>

<section class="section section--deep">
<div class="shell">
<div class="section__head">
<p class="eyebrow">Почему мы</p>
<h2>Дилер, а не перепродажа</h2>
</div>
<div class="grid grid--4">{advantages}</div>
</div>
</section>

<div id="zayavka"></div>
{cta_block(cfg, "home", "Заявка с главной страницы",
           "Подберём технику под вашу задачу",
           "Расскажите, какие работы предстоят и в каком регионе — предложим модель, "
           "посчитаем стоимость с доставкой и вариант лизинга.")}
</main>"""

        self.page("index.html", 0,
                  f"{cfg['company']} — спецтехника UMG и ЗЗГТ, запчасти и сервис",
                  "Официальный дилер UMG и ВПК (ЗЗГТ). Экскаваторы, погрузчики, автогрейдеры, "
                  "бульдозеры и снегоболотоходы: характеристики, цены, запчасти и сервис.",
                  "index.html", body,
                  extra_head=f'<script type="application/ld+json">{org}</script>\n')

    def category_tile(self, depth, cat):
        base = rel(depth)
        photo = next((i["photos"][0]["thumb"] for i in cat["items"] if i["photos"]), None)
        img = (f'<div class="cat-tile__img"><img src="{base}{esc(photo)}" alt="" loading="lazy" '
               f'width="640" height="480"></div>' if photo else "")
        return f"""<a class="cat-tile" href="{base}catalog/{cat['brand']}/{cat['slug']}/index.html">
{img}
<div class="cat-tile__body">
<span class="badge badge--green" style="margin-bottom:10px">{esc(BRANDS[cat['brand']]['name'])}</span>
<h3 class="cat-tile__title">{esc(cat['title'])}</h3>
<p class="cat-tile__meta">{len(cat['items'])} моделей</p>
</div>
</a>"""

    # --- каталог ---

    def build_catalog_index(self):
        cfg = self.cfg
        blocks = []
        for brand_key, brand in BRANDS.items():
            cats = [c for c in self.categories if c["brand"] == brand_key]
            if not cats:
                continue
            tiles = "".join(self.category_tile(1, c) for c in cats)
            count = sum(len(c["items"]) for c in cats)
            blocks.append(f"""<section class="section{' section--panel' if brand_key == 'zzgt' else ''}">
<div class="shell">
<div class="section__head">
<p class="eyebrow">{esc(brand['name'])}</p>
<h2>{esc(brand['full'])}</h2>
<p>{esc(brand['note'])} В каталоге {count} моделей.</p>
</div>
<div class="grid grid--3">{tiles}</div>
<p style="margin-top:26px"><a class="link-arrow" href="{brand_key}/index.html">Все модели {esc(brand['name'])}</a></p>
</div>
</section>""")

        body = (breadcrumbs(cfg, 1, [("Главная", "index.html"), ("Каталог", None)])
                + f"""<main>
<section class="section hex-bg" style="padding-bottom:0">
<div class="shell">
<div class="section__head">
<p class="eyebrow">Каталог техники</p>
<h1>Вся техника {esc(cfg['company'])}</h1>
<p>Два производителя, {len(self.categories)} категорий и {len(self.items)} моделей.
В каждой карточке — заводская таблица характеристик и фотографии машины.</p>
</div>
</div>
</section>
{"".join(blocks)}
{cta_block(cfg, "catalog", "Заявка из каталога", "Не нашли нужную модель?",
           "Заводы выпускают больше исполнений, чем показано в каталоге. "
           "Напишите задачу — подберём машину и посчитаем стоимость.")}
</main>""")

        self.page("catalog/index.html", 1, f"Каталог спецтехники UMG и ЗЗГТ — {cfg['company']}",
                  "Полный каталог: гусеничные и колёсные экскаваторы, погрузчики, автогрейдеры, "
                  "бульдозеры UMG и гусеничные снегоболотоходы ЗЗГТ с характеристиками.",
                  "catalog/index.html", body)

    def build_brand_page(self, brand_key):
        cfg = self.cfg
        brand = BRANDS[brand_key]
        cats = [c for c in self.categories if c["brand"] == brand_key]
        items = [i for i in self.items if i["brand"] == brand_key]

        filters = "".join(
            f'<label><input type="checkbox" data-filter="category" value="{esc(c["slug"])}">'
            f'<span>{esc(c["title"])}</span></label>' for c in cats)
        cards = "".join(machine_card(cfg, 2, i) for i in items)

        body = (breadcrumbs(cfg, 2, [("Главная", "index.html"), ("Каталог", "catalog/index.html"),
                                     (brand["name"], None)])
                + f"""<main>
<section class="section hex-bg">
<div class="shell">
<div class="section__head">
<p class="eyebrow">{esc(brand['name'])}</p>
<h1>Техника {esc(brand['name'])}</h1>
<p>{esc(brand['note'])}</p>
</div>
<div class="catalog-layout" data-catalog>
<aside class="filters">
<div class="filters__group">
<p class="filters__legend">Категория</p>
{filters}
</div>
<div class="filters__group">
<button type="button" class="btn btn--dark btn--wide" data-catalog-reset>Сбросить</button>
</div>
</aside>
<div>
<div class="catalog-toolbar">
<p class="catalog-toolbar__count" data-catalog-count></p>
<label class="visually-hidden" for="sort-{brand_key}">Сортировка</label>
<select class="select" id="sort-{brand_key}" data-catalog-sort>
<option value="name">По названию</option>
<option value="massDesc">Масса: по убыванию</option>
<option value="massAsc">Масса: по возрастанию</option>
<option value="powerDesc">Мощность: по убыванию</option>
</select>
</div>
<div class="grid grid--3" data-catalog-grid>{cards}</div>
<p class="catalog-empty" data-catalog-empty hidden>Под выбранные фильтры моделей нет — сбросьте часть условий.</p>
</div>
</div>
</div>
</section>
{cta_block(cfg, brand_key, f"Заявка на технику {brand['name']}",
           f"Нужна консультация по технике {brand['name']}?",
           "Подскажем, какая модель закроет вашу задачу, и посчитаем стоимость с доставкой.")}
</main>""")

        self.page(f"catalog/{brand_key}/index.html", 2,
                  f"Техника {brand['name']} — модели и характеристики | {cfg['company']}",
                  f"{brand['note']} {len(items)} моделей с полными техническими характеристиками.",
                  "catalog/index.html", body)

    def build_category_page(self, cat):
        cfg = self.cfg
        brand = BRANDS[cat["brand"]]
        cards = "".join(machine_card(cfg, 3, i) for i in cat["items"])

        body = (breadcrumbs(cfg, 3, [("Главная", "index.html"), ("Каталог", "catalog/index.html"),
                                     (brand["name"], f"catalog/{cat['brand']}/index.html"),
                                     (cat["title"], None)])
                + f"""<main>
<section class="section hex-bg">
<div class="shell">
<div class="section__head">
<p class="eyebrow">{esc(brand['name'])}</p>
<h1>{esc(cat['title'])}</h1>
<p>{esc(cat['blurb'])}</p>
</div>
<div data-catalog>
<div class="catalog-toolbar">
<p class="catalog-toolbar__count" data-catalog-count></p>
<label class="visually-hidden" for="sort-{cat['slug']}">Сортировка</label>
<select class="select" id="sort-{cat['slug']}" data-catalog-sort>
<option value="name">По названию</option>
<option value="massDesc">Масса: по убыванию</option>
<option value="massAsc">Масса: по возрастанию</option>
<option value="powerDesc">Мощность: по убыванию</option>
</select>
</div>
<div class="grid grid--3" data-catalog-grid>{cards}</div>
<p class="catalog-empty" data-catalog-empty hidden>Моделей нет.</p>
</div>
</div>
</section>
{cta_block(cfg, cat['slug'], f"Заявка: {cat['title']}",
           "Поможем выбрать между моделями",
           "Разница между исполнениями часто в ширине хода, длине рукояти и объёме ковша. "
           "Опишите условия работы — подберём точно.")}
</main>""")

        self.page(f"catalog/{cat['brand']}/{cat['slug']}/index.html", 3,
                  f"{cat['title']} {brand['name']} — характеристики и цены | {cfg['company']}",
                  f"{cat['blurb']} {len(cat['items'])} моделей {brand['name']} с характеристиками.",
                  "catalog/index.html", body)

    def build_product_page(self, item):
        cfg = self.cfg
        brand = BRANDS[item["brand"]]
        depth = 3
        base = rel(depth)

        if item["photos"]:
            main_photo = item["photos"][0]
            main_html = (f'<img src="{base}{esc(main_photo["src"])}" alt="{esc(item["name"])}" '
                         f'width="1200" height="900" fetchpriority="high">')
            thumbs = "".join(
                f'<button type="button" class="gallery__thumb'
                f'{" is-cutout" if p["cutout"] else ""}" data-full="{base}{esc(p["src"])}" '
                f'data-cutout="{str(p["cutout"]).lower()}" '
                f'data-alt="{esc(item["name"])} — фото {n}" aria-label="Фото {n}">'
                f'<img src="{base}{esc(p["thumb"])}" alt="" loading="lazy" width="640" height="480">'
                f'</button>' for n, p in enumerate(item["photos"], 1))
            thumbs_html = f'<div class="gallery__thumbs">{thumbs}</div>' if len(item["photos"]) > 1 else ""
            main_class = " is-cutout" if main_photo["cutout"] else ""
        else:
            main_html = '<span class="gallery__empty">Фотографии уточняются</span>'
            thumbs_html = ""
            main_class = ""

        key_items = []
        for key, label in (("mass", "Эксплуатационная масса"), ("power", "Мощность двигателя")):
            value = short_value(item["key"].get(key))
            if value:
                key_items.append(f'<div class="keyspecs__item"><p class="keyspecs__label">{label}</p>'
                                 f'<p class="keyspecs__value">{esc(value["value"])}'
                                 f'<span>{esc(value["unit"])}</span></p></div>')
        third_key, third_label = CARD_THIRD.get(item["category"], (None, None))
        third = short_value(item["key"].get(third_key)) if third_key else None
        if third:
            key_items.append(f'<div class="keyspecs__item"><p class="keyspecs__label">{esc(third_label)}</p>'
                             f'<p class="keyspecs__value">{esc(third["value"])}'
                             f'<span>{esc(third["unit"])}</span></p></div>')

        overview = prose_from(item["description"]) or (
            f"<p>{esc(item['name'])} — техника производства {esc(brand['full'])}. "
            f"Полное описание и комплектацию уточняйте у менеджера.</p>")

        similar = [i for i in self.items
                   if i["category"] == item["category"] and i["slug"] != item["slug"]][:3]
        similar_html = ""
        if similar:
            similar_html = f"""<section class="section section--panel">
<div class="shell">
<div class="section__head"><p class="eyebrow">Сравните</p><h2>Похожие модели</h2></div>
<div class="grid grid--3">{"".join(machine_card(cfg, depth, i) for i in similar)}</div>
</div>
</section>"""

        product_ld = json.dumps({
            "@context": "https://schema.org",
            "@type": "Product",
            "name": f"{brand['name']} {item['name']}",
            "category": item["categoryTitle"],
            "brand": {"@type": "Brand", "name": brand["name"]},
            "image": [f"{cfg['domain']}/{p['src']}" for p in item["photos"][:4]],
            "description": (item["description"].get("purpose") or [item["categoryTitle"]])[0][:300],
            "offers": {"@type": "Offer", "availability": "https://schema.org/InStock",
                       "priceCurrency": "RUB", "url": f"{cfg['domain']}/catalog/{item['brand']}/"
                                                      f"{item['category']}/{item['slug']}.html",
                       "seller": {"@type": "Organization", "name": cfg["legalName"]}},
        }, ensure_ascii=False)

        equipment_tab = ""
        equipment_btn = ""
        if item["description"].get("equipment"):
            lines = item["description"]["equipment"]
            equipment_btn = ('<button type="button" class="tabs__btn" role="tab" '
                             'aria-controls="tab-equipment" aria-selected="false" '
                             'id="tabbtn-equipment">Комплектация</button>')
            equipment_tab = (f'<div class="tabs__panel prose" role="tabpanel" id="tab-equipment" '
                             f'aria-labelledby="tabbtn-equipment" hidden><ul>'
                             + "".join(f"<li>{esc(l)}</li>" for l in lines) + "</ul></div>")

        body = (breadcrumbs(cfg, depth, [
            ("Главная", "index.html"),
            ("Каталог", "catalog/index.html"),
            (brand["name"], f"catalog/{item['brand']}/index.html"),
            (item["categoryTitle"], f"catalog/{item['brand']}/{item['category']}/index.html"),
            (item["name"], None)])
            + f"""<main>
<section class="product">
<div class="shell">
<div class="product__top">
<div data-gallery>
<div class="gallery__main{main_class}">{main_html}</div>
{thumbs_html}
</div>
<div>
<span class="badge badge--green">{esc(brand['name'])}</span>
<h1 class="product__title">{esc(item['name'])}</h1>
<p class="product__sub">{esc(item['categoryTitle'])} · {esc(brand['full'])}</p>
<div class="keyspecs">{"".join(key_items)}</div>
<div class="product__actions">
<a class="btn" href="#zapros">Запросить цену</a>
<a class="btn btn--ghost" href="{base}financing.html">В лизинг</a>
<a class="btn btn--dark" href="tel:{esc(cfg['phoneHref'])}">Позвонить</a>
</div>
<p class="product__note">Заводская гарантия, оригинальные запчасти и сервис
{esc(cfg['company'])} на весь срок эксплуатации.</p>
</div>
</div>

<div class="tabs" data-tabs>
<div class="tabs__list" role="tablist" aria-label="Информация о модели">
<button type="button" class="tabs__btn" role="tab" aria-controls="tab-overview" aria-selected="true" id="tabbtn-overview">Обзор</button>
<button type="button" class="tabs__btn" role="tab" aria-controls="tab-specs" aria-selected="false" id="tabbtn-specs">Характеристики</button>
{equipment_btn}
<button type="button" class="tabs__btn" role="tab" aria-controls="tab-docs" aria-selected="false" id="tabbtn-docs">Документы</button>
</div>
<div class="tabs__panel prose" role="tabpanel" id="tab-overview" aria-labelledby="tabbtn-overview">{overview}</div>
<div class="tabs__panel" role="tabpanel" id="tab-specs" aria-labelledby="tabbtn-specs" hidden>
{spec_table(item)}
<p style="margin-top:16px;font-size:.85rem;color:var(--muted)">Данные приведены по официальной
документации производителя (<a href="{esc(item['source'])}" rel="nofollow noopener" target="_blank"
style="color:var(--alpha-green)">{esc(brand['name'])}</a>). Завод вправе менять параметры без уведомления.</p>
</div>
{equipment_tab}
<div class="tabs__panel prose" role="tabpanel" id="tab-docs" aria-labelledby="tabbtn-docs" hidden>
<h3>Что передаём с машиной</h3>
<ul>
<li>Паспорт самоходной машины (ПСМ) и сертификат соответствия;</li>
<li>Руководство по эксплуатации и сервисная книжка;</li>
<li>Каталог запасных частей под ваше исполнение;</li>
<li>Договор поставки и гарантийные обязательства завода.</li>
</ul>
<p>Коммерческое предложение с ценой, сроком поставки и комплектацией высылаем в ответ
на заявку — обычно в течение рабочего дня.</p>
<p><a class="btn" href="#zapros">Запросить документы</a></p>
</div>
</div>
</div>
</section>

{similar_html}

<section class="section" id="zapros">
<div class="shell">
<div class="cta hex-bg">
<div class="cta__grid">
<div>
<p class="eyebrow">Запрос цены</p>
<h2>{esc(item['name'])} — узнать стоимость</h2>
<p>Пришлём коммерческое предложение с ценой, сроком поставки, комплектацией
и вариантом лизинга.</p>
<ul class="contact-list">
<li><div><p class="contact-list__label">Телефон</p>
<a class="contact-list__value" href="tel:{esc(cfg['phoneHref'])}">{esc(cfg['phone'])}</a></div></li>
<li><div><p class="contact-list__label">Почта</p>
<a class="contact-list__value" href="mailto:{esc(cfg['email'])}">{esc(cfg['email'])}</a></div></li>
</ul>
</div>
<div>{request_form(cfg, 'product', f"Запрос цены: {brand['name']} {item['name']}",
                   hidden={"Модель": f"{brand['name']} {item['name']}",
                           "Категория": item["categoryTitle"]})}</div>
</div>
</div>
</div>
</section>
</main>

<div class="lightbox" id="lightbox" hidden role="dialog" aria-modal="true" aria-label="Просмотр фото">
<button type="button" class="lightbox__close" aria-label="Закрыть">&times;</button>
<button type="button" class="lightbox__nav lightbox__nav--prev" aria-label="Предыдущее фото">&lsaquo;</button>
<img alt="">
<button type="button" class="lightbox__nav lightbox__nav--next" aria-label="Следующее фото">&rsaquo;</button>
</div>""")

        mass = short_value(item["key"].get("mass"))
        power = short_value(item["key"].get("power"))
        summary = ", ".join(filter(None, [
            f"масса {mass['value']} {mass['unit']}" if mass else None,
            f"мощность {power['value']} {power['unit']}" if power else None,
        ]))
        self.page(f"catalog/{item['brand']}/{item['category']}/{item['slug']}.html", depth,
                  f"{brand['name']} {item['name']} — характеристики, фото, цена | {cfg['company']}",
                  f"{item['categoryTitle']} {brand['name']} {item['name']}"
                  + (f": {summary}. " if summary else ". ")
                  + "Полные технические характеристики, фотографии и запрос цены у дилера.",
                  "catalog/index.html", body,
                  extra_head=f'<script type="application/ld+json">{product_ld}</script>\n')

    # --- служебные страницы ---

    def build_parts(self):
        cfg = self.cfg
        cards = "".join(
            icon_card(icon, title, text)
            for (title, text), icon in zip(
                PARTS_GROUPS,
                ["service", "hydraulics", "excavator", "gearbox", "electric", "bucket"]))

        body = (breadcrumbs(cfg, 0, [("Главная", "index.html"), ("Запчасти", None)])
                + f"""<main>
<section class="section hex-bg">
<div class="shell">
<div class="section__head">
<p class="eyebrow">Запчасти</p>
<h1>Оригинальные запчасти UMG и ЗЗГТ</h1>
<p>Поставляем детали напрямую с заводов-изготовителей. Подбираем по серийному номеру машины,
чтобы деталь подошла к вашему исполнению, а не «к похожей модели».</p>
</div>
<div class="grid grid--3">{cards}</div>
</div>
</section>

<section class="section section--panel">
<div class="shell">
<div class="section__head">
<p class="eyebrow">Как это работает</p>
<h2>От заявки до отгрузки</h2>
</div>
<div class="grid grid--4">
{icon_card('doc', '1. Заявка', 'Присылаете модель, серийный номер машины и список деталей — или просто фото узла.')}
{icon_card('parts', '2. Подбор', 'Сверяем по заводскому каталогу запчастей и подтверждаем артикулы.')}
{icon_card('clock', '3. Сроки и цена', 'Сообщаем наличие, стоимость и срок поставки до вашего склада.')}
{icon_card('truck', '4. Отгрузка', 'Отправляем транспортной компанией в любой регион России.')}
</div>
</div>
</section>

{cta_block(cfg, "parts", "Подбор запчастей",
           "Подберём запчасть по серийному номеру",
           "Укажите модель техники и серийный номер — так мы гарантированно попадём "
           "в нужное исполнение узла.")}
</main>""")

        self.page("parts.html", 0, f"Запчасти для техники UMG и ЗЗГТ | {cfg['company']}",
                  "Оригинальные запчасти UMG и ЗЗГТ: двигатель, гидравлика, ходовая часть, "
                  "трансмиссия, рабочее оборудование. Подбор по серийному номеру.",
                  "parts.html", body)

    def build_service(self):
        cfg = self.cfg
        cards = "".join(
            icon_card(icon, title, text)
            for (title, text), icon in zip(
                SERVICE_ITEMS,
                ["shield", "clock", "truck", "hydraulics", "excavator", "gearbox"]))

        body = (breadcrumbs(cfg, 0, [("Главная", "index.html"), ("Сервис", None)])
                + f"""<main>
<section class="section hex-bg">
<div class="shell">
<div class="section__head">
<p class="eyebrow">Сервис</p>
<h1>Обслуживание техники</h1>
<p>Ремонтируем и обслуживаем технику UMG и ЗЗГТ. Гарантийные работы проводим с сохранением
заводской гарантии, постгарантийные — на оригинальных запчастях.</p>
</div>
<div class="grid grid--3">{cards}</div>
</div>
</section>

<section class="section section--panel">
<div class="shell">
<div class="section__head">
<p class="eyebrow">Вопросы</p>
<h2>Что спрашивают чаще всего</h2>
</div>
<div class="accordion">
<div class="accordion__item">
<button type="button" class="accordion__btn" aria-expanded="false" aria-controls="faq-1">
Выезжаете ли вы на объект?<span class="accordion__icon" aria-hidden="true"></span></button>
<div class="accordion__panel" id="faq-1" hidden>
<p>Да. Для большинства работ бригада приезжает на площадку со своим инструментом
и диагностическим оборудованием — технику не нужно снимать с объекта.</p>
</div>
</div>
<div class="accordion__item">
<button type="button" class="accordion__btn" aria-expanded="false" aria-controls="faq-2">
Сохраняется ли гарантия завода?<span class="accordion__icon" aria-hidden="true"></span></button>
<div class="accordion__panel" id="faq-2" hidden>
<p>Да, при обслуживании у официального дилера с использованием оригинальных запчастей
гарантия производителя сохраняется в полном объёме.</p>
</div>
</div>
<div class="accordion__item">
<button type="button" class="accordion__btn" aria-expanded="false" aria-controls="faq-3">
Обслуживаете технику, купленную не у вас?<span class="accordion__icon" aria-hidden="true"></span></button>
<div class="accordion__panel" id="faq-3" hidden>
<p>Обслуживаем. Для постановки на сервис нужны модель, серийный номер и текущая наработка
в моточасах.</p>
</div>
</div>
<div class="accordion__item">
<button type="button" class="accordion__btn" aria-expanded="false" aria-controls="faq-4">
Как быстро реагируете на заявку?<span class="accordion__icon" aria-hidden="true"></span></button>
<div class="accordion__panel" id="faq-4" hidden>
<p>Заявки принимаем круглосуточно. Диагностику и план работ согласовываем в ближайший
рабочий день, срок выезда зависит от региона и наличия запчастей.</p>
</div>
</div>
</div>
</div>
</section>

{cta_block(cfg, "service", "Заявка на сервис",
           "Оставьте заявку на обслуживание",
           "Укажите модель, серийный номер и характер неисправности — согласуем диагностику "
           "и назовём срок выезда.")}
</main>""")

        self.page("service.html", 0, f"Сервис и ремонт спецтехники UMG и ЗЗГТ | {cfg['company']}",
                  "Гарантийный и постгарантийный ремонт, плановое ТО, выездные бригады, "
                  "ремонт гидравлики и ходовой части техники UMG и ЗЗГТ.",
                  "service.html", body)

    def build_financing(self):
        cfg = self.cfg
        steps = "".join(
            f'<div class="card"><p class="stats__value">{n}</p><h3>{esc(title)}</h3><p>{esc(text)}</p></div>'
            for n, (title, text) in enumerate(FINANCING_STEPS, 1))

        body = (breadcrumbs(cfg, 0, [("Главная", "index.html"), ("Лизинг", None)])
                + f"""<main>
<section class="section hex-bg">
<div class="shell">
<div class="section__head">
<p class="eyebrow">Финансирование</p>
<h1>Лизинг и trade-in</h1>
<p>Техника окупается в работе, а не на стоянке. Помогаем взять машину в лизинг с посильным
авансом и графиком платежей под сезонность вашей выручки.</p>
</div>
<div class="grid grid--3">
{icon_card('handshake', 'Лизинг для юрлиц и ИП', 'Аванс от 10%, срок до 60 месяцев. Предмет лизинга остаётся обеспечением — дополнительный залог обычно не нужен.')}
{icon_card('doc', 'Налоговая выгода', 'Лизинговые платежи относятся на расходы, НДС принимается к вычету. Возможна ускоренная амортизация.')}
{icon_card('truck', 'Trade-in', 'Принимаем вашу технику в зачёт стоимости новой — оцениваем по состоянию и наработке.')}
</div>
</div>
</section>

<section class="section section--panel">
<div class="shell">
<div class="section__head">
<p class="eyebrow">Порядок</p>
<h2>Как проходит сделка</h2>
</div>
<div class="grid grid--3">{steps}</div>
</div>
</section>

{cta_block(cfg, "financing", "Заявка на лизинг",
           "Рассчитаем лизинг под вашу технику",
           "Напишите модель и желаемый аванс — сравним предложения лизинговых компаний "
           "и покажем итоговое удорожание.")}
</main>""")

        self.page("financing.html", 0, f"Лизинг спецтехники и trade-in | {cfg['company']}",
                  "Лизинг техники UMG и ЗЗГТ для юридических лиц и ИП: аванс от 10%, срок до 60 "
                  "месяцев, приём техники в trade-in.",
                  "financing.html", body)

    def build_about(self):
        cfg = self.cfg
        brand_cards = "".join(f"""<div class="card">
<span class="badge badge--green" style="margin-bottom:14px">{esc(b['name'])}</span>
<h3>{esc(b['full'])}</h3>
<p>{esc(b['note'])}</p>
<p style="margin-top:14px"><a class="link-arrow" href="catalog/{key}/index.html">Модельный ряд</a></p>
</div>""" for key, b in BRANDS.items())

        body = (breadcrumbs(cfg, 0, [("Главная", "index.html"), ("О компании", None)])
                + f"""<main>
<section class="section hex-bg">
<div class="shell">
<div class="section__head">
<p class="eyebrow">О компании</p>
<h1>{esc(cfg['company'])}</h1>
<p>Мы поставляем и обслуживаем спецтехнику. Три направления — продажа, запчасти и сервис —
закрывают весь жизненный цикл машины: от подбора модели под задачу до ремонта на объекте.</p>
</div>
<div class="grid grid--2">{brand_cards}</div>
</div>
</section>

<section class="section section--panel">
<div class="shell">
<div class="section__head">
<p class="eyebrow">Принципы</p>
<h2>Как мы работаем</h2>
</div>
<div class="grid grid--4">
{"".join(icon_card(icon, title, text) for (title, text), icon in zip(ADVANTAGES, ['shield', 'parts', 'service', 'handshake']))}
</div>
</div>
</section>

<section class="section">
<div class="shell">
<div class="section__head">
<p class="eyebrow">Дилерский статус</p>
<h2>Почему это важно</h2>
</div>
<div class="prose">
<p>Официальный дилер работает по договору с заводом: техника приходит с заводским ПСМ,
гарантией и правом на гарантийное обслуживание. Запчасти идут по заводским артикулам,
а не «аналог, который подошёл в прошлый раз».</p>
<p>На практике это означает три вещи:</p>
<ul>
<li>гарантия производителя действует и не аннулируется после первого же ремонта;</li>
<li>сервис имеет доступ к технической документации и обновлениям от завода;</li>
<li>цена на технику — дилерская, без наценки посредника в цепочке.</li>
</ul>
</div>
</div>
</section>

{cta_block(cfg, "about", "Заявка со страницы о компании",
           "Обсудим вашу задачу",
           "Расскажите, какую технику подбираете или что нужно обслужить — ответим "
           "в ближайший рабочий день.")}
</main>""")

        self.page("about.html", 0, f"О компании — официальный дилер UMG и ЗЗГТ | {cfg['company']}",
                  f"{cfg['company']} — официальный дилер UMG и ВПК (ЗЗГТ): продажа спецтехники, "
                  "поставка оригинальных запчастей и сервисное обслуживание.",
                  "about.html", body)

    def build_contacts(self):
        cfg = self.cfg
        rows = [("Телефон", cfg["phone"], f"tel:{cfg['phoneHref']}"),
                ("Электронная почта", cfg["email"], f"mailto:{cfg['email']}"),
                ("Режим работы", cfg["hours"], None),
                ("Адрес", full_address(cfg), None)]
        if cfg.get("inn"):
            rows.append(("ИНН", cfg["inn"], None))
        if cfg.get("ogrn"):
            rows.append(("ОГРН", cfg["ogrn"], None))

        contact_html = "".join(
            f'<li><div><p class="contact-list__label">{esc(label)}</p>'
            + (f'<a class="contact-list__value" href="{esc(href)}">{esc(value)}</a>'
               if href else f'<p class="contact-list__value">{esc(value)}</p>')
            + "</div></li>" for label, value, href in rows)

        messengers = ""
        wa = cfg.get("messengers", {}).get("whatsapp")
        if wa:
            messengers = (f'<p style="margin-top:20px"><a class="btn btn--ghost" href="{esc(wa)}" '
                          f'target="_blank" rel="noopener">Написать в WhatsApp</a></p>')

        body = (breadcrumbs(cfg, 0, [("Главная", "index.html"), ("Контакты", None)])
                + f"""<main>
<section class="section hex-bg">
<div class="shell">
<div class="section__head">
<p class="eyebrow">Контакты</p>
<h1>Связаться с нами</h1>
<p>Звоните в рабочее время или оставьте заявку — перезвоним и уточним детали.</p>
</div>
<div class="cta">
<div class="cta__grid">
<div>
<ul class="contact-list">{contact_html}</ul>
{messengers}
</div>
<div>{request_form(cfg, "contacts", "Заявка со страницы контактов")}</div>
</div>
</div>
</div>
</section>
</main>""")

        self.page("contacts.html", 0, f"Контакты | {cfg['company']}",
                  f"Телефон {cfg['phone']}, почта {cfg['email']}. Заявки на технику, "
                  "запчасти и сервис.",
                  "contacts.html", body)

    def build_404(self):
        cfg = self.cfg
        markup = (head(cfg, 0, f"Страница не найдена | {cfg['company']}",
                       "Такой страницы нет — вернитесь в каталог техники.", "404.html")
                  .replace('href="assets/', 'href="/assets/')
                  + f"""<main class="section hex-bg" style="min-height:70vh;display:grid;place-items:center">
<div class="shell" style="text-align:center;max-width:640px">
<p class="eyebrow" style="justify-content:center">Ошибка 404</p>
<h1>Страница не найдена</h1>
<p>Возможно, адрес устарел или модель переехала в другую категорию.</p>
<p style="margin-top:26px"><a class="btn" href="/catalog/index.html">Открыть каталог</a></p>
<p><a class="link-arrow" href="/index.html" style="justify-content:center">На главную</a></p>
</div>
</main>
<script src="/assets/js/config.js"></script>
<script src="/assets/js/site.js"></script>
</body>
</html>
""")
        self.write("404.html", markup)

    def build_config_js(self):
        cfg = self.cfg
        payload = json.dumps({
            "phone": cfg["phone"], "phoneHref": cfg["phoneHref"], "email": cfg["email"],
            "formEndpoint": cfg["formEndpoint"],
        }, ensure_ascii=False)
        path = os.path.join(ROOT, "assets", "js", "config.js")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"window.ALFA_CONFIG = {payload};\n")

    def build_sitemap(self):
        cfg = self.cfg
        urls = "".join(
            f"<url><loc>{esc(cfg['domain'])}/{esc(p.replace('index.html', ''))}</loc></url>"
            for p in sorted(self.pages) if p != "404.html")
        self.write("sitemap.xml",
                   '<?xml version="1.0" encoding="UTF-8"?>\n'
                   '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                   f"{urls}</urlset>\n")
        with open(os.path.join(ROOT, "robots.txt"), "w", encoding="utf-8") as f:
            f.write(f"User-agent: *\nAllow: /\n\nSitemap: {cfg['domain']}/sitemap.xml\n")


def prepare(items):
    """Добавляет каждой модели ключевые ТТХ и числа для сортировки."""
    tone = {}
    if os.path.exists(TONE_CACHE):
        with open(TONE_CACHE, encoding="utf-8") as f:
            tone = json.load(f)

    # <sup> при разборе схлопнулся в пробел: «кг/см 2» → «кг/см²».
    def superscripts(text):
        return re.sub(r"\b(мм|см|дм|м)\s?([23])(?![\w-])",
                      lambda m: m.group(1) + "²³"[int(m.group(2)) - 2], text)

    latin = str.maketrans("АВСЕНКМОРТХ", "ABCEHKMOPTX")
    for item in items:
        for row in item["specs"]:
            if "cells" in row:
                row["cells"] = [superscripts(c) for c in row["cells"]]
                row["name"] = superscripts(row["name"])
        # Заводы набирают индексы вроде «Е160С СТ» кириллицей — приводим к латинице.
        item["specColumns"] = [
            c.translate(latin) if item["brand"] == "umg" and len(c) < 25 and re.search(r"[A-Za-z]", c)
            else c for c in item["specColumns"]]
        # Безликие «Значение»/«Показатель» в шапке заменяем индексом модели.
        item["specColumns"] = [
            item["name"] if re.fullmatch(r"значени[ея]|показател[ья]|велич\w*", c.strip(), re.I) else c
            for c in item["specColumns"]] or [item["name"]]
        item["key"] = {key: find_spec(item, key) for key in SPEC_KEYS}
        item["sort"] = {
            "mass": round(spec_number(item["key"]["mass"], to_kg=True), 2),
            "power": round(spec_number(item["key"]["power"]), 2),
        }
        # У некоторых моделей завод выкладывает по 30 снимков — в галерее это лишний вес.
        item["photos"] = item["photos"][:8]
        for photo in item["photos"]:
            photo["cutout"] = is_cutout(photo["thumb"], tone)

    with open(TONE_CACHE, "w", encoding="utf-8") as f:
        json.dump(tone, f, ensure_ascii=False, indent=1)
    return items


def main():
    with open(os.path.join(DATA, "site-config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    with open(os.path.join(DATA, "catalog-raw.json"), encoding="utf-8") as f:
        items = prepare(json.load(f))

    with open(os.path.join(DATA, "catalog.json"), "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    shutil.rmtree(os.path.join(ROOT, "catalog"), ignore_errors=True)

    site = Site(cfg, items)
    site.build_config_js()
    site.build_home()
    site.build_catalog_index()
    for brand_key in BRANDS:
        if any(i["brand"] == brand_key for i in items):
            site.build_brand_page(brand_key)
    for cat in site.categories:
        site.build_category_page(cat)
    for item in items:
        site.build_product_page(item)
    site.build_parts()
    site.build_service()
    site.build_financing()
    site.build_about()
    site.build_contacts()
    site.build_404()
    site.build_sitemap()

    print(f"Собрано страниц: {len(site.pages)}")
    print(f"Моделей: {len(items)} · категорий: {len(site.categories)}")


if __name__ == "__main__":
    main()
