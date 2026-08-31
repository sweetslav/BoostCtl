# HAR Inspector

`yandex_boost.har_inspect` analyses a manually exported Chrome DevTools HAR locally and
writes a sanitized diagnostic report for potential Yandex Market Sales Boost inventory
sources. It does not start a browser or make network requests.

Run it from the repository root:

```cmd
.venv\Scripts\python.exe -m yandex_boost.har_inspect local_data\har\sales_boost_inventory.har local_data\reports\sales_boost_inventory_report.json
```

The output is a UTF-8 JSON object with `summary` and `entries`. Candidate entries retain
the request method, a sanitized URL and query parameters, parsed JSON request/response
bodies when available, response metadata, and evidence-based inventory scores.

Cookie, Set-Cookie, Authorization, `sk`, CSRF, session, and token-like keys use the shared
capture sanitizer and are redacted. Non-JSON response bodies are not copied into the
report; only their parse error and safe metadata are retained. Base64-encoded JSON response
bodies are decoded locally before parsing.

The command refuses to replace an existing report. Use `--force` only to overwrite that
report; sanitization and the post-sanitization secret scan remain mandatory:

```cmd
.venv\Scripts\python.exe -m yandex_boost.har_inspect local_data\har\sales_boost_inventory.har local_data\reports\sales_boost_inventory_report.json --force
```

`statisticsWidget` numeric collection keys are reported as unconfirmed numeric candidate
IDs. They are not treated as campaign IDs without separate campaign-field evidence.
