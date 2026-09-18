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


def probe_ratio(path: Path) -> str:
    """Определяет пропорцию медиафайла и округляет до ближайшего ходового формата."""
    w = h = None
    if path.suffix.lower() in PHOTO_EXT:
        try:
            from PIL import Image
            with Image.open(path) as im:
                w, h = im.size
        except Exception:
            pass
    elif HAS_FFMPEG:
        try:
            out = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(path)],
                capture_output=True, text=True, timeout=20).stdout.strip()
            w, h = (int(v) for v in out.split("x")[:2])
        except Exception:
            pass
    if not w or not h:
        return "16/9"
    target = w / h
    known = {"9/16": 9 / 16, "4/5": 4 / 5, "1/1": 1.0, "3/2": 1.5, "16/9": 16 / 9, "21/9": 21 / 9}
    return min(known, key=lambda k: abs(known[k] - target))


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


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def collect(folder: Path) -> dict | None:
    info = parse_info(folder / "info.txt")
    media = sorted(p for p in folder.iterdir()
                   if p.is_file() and not p.name.startswith((".", "_"))
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
        "link": info.get("link", ""),
        "en": {k[:-3]: info[k] for k in ("title_en", "sub_en", "desc_en") if k in info},
        "photos": [rel(p) for p in photos],
        "hasCase": (folder / "case.md").exists(),
    }

    if videos:
        main = videos[0]
        project["video"] = rel(main)
        poster = folder / "_poster.jpg"
        preview = folder / "_preview.mp4"
        if make_poster(main, poster):
            project["poster"] = rel(poster)
        if make_preview(main, preview):
            project["preview"] = rel(preview)
        elif photos:
            project["poster"] = rel(photos[0])
    elif photos:
        project["poster"] = rel(photos[0])

    first = project.get("video") or (project["photos"][0] if project["photos"] else None)
    project["ratio"] = info.get("ratio") or (probe_ratio(ROOT / first) if first else "16/9")
    return project


def main() -> int:
    if not WORKS.exists():
        print("нет папки works/ — создай её и положи туда проекты")
        return 1

    folders = sorted(p for p in WORKS.iterdir()
                     if p.is_dir() and not p.name.startswith((".", "_")))
    projects = [pr for pr in (collect(f) for f in folders) if pr]

    OUT.write_text(json.dumps(projects, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nсобрано проектов: {len(projects)}\n")
    for p in projects:
        flags = []
        if p.get("preview"):
            flags.append("превью")
        if p["hasCase"]:
            flags.append("кейс-страница")
        if not p["desc"]:
            flags.append("!нет описания")
        print(f"  {p['ratio']:>5}  {p['title'][:34]:34} {' · '.join(flags)}")

    if not HAS_FFMPEG:
        print("\nffmpeg не установлен — постеры и лёгкие превью не сделаны.")
        print("поставить:  brew install ffmpeg")
        print("без него положи в папку проекта cover.jpg вручную.")
    print(f"\nзаписано в {OUT.name}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
