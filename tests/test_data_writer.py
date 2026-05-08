"""Tests for the data writer — upsert idempotency and sort order."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ingest.data_writer import _short_id_to_sort_key, load_data, save_data, upsert_month


def test_sort_key_orders_chronologically():
    keys = ["Apr-26", "Jul-25", "Dec-25", "Jan-26", "Aug-25"]
    assert sorted(keys, key=_short_id_to_sort_key) == ["Jul-25", "Aug-25", "Dec-25", "Jan-26", "Apr-26"]


def test_upsert_replaces_existing_month():
    data = {"months": [], "mwOffices": {}}
    m1 = {"month": "Apr-26", "label": "April 2026", "short": "Apr", "zaiNet": 100.0}
    m1_v2 = {"month": "Apr-26", "label": "April 2026", "short": "Apr", "zaiNet": 200.0}

    upsert_month(data, m1, {})
    upsert_month(data, m1_v2, {})

    assert len(data["months"]) == 1
    assert data["months"][0]["zaiNet"] == 200.0


def test_upsert_keeps_months_sorted():
    data = {"months": [], "mwOffices": {}}
    upsert_month(data, {"month": "Apr-26", "label": "April 2026", "short": "Apr"}, {})
    upsert_month(data, {"month": "Jan-26", "label": "January 2026", "short": "Jan"}, {})
    upsert_month(data, {"month": "Mar-26", "label": "March 2026", "short": "Mar"}, {})
    assert [m["month"] for m in data["months"]] == ["Jan-26", "Mar-26", "Apr-26"]


def test_save_load_roundtrip(tmp_path: Path):
    data = {"months": [{"month": "Apr-26", "label": "April 2026", "short": "Apr"}], "mwOffices": {}}
    path = tmp_path / "data.json"
    save_data(data, path)
    reloaded = load_data(path)
    assert reloaded["months"][0]["month"] == "Apr-26"
