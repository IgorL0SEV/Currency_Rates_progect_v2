"""Файловый слой: чтение и запись кэша курсов.

Модуль не делает запросов и не печатает: только JSON-файл и TTL.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

DEFAULT_CACHE_PATH = "currency_rate.json"
CACHE_TTL_SECONDS = 24 * 60 * 60


def save_to_file(data: dict, path: str = DEFAULT_CACHE_PATH) -> None:
    """Сохранить ответ API в JSON-файл в читаемом виде."""
    # ensure_ascii=False сохраняет кириллицу, indent=4 — отступы.
    # encoding задаётся у open(), а не у json.dump().
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def read_from_file(path: str = DEFAULT_CACHE_PATH) -> dict:
    """Прочитать JSON-файл кэша."""
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def is_cache_fresh(path: str = DEFAULT_CACHE_PATH, ttl: int = CACHE_TTL_SECONDS) -> bool:
    """Свежий ли файл кэша (моложе ttl секунд)."""
    file = Path(path)
    if not file.is_file():
        return False
    return (time.time() - file.stat().st_mtime) < ttl
