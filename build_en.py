#!/usr/bin/env python3
"""
Собирает английскую версию: en/index.html из index.html.

Запуск:  python3 build_en.py

Источник текстов один — атрибуты data-ru / data-en в index.html.
Английский текст подставляется в саму разметку, поэтому поисковик
и человек без JS видят нормальную страницу, а не русскую с кнопкой.

Правишь только index.html, потом прогоняешь этот скрипт.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "index.html"
OUT = ROOT / "en" / "index.html"

# тег с атрибутами: значения в кавычках могут содержать «>», поэтому
# простым [^>]* обойтись нельзя
TAG = re.compile(r'<([A-Za-z][\w-]*)((?:\s+[\w:.-]+(?:\s*=\s*"[^"]*")?)*)\s*(/?)>')
ATTR = re.compile(r'([\w:.-]+)(?:\s*=\s*"([^"]*)")?')
VOID = {"br", "img", "meta", "link", "input", "hr", "source", "path", "rect", "circle"}


def attrs_of(raw: str) -> dict:
    return {m.group(1): (m.group(2) or "") for m in ATTR.finditer(raw)}


def close_index(html: str, start: int, name: str) -> int:
    """Индекс начала закрывающего тега, парного открытому в start.
    Считает вложенность одноимённых тегов."""
    depth, pos = 1, start
    closer = re.compile(rf'</{name}\s*>', re.I)
    while pos < len(html):
        nxt_open = TAG.search(html, pos)
        nxt_close = closer.search(html, pos)
        if not nxt_close:
            return -1
        if nxt_open and nxt_open.start() < nxt_close.start():
            if nxt_open.group(1).lower() == name and not nxt_open.group(3) and name not in VOID:
                depth += 1
            pos = nxt_open.end()
            continue
        depth -= 1
        if depth == 0:
            return nxt_close.start()
        pos = nxt_close.end()
    return -1


def swap_to_english(html: str) -> tuple[str, int]:
    """Подставляет data-en внутрь тега и убирает служебные атрибуты."""
    out, pos, swapped = [], 0, 0
    while True:
        m = TAG.search(html, pos)
        if not m:
            out.append(html[pos:])
            break
        a = attrs_of(m.group(2))
        if "data-en" not in a:
            out.append(html[pos:m.end()])
            pos = m.end()
            continue

        name = m.group(1)
        end = close_index(html, m.end(), name.lower())
        if end < 0:                       # не нашли пару — оставляем как есть
            out.append(html[pos:m.end()])
            pos = m.end()
            continue

        kept = " ".join(
            f'{k}="{v}"' if v != "" or k in ("alt",) else k
            for k, v in a.items() if k not in ("data-ru", "data-en")
        )
        out.append(html[pos:m.start()])
        out.append(f'<{name}{" " + kept if kept else ""}>')
        out.append(a["data-en"].replace("&quot;", '"'))
        pos = end
        swapped += 1
    return "".join(out), swapped


def main() -> int:
    if not SRC.exists():
        print("нет index.html рядом со скриптом")
        return 1

    html = SRC.read_text(encoding="utf-8")
    html, swapped = swap_to_english(html)

    html = html.replace('<html lang="ru">', '<html lang="en">')

    # заголовок и описание для выдачи и превью
    html = re.sub(r"<title>.*?</title>",
                  "<title>Anastasia Arkhipenko — AI Artist &amp; Director | advertising, fashion, music videos</title>",
                  html, flags=re.S)
    html = re.sub(r'(<meta name="description" content=")[^"]*"',
                  r"\1Anastasia Arkhipenko — AI Artist &amp; Director. I design and direct projects: "
                  r"commercials, product films, fashion campaigns, trailers, music videos and experimental art. "
                  r'Fully AI, or mixed with real footage."', html)
    html = html.replace('content="Анастасия Архипенко — AI Artist &amp; Director"',
                        'content="Anastasia Arkhipenko — AI Artist &amp; Director"')
    html = html.replace('content="Проектирую и режиссирую проекты: от визуального языка до готового видео. '
                        'Полностью на ИИ или в связке с реальной съемкой."',
                        'content="I design and direct projects: from visual language to the final cut. '
                        'Fully AI, or mixed with real footage."')

    # адреса: страница лежит на уровень глубже
    html = html.replace('href="https://aimamba.art/">\n<link rel="alternate" hreflang="ru"',
                        'href="https://aimamba.art/en/">\n<link rel="alternate" hreflang="ru"', 1)
    html = html.replace('<meta property="og:url" content="https://aimamba.art/">',
                        '<meta property="og:url" content="https://aimamba.art/en/">')
    html = html.replace('"assets/', '"../assets/')
    html = html.replace("fetch('projects.json'", "fetch('../projects.json'")
    html = html.replace('href="work/${w.slug}/"', 'href="../work/${w.slug}/"')

    # переключатель языка
    html = html.replace('<a href="./" hreflang="ru" aria-current="page">RU</a>',
                        '<a href="../" hreflang="ru">RU</a>')
    html = html.replace('<a href="en/" hreflang="en">EN</a>',
                        '<a href="./" hreflang="en" aria-current="page">EN</a>')

    # атрибуты: alt и подписи для скринридеров
    for ru, en in {
        "Анастасия Архипенко в желтом костюме в прыжке с ударом ноги":
            "Anastasia Arkhipenko in a yellow tracksuit, mid kick",
        "Анастасия Архипенко с жевательной резинкой":
            "Anastasia Arkhipenko blowing a bubble",
        'aria-label="Меню"': 'aria-label="Menu"',
        'aria-label="Закрыть"': 'aria-label="Close"',
        'aria-label="Включить звук"': 'aria-label="Unmute"',
        'aria-label="Лопнуть пузырь"': 'aria-label="Pop the bubble"',
        'aria-label="Язык / Language"': 'aria-label="Language"',
    }.items():
        html = html.replace(ru, en)

    html = html.replace("const LANG = 'ru';", "const LANG = 'en';")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(html, encoding="utf-8")

    print(f"собрано: {OUT.relative_to(ROOT)}")
    print(f"переведено блоков: {swapped}")
    left = len(re.findall(r'data-ru="', html))
    print("остаточных data-ru:", left)
    for probe, what in [("../assets/kick-1600.webp", "картинки"),
                        ("const LANG = 'en'", "язык"),
                        ("aria-current=\"page\">EN", "переключатель")]:
        print(("  ✓ " if probe in html else "  ✗ ") + what)
    return 0


if __name__ == "__main__":
    sys.exit(main())
