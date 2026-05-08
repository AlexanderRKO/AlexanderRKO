"""Smoke tests for CSV parsers and manual loader."""
from __future__ import annotations

from pathlib import Path

import pytest

from ingest.parsers.platform_revenue import parse_platform_revenue
from ingest.parsers.agency_performance import parse_agency_performance
from ingest.parsers.mw_charges import parse_mw_charges
from ingest.parsers.manual import load_manual


def test_platform_revenue_basic(tmp_path: Path):
    csv = tmp_path / "platform-revenue.csv"
    csv.write_text(
        "Line Item,Billed,Completed,Debtors\n"
        "Base Subscription Revenue,41511.45,38781.45,2730.00\n"
        "Managed+ Revenue,15782.60,15242.60,540.00\n"
        "Transaction Cost Revenue,68559.31,64978.31,3581.00\n"
        "Tradie Job Revenue,26494.26,26477.96,16.30\n"
        "SMS Revenue,2250.00,2250.00,0\n"
        "Implementation Fees,6609.09,6609.09,0\n"
    )
    out = parse_platform_revenue(csv)
    assert out["revenue"]["baseSub"]["billed"] == pytest.approx(41511.45)
    assert out["revenue"]["managedPlus"]["billed"] == pytest.approx(15782.60)
    assert out["revenue"]["transaction"]["billed"] == pytest.approx(68559.31)
    assert out["revenue"]["tradie"]["billed"] == pytest.approx(26494.26)
    assert out["smsRevenue"] == pytest.approx(2250.00)
    assert out["implFees"] == pytest.approx(6609.09)


def test_agency_performance_aggregates(tmp_path: Path):
    csv = tmp_path / "agency-performance.csv"
    csv.write_text(
        "Agency,Properties,Active Leases\n"
        "Armadale,978,950\n"
        "Hawthorn,789,770\n"
        "Empty Office,5,0\n"
    )
    out = parse_agency_performance(csv)
    assert out["agencies"] == 3
    assert out["activeAgencies"] == 2
    assert out["inactiveAgencies"] == 1
    assert out["totalProperties"] == 1772
    assert out["totalLeases"] == 1720


def test_mw_charges_parses_offices(tmp_path: Path):
    csv = tmp_path / "mw-charges.csv"
    csv.write_text(
        "Office,Invoice No,Properties,Amount ex GST\n"
        "Armadale,INV-1234,978,2090.81\n"
        "Hawthorn,INV-5678,789,1621.64\n"
    )
    out = parse_mw_charges(csv)
    assert len(out["offices"]) == 2
    assert out["offices"][0]["office"] == "Armadale"
    assert out["offices"][0]["jobFeesExGst"] == pytest.approx(2090.81)
    assert out["invoicedTotal"] == pytest.approx(3712.45)


def test_mw_charges_falls_back_to_inc_gst(tmp_path: Path):
    csv = tmp_path / "mw-charges-inc.csv"
    csv.write_text(
        "Office,Properties,Amount inc GST\n"
        "Armadale,978,2299.89\n"  # 2090.81 * 1.1
    )
    out = parse_mw_charges(csv)
    assert out["offices"][0]["jobFeesExGst"] == pytest.approx(2090.81, abs=0.01)


def test_manual_yml_loads(tmp_path: Path):
    (tmp_path / "manual.yml").write_text(
        "mwRebate: 11077.95\n"
        "agencyRevShare: 2270.03\n"
        "_mw:\n"
        "  mwInvoiceNo: '#796'\n"
        "  mwPaid: 11077.95\n"
    )
    data = load_manual(tmp_path)
    assert data["mwRebate"] == 11077.95
    assert data["_mw"]["mwInvoiceNo"] == "#796"


def test_manual_returns_empty_when_missing(tmp_path: Path):
    assert load_manual(tmp_path) == {}
