"""Фасад и точка входа: связывает HTTP-слой, кэш и интерфейс.

Запуск:
    python currency.py

Модульная версия (v2):
    api_client.py — HTTP-запросы и проверка ответа;
    storage.py    — чтение/запись JSON-кэша;
    cli.py        — меню и ввод/вывод;
    currency.py   — бизнес-логика (кэш или API, конвертация) и точка входа.

Обязательные функции доступны и здесь: get_currency_rates, save_to_file,
read_from_file (реэкспорт из слоёв).
"""

from __future__ import annotations

import sys

from api_client import CurrencyError, extract_rates, get_currency_rates, normalize_code
from storage import (
    DEFAULT_CACHE_PATH,
    is_cache_fresh,
    read_from_file,
    save_to_file,
)

__all__ = [
    "CurrencyError",
    "normalize_code",
    "get_currency_rates",
    "extract_rates",
    "save_to_file",
    "read_from_file",
    "is_cache_fresh",
    "load_rates",
    "convert",
    "main",
]


def load_rates(
    base: str,
    path: str = DEFAULT_CACHE_PATH,
    force_refresh: bool = False,
) -> tuple[dict, str]:
    """Вернуть (ответ API, источник), где источник — "кэш" или "API".

    Кэш используется, только если он свежий и снят для той же базовой валюты.
    """
    base = normalize_code(base)

    if not force_refresh and is_cache_fresh(path):
        try:
            cached = read_from_file(path)
        except (OSError, ValueError):
            cached = None
        if isinstance(cached, dict) and str(cached.get("base_code", "")).upper() == base:
            if extract_rates(cached):
                return cached, "кэш"

    payload = get_currency_rates(base)
    try:
        save_to_file(payload, path)
    except OSError as exc:
        raise CurrencyError(f"Не удалось сохранить кэш {path}: {exc}") from exc
    return payload, "API"


def convert(
    amount: float,
    from_currency: str,
    to_currency: str,
    path: str = DEFAULT_CACHE_PATH,
) -> tuple[float, str]:
    """Сконвертировать сумму по курсам.

    Returns:
        (результат, источник данных).

    Raises:
        CurrencyError: неизвестный код валюты.
    """
    from_currency = normalize_code(from_currency)
    to_currency = normalize_code(to_currency)

    payload, source = load_rates(from_currency, path)
    rates = extract_rates(payload)

    missing = [code for code in (from_currency, to_currency) if code not in rates]
    if missing:
        examples = ", ".join(sorted(rates)[:10])
        raise CurrencyError(
            f"Валюта «{missing[0]}» не найдена. Доступно кодов: {len(rates)}. "
            f"Например: {examples}."
        )

    rate = rates[to_currency] / rates[from_currency]
    return amount * rate, source


def main() -> int:
    """Точка входа CLI (реализация — в cli.py)."""
    from cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    sys.exit(main())
