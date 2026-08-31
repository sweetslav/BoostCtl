# Manual Smoke Test

Do not run an apply command until its V2 preview has been reviewed. Use exactly one SKU for each smoke test.

## Sales Create V2

1. Run `python -m yandex_boost test --dry-run`.
2. Confirm the preview is `CREATE`, the exact `offer_id`, fee, campaign name, and any `UI_OBSERVED` duplicate warning.
3. Inspect `local_data/boostctl.db` before authorizing `python -m yandex_boost test`.
4. Confirm the CSV compatibility row in `reports/api_report.csv` and the best-effort UI verification recorded in the journal.

## Shows Create V2

1. Run `python -m yandex_boost.shows_create --limit 1 --dry-run`.
2. Confirm `CREATE`, exact `offer_id`, campaign name, and the unchanged `daily_limit` (default 300).
3. Inspect `local_data/boostctl.db` before authorizing `python -m yandex_boost.shows_create --limit 1`.
4. Confirm the journal entry and compatibility row in `reports/shows_create_report.csv`. This CSV is local history, not factual Yandex inventory.

For both flows, `UNKNOWN_RESULT`, `APPLYING`, and `VERIFY_REQUIRED` block a repeat create. Do not retry an ambiguous operation automatically. HTTP success is recorded separately from verification; Shows has no factual/UI verification source in this release.

Fee update and delete remain legacy workflows and require separate explicit approval.
