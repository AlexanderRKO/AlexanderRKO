"""Tests for month_builder — folder name parsing and validation."""
from __future__ import annotations

from pathlib import Path

import pytest

from ingest.month_builder import _yyyymm_to_labels, _validate, _deep_merge


def test_yyyymm_to_labels_apr26():
    assert _yyyymm_to_labels("2026-04") == ("Apr-26", "April 2026", "Apr")


def test_yyyymm_to_labels_dec25():
    assert _yyyymm_to_labels("2025-12") == ("Dec-25", "December 2025", "Dec")


def test_yyyymm_to_labels_rejects_garbage():
    assert _yyyymm_to_labels("not-a-month") is None
    assert _yyyymm_to_labels("2026-13") is None
    assert _yyyymm_to_labels("26-04") is None


def test_validate_passes_for_well_formed_month():
    month = {
        "month": "Apr-26", "label": "April 2026", "short": "Apr",
        "zaiNet": 30.0, "totalProperties": 100, "totalLeases": 90,
        "revenue": {
            "baseSub":     {"billed": 10, "completed": 10, "debtors": 0},
            "managedPlus": {"billed": 5,  "completed": 5,  "debtors": 0},
            "transaction": {"billed": 8,  "completed": 8,  "debtors": 0},
            "tradie":      {"billed": 7,  "completed": 7,  "debtors": 0},
        },
        "zaiLines": {
            "payinBpay": 10.0, "payinRealtime": 5.0,
            "payoutBpay": 0, "payoutDirect": 0, "payoutEntry": 0, "payoutRealtime": 5.0,
            "cardVisa": 5.0, "cardMaster": 0, "cardDebit": 0, "cardAmex": 0,
            "vaActive": 5.0, "vaSetup": 0,
            "chargebacks": 0, "disputes": 0, "manualMatch": 0,
        },
    }
    assert _validate(month) == []


def test_validate_flags_zai_sum_mismatch():
    month = {
        "month": "Apr-26", "label": "April 2026", "short": "Apr",
        "zaiNet": 100.0, "totalProperties": 1, "totalLeases": 1,
        "revenue": {k: {"billed": 0, "completed": 0, "debtors": 0}
                    for k in ("baseSub", "managedPlus", "transaction", "tradie")},
        "zaiLines": {"payinBpay": 50.0},  # gap of $50
    }
    errors = _validate(month)
    assert any("zaiNet" in e and "zaiLines" in e for e in errors)


def test_deep_merge_overlay_wins():
    base = {"a": 1, "nested": {"x": 1, "y": 2}}
    overlay = {"a": 99, "nested": {"y": 22, "z": 3}}
    assert _deep_merge(base, overlay) == {"a": 99, "nested": {"x": 1, "y": 22, "z": 3}}
