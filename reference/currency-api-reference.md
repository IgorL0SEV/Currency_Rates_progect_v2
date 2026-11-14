# Справочник: open.er-api.com и JSON-ответы

## Endpoint

```http
GET https://open.er-api.com/v6/latest/{base}
```

- `{base}` — трёхбуквенный код валюты (`USD`, `EUR`, `RUB`).
- Ключ API не нужен (open access).
- Курсы обновляются примерно раз в сутки.

## Ответ `latest` (успех)

```json
{
    "result": "success",
    "provider": "https://www.exchangerate-api.com",
    "documentation": "https://www.exchangerate-api.com/docs/free",
    "terms_of_use": "https://www.exchangerate-api.com/terms",
    "time_last_update_unix": 1794614551,
    "time_last_update_utc": "Sat, 14 Nov 2026 00:02:31 +0000",
    "time_next_update_unix": 1794702541,
    "time_next_update_utc": "Sun, 15 Nov 2026 00:29:01 +0000",
    "time_eol_unix": 0,
    "base_code": "USD",
    "rates": {
        "USD": 1,
        "RUB": 82.504954,
        "EUR": 0.905954,
        "GBP": 0.756419
    }
}
```

## Поля

| Поле | Тип | Смысл |
|---|---|---|
| `result` | строка | `success` / `error` |
| `provider` | строка | провайдер данных |
| `documentation` | строка | ссылка на документацию |
| `terms_of_use` | строка | условия использования |
| `time_last_update_unix` | число | время обновления, Unix timestamp |
| `time_last_update_utc` | строка | время обновления, UTC |
| `time_next_update_unix` | число | следующее обновление, Unix timestamp |
| `time_next_update_utc` | строка | следующее обновление, UTC |
| `time_eol_unix` | число | признак завершения поддержки (0 — нет) |
| `base_code` | строка | базовая валюта |
| `rates` | объект | «код валюты → курс к базе» |

## Ответ с ошибкой (HTTP 200)

```json
{
    "result": "error",
    "error-type": "unsupported-code"
}
```

Встречались коды ошибок: `unsupported-code` (неизвестный код валюты),
`malformed-request`, `invalid-key`, `inactive-account`, `quota-reached`.
Список может меняться — ориентируйтесь на поле `error-type` как есть.

## Дрейф документации

- В старых материалах курса курсы названы `conversion_rates`. Актуальный open-эндпоинт
  отдаёт `rates`; `conversion_rates` в ответе нет.
- В примерах курса встречается `json.dump(..., encoding="utf-8")` — такого параметра
  у `json.dump` нет; кодировка задаётся при `open(path, "w", encoding="utf-8")`.

## Соответствие форматов

| Формат | Использование в проекте |
|---|---|
| JSON | ответ API и файл кэша |
| `dict` | результат `response.json()` |
| `float` | курсы и результат конвертации |

## Происхождение курсов, регион и время

- В запросе нет параметра региона, города или банка — только базовая валюта.
- Ответ содержит `provider` (`https://www.exchangerate-api.com`) и один общий набор
  курсов. Разделения «курс для Лондона» / «курс для Пекина» в API нет.
- Время обновления — UTC; курсы обновляются примерно раз в сутки.
- Это ориентировочный рыночный курс провайдера, не курс покупки/продажи банка
  или обменника. Конкретный банк считает по своему курсу с наценкой.
- Открытая документация free-эндпоинта не называет конкретный банк или биржу —
  только провайдера. Не приписывайте курсу регион без отдельного источника.

## Команды проверки

```powershell
# ответ вручную
curl "https://open.er-api.com/v6/latest/USD"

# ключевые поля
python -c "import requests; d=requests.get('https://open.er-api.com/v6/latest/USD', timeout=10).json(); print(d['base_code'], d['time_last_update_utc'], d['rates']['RUB'])"

# ошибка: неизвестный код
curl "https://open.er-api.com/v6/latest/XXX"
```
