#!/usr/bin/env python3
"""
Собирает данные сайта из папки works/.

Запуск:  python3 build.py

Читает каждую подпапку works/, вытаскивает info.txt и медиафайлы,
складывает всё в projects.json — его читает сайт.
Если установлен ffmpeg, дополнительно делает постеры и лёгкие превью-петли.
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
WORKS = ROOT / "works"
OUT = ROOT / "projects.json"

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm"}
PHOTO_EXT = {".jpg", ".jpeg", ".png", ".webp", ".avif"}

# синонимы ключей в info.txt — пиши как удобно, скрипт поймёт
KEYS = {
    "title":    ["название", "заголовок", "title", "имя"],
    "title_en": ["название en", "en", "title en"],
    "sub":      ["подзаголовок", "подпись", "sub"],
    "sub_en":   ["подзаголовок en", "sub en"],
    "desc":     ["описание", "текст", "desc"],
    "desc_en":  ["описание en", "desc en"],
    "role":     ["роль", "role"],
    "stack":    ["стек", "инструменты", "stack"],
    "year":     ["год", "year"],
    "client":   ["клиент", "заказчик", "client"],
    "category": ["категория", "раздел", "category"],
    "ratio":    ["формат", "пропорции", "ratio"],
    # куда смотреть при обрезке плитки: центр / верх / низ / «50% 22%»
    "focus":    ["фокус", "кадрирование", "focus"],
    # плитка на две колонки — для горизонтальных обложек
    "wide":     ["широкая", "wide"],
    # то же, но закреплена справа сверху: над ней ничего не встаёт
    "hero":     ["главная", "hero"],
    # номер колонки на широком экране — им доводится композиция
    "col":      ["колонка", "col"],
    # подпись на значке проигрывания, вида 0:38
    "dur":      ["длительность", "хронометраж", "duration"],
    # подпись на чипе слева вверху; по умолчанию берётся из жанра
    "tag":      ["тег", "чип", "tag"],
    "tag_en":   ["тег en", "tag en"],
    # жанр для фильтра на главной: ad / music / fashion / cine / creative
    "genre":    ["жанр", "genre"],
    "link":     ["ссылка", "link", "url"],
}
LOOKUP = {alias: field for field, aliases in KEYS.items() for alias in aliases}

HAS_FFMPEG = shutil.which("ffmpeg") is not None


def parse_info(path: Path) -> dict:
    """Читает info.txt: строки вида «ключ: значение». Многострочное значение
    продолжается, пока строка не начнётся с нового «ключ:»."""
    data, current = {}, None
    if not path.exists():
        return data
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        m = re.match(r"^\s*([A-Za-zА-Яа-яЁё ]{2,20}?)\s*:\s*(.*)$", line)
        key = LOOKUP.get(m.group(1).strip().lower()) if m else None
        if key:
            data[key] = m.group(2).strip()
            current = key
        elif current and line.strip():
            data[current] += "\n" + line.strip()
    return data


RHYTHM = ["4/5", "1/1", "3/4", "9/16", "4/5", "3/4", "1/1", "4/5"]


def probe_duration(video: Path) -> str:
    """Длительность ролика как 0:38 — её печатает значок проигрывания."""
    if not HAS_FFMPEG:
        return ""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(video)],
            capture_output=True, text=True, timeout=20).stdout.strip()
        sec = round(float(out))
        return f"{sec // 60}:{sec % 60:02d}"
    except Exception:
        return ""


def make_poster(video: Path, dest: Path) -> bool:
    """Снимает кадр на 1-й секунде как постер для карточки."""
    if not HAS_FFMPEG or dest.exists():
        return dest.exists()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "1", "-i", str(video),
                    "-frames:v", "1", "-vf", "scale=1200:-2", str(dest)], timeout=120)
    return dest.exists()


def make_preview(video: Path, dest: Path) -> bool:
    """Делает немую петлю 6 секунд, 720p — её сайт крутит на наведение."""
    if not HAS_FFMPEG or dest.exists():
        return dest.exists()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video),
                    "-t", "6", "-an", "-vf", "scale=-2:720",
                    "-c:v", "libx264", "-crf", "30", "-preset", "slow",
                    "-movflags", "+faststart", str(dest)], timeout=600)
    return dest.exists()


TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e",
    "ю": "yu", "я": "ya",
}


def slugify(name: str) -> str:
    """Имя папки → адрес страницы. Кириллицу переводит в латиницу,
    чтобы ссылка вида /work/nochnaya-scena/ читалась и не ломалась."""
    name = re.sub(r"^\d+[-_. ]*", "", name).lower()
    name = "".join(TRANSLIT.get(ch, ch) for ch in name)
    return re.sub(r"[^a-z0-9]+", "-", name).strip("-")


# обложку и петлю можно положить руками — так кадр выбираешь ты, а не ffmpeg
COVER_NAMES = {"cover", "обложка", "poster", "постер"}
PREVIEW_NAMES = {"preview", "превью", "loop", "петля"}


def pick(folder: Path, names: set, exts: set) -> Path | None:
    return next((p for p in sorted(folder.iterdir())
                 if p.is_file() and p.stem.lower() in names and p.suffix.lower() in exts), None)


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


YES = {"да", "yes", "true", "1", "+"}


def collect(folder: Path, idx: int = 0) -> dict | None:
    info = parse_info(folder / "info.txt")
    cover = pick(folder, COVER_NAMES, PHOTO_EXT)
    manual_preview = pick(folder, PREVIEW_NAMES, VIDEO_EXT)
    # обложка и петля — служебные файлы, в серию кадров они не попадают
    skip = {p.name for p in (cover, manual_preview) if p}
    media = sorted(p for p in folder.iterdir()
                   if p.is_file() and not p.name.startswith((".", "_"))
                   and p.name not in skip
                   and "preview" not in p.stem and "poster" not in p.stem)
    videos = [p for p in media if p.suffix.lower() in VIDEO_EXT]
    photos = [p for p in media if p.suffix.lower() in PHOTO_EXT]

    if not videos and not photos and not info:
        return None

    slug = slugify(folder.name) or f"project-{abs(hash(folder.name)) % 10000}"

    project = {
        "slug": slug,
        "folder": rel(folder),
        "type": "video" if videos else "photos",
        "title": info.get("title") or folder.name,
        "sub": info.get("sub", ""),
        "desc": info.get("desc", ""),
        "role": info.get("role", ""),
        "stack": info.get("stack", ""),
        "year": info.get("year", ""),
        "client": info.get("client", ""),
        "category": info.get("category", ""),
        # ключ фильтра на главной: ad / music / fashion / cine / creative
        "genre": info.get("genre", ""),
        "tag": info.get("tag", ""),
        "tag_en": info.get("tag_en", ""),
        # object-position обложки: кадр обрезается под плитку, а не наоборот
        "focus": info.get("focus", ""),
        "wide": info.get("wide", "").strip().lower() in YES,
        "hero": info.get("hero", "").strip().lower() in YES,
        "col": info.get("col", "").strip(),
        "link": info.get("link", ""),
        "en": {k[:-3]: info[k] for k in ("title_en", "sub_en", "desc_en") if k in info},
        "photos": [rel(p) for p in photos],
        "hasCase": (folder / "case.md").exists(),
    }

    if videos:
        main = videos[0]
        project["video"] = rel(main)
        # несколько роликов в папке — это серия: в карточке они идут каруселью
        if len(videos) > 1:
            project["clips"] = [rel(v) for v in videos]
        if manual_preview:
            project["preview"] = rel(manual_preview)
        elif make_preview(main, folder / "_preview.mp4"):
            project["preview"] = rel(folder / "_preview.mp4")
        if cover:
            project["poster"] = rel(cover)
        elif make_poster(main, folder / "_poster.jpg"):
            project["poster"] = rel(folder / "_poster.jpg")
        elif photos:
            project["poster"] = rel(photos[0])
    elif cover:
        project["poster"] = rel(cover)
    elif photos:
        project["poster"] = rel(photos[0])

    if videos:
        project["dur"] = info.get("dur") or probe_duration(ROOT / project["video"])

    # Пропорцию задаёт СЕТКА, а не файл: плитки должны быть разной высоты,
    # иначе галерея выглядит как таблица. Обложку под плитку подрезает
    # браузер (object-fit), а куда смотреть при обрезке — ключ «фокус».
    project["ratio"] = info.get("ratio") or RHYTHM[idx % len(RHYTHM)]
    return project


def main() -> int:
    if not WORKS.exists():
        print("нет папки works/ — создай её и положи туда проекты")
        return 1

    folders = sorted(p for p in WORKS.iterdir()
                     if p.is_dir() and not p.name.startswith((".", "_")))
    projects = [pr for pr in (collect(f, i) for i, f in enumerate(folders)) if pr]

    OUT.write_text(json.dumps(projects, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nсобрано проектов: {len(projects)}\n")
    for p in projects:
        flags = []
        if p.get("clips"):
            flags.append(f"роликов: {len(p['clips'])}")
        if p.get("preview"):
            flags.append("превью")
        if p.get("hero"):
            flags.append("главная")
        elif p.get("wide"):
            flags.append("широкая")
        if p["hasCase"]:
            flags.append("кейс-страница")
        if not p["desc"]:
            flags.append("!нет описания")
        print(f"  {p['ratio']:>5}  {p['title'][:34]:34} {' · '.join(flags)}")

    if not HAS_FFMPEG:
        print("\nffmpeg не установлен — постеры и лёгкие превью не сделаны.")
        print("поставить:  brew install ffmpeg")
        print("без него положи в папку проекта cover.webp и preview.mp4 вручную.")
    print(f"\nзаписано в {OUT.name}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
