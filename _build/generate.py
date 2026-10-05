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
        "note": "Группа заводов «Брянский Арсенал», «Челябинские строительно-дорожные машины» "
                "и «Тверской экскаватор»: экскаваторы, погрузчики, автогрейдеры и бульдозеры.",
        "site": "https://umg-sdm.com/",
    },
    "zzgt": {
        "name": "ВПК (ЗЗГТ)",
        "full": "ВПК — Заволжский завод гусеничных тягачей",
        "note": "Гусеничные снегоболотоходы для работы вне дорог: нефтегаз, геологоразведка, "
                "энергетика, Крайний Север.",
        "site": "https://zzgt.ru/",
    },
    "ormast": {
        "name": "Шмель",
        "full": "Оружейные Мастерские — мини-погрузчики Шмель",
        "note": "Многофункциональные мини-погрузчики с бортовым поворотом для строительных, "
                "дорожных, коммунальных и складских работ.",
        "site": "https://ormast.ru/",
    },
}

NAV = [
    ("Главная", "index.html"),
    ("Каталог", "catalog/index.html"),
    ("Запчасти", "parts.html"),
    ("Сервис", "service.html"),
    ("О компании", "about.html"),
    ("Новости", "news/index.html"),
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
    "mini-pogruzchiki": ("capacity", "Грузоподъёмность"),
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
    "mini-pogruzchiki": "Компактные погрузчики с бортовым поворотом для погрузки, планировки, "
                         "уборки территории и работы со сменным оборудованием.",
    "ekskavatory-pogruzchiki": "Универсальные машины «два в одном» для коммунальных, дорожных "
                              "и благоустроительных работ.",
    "avtogreydery": "Планировка и профилирование земляного полотна при строительстве дорог, "
                   "аэродромов и площадок.",
    "buldozery": "Разработка и перемещение грунта в дорожном и промышленном строительстве.",
    "snegobolotokhody": "Плавающие гусеничные вездеходы для перевозки людей и грузов по бездорожью "
                       "при температурах от +40 °C до −50 °C.",
}

# Полезные ориентиры для выбора на посадочных страницах категорий.
CATEGORY_SELECTION = {
    "gusenichnye-ekskavatory": "Сначала определите требуемые массу машины, глубину копания и объём ковша. "
                                "Для работы в слабых грунтах важны ширина гусениц и удельное давление на грунт.",
    "kolesnye-ekskavatory": "Сравните массу, радиус копания, скорость передвижения и варианты рабочего оборудования. "
                            "Для города также важны габариты и возможность быстро переезжать между объектами.",
    "frontalnykh-pogruzchikov": "При подборе смотрят на грузоподъёмность, объём ковша, высоту разгрузки и тип работ. "
                                "Для карьера и склада сыпучих материалов нужна разная комплектация.",
    "teleskopicheskie-pogruzchiki": "Ключевые параметры — грузоподъёмность на нужной высоте, высота подъёма и вылет стрелы. "
                                  "Также стоит заранее определить необходимое навесное оборудование.",
    "mini-pogruzchiki": "Для мини-погрузчика важны номинальная грузоподъёмность, ширина машины и перечень навесного оборудования. "
                         "Это помогает подобрать модель под узкие проезды, планировку или уборку территории.",
    "ekskavatory-pogruzchiki": "Сравните глубину копания, грузоподъёмность фронтального ковша и доступные исполнения рукояти. "
                              "Так машина будет одинаково полезна и на земляных, и на погрузочных работах.",
    "avtogreydery": "При выборе учитывают мощность двигателя, длину отвала, тяговый класс и комплектацию для конкретного типа дороги. "
                    "Для круглогодичной работы заранее согласуйте дополнительное оборудование.",
    "buldozery": "Основные параметры — тяговый класс, мощность, тип отвала и условия грунта. "
                  "Для карьеров, дорожного строительства и планировки подбирают разные исполнения.",
    "snegobolotokhody": "Уточните число пассажиров, полезную нагрузку, маршрут и сезон эксплуатации. "
                         "Для работы в тундре, лесу или на промышленных объектах подбирают подходящий кузов и комплектацию.",
}

# Подробные ответы на частые вопросы покупателя — для приоритетных категорий.
CATEGORY_GUIDE = {
    "gusenichnye-ekskavatory": [
        ("Где работает гусеничный экскаватор",
         "Гусеничный ход даёт устойчивость и проходимость на слабых, мокрых и неровных грунтах, "
         "поэтому такие машины берут для котлованов, траншей, карьеров, берегоукрепления и "
         "промышленного строительства. Минус — переезд между объектами на трале, а не своим ходом."),
        ("На что смотреть при выборе",
         "Эксплуатационная масса и мощность двигателя определяют класс машины, объём ковша — "
         "производительность, а глубина копания и радиус — рабочую зону. Если грунты слабые, "
         "уточните ширину гусениц и удельное давление на грунт."),
    ],
    "kolesnye-ekskavatory": [
        ("Когда колёсный экскаватор выгоднее гусеничного",
         "Колёсный экскаватор переезжает между объектами своим ходом, не требует трала и не "
         "разрушает дорожное покрытие. Его выбирают для городских работ, ЖКХ, ремонта дорог и "
         "коммуникаций. На слабых грунтах и в карьерах гусеничные машины устойчивее."),
        ("На что смотреть при выборе",
         "Сравните массу, радиус копания, скорость передвижения и состав рабочего оборудования. "
         "Для работы в городе важны габариты машины и наличие аутригеров и отвала."),
    ],
    "ekskavatory-pogruzchiki": [
        ("Что такое экскаватор-погрузчик",
         "Это колёсная машина «два в одном»: спереди — погрузочный ковш, сзади — экскаваторное "
         "оборудование с рукоятью. Одна техника заменяет и экскаватор, и фронтальный погрузчик, "
         "поэтому её берут коммунальные службы, дорожники и подрядчики, которым нужно быстро "
         "переезжать с объекта на объект."),
        ("Для каких работ подходит",
         "Рытьё траншей под коммуникации, ремонт дорог, засыпка и планировка, погрузка и перемещение "
         "сыпучих материалов, работа со сменным навесным оборудованием. Для крупных земляных работ "
         "и карьеров лучше смотреть в сторону гусеничных экскаваторов."),
        ("На что смотреть при выборе",
         "Глубина копания, грузоподъёмность и объём фронтального ковша, мощность двигателя, "
         "исполнение рукояти и комплектация кабины. Если планируется гидромолот или другое навесное "
         "оборудование, заранее уточните, есть ли для него гидролиния."),
    ],
    "avtogreydery": [
        ("Для чего нужен автогрейдер",
         "Автогрейдер профилирует и планирует земляное полотно, формирует дорожное основание, "
         "срезает и перемещает грунт, расчищает дороги от снега. Это основная техника при "
         "строительстве и содержании дорог, аэродромов и площадок."),
        ("На что смотреть при выборе",
         "Тяговый класс и мощность двигателя, длина отвала, тип трансмиссии и дополнительное "
         "оборудование — бульдозерный отвал, рыхлитель, снегоуборочная оснастка. Для круглогодичной "
         "работы заранее согласуйте комплектацию под зимнее содержание дорог."),
    ],
}

CATEGORY_GENITIVE = {
    "gusenichnye-ekskavatory": "гусеничных экскаваторов",
    "kolesnye-ekskavatory": "колёсных экскаваторов",
    "frontalnykh-pogruzchikov": "фронтальных погрузчиков",
    "teleskopicheskie-pogruzchiki": "телескопических погрузчиков",
    "mini-pogruzchiki": "мини-погрузчиков",
    "ekskavatory-pogruzchiki": "экскаваторов-погрузчиков",
    "avtogreydery": "автогрейдеров",
    "buldozery": "бульдозеров",
    "snegobolotokhody": "гусеничных снегоболотоходов",
}

CATEGORY_SINGULAR = {
    "gusenichnye-ekskavatory": "гусеничный экскаватор",
    "kolesnye-ekskavatory": "колёсный экскаватор",
    "frontalnykh-pogruzchikov": "фронтальный погрузчик",
    "teleskopicheskie-pogruzchiki": "телескопический погрузчик",
    "mini-pogruzchiki": "мини-погрузчик",
    "ekskavatory-pogruzchiki": "экскаватор-погрузчик",
    "avtogreydery": "автогрейдер",
    "buldozery": "бульдозер",
    "snegobolotokhody": "гусеничный снегоболотоход",
}

SERVICE_ITEMS = [
    ("Гарантийный ремонт", "Обслуживаем технику UMG, ЗЗГТ и Шмель в течение гарантийного срока — "
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
    ("Официальный дилер", "Прямые поставки с заводов UMG, ЗЗГТ и Шмель. Заводская гарантия и "
     "оригинальная документация на каждую машину."),
    ("Склад запчастей", "Расходники и узлы под технику всех производителей — "
     "простой машины стоит дороже детали."),
    ("Собственный сервис", "Гарантийный и постгарантийный ремонт, выездные бригады, "
     "плановое обслуживание по наработке."),
    ("Лизинг", "Подбираем схему финансирования под ваш парк."),
]

FINANCING_STEPS = [
    ("Заявка", "Присылаете модель и желаемые условия — аванс, срок, график платежей."),
    ("Расчёт", "Готовим предложения от лизинговых компаний и сравниваем удорожание."),
    ("Документы", "Собираем пакет: устав, бухгалтерская отчётность, паспорт руководителя."),
    ("Договор", "Подписываем договор лизинга и поставки, вносите аванс."),
    ("Передача", "Отгружаем технику, передаём ПСМ и документы для постановки на учёт."),
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

# Сеть из линий и узлов для .hero__glow: рисуется и гаснет по кругу
# (--gd задаёт сдвиг по времени, чтобы линии загорались не разом).
# Держим правее центра — левее лежит текст на тёмном участке оверлея.
HERO_GLOW_PATHS = [
    ("M560,70 L660,70 L730,140 L730,250", 0.0),
    ("M660,70 L660,160", 0.6),
    ("M730,250 L840,250 L900,310", 1.9),
    ("M900,60 L900,160 L995,250 L995,400", 0.9),
    ("M995,400 L1120,400", 2.6),
    ("M900,310 L900,470 L995,560", 1.4),
    ("M520,420 L660,420 L730,490 L730,610", 3.3),
    ("M730,490 L860,490 L915,545", 3.9),
    ("M320,600 L470,600 L540,530", 4.6),
    ("M995,250 L1120,250", 2.1),
]
HERO_GLOW_NODES = [
    (730, 250, 5, 1.9), (995, 400, 4, 2.6), (900, 310, 4, 1.4),
    (660, 70, 4, 0.6), (730, 610, 5, 3.3), (915, 545, 4, 3.9),
    (540, 530, 4, 4.6), (1120, 400, 3, 2.9), (995, 250, 3, 2.4),
]
HERO_GLOW = ('<svg viewBox="0 0 1200 700" preserveAspectRatio="xMaxYMid slice" aria-hidden="true">'
             + "".join(f'<path d="{d}" style="--gd:{delay}s"/>' for d, delay in HERO_GLOW_PATHS)
             + "".join(f'<circle cx="{x}" cy="{y}" r="{r}" style="--gd:{delay}s"/>'
                       for x, y, r, delay in HERO_GLOW_NODES)
             + "</svg>")


def esc(text):
    return html.escape(str(text), quote=True)


def meta_description_for(item, limit=300):
    """Собирает связное описание модели для мета-тегов и JSON-LD из пунктов
    «Назначение и область применения», обрезая по границе слова, а не байта."""
    fragments = [p.strip() for p in (item["description"].get("purpose") or []) if p and p.strip()]
    parts = []
    for frag in fragments:
        if frag[-1] not in ".!?:;,":
            frag += "."
        parts.append(frag)
    text = re.sub(r"\s+", " ", " ".join(parts)).strip()
    text = re.sub(r"\s+([:;,.!?])", r"\1", text)
    text = re.sub(r"\.{2,}", ".", text)

    if not text:
        brand = BRANDS.get(item["brand"], {}).get("name", "")
        category = CATEGORY_SINGULAR.get(item["category"], item["categoryTitle"].lower())
        return (f"{item['name']} — {category} {brand}. "
                "Характеристики и комплектацию уточняйте у менеджера.")

    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(" ,:;.–—-")
    return cut + "…"


def model_word(count):
    """Возвращает «модель»/«модели»/«моделей» с корректным русским окончанием."""
    last_two = count % 100
    last = count % 10
    if 11 <= last_two <= 14:
        return "моделей"
    if last == 1:
        return "модель"
    if 2 <= last <= 4:
        return "модели"
    return "моделей"


def model_count_label(count):
    return f"{count} {model_word(count)}"


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


def base_path(cfg):
    """Подпапка, в которой лежит сайт: «/-» для github.io/-/, пусто для своего домена."""
    after_host = cfg["domain"].split("//", 1)[-1].partition("/")[2].strip("/")
    return "/" + after_host if after_host else ""


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

ASSET_VERSION = "20261005-seo"


def head(cfg, depth, title, description, canonical, extra=""):
    base = rel(depth)
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<meta name="yandex-verification" content="3b56a02ddbf961a8">
<meta name="yandex-verification" content="bcc5639b80bc8ed0">
<link rel="canonical" href="{esc(cfg['domain'] + '/' + canonical)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{esc(cfg['company'])}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:image" content="{esc(cfg['domain'])}/assets/img/brand/og-image.png">
<meta property="og:url" content="{esc(cfg['domain'] + '/' + canonical)}">
<link rel="icon" type="image/png" sizes="32x32" href="{base}assets/img/brand/favicon-32.png">
<link rel="apple-touch-icon" href="{base}assets/img/brand/favicon-180.png">
<link rel="stylesheet" href="{base}assets/css/main.css?v={ASSET_VERSION}">
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
        f'<li><a href="{base}catalog/ekskavatory/index.html">Все экскаваторы</a></li>'
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
    legal_links = (f'{page_links}'
                   f'<li><a href="{base}personal-data-consent.html">'
                   'Согласие на обработку персональных данных</a></li>')

    return f"""<footer class="footer">
<div class="shell">
<div class="footer__grid">
<div>
<div class="footer__logo"><img src="{base}assets/img/brand/logo.png" alt="{esc(cfg['company'])}" width="798" height="205"></div>
<p class="footer__about">Официальный дилер UMG, ВПК (ЗЗГТ) и Шмель. Продажа спецтехники, поставка
оригинальных запчастей и сервисное обслуживание.</p>
</div>
<div>
<p class="footer__title">Каталог</p>
<ul class="footer__list">{cat_links}</ul>
</div>
<div>
<p class="footer__title">Разделы</p>
<ul class="footer__list">{legal_links}</ul>
</div>
<div>
<p class="footer__title">Контакты</p>
<ul class="footer__list">
<li><a href="tel:{esc(cfg['phoneHref'])}">{esc(cfg['phone'])}</a></li>
<li><a href="mailto:{esc(cfg['email'])}">{esc(cfg['email'])}</a></li>
<li>{esc(cfg['hours'])}</li>
<li>{esc(cfg.get('dealerCities', full_address(cfg)))}</li>
</ul>
</div>
</div>
<div class="footer__bottom">
<p>© 2020–2026 {esc(cfg['legalName'])}</p>
<p>{esc(cfg['tagline'])}</p>
<p class="footer__disclaimer">Технические характеристики и фотографии приведены по данным
производителей UMG, ЗЗГТ и Шмель и не являются публичной офертой. Комплектация и параметры
могут быть изменены заводом-изготовителем.</p>
</div>
</div>
</footer>
<script src="{base}assets/js/config.js?v={ASSET_VERSION}"></script>
<script src="{base}assets/js/site.js?v={ASSET_VERSION}"></script>
</body>
</html>
"""


def request_form(cfg, form_id, subject, hidden=None, compact=False):
    endpoint = cfg.get("formEndpoint", "")
    action = "" if not endpoint or "ВСТАВЬТЕ" in endpoint else f' action="{esc(endpoint)}" method="POST"'
    hidden_html = "".join(
        f'<input type="hidden" name="{esc(k)}" value="{esc(v)}">' for k, v in (hidden or {}).items())
    message = "" if compact else f"""
<div class="field">
<label for="{form_id}-msg">Комментарий</label>
<textarea id="{form_id}-msg" name="Комментарий" rows="4" placeholder="Модель техники, регион работы, сроки"></textarea>
</div>"""

    return f"""<form class="form" data-form data-subject="{esc(subject)}"{action} novalidate>
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
<input type="checkbox" name="Согласие на обработку персональных данных" value="Дано" required>
<span>Даю <a href="/personal-data-consent.html" target="_blank" rel="noopener">согласие на обработку персональных данных</a> в соответствии с Федеральным законом № 152-ФЗ <span aria-hidden="true">*</span>
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


RU_MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня",
             "июля", "августа", "сентября", "октября", "ноября", "декабря"]


def format_date_ru(iso_date):
    year, month, day = iso_date.split("-")
    return f"{int(day)} {RU_MONTHS[int(month) - 1]} {year}"


def news_card(depth, post):
    base = rel(depth)
    href = f"{base}news/{post['slug']}.html"
    media = (f'<img src="{base}{esc(post["image"])}" alt="{esc(post["title"])}" loading="lazy" '
             f'width="640" height="360">'
             if post.get("image") else '<span class="gallery__empty">Фото уточняется</span>')
    return f"""<article class="news-card">
<a class="news-card__media" href="{href}" tabindex="-1" aria-hidden="true">{media}</a>
<div class="news-card__body">
<p class="news-card__date">{esc(format_date_ru(post['date']))}</p>
<h3 class="news-card__title"><a href="{href}">{esc(post['title'])}</a></h3>
<p class="news-card__excerpt">{esc(post['excerpt'])}</p>
<a class="link-arrow" href="{href}">Читать</a>
</div>
</article>"""


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
    def __init__(self, cfg, items, news=None):
        self.cfg = cfg
        self.items = items
        self.news = sorted(news or [], key=lambda n: n["date"], reverse=True)
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
        # Показываем разные типы техники, используя живые кадры, а не вырезки.
        hero_photos = []
        for slug in ("e225c", "wl30", "ag-140", "gaz-34039"):
            candidate = next((i for i in self.items if i["slug"] == slug), None)
            photo = next((p for p in candidate["photos"] if not p["cutout"]), None) if candidate else None
            if photo:
                hero_photos.append((candidate, photo))
        hero_slides = "".join(
            f'<div class="hero-carousel__slide" aria-hidden="{str(n != 0).lower()}">'
            f'<img src="{esc(photo["src"])}" alt="{esc(item["name"])}" width="1200" height="900" '
            + ('fetchpriority="high">' if n == 0 else 'loading="lazy">')
            + '</div>'
            for n, (item, photo) in enumerate(hero_photos)
        )
        hero_dots = "".join(
            f'<button type="button" class="hero-carousel__dot" data-hero-carousel-dot '
            f'aria-label="Показать фотографию {n + 1}" aria-current="{str(n == 0).lower()}"></button>'
            for n in range(len(hero_photos))
        )
        hero_carousel = (f'''<div class="hero-carousel__viewport"><div class="hero-carousel__track">{hero_slides}</div></div>
<div class="hero__overlay"></div>
<div class="hero__glow">{HERO_GLOW}</div>
<span class="diag-accent" style="right:12%"></span>
<div class="shell hero__content">
<p class="eyebrow">Официальный дилер UMG, ВПК (ЗЗГТ) и Шмель</p>
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
<span class="badge badge--outline">Лизинг</span>
</div>
</div>
<button type="button" class="hero-carousel__control hero-carousel__control--prev" data-hero-carousel-prev aria-label="Предыдущая фотография">&larr;</button>
<button type="button" class="hero-carousel__control hero-carousel__control--next" data-hero-carousel-next aria-label="Следующая фотография">&rarr;</button>
<div class="hero-carousel__dots" aria-label="Выбор фотографии">{hero_dots}</div>''' if hero_photos else "")

        tiles = "".join(self.category_tile(0, c) for c in self.categories)
        # По одной модели из каждой категории по кругу, чтобы в блоке
        # не оказались одни гусеничные экскаваторы (они первые в каталоге).
        popular = []
        pool = {c["slug"]: [i for i in c["items"] if i["photos"]] for c in self.categories}
        while len(popular) < 6:
            added = False
            for c in self.categories:
                bucket = pool[c["slug"]]
                if bucket:
                    popular.append(bucket.pop(0))
                    added = True
                    if len(popular) == 6:
                        break
            if not added:
                break
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
            "description": "Официальный дилер UMG, ВПК (ЗЗГТ) и Шмель: продажа спецтехники, "
                           "запчасти и сервисное обслуживание.",
            "areaServed": [
                {"@type": "AdministrativeArea", "name": region}
                for region in cfg.get("regions", [])
            ],
        }, ensure_ascii=False)

        body = f"""<main>
<section class="hero hero--carousel" data-hero-carousel aria-roledescription="carousel"
aria-label="Фотографии техники">
{hero_carousel}
</section>

<section class="section section--deep" style="padding-top:0;padding-bottom:0">
<div class="shell" style="padding:0">
<div class="stats">
<div class="stats__item"><p class="stats__value">5</p><p class="stats__label">заводов-производителей, чью технику мы поставляем напрямую</p></div>
<div class="stats__item"><p class="stats__value">{len(self.items)}</p><p class="stats__label">{model_word(len(self.items))} техники в каталоге с полными характеристиками</p></div>
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
                  f"Экскаваторы, экскаваторы-погрузчики, автогрейдеры UMG — Уфа, Казань | {cfg['company']}",
                  "Официальный дилер UMG, ВПК (ЗЗГТ) и Шмель в Уфе и Казани: экскаваторы, "
                  "экскаваторы-погрузчики, автогрейдеры и другая спецтехника. "
                  "Цена по запросу, лизинг, запчасти, сервис.",
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
<p class="cat-tile__meta">{model_count_label(len(cat['items']))}</p>
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
<p>{esc(brand['note'])} В каталоге {model_count_label(count)}.</p>
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
<p>Пять заводов-производителей, {len(self.categories)} категорий и {model_count_label(len(self.items))}.
В каждой карточке — заводская таблица характеристик и фотографии машины.</p>
</div>
</div>
</section>
{"".join(blocks)}
{cta_block(cfg, "catalog", "Заявка из каталога", "Не нашли нужную модель?",
           "Заводы выпускают больше исполнений, чем показано в каталоге. "
           "Напишите задачу — подберём машину и посчитаем стоимость.")}
</main>""")

        self.page("catalog/index.html", 1, f"Каталог спецтехники UMG, ЗЗГТ и Шмель — {cfg['company']}",
                  "Полный каталог: гусеничные и колёсные экскаваторы, погрузчики, автогрейдеры, "
                  "бульдозеры UMG, гусеничные снегоболотоходы ЗЗГТ и мини-погрузчики Шмель "
                  "с характеристиками.",
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
                  f"{brand['note']} {model_count_label(len(items))} с полными техническими характеристиками.",
                  "catalog/index.html", body)

    def build_category_page(self, cat):
        cfg = self.cfg
        brand = BRANDS[cat["brand"]]
        cards = "".join(machine_card(cfg, 3, i) for i in cat["items"])
        category_name = cat["title"].lower()
        category_genitive = CATEGORY_GENITIVE.get(cat["slug"], category_name)
        category_singular = CATEGORY_SINGULAR.get(cat["slug"], category_name)
        city_locative = cfg.get("cityLocative", cfg["city"])
        regions_phrase = "по " + " и по ".join(cfg.get("regionsDative", cfg.get("regions", [])))
        dealer_cities = cfg.get("dealerCitiesLocative", city_locative)
        category_url = (f"{cfg['domain']}/catalog/{cat['brand']}/{cat['slug']}/")
        selection = CATEGORY_SELECTION.get(cat["slug"],
                                           "Сравните характеристики, условия работы и нужную комплектацию. "
                                           "Менеджер поможет выбрать подходящую модель.")
        faq = [
            (f"Как выбрать {category_singular}?", selection),
            ("Как узнать цену и срок поставки?",
             "Оставьте заявку с нужной моделью или задачей. Подготовим коммерческое предложение "
             "с ценой, сроком поставки, комплектацией и вариантом лизинга."),
            (f"Можно ли купить {category_singular} в лизинг?",
             "Да. Лизинг доступен юридическим лицам и ИП: аванс от 10%, срок до 60 месяцев. "
             "Сравним предложения лизинговых компаний и покажем итоговое удорожание."),
            (f"Где купить {category_singular} и обслуживать технику?",
             f"Дилерские центры {cfg['company']} находятся в {dealer_cities}. Поставляем технику "
             f"{regions_phrase}, организуем гарантийный и постгарантийный сервис и поставку запчастей."),
        ]
        faq_html = "".join(
            f'''<div class="accordion__item">
<button type="button" class="accordion__btn" aria-expanded="false" aria-controls="faq-{cat['slug']}-{n}">
{esc(question)}<span class="accordion__icon" aria-hidden="true"></span></button>
<div class="accordion__panel" id="faq-{cat['slug']}-{n}" hidden><p>{esc(answer)}</p></div>
</div>'''
            for n, (question, answer) in enumerate(faq, 1))
        guide_html = "".join(f"<h3>{esc(title)}</h3><p>{esc(text)}</p>"
                             for title, text in CATEGORY_GUIDE.get(cat["slug"], []))
        hub_link = ""
        if cat["slug"] in ("gusenichnye-ekskavatory", "kolesnye-ekskavatory"):
            hub_link = ('<p><a class="link-arrow" href="../../ekskavatory/index.html">'
                        'Все экскаваторы: гусеничные и колёсные</a></p>')
        category_ld = json.dumps({
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": f"{cat['title']} {brand['name']}",
            "description": cat["blurb"],
            "url": category_url,
            "mainEntity": {
                "@type": "ItemList",
                "numberOfItems": len(cat["items"]),
                "itemListElement": [
                    {"@type": "ListItem", "position": n, "name": item["name"],
                     "url": f"{cfg['domain']}/catalog/{item['brand']}/{item['category']}/{item['slug']}.html"}
                    for n, item in enumerate(cat["items"], 1)
                ],
            },
        }, ensure_ascii=False)
        faq_ld = json.dumps({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": question,
                 "acceptedAnswer": {"@type": "Answer", "text": answer}}
                for question, answer in faq
            ],
        }, ensure_ascii=False)

        body = (breadcrumbs(cfg, 3, [("Главная", "index.html"), ("Каталог", "catalog/index.html"),
                                     (brand["name"], f"catalog/{cat['brand']}/index.html"),
                                     (cat["title"], None)])
                + f"""<main>
<section class="section hex-bg">
<div class="shell">
<div class="section__head">
<p class="eyebrow">{esc(brand['name'])}</p>
<h1>{esc(cat['title'])} {esc(brand['name'])}</h1>
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

<section class="section section--panel">
<div class="shell">
<div class="section__head">
<p class="eyebrow">Подбор техники</p>
<h2>Как выбрать технику для работы</h2>
</div>
<div class="prose">
<p>{esc(cat['blurb'])} {esc(cfg['company'])} поставляет технику {esc(regions_phrase)}, дилерские
центры — в {esc(dealer_cities)}: организуем подбор модели, расчёт стоимости, лизинг, сервис
и поставку запчастей.</p>
<p>{esc(selection)}</p>
{guide_html}
{hub_link}
</div>
</div>
</section>

<section class="section">
<div class="shell">
<div class="section__head"><p class="eyebrow">Вопросы</p><h2>Покупка и поставка</h2></div>
<div class="accordion">{faq_html}</div>
</div>
</section>
{cta_block(cfg, cat['slug'], f"Заявка: {cat['title']}",
           "Поможем выбрать между моделями",
           "Разница между исполнениями часто в ширине хода, длине рукояти и объёме ковша. "
           "Опишите условия работы — подберём точно.")}
</main>""")

        self.page(f"catalog/{cat['brand']}/{cat['slug']}/index.html", 3,
                  f"Купить {category_name} {brand['name']} в {dealer_cities} | {cfg['company']}",
                  f"Продажа {category_genitive} {brand['name']} {regions_phrase}: "
                  f"{model_count_label(len(cat['items']))}, характеристики, подбор, цена по запросу, "
                  "лизинг и сервис.",
                  "catalog/index.html", body,
                  extra_head=(f'<script type="application/ld+json">{category_ld}</script>\n'
                              f'<script type="application/ld+json">{faq_ld}</script>\n'))

    def build_excavators_hub(self):
        """Общая страница «Экскаваторы» под запрос «купить экскаватор»: гусеничные и колёсные вместе."""
        cfg = self.cfg
        slugs = ("gusenichnye-ekskavatory", "kolesnye-ekskavatory")
        items = [i for i in self.items if i["category"] in slugs]
        if not items:
            return
        base = rel(2)
        dealer_cities = cfg.get("dealerCitiesLocative", cfg["city"])
        regions_phrase = "по " + " и по ".join(cfg.get("regionsDative", cfg.get("regions", [])))
        cards = "".join(machine_card(cfg, 2, i) for i in items)
        count = model_count_label(len(items))

        guide = "".join(f"<h3>{esc(t)}</h3><p>{esc(p)}</p>"
                        for slug in slugs for t, p in CATEGORY_GUIDE[slug][:1])
        links = "".join(
            f'<li><a class="link-arrow" href="{base}catalog/{c["brand"]}/{c["slug"]}/index.html">'
            f'{esc(c["title"])} {esc(BRANDS[c["brand"]]["name"])}</a></li>'
            for c in self.categories if c["slug"] in slugs + ("ekskavatory-pogruzchiki",))

        faq = [
            ("Какой экскаватор выбрать: гусеничный или колёсный?",
             "Гусеничный устойчивее на слабых и неровных грунтах и лучше подходит для карьеров, "
             "котлованов и промышленного строительства. Колёсный переезжает между объектами своим "
             "ходом и не разрушает покрытие — его берут для города, ЖКХ и дорожных работ."),
            ("Сколько стоит экскаватор UMG?",
             "Цена зависит от модели, комплектации и условий поставки. Оставьте заявку — подготовим "
             "коммерческое предложение с ценой, сроком поставки и вариантом лизинга."),
            ("Можно ли купить экскаватор в лизинг?",
             "Да. Лизинг доступен юридическим лицам и ИП: аванс от 10%, срок до 60 месяцев. "
             "Сравним предложения лизинговых компаний и покажем итоговое удорожание."),
            (f"Где купить экскаватор UMG и обслуживать его?",
             f"Дилерские центры {cfg['company']} находятся в {dealer_cities}. Поставляем технику "
             f"{regions_phrase}, организуем гарантийный и постгарантийный сервис и поставку запчастей."),
        ]
        faq_html = "".join(
            f'''<div class="accordion__item">
<button type="button" class="accordion__btn" aria-expanded="false" aria-controls="faq-excavators-{n}">
{esc(q)}<span class="accordion__icon" aria-hidden="true"></span></button>
<div class="accordion__panel" id="faq-excavators-{n}" hidden><p>{esc(a)}</p></div>
</div>''' for n, (q, a) in enumerate(faq, 1))
        faq_ld = json.dumps({
            "@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": q,
                            "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq],
        }, ensure_ascii=False)

        body = (breadcrumbs(cfg, 2, [("Главная", "index.html"), ("Каталог", "catalog/index.html"),
                                     ("Экскаваторы", None)])
                + f"""<main>
<section class="section hex-bg">
<div class="shell">
<div class="section__head">
<p class="eyebrow">UMG</p>
<h1>Экскаваторы UMG: гусеничные и колёсные</h1>
<p>Продаём гусеничные и колёсные экскаваторы {esc(regions_phrase)}: {esc(count)} с полными
техническими характеристиками. Дилерские центры {esc(cfg['company'])} — в {esc(dealer_cities)}.</p>
</div>
<div data-catalog>
<div class="catalog-toolbar">
<p class="catalog-toolbar__count" data-catalog-count></p>
<label class="visually-hidden" for="sort-excavators">Сортировка</label>
<select class="select" id="sort-excavators" data-catalog-sort>
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

<section class="section section--panel">
<div class="shell">
<div class="section__head">
<p class="eyebrow">Подбор техники</p>
<h2>Гусеничный или колёсный экскаватор</h2>
</div>
<div class="prose">
{guide}
<p>Если нужна универсальная машина для коммунальных и дорожных работ, посмотрите также
экскаваторы-погрузчики.</p>
<ul>{links}</ul>
</div>
</div>
</section>

<section class="section">
<div class="shell">
<div class="section__head"><p class="eyebrow">Вопросы</p><h2>Покупка и поставка</h2></div>
<div class="accordion">{faq_html}</div>
</div>
</section>
{cta_block(cfg, "excavators", "Заявка: экскаваторы",
           "Поможем выбрать экскаватор",
           "Опишите задачу, грунты и объём работ — подберём модель и посчитаем стоимость с доставкой.")}
</main>""")

        collection_ld = json.dumps({
            "@context": "https://schema.org", "@type": "CollectionPage",
            "name": "Экскаваторы UMG", "url": f"{cfg['domain']}/catalog/ekskavatory/",
            "mainEntity": {"@type": "ItemList", "numberOfItems": len(items), "itemListElement": [
                {"@type": "ListItem", "position": n, "name": i["name"],
                 "url": f"{cfg['domain']}/catalog/{i['brand']}/{i['category']}/{i['slug']}.html"}
                for n, i in enumerate(items, 1)]},
        }, ensure_ascii=False)

        self.page("catalog/ekskavatory/index.html", 2,
                  f"Купить экскаватор в {dealer_cities} — гусеничные и колёсные UMG | {cfg['company']}",
                  f"Продажа гусеничных и колёсных экскаваторов UMG {regions_phrase}: {count}, "
                  "характеристики, подбор, цена по запросу, лизинг и сервис.",
                  "catalog/index.html", body,
                  extra_head=(f'<script type="application/ld+json">{collection_ld}</script>\n'
                              f'<script type="application/ld+json">{faq_ld}</script>\n'))

    def build_product_page(self, item):
        cfg = self.cfg
        brand = BRANDS[item["brand"]]
        product_name = (item["name"] if item["name"].casefold().startswith(brand["name"].casefold())
                        else f"{brand['name']} {item['name']}")
        depth = 3
        base = rel(depth)
        type_singular = CATEGORY_SINGULAR.get(item["category"], item["categoryTitle"].lower())
        product_title = f"Купить {type_singular} {product_name} — цена, характеристики | {cfg['company']}"
        if len(product_title) > 80:
            product_title = (f"{type_singular.capitalize()} {product_name} — "
                             f"цена, характеристики | {cfg['company']}")
        h1_type = type_singular.capitalize()
        if product_name != item["name"]:
            h1_type += f" {brand['name']}"

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
            "name": product_name,
            "category": item["categoryTitle"],
            "brand": {"@type": "Brand", "name": brand["name"]},
            "image": [f"{cfg['domain']}/{p['src']}" for p in item["photos"][:4]],
            "description": meta_description_for(item),
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
<h1 class="product__title"><span class="product__type">{esc(h1_type)}</span> {esc(item['name'])}</h1>
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
<div>{request_form(cfg, 'product', f"Запрос цены: {product_name}",
                   hidden={"Модель": product_name,
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
                  product_title,
                  f"{type_singular.capitalize()} {product_name}"
                  + (f": {summary}. " if summary else ". ")
                  + "Характеристики, фото, цена по запросу, лизинг. "
                  + f"Дилерские центры в {cfg.get('dealerCitiesLocative', cfg['city'])}.",
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
<h1>Оригинальные запчасти UMG, ЗЗГТ и Шмель</h1>
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

        self.page("parts.html", 0, f"Запчасти для техники UMG, ЗЗГТ и Шмель | {cfg['company']}",
                  "Оригинальные запчасти UMG, ЗЗГТ и Шмель: двигатель, гидравлика, ходовая часть, "
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
<p>Ремонтируем и обслуживаем технику UMG, ЗЗГТ и Шмель. Гарантийные работы проводим с сохранением
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

        self.page("service.html", 0, f"Сервис и ремонт спецтехники UMG, ЗЗГТ и Шмель | {cfg['company']}",
                  "Гарантийный и постгарантийный ремонт, плановое ТО, выездные бригады, "
                  "ремонт гидравлики и ходовой части техники UMG, ЗЗГТ и Шмель.",
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
<h1>Лизинг</h1>
<p>Техника окупается в работе, а не на стоянке. Помогаем взять машину в лизинг с посильным
авансом и графиком платежей под сезонность вашей выручки.</p>
</div>
<div class="grid grid--3">
{icon_card('handshake', 'Лизинг для юрлиц и ИП', 'Аванс от 10%, срок до 60 месяцев. Предмет лизинга остаётся обеспечением — дополнительный залог обычно не нужен.')}
{icon_card('doc', 'Налоговая выгода', 'Лизинговые платежи относятся на расходы, НДС принимается к вычету. Возможна ускоренная амортизация.')}
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

        self.page("financing.html", 0, f"Лизинг спецтехники | {cfg['company']}",
                  "Лизинг техники UMG, ЗЗГТ и Шмель для юридических лиц и ИП: аванс от 10%, срок до 60 "
                  "месяцев.",
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

        self.page("about.html", 0, f"О компании — официальный дилер UMG, ЗЗГТ и Шмель | {cfg['company']}",
                  f"{cfg['company']} — официальный дилер UMG, ВПК (ЗЗГТ) и Шмель: продажа спецтехники, "
                  "поставка оригинальных запчастей и сервисное обслуживание.",
                  "about.html", body)

    def build_personal_data_consent(self):
        cfg = self.cfg
        operator_address = full_address(cfg)
        body = (breadcrumbs(cfg, 0, [("Главная", "index.html"),
                                     ("Согласие на обработку персональных данных", None)])
                + f"""<main>
<section class="section">
<div class="shell">
<div class="section__head">
<p class="eyebrow">Персональные данные</p>
<h1>Согласие на обработку персональных данных</h1>
<p>Редакция от 28 июля 2026 года.</p>
</div>
<div class="prose legal-text">
<p>Настоящим пользователь сайта <a href="{esc(cfg['domain'])}">{esc(cfg['domain'])}</a>, заполняя форму заявки и проставляя отметку о согласии, свободно, своей волей и в своём интересе даёт согласие {esc(cfg['legalName'])} на обработку персональных данных на условиях, изложенных ниже.</p>

<h2>1. Оператор</h2>
<p>Оператор персональных данных: {esc(cfg['legalName'])}. Место нахождения: {esc(operator_address)}. Контакт для обращений по персональным данным: <a href="mailto:{esc(cfg['email'])}">{esc(cfg['email'])}</a>.</p>

<h2>2. Правовое основание</h2>
<p>Согласие предоставляется в соответствии с Федеральным законом от 27.07.2006 № 152-ФЗ «О персональных данных», включая пункт 1 части 1 статьи 6 указанного закона.</p>

<h2>3. Цели обработки</h2>
<p>Персональные данные обрабатываются для приёма и обработки заявки, обратной связи с пользователем, подготовки ответа, консультации, коммерческого предложения, подбора техники, запчастей, сервиса или условий лизинга.</p>

<h2>4. Перечень персональных данных</h2>
<p>Оператор может обрабатывать данные, которые пользователь самостоятельно указывает в формах сайта: имя, телефон, адрес электронной почты, комментарий к заявке, интересующая модель техники или услуга, а также технические сведения, связанные с отправкой формы.</p>

<h2>5. Действия с персональными данными</h2>
<p>Согласие даётся на сбор, запись, систематизацию, накопление, хранение, уточнение, использование, передачу лицам, привлекаемым для приёма и маршрутизации заявок, обезличивание, блокирование, удаление и уничтожение персональных данных с использованием средств автоматизации и без их использования.</p>

<h2>6. Передача и поручение обработки</h2>
<p>Для технического приёма заявок сайт использует сервис Formspree. Персональные данные передаются через этот сервис только для доставки сообщения оператору и последующей обработки заявки. Оператор не размещает полученные через формы персональные данные в открытом доступе и не передаёт их неограниченному кругу лиц.</p>

<h2>7. Срок действия согласия</h2>
<p>Согласие действует до достижения целей обработки либо до его отзыва пользователем, если более длительный срок хранения не требуется по закону, договору или для защиты прав и законных интересов оператора.</p>

<h2>8. Отзыв согласия</h2>
<p>Пользователь может отозвать согласие, направив обращение на электронную почту <a href="mailto:{esc(cfg['email'])}">{esc(cfg['email'])}</a> с темой «Отзыв согласия на обработку персональных данных». После получения отзыва оператор прекращает обработку и уничтожает персональные данные в случаях и сроки, предусмотренные законодательством РФ.</p>

<h2>9. Подтверждение согласия</h2>
<p>Отправляя форму на сайте, пользователь подтверждает, что ознакомлен с настоящим согласием, понимает его содержание и выражает конкретное, предметное, информированное, сознательное и однозначное согласие на обработку персональных данных.</p>

<h2>10. Cookies и аналитика</h2>
<p>Сайт может использовать cookies — небольшие файлы, которые сохраняются в браузере и помогают обеспечить работу сайта, а также оценивать посещаемость. Для аналитики используется Яндекс Метрика, которая может обрабатывать технические сведения: IP-адрес, данные браузера и устройства, посещённые страницы и действия на сайте.</p>
<p>Аналитические cookies и Яндекс Метрика подключаются только после выбора пользователем действия «Принять» в уведомлении о cookies. Пользователь может выбрать «Отклонить»; это не ограничивает доступ к материалам и формам сайта.</p>
</div>
</div>
</section>
</main>""")

        self.page("personal-data-consent.html", 0,
                  f"Согласие на обработку персональных данных | {cfg['company']}",
                  "Согласие пользователя сайта Альфа Машинери на обработку персональных данных "
                  "по Федеральному закону № 152-ФЗ.",
                  "personal-data-consent.html", body)

    def build_contacts(self):
        cfg = self.cfg
        rows = [("Телефон", cfg["phone"], f"tel:{cfg['phoneHref']}"),
                ("Электронная почта", cfg["email"], f"mailto:{cfg['email']}"),
                ("Режим работы", cfg["hours"], None),
                ("Дилерские центры", cfg.get("dealerCities", full_address(cfg)), None)]
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

    # --- новости -------------------------------------------------------------

    def build_news_index(self):
        cfg = self.cfg
        if self.news:
            grid = f'<div class="grid grid--3">{"".join(news_card(1, p) for p in self.news)}</div>'
        else:
            grid = ('<p class="catalog-empty">Пока новостей нет — скоро здесь появятся новые '
                    'модели в каталоге, акции и события компании.</p>')

        body = (breadcrumbs(cfg, 1, [("Главная", "index.html"), ("Новости", None)])
                + f"""<main>
<section class="section hex-bg">
<div class="shell">
<div class="section__head">
<p class="eyebrow">Новости</p>
<h1>Новости {esc(cfg['company'])}</h1>
<p>Новые модели в каталоге, изменения условий поставки, акции и события компании.</p>
</div>
{grid}
</div>
</section>
{cta_block(cfg, "news", "Заявка со страницы новостей", "Есть вопрос по технике?",
           "Напишите, что подбираете — ответим в ближайший рабочий день.")}
</main>""")

        self.page("news/index.html", 1, f"Новости | {cfg['company']}",
                  "Новые модели в каталоге, акции и события компании "
                  f"{cfg['company']}.",
                  "news/index.html", body)

    def build_news_post(self, post):
        cfg = self.cfg
        base = rel(1)
        body_html = "".join(f"<p>{esc(p)}</p>" for p in post["body"])
        cover = (f'<div class="news-post__cover"><img src="{base}{esc(post["image"])}" '
                 f'alt="{esc(post["title"])}" width="1200" height="675"></div>'
                 if post.get("image") else "")
        source = (f'<p style="margin-top:18px;font-size:.85rem;color:var(--muted)">Источник: '
                   f'<a href="{esc(post["source"])}" rel="nofollow noopener" target="_blank" '
                   f'style="color:var(--alpha-green)">{esc(post.get("sourceLabel", "сайт производителя"))}'
                   f'</a></p>' if post.get("source") else "")

        others = [p for p in self.news if p["slug"] != post["slug"]][:3]
        others_html = ""
        if others:
            others_html = f"""<section class="section section--panel">
<div class="shell">
<div class="section__head"><p class="eyebrow">Читайте также</p><h2>Другие новости</h2></div>
<div class="grid grid--3">{"".join(news_card(1, p) for p in others)}</div>
</div>
</section>"""

        article_ld = json.dumps({
            "@context": "https://schema.org",
            "@type": "NewsArticle",
            "headline": post["title"],
            "datePublished": post["date"],
            "description": post["excerpt"],
            "image": [f"{cfg['domain']}/{post['image']}"] if post.get("image") else [],
            "author": {"@type": "Organization", "name": cfg["company"]},
            "publisher": {"@type": "Organization", "name": cfg["company"],
                          "logo": {"@type": "ImageObject",
                                   "url": f"{cfg['domain']}/assets/img/brand/logo.png"}},
            "mainEntityOfPage": f"{cfg['domain']}/news/{post['slug']}.html",
        }, ensure_ascii=False)

        body = (breadcrumbs(cfg, 1, [("Главная", "index.html"), ("Новости", "news/index.html"),
                                     (post["title"], None)])
                + f"""<main>
<article class="section hex-bg">
<div class="shell" style="max-width:820px">
<p class="eyebrow">{esc(format_date_ru(post['date']))}</p>
<h1>{esc(post['title'])}</h1>
{cover}
<div class="prose">{body_html}</div>
{source}
<p style="margin-top:26px"><a class="link-arrow" href="{base}news/index.html">← Все новости</a></p>
</div>
</article>
{others_html}
{cta_block(cfg, "news-post", "Заявка со страницы новости", "Остались вопросы?",
           "Напишите — ответим в ближайший рабочий день.")}
</main>""")

        self.page(f"news/{post['slug']}.html", 1, f"{post['title']} | {cfg['company']}",
                  post["excerpt"], "news/index.html", body,
                  extra_head=f'<script type="application/ld+json">{article_ld}</script>\n')

    def build_404(self):
        """Страница ошибки отдаётся с любого пути, поэтому ссылки в ней —
        только от корня сайта. На GitHub Pages корень проекта лежит в подпапке,
        её и подставляем из адреса в конфиге."""
        cfg = self.cfg
        base = base_path(cfg)
        markup = (head(cfg, 0, f"Страница не найдена | {cfg['company']}",
                       "Такой страницы нет — вернитесь в каталог техники.", "404.html")
                  .replace('href="assets/', f'href="{base}/assets/')
                  + f"""<main class="section hex-bg" style="min-height:70vh;display:grid;place-items:center">
<div class="shell" style="text-align:center;max-width:640px">
<p class="eyebrow" style="justify-content:center">Ошибка 404</p>
<h1>Страница не найдена</h1>
<p>Возможно, адрес устарел или модель переехала в другую категорию.</p>
<p style="margin-top:26px"><a class="btn" href="{base}/catalog/index.html">Открыть каталог</a></p>
<p><a class="link-arrow" href="{base}/index.html" style="justify-content:center">На главную</a></p>
</div>
</main>
<script src="{base}/assets/js/config.js?v={ASSET_VERSION}"></script>
<script src="{base}/assets/js/site.js?v={ASSET_VERSION}"></script>
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

    # <sup> при разборе схлопнулся в пробел: «кг/см 2» → «кг/см²», «1м3» → «1м³».
    def superscripts(text):
        return re.sub(r"(?<![A-Za-zА-Яа-яЁё])(мм|см|дм|м)\s?([23])(?![\w-])",
                      lambda m: m.group(1) + "²³"[int(m.group(2)) - 2], text)

    latin = str.maketrans("АВСЕНКМОРТХ", "ABCEHKMOPTX")
    for item in items:
        for row in item["specs"]:
            if "cells" in row:
                row["cells"] = [superscripts(c) for c in row["cells"]]
                row["name"] = superscripts(row["name"])
            elif "group" in row:
                row["group"] = superscripts(row["group"])
        for key, vals in item["description"].items():
            if isinstance(vals, list):
                item["description"][key] = [superscripts(v) for v in vals]
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
    with open(os.path.join(DATA, "news.json"), encoding="utf-8") as f:
        news = json.load(f)

    with open(os.path.join(DATA, "catalog.json"), "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    shutil.rmtree(os.path.join(ROOT, "catalog"), ignore_errors=True)
    shutil.rmtree(os.path.join(ROOT, "news"), ignore_errors=True)

    site = Site(cfg, items, news)
    site.build_config_js()
    site.build_home()
    site.build_catalog_index()
    for brand_key in BRANDS:
        if any(i["brand"] == brand_key for i in items):
            site.build_brand_page(brand_key)
    for cat in site.categories:
        site.build_category_page(cat)
    site.build_excavators_hub()
    for item in items:
        site.build_product_page(item)
    site.build_parts()
    site.build_service()
    site.build_financing()
    site.build_about()
    site.build_personal_data_consent()
    site.build_contacts()
    site.build_news_index()
    for post in site.news:
        site.build_news_post(post)
    site.build_404()
    site.build_sitemap()

    print(f"Собрано страниц: {len(site.pages)}")
    print(f"Моделей: {len(items)} · категорий: {len(site.categories)} · новостей: {len(news)}")


if __name__ == "__main__":
    main()
