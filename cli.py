"""Интерфейс: меню, ввод/вывод и обработка ошибок.

Модуль не делает запросов и не пишет файлы — вызывает бизнес-логику из currency.py.
"""

from __future__ import annotations

import time
from pathlib import Path

from currency import (
    CurrencyError,
    convert,
    extract_rates,
    is_cache_fresh,
    load_rates,
    normalize_code,
    read_from_file,
)
from storage import CACHE_TTL_SECONDS, DEFAULT_CACHE_PATH

DISPLAY_CURRENCIES = ("RUB", "EUR", "GBP")
RATES_NOTE = (
    "Ориентировочный рыночный курс провайдера — не курс конкретного банка "
    "или обменника; банки добавляют свою наценку."
)


def _ask(prompt: str, default: str = "") -> str:
    """Спросить строку; пустой ввод — значение по умолчанию."""
    value = input(prompt).strip()
    return value or default


def _cache_hint(path: str, base: str) -> str:
    """Одна строка о том, откуда возьмутся данные для текущей базы."""
    file = Path(path)
    if not file.is_file():
        return "данных нет — загрузятся при первом запросе"

    try:
        payload = read_from_file(path)
    except (OSError, ValueError):
        return "кэш повреждён — будет перезаписан"

    age_hours = (time.time() - file.stat().st_mtime) / 3600
    cached_base = str(payload.get("base_code", "?")).upper()

    if cached_base != base.upper():
        return f"в кэше {cached_base} ({age_hours:.1f} ч) — данные по {base} обновятся при запросе"
    if is_cache_fresh(path):
        return f"кэш {age_hours:.1f} ч, актуален"
    return f"кэш {age_hours:.1f} ч, устарел — обновится при запросе"


def _show_rates(base: str, path: str) -> None:
    """Показать курсы текущей базовой валюты к RUB, EUR, GBP."""
    payload, source = load_rates(base, path)
    rates = extract_rates(payload)
    base_code = payload.get("base_code", base)
    provider = str(payload.get("provider", "exchangerate-api.com")).replace("https://", "").replace("http://", "")

    print(f"\nКурсы к {base_code} — провайдер {provider}")
    print(f"  данные: {source}, обновлено: {payload.get('time_last_update_utc', '?')} (UTC)")
    print(f"  {RATES_NOTE}")
    for code in DISPLAY_CURRENCIES:
        if code == base_code:
            continue
        value = rates.get(code)
        if value is None:
            print(f"  {code}: нет в ответе")
        else:
            print(f"  1 {base_code} = {value:.4f} {code}")


def _convert_amount(base: str, path: str) -> None:
    """Сконвертировать сумму; по умолчанию — из текущей базовой валюты."""
    from_currency = _ask(f"Из валюты [{base}]: ", base)
    to_currency = _ask("В валюту [RUB]: ", "RUB")
    raw_amount = _ask("Сумма: ")
    try:
        amount = float(raw_amount.replace(",", "."))
    except ValueError as exc:
        raise CurrencyError("Сумма должна быть числом, например 100 или 99.5.") from exc

    result, source = convert(amount, from_currency, to_currency, path)
    print(f"\n{amount:.2f} {from_currency} = {result:.4f} {to_currency}  (источник: {source}, ориентировочно)")


def _choose_base(base: str, path: str) -> str:
    """Сменить базовую валюту сессии. Проверяет код запросом, чтобы не сохранить несуществующий."""
    new_base = normalize_code(_ask(f"Новая базовая валюта [{base}]: ", base))
    if new_base == base.upper():
        print(f"База не изменена: {base}.")
        return base

    payload, source = load_rates(new_base, path)
    print(f"База изменена: {base} -> {new_base} (источник: {source}).")
    return str(payload.get("base_code", new_base))


def _available_codes(path: str) -> tuple[list[str], str]:
    """Все поддерживаемые коды. Набор одинаков для любой базы, поэтому свежего кэша достаточно."""
    if is_cache_fresh(path):
        try:
            cached = read_from_file(path)
        except (OSError, ValueError):
            cached = None
        rates = extract_rates(cached) if isinstance(cached, dict) else {}
        if rates:
            return sorted(rates), "кэш"
    payload, source = load_rates("USD", path)
    return sorted(extract_rates(payload)), source


def _print_codes(codes: list[str]) -> None:
    for start in range(0, len(codes), 20):
        print("  " + ", ".join(codes[start:start + 20]))


def _find_currency(path: str) -> None:
    """Найти код валюты: точный код, начало кода или весь список по Enter."""
    codes, source = _available_codes(path)
    query = _ask("Код или начало кода (Enter — весь список): ").upper()

    print(f"\nВсего кодов: {len(codes)} (источник: {source})")
    if not query:
        _print_codes(codes)
        return

    if query in codes:
        print(f"  {query} — есть в списке. Курсы к {query} — пункт 1.")
        return

    matches = [code for code in codes if code.startswith(query)]
    if not matches:
        matches = [code for code in codes if query in code]

    if matches:
        print(f"  Точного совпадения нет. Похожие ({len(matches)}):")
        _print_codes(matches)
    else:
        print(f"  «{query}» не найдено. Весь список:")
        _print_codes(codes)


def _show_cache_status(path: str) -> None:
    """Показать состояние файла кэша: возраст, база, время обновления."""
    file = Path(path)
    if not file.is_file():
        print(f"\nКэш не создан: {path}")
        return

    try:
        payload = read_from_file(path)
    except (OSError, ValueError) as exc:
        raise CurrencyError(f"Кэш повреждён и не читается: {exc}") from exc

    age_hours = (time.time() - file.stat().st_mtime) / 3600
    state = "свежий" if is_cache_fresh(path) else "устарел"
    rates = extract_rates(payload)

    print(f"\nФайл: {file.resolve()}")
    print(f"  возраст: {age_hours:.1f} ч (TTL {CACHE_TTL_SECONDS // 3600} ч, {state})")
    print(f"  база: {payload.get('base_code', '?')}, валют в файле: {len(rates)}")
    print(f"  обновлено API: {payload.get('time_last_update_utc', '?')}")
    print(f"  следующее обновление API: {payload.get('time_next_update_utc', '?')}")


def _refresh_cache(base: str, path: str) -> None:
    """Принудительно запросить API и перезаписать кэш для текущей базы."""
    payload, _ = load_rates(base, path, force_refresh=True)
    print(
        f"\nДанные обновлены: база {payload.get('base_code', base)}, "
        f"валют: {len(extract_rates(payload))}, "
        f"API обновил: {payload.get('time_last_update_utc', '?')}"
    )


def main() -> int:
    """Мини-CLI: состояние сессии, курсы, конвертация, поиск валюты, кэш."""
    path = DEFAULT_CACHE_PATH
    base = "USD"

    print("Курсы валют — open.er-api.com (провайдер exchangerate-api.com)")
    print(RATES_NOTE)
    print("Один общий набор курсов провайдера, время обновления — UTC, раз в сутки.")
    print(f"Считаем от базовой валюты {base}. Сменить — пункт 3.\n")

    while True:
        targets = ", ".join(code for code in DISPLAY_CURRENCIES if code != base)
        print(f"База: {base} | {_cache_hint(path, base)}")
        print(f"1 - Показать курсы: 1 {base} = {targets}")
        print("2 - Конвертировать сумму")
        print(f"3 - Сменить базовую валюту (сейчас {base})")
        print("4 - Найти валюту / список кодов")
        print(f"5 - Обновить данные из API (для {base})")
        print("6 - Состояние кэша")
        print("0 - Выход")

        try:
            choice = input("Выбор: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nВыход.")
            return 0

        try:
            if choice == "1":
                _show_rates(base, path)
            elif choice == "2":
                _convert_amount(base, path)
            elif choice == "3":
                base = _choose_base(base, path)
            elif choice == "4":
                _find_currency(path)
            elif choice == "5":
                _refresh_cache(base, path)
            elif choice == "6":
                _show_cache_status(path)
            elif choice == "0":
                print("Пока!")
                return 0
            else:
                print("Неизвестный пункт меню.")
        except CurrencyError as exc:
            print(f"\n[ОШИБКА] {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
