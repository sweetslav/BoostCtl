from __future__ import annotations

import json
from pathlib import Path


class OfferCache:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data: dict[str, str] = {}
        if self.path.exists():
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self.data = {str(k): str(v) for k, v in raw.items()}

    def get(self, sku: str) -> str | None:
        return self.data.get(sku)

    def set(self, sku: str, offer_id: str) -> None:
        self.data[sku] = offer_id
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
