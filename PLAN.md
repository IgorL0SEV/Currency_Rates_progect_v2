# План проекта VPd02 — Currency Rates

## Шаги

| # | Шаг | Статус |
|---|---|---|
| 1 | Прочитать документацию open.er-api.com, выписать 5 полей `latest` | ✅ |
| 2 | Реализовать `get_currency_rates(base) -> dict` с проверкой статуса и тела | ✅ |
| 3 | Кэш: `save_to_file`, `read_from_file`, TTL 24 ч, проверка `base_code` | ✅ |
| 4 | Мини-CLI: база → RUB/EUR/GBP; источник «кэш» или «API» | ✅ |
| 5 | Конвертер суммы с 4 знаками (опционально) | ✅ |
| 6 | Валидация кодов валют по `rates.keys()` (опционально) | ✅ |
| 7 | Тесты без сети (`unittest.mock`) | ✅ |
| 8 | Проверка в чистом venv и на повторном запуске | ✅ |
| 9 | Опубликовать репозиторий и приложить ссылку | ✅ [Currency_Rates_progect](https://github.com/IgorL0SEV/Currency_Rates_progect) |
| 10 | Расширить меню: список валют, статус кэша, принудительное обновление | ✅ |
| 11 | Версия 2: модульное разделение `api_client` / `storage` / `cli` | ✅ [Currency_Rates_progect_v2](https://github.com/IgorL0SEV/Currency_Rates_progect_v2) |

## Предусловия

- Python 3.10+ (используются `dict[str, float]` и `tuple[dict, str]` в аннотациях;
  с `from __future__ import annotations` работает и на 3.9).
- Доступ в интернет к `open.er-api.com`.
- Ключ API не нужен.

## Runbook: продолжение на другой машине

```powershell
cd D:\python-projects
git clone https://github.com/IgorL0SEV/Currency_Rates_progect_v2.git
cd Currency_Rates_progect_v2
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python currency.py
```

Проверка без сети:

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Риски и заметки

- **`conversion_rates` в задании устарел.** Живой open-эндпоинт отдаёт `rates`.
  Код читает оба ключа, поэтому работает и со старыми ответами.
- **Неизвестный код валюты приходит с HTTP 200.** Проверка только `status_code`
  пропустит ошибку — нужна проверка `result`/`error-type`.
- **Кэш один на все базовые валюты.** При смене базы файл перезаписывается;
  проверка `base_code` не даёт отдать чужие курсы.
- **`json.dump` не принимает `encoding`.** Кодировка задаётся у `open()`.
- **Курсы обновляются раз в сутки** — расхождение с «живым» курсом банка нормально.
