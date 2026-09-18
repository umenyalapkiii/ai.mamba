#!/usr/bin/env python3
"""
Собирает альтернативную цветовую схему 4B Studio Magenta из index.html.

Запуск:  python3 build_magenta.py

Делает две вещи:
  magenta/index.html        — версия для сайта, картинки берёт из ../assets/
  ai.mamba-magenta.html     — один файл со всем внутри, для скачивания

Правило схемы из гайда: малиновый — только фон и заливки, текст на нём
светлый; жёлтый остаётся акцентом в тексте и кнопках.
Основной сайт не трогается: правишь index.html, потом прогоняешь этот скрипт.
"""

import base64
import mimetypes
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "index.html"
OUT_SITE = ROOT / "magenta" / "index.html"
OUT_FILE = ROOT.parent / "ai.mamba-magenta.html"

OVERRIDE = """
/* ============================================================
   4B · STUDIO MAGENTA
   Малиновый #CE1B6F работает только заливкой, текст на нём светлый.
   Жёлтый остаётся акцентом в тексте и рамках — как в гайде.
   ============================================================ */
:root{ --magenta:#CE1B6F; --magenta-dim:#7A1042; }

/* герой: малиновая циклорама за мамбой */
.hero .scene::before{
  content:"";position:absolute;inset:-3% -7% 4% -7%;
  background:
    repeating-linear-gradient(135deg, rgba(0,0,0,.07) 0 9px, transparent 9px 18px),
    var(--magenta);
}

/* подпись должности — малиновой плашкой */
.hero__eyebrow{
  display:inline-block;padding:8px 14px;margin-bottom:clamp(14px,2vw,22px);
  background:var(--magenta);color:#F2F1EE;
}
.hero__eyebrow s{color:rgba(242,241,238,.55)}
.hero__eyebrow b{color:rgba(242,241,238,.8)}

/* шкала дедлайна — малиновая заливка */
.hud__bar i{background:var(--magenta)}

/* работы: рамка малиновая, цифры и название остаются жёлтыми */
.card:hover,.card:focus-visible{border-color:var(--magenta)}
.card__media::after{background:linear-gradient(180deg,transparent,rgba(206,27,111,.3),transparent)}
.card__series{background:var(--magenta);border-color:var(--magenta);color:#F2F1EE}

/* услуги: активная строка заливается малиновым */
.srv__row:hover,.srv__row.is-near{background:var(--magenta)}
.srv__row:hover .srv__t,.srv__row.is-near .srv__t{color:#F2F1EE}
.srv__row:hover .srv__d,.srv__row.is-near .srv__d{color:rgba(242,241,238,.88)}
.srv__row:hover .srv__n,.srv__row.is-near .srv__n{color:rgba(242,241,238,.6)}
.srv__row{padding-inline:10px;margin-inline:-10px;transition:background .3s}

/* пузырь лопается малиновым */
.pop.on .pop__bubble{animation-name:bubbleMagenta}
@keyframes bubbleMagenta{
  0%  {transform:scale(1);opacity:1;box-shadow:0 0 0 rgba(206,27,111,0)}
  15% {transform:scale(1.14)}
  40% {transform:scale(1.58);box-shadow:0 0 70px 18px rgba(206,27,111,.6)}
  52% {transform:scale(1.78);opacity:1;box-shadow:0 0 96px 26px rgba(206,27,111,.78)}
  60% {transform:scale(1.94);opacity:0;box-shadow:0 0 0 rgba(206,27,111,0)}
  100%{transform:scale(1);opacity:1;box-shadow:0 0 0 rgba(206,27,111,0)}
}
.pop__burst i{background:var(--magenta)}

/* карусель */
.car__nav:hover{background:rgba(206,27,111,.3);border-color:var(--magenta);color:#F2F1EE}
.car__dots i.on{background:var(--magenta)}

/* контакты: плашка малиновая, текст светлый, кнопка жёлтым по чёрному */
.contact{background:var(--magenta);color:#F2F1EE}
.contact h2,.contact h2 .y{color:#F2F1EE}
.steps{border-top-color:rgba(242,241,238,.28)}
.steps li{border-bottom-color:rgba(242,241,238,.28);color:#F2F1EE}
.steps li::before{color:#F2F1EE;border-color:rgba(242,241,238,.5)}
.point{color:#F2F1EE}
.soc{border-color:rgba(242,241,238,.4);color:rgba(242,241,238,.85)}
.soc:hover{color:var(--yellow);background:#0B0B0C;border-color:#0B0B0C}

/* фоновый луч под цвет схемы */
.bg__beam{
  background:radial-gradient(440px 440px at var(--mx,50%) var(--my,26%),
    rgba(206,27,111,.2) 0%,rgba(206,27,111,.06) 38%,transparent 70%);
}
.bg__grid{
  background-image:
    linear-gradient(rgba(206,27,111,.06) 1px,transparent 1px),
    linear-gradient(90deg,rgba(206,27,111,.06) 1px,transparent 1px);
}
"""

BANNER = """<!-- ============================================================
     ai.mamba — альтернативная цветовая схема 4B Studio Magenta.
     Собрано из index.html скриптом build_magenta.py.
     Основной сайт живёт отдельно и этим файлом не затрагивается.
     ============================================================ -->
"""


def tint(html: str, title_suffix: str) -> str:
    html = html.replace("</style>", OVERRIDE + "\n</style>", 1)
    html = re.sub(r"<title>(.*?)</title>", lambda m: f"<title>{m.group(1)} · {title_suffix}</title>",
                  html, count=1, flags=re.S)
    # у альтернативной схемы своя жизнь: из поиска её прятать, чтобы она
    # не конкурировала с основным сайтом
    html = html.replace('<meta name="viewport"',
                        '<meta name="robots" content="noindex">\n<meta name="viewport"', 1)
    return BANNER + html


def inline_assets(html: str) -> str:
    """Вшивает картинки и шрифты прямо в файл — чтобы он работал
    сам по себе, без папки assets рядом."""
    seen: dict[str, str] = {}

    def to_data_uri(rel: str) -> str | None:
        path = ROOT / rel
        if not path.exists():
            return None
        if rel not in seen:
            mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            if path.suffix == ".woff2":
                mime = "font/woff2"
            seen[rel] = f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"
        return seen[rel]

    def sub(m: re.Match) -> str:
        quote, rel = m.group(1), m.group(2)
        uri = to_data_uri(rel)
        return m.group(0) if uri is None else f"{m.group(0)[:m.start(1)-m.start(0)]}{quote}{uri}"

    html = re.sub(r'(?<==)(")(assets/[^"]+)"',
                  lambda m: f'"{to_data_uri(m.group(2)) or m.group(2)}"', html)
    html = re.sub(r'url\("(assets/[^"]+)"\)',
                  lambda m: f'url("{to_data_uri(m.group(1)) or m.group(1)}")', html)
    # предзагрузка вшитых файлов теряет смысл и только раздувает разметку
    html = re.sub(r'\n<link rel="preload"[^>]*>', "", html)
    return html


def main() -> int:
    if not SRC.exists():
        print("нет index.html рядом со скриптом")
        return 1
    src = SRC.read_text(encoding="utf-8")

    site = tint(src, "Magenta").replace('"assets/', '"../assets/').replace('url("assets/', 'url("../assets/')
    site = site.replace("fetch('projects.json'", "fetch('../projects.json'")
    site = site.replace('href="work/${w.slug}/"', 'href="../work/${w.slug}/"')
    site = site.replace('<a href="./" hreflang="ru" aria-current="page">RU</a>',
                        '<a href="../" hreflang="ru">RU</a>')
    site = site.replace('<a href="en/" hreflang="en">EN</a>',
                        '<a href="../en/" hreflang="en">EN</a>')
    OUT_SITE.parent.mkdir(exist_ok=True)
    OUT_SITE.write_text(site, encoding="utf-8")

    standalone = inline_assets(tint(src, "Magenta"))
    OUT_FILE.write_text(standalone, encoding="utf-8")

    print(f"на сайте:      {OUT_SITE.relative_to(ROOT)}  ({OUT_SITE.stat().st_size // 1024} КБ)")
    print(f"для скачивания:{OUT_FILE.name}  ({OUT_FILE.stat().st_size // 1024} КБ, всё внутри)")
    left = len(re.findall(r'"(?:\.\./)?assets/', standalone))
    print(f"невшитых ссылок на assets в отдельном файле: {left}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
