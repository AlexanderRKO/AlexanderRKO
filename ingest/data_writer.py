"""Read/update dashboard/src/data.json.

Months are kept sorted chronologically by their YYYY-MM short id.
If a month with the same id already exists, it's replaced (idempotent).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from .paths import DATA_JSON

log = logging.getLogger(__name__)


def _short_id_to_sort_key(short_id: str) -> tuple[int, int]:
    # "Apr-26" -> (2026, 4). Used to keep months ordered.
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    try:
        m, y = short_id.split("-")
        return (2000 + int(y), months.index(m) + 1)
    except (ValueError, IndexError):
        return (0, 0)


def load_data(path: Path = DATA_JSON) -> dict[str, Any]:
    if path.exists():
        with path.open() as f:
            return json.load(f)
    return {
        "client": {
            "account": "MAN2077",
            "name": "Managed Platforms",
            "advisor": "LMS Advisory",
            "abn": "65 302 567 149",
        },
        "months": [],
        "mwOffices": {},
    }


def save_data(data: dict[str, Any], path: Path = DATA_JSON) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    log.info("wrote %s (%d months)", path, len(data.get("months", [])))


def upsert_month(data: dict[str, Any], month: dict[str, Any], mw_office: dict[str, Any]) -> dict[str, Any]:
    short_id = month["month"]

    months = [m for m in data.get("months", []) if m.get("month") != short_id]
    months.append(month)
    months.sort(key=lambda m: _short_id_to_sort_key(m["month"]))
    data["months"] = months

    if mw_office:
        data.setdefault("mwOffices", {})[short_id] = mw_office
        # Re-sort mwOffices keys chronologically
        data["mwOffices"] = {
            k: data["mwOffices"][k]
            for k in sorted(data["mwOffices"].keys(), key=_short_id_to_sort_key)
        }

    data.setdefault("meta", {})["lastUpdated"] = datetime.now().isoformat(timespec="seconds")
    return data
