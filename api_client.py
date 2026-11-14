"""HTTP-слой: запросы к open.er-api.com и проверка ответа.

Модуль ничего не знает про кэш и интерфейс: только сеть и разбор ответа.
"""

from __future__ import annotations

import re

import requests

REQUEST_TIMEOUT = 10
CODE_PATTERN = re.compile(r"^[A-Z]{3}$")


class CurrencyError(Exception):
    """Ошибка, которую можно показать пользователю без стектрейса."""


def normalize_code(code: str) -> str:
    """Привести код валюты к верхнему регистру и проверить формат ISO 4217.

    Raises:
        CurrencyError: пустой код или не три латинские буквы.
    """
    code = (code or "").strip().upper()
    if not code:
        raise CurrencyError("Код валюты не может быть пустым.")
    if not CODE_PATTERN.fullmatch(code):
        raise CurrencyError(
            f"«{code}» не похоже на код валюты. Нужны три латинские буквы, "
            "например USD, EUR, RUB. Список кодов — пункт меню 4."
        )
    return code


def get_currency_rates(base: str) -> dict:
    """Запросить курсы к базовой валюте через open.er-api.com.

    Args:
        base: код базовой валюты, например "USD".

    Returns:
        Ответ API целиком как dict (в нём base_code, time_last_update_utc, rates).

    Raises:
        CurrencyError: пустой или неизвестный код, ошибка сети, не-JSON ответ.
    """
    base = normalize_code(base)
    url = f"https://open.er-api.com/v6/latest/{base}"

    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        raise CurrencyError(f"Не удалось связаться с API: {exc}") from exc

    if response.status_code != 200:
        raise CurrencyError(
            f"API вернул HTTP {response.status_code} ({response.reason}). "
            "Проверьте код валюты и подключение к сети."
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise CurrencyError("Ответ API не является JSON.") from exc

    if not isinstance(payload, dict):
        raise CurrencyError("Неожиданный формат ответа API.")

    # Неизвестный код API отдаёт с HTTP 200 и result="error" — проверяем тело.
    if payload.get("result") != "success":
        reason = payload.get("error-type") or payload.get("result") or "неизвестная ошибка"
        raise CurrencyError(f"API отклонил запрос: {reason}. Проверьте код валюты «{base}».")

    if not extract_rates(payload):
        raise CurrencyError("В ответе API нет курсов валют.")

    return payload


def extract_rates(payload: dict) -> dict:
    """Достать курсы из ответа.

    Актуальный ключ — "rates"; "conversion_rates" поддерживается как запасной,
    потому что он встречается в старых материалах и ответах.
    """
    rates = payload.get("rates")
    if isinstance(rates, dict) and rates:
        return rates
    rates = payload.get("conversion_rates")
    return rates if isinstance(rates, dict) else {}
