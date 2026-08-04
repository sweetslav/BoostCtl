# Yandex Market Sales Boost Automation

Создаёт отдельную кампанию **«Буст продаж»** для каждого SKU в кабинете Яндекс Маркета.

Рабочая схема:

```text
видимый SKU
    ↓
resolveOffersForModels
    ↓
внутренний offerId (dcmp-...)
    ↓
resolvePutSalesCampaign
    ↓
отдельная кампания
```

## Возможности

- одна кампания на один SKU;
- название `SKU | ДД.ММ.ГГГГ`;
- текущая дата берётся из Windows автоматически;
- точное сопоставление `article == SKU`;
- кэш внутренних `offerId`;
- режим проверки без создания кампаний;
- повтор только ошибочных строк;
- CSV-отчёт и текстовые логи;
- повторные HTTP-попытки при временных ошибках;
- сохранение браузерной сессии локально.

## Быстрый запуск на Windows

1. Установите Python 3.11+.
2. Запустите:

```text
00_INSTALL.bat
```

3. Заполните `data/campaigns.json`.
4. Проверьте файл:

```text
01_VALIDATE.bat
```

5. Выполните безопасную проверку без создания:

```text
02_DRY_RUN.bat
```

6. Создайте одну тестовую кампанию:

```text
03_TEST_ONE.bat
```

7. Запустите весь список:

```text
04_RUN_ALL.bat
```

Ошибочные строки можно повторить через:

```text
05_RETRY_ERRORS.bat
```

## Формат входного файла

`data/campaigns.json`:

```json
[
  {
    "sku": "20210026/9#1",
    "bid": 18
  },
  {
    "sku": "21211538/9#1",
    "bid": 17
  }
]
```

## Командная строка

После `00_INSTALL.bat` доступна команда:

```bash
yandex-boost validate
yandex-boost run --dry-run
yandex-boost test
yandex-boost run
yandex-boost retry-errors
```

Дополнительные параметры:

```bash
yandex-boost run --date 05.08.2026
yandex-boost run --start 10 --limit 20
yandex-boost run --no-cache
yandex-boost run --verbose
```

## Конфигурация

`config.json`:

```json
{
  "business_id": 950637,
  "source_type": "BUSINESS",
  "cost_model": "CPA",
  "offer_service": "MARKET",
  "request_delay_seconds": 0.8,
  "max_retries": 3
}
```

## Результаты

- `reports/api_report.csv` — результат каждой строки;
- `logs/YYYY-MM-DD.log` — подробный журнал;
- `data/offer_cache.json` — кэш соответствий SKU → `dcmp-offerId`;
- `browser_profile/` — локальная сессия браузера.

Эти файлы исключены из Git через `.gitignore`.

## Безопасность

Никогда не публикуйте:

- `browser_profile/`;
- cookies и `Session_id`;
- заголовок `sk`;
- HAR-файлы;
- реальный `data/campaigns.json`, если SKU являются внутренними данными.

Скрипт не сохраняет cookie или `sk` в исходники: токен считывается из текущей авторизованной браузерной сессии.

## Важное ограничение

Используются внутренние HTTP-запросы веб-интерфейса Яндекс Маркета. Яндекс может изменить их без предварительного уведомления. Перед массовым запуском после изменений кабинета выполняйте `02_DRY_RUN.bat` и `03_TEST_ONE.bat`.

## Разработка

```bash
python -m pip install -e . -r requirements-dev.txt
ruff check .
pytest
```

## Лицензия

MIT.
