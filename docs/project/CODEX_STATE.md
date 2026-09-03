# Codex State

## Current Baseline

- 95 tests passed.
- V2 smoke complete: Sales create, fee update, delete, and Shows create verified.
- Shows uses `LOCAL_HISTORY`; it is not factual Yandex inventory.
- Operator UX is connected in `product_cli.py` through `operator_workflows` and existing V2 services.
- Preview has an explicit `Выполнить / Отмена` gate; typed confirmation is requested only after `Выполнить`.
- History is rendered from SQLite operation rows without rewriting legacy journal records.

## Non-Negotiable Rules

- No direct low-level mutations from user-facing CLI.
- Preview equals zero mutation.
- Persist journal intent before mutation.
- No blind mutation retry.
- Never auto-retry `UNKNOWN_RESULT`.
- `UI_OBSERVED` is not `FACTUAL`.
- `LOCAL_HISTORY` is not factual inventory.

## Current Next Task

- No pending operator UX implementation task.
- Keep legacy JSON/CSV workflows for compatibility, but do not require them for normal operator use.
