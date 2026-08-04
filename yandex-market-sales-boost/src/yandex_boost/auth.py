from __future__ import annotations

import time

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page

from .models import AppConfig


def safe_goto(page: Page, url: str, timeout: int = 60_000) -> None:
    try:
        page.goto(url, wait_until="commit", timeout=timeout)
    except PlaywrightError as exc:
        if "interrupted by another navigation" not in str(exc):
            raise
    page.wait_for_timeout(1500)


def capture_session_token(page: Page, config: AppConfig) -> str:
    captured: dict[str, str] = {}

    def on_request(request) -> None:
        try:
            token = request.headers.get("sk")
            if token and "partner.market.yandex.ru" in request.url:
                captured["sk"] = token
        except Exception:
            pass

    page.on("request", on_request)

    boost_url = (
        "https://partner.market.yandex.ru/business/"
        f"{config.business_id}/sales-boost?sourceType={config.source_type}"
    )
    edit_url = (
        "https://partner.market.yandex.ru/business/"
        f"{config.business_id}/sales-boost/draft/edit"
        f"?sourceType={config.source_type}&costModel={config.cost_model}"
    )

    safe_goto(page, boost_url)

    current_url = page.url.lower()
    need_login = (
        "passport.yandex" in current_url
        or "sso.passport.yandex" in current_url
        or page.get_by_role("button", name="Войти").count() > 0
    )
    if need_login:
        print("\nВойдите в Яндекс вручную в открытом браузере.")
        print("После входа дождитесь страницы «Буст продаж».")
        input("Когда список кампаний загрузится, нажмите Enter здесь... ")

    safe_goto(page, boost_url)

    deadline = time.time() + 60
    while time.time() < deadline:
        url = page.url.lower()
        if (
            "partner.market.yandex.ru/business/" in url
            and "passport.yandex" not in url
            and "sso.passport.yandex" not in url
        ):
            break
        page.wait_for_timeout(1000)
    else:
        raise RuntimeError("Авторизация не завершилась.")

    page.wait_for_timeout(3000)
    if "sk" in captured:
        return captured["sk"]

    safe_goto(page, edit_url)
    page.wait_for_timeout(3000)
    if "sk" in captured:
        return captured["sk"]

    try:
        page.reload(wait_until="commit", timeout=60_000)
    except PlaywrightError as exc:
        if "interrupted by another navigation" not in str(exc):
            raise
    page.wait_for_timeout(3000)

    if "sk" not in captured:
        raise RuntimeError(
            "Не удалось получить токен sk из активной браузерной сессии."
        )
    return captured["sk"]
