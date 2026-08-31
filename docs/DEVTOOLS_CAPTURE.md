# DevTools Capture

Цель capture - подтвердить фактический read-only inventory, а не изменить кампании.
Не выполняйте POST, PUT, PATCH или DELETE для этой задачи.

## Sales Boost

1. Откройте список кампаний Sales Boost.
2. В DevTools откройте Network и включите Fetch/XHR.
3. Обновите страницу и найдите запрос со списком кампаний.
4. Сохраните безопасные Request URL, method, query params, request payload и response JSON.
5. Повторите capture для одной активной кампании, одной неактивной/остановленной и,
   если UI позволяет, одной архивной.

## Shows Boost

Повторите те же действия для списка Shows Boost, активной кампании,
неактивной/остановленной и архивной/завершённой, если такие представления доступны.

Особенно нужны поля `campaignId`, name, SKU/offer IDs, status/raw status, bid,
daily limit и created/updated timestamps.

## NEEDS_CAPTURE

Нужны request/response для stop, resume и archive. Не выполняйте эти действия
специально для capture. Если такое действие позже выполняется вручную в UI,
снимите его Network request/response и предварительно удалите секреты.
