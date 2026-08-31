# Yandex factual capture fixtures

Эта папка предназначена только для обезличенных JSON captures, полученных вручную
из DevTools Network. Допустимые имена: `sales_inventory.json` и
`shows_inventory.json`.

Сохраняйте URL/path без секретных query parameters, HTTP method, безопасный request
body и response JSON. Разрешено сохранять campaign/business IDs, SKU, статус,
ставки, бюджеты и timestamps.

Никогда не сохраняйте Cookie, Authorization, `sk`, session/CSRF tokens, персональные
данные или browser profile. Перед добавлением в Git пропустите capture через
`sanitize_capture()`. Если секрет остался в capture, файл нельзя коммитить.
