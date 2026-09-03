# Codex State

## Current Baseline

- 99 tests passed.
- V2 smoke complete: Sales create, fee update, delete, and Shows create verified.
- Shows uses `LOCAL_HISTORY`; it is not factual Yandex inventory.
- Operator UX is connected in `product_cli.py` through `operator_workflows` and existing V2 services.
- Preview has an explicit `Выполнить / Отмена` gate; typed confirmation is requested only after `Выполнить`.
- History is rendered from SQLite operation rows without rewriting legacy journal records.
- Shows create duplicate protection uses current read-only UI inventory; `LOCAL_HISTORY` is retained only for legacy reports/diagnostics.

## Non-Negotiable Rules

- No direct low-level mutations from user-facing CLI.
- Preview equals zero mutation.
- Persist journal intent before mutation.
- No blind mutation retry.
- Never auto-retry `UNKNOWN_RESULT`.
- `UI_OBSERVED` is not `FACTUAL`.
- `LOCAL_HISTORY` is not factual inventory.

## Current Next Task

- Run the read-only Shows inventory against the current cabinet before any future Shows create batch; expected baseline is about 34 campaigns and `ACTIVE = 0`.
- Keep legacy JSON/CSV workflows for compatibility, but do not require them for normal operator use.
