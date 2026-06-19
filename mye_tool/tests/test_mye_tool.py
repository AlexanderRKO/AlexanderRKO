"""Tests for mye_tool using a synthetic fixture that mirrors the byte
layout of a real Xero "Accountants Enterprise (MAS)" .MYE export
(no real client data is stored in the repository)."""

import io
import os
import zipfile
from decimal import Decimal

import pytest

import mye_tool
from mye_tool import exporters
from mye_tool.core import MyeFile

EXTRACT_INF = (
    b"[Info]\r\n"
    b"ExtractVersion=1.0\r\n"
    b"ExtractCount=1\r\n"
    b"\r\n"
    b"[Extract001]\r\n"
    b"ExtractFile=MYOBAO.TXT\r\n"
    b"EntityType=MYOBAccounting\r\n"
    b"DataFileName=Test Company Pty Ltd\r\n"
    b"FinancialYearEnd=20250630\r\n"
    b"RangeStart=20240701\r\n"
    b"RangeEnd=20250630\r\n"
)

# Faithful to the real layout: CRLF everywhere, account rows have four
# tab-separated fields, journal rows end \r\r\n, blank line after each
# journal entry (including the last).
MYOBAO = (
    b"[MYOB2000.05]\r\n"
    b"Test Company Pty Ltd\tPO Box 1  Testville\t\t\t01/07/2024\t30/06/2025\r\n"
    b"[ACCOUNTS]\r\n"
    b"200\t\tSales\t\r\n"
    b"406\t\tBank Fees\t\r\n"
    b"680\t\tBank Account\t\r\n"
    b"820\t\tGST\t\r\n"
    b"[JOURNAL]\r\n"
    b"01/07/2024\t1001\t680\t-110.0000\tWidget sale\r\r\n"
    b"01/07/2024\t1001\t200\t100.0000\tWidget sale\r\r\n"
    b"01/07/2024\t1001\t820\t10.0000\tWidget sale\r\r\n"
    b"\r\n"
    b"02/07/2024\t1002\t680\t-10.0000\tBANK FEE\r\r\n"
    b"02/07/2024\t1002\t406\t10.0000\tBANK FEE\r\r\n"
    b"\r\n"
)


@pytest.fixture
def sample_mye(tmp_path):
    path = tmp_path / "sample.mye"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("Extract.inf", EXTRACT_INF)
        z.writestr("MYOBAO.TXT", MYOBAO)
    return str(path)


# A second variant mirroring a MYOB Premier / BASLink export: journal
# lines end with a single "\r\n", there is NO trailing blank line after
# the last entry, the company line carries an ABN in field 3, member
# names are uppercase, and a BASLINK.TXT side file is present.
MYOBAO_PREMIER = (
    b"[MYOB2000.05]\r\n"
    b"Premier Co Pty Ltd\t1 Test St\t12345678901\t\t01/06/2026\t30/06/2026\r\n"
    b"[ACCOUNTS]\r\n"
    b"11100\t\tCash On Hand\t\r\n"
    b"21430\t\tWages Payable\t\r\n"
    b"63971\t\tWages\t\r\n"
    b"[JOURNAL]\r\n"
    b"01/06/2026\t555\t21430\t-372.79\tWages\r\n"
    b"01/06/2026\t555\t63971\t372.79\tWages\r\n"
    b"\r\n"
    b"02/06/2026\t556\t11100\t-80.00\tPurchase\r\n"
    b"02/06/2026\t556\t63971\t80.00\tPurchase\r\n"
)  # note: ends right after the last line, no trailing blank

BASLINK = b"H0\tMYOB BASLink V5.0.0\tPREMIER\r\nD0\tGST\tGoods & Services Tax\r\n"


@pytest.fixture
def premier_mye(tmp_path):
    path = tmp_path / "premier.MYE"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("MYOBAO.TXT", MYOBAO_PREMIER)
        z.writestr("BASLINK.TXT", BASLINK)
        z.writestr("EXTRACT.INF", EXTRACT_INF)
    return str(path)


def test_premier_variant_parse(premier_mye):
    mye = mye_tool.load(premier_mye)
    assert mye.company_name == "Premier Co Pty Ltd"
    assert mye.company_fields[2] == "12345678901"  # ABN preserved
    assert mye.journal_line_terminator == "\r\n"
    assert mye.trailing_blank is False
    assert "BASLINK.TXT" in mye.extra_members
    assert len(mye.entries) == 2
    # 2-decimal amounts keep their precision
    assert mye.entries[0].lines[0].amount_text == "-372.79"
    assert mye.validate() == []


def test_premier_roundtrip_byte_exact(premier_mye):
    mye = mye_tool.load(premier_mye)
    assert mye.data_text_bytes() == MYOBAO_PREMIER


def test_premier_save_preserves_baslink(premier_mye, tmp_path):
    mye = mye_tool.load(premier_mye)
    out = str(tmp_path / "resaved.MYE")
    mye.save(out)
    z = zipfile.ZipFile(out)
    assert z.read("BASLINK.TXT") == BASLINK
    assert z.read("MYOBAO.TXT") == MYOBAO_PREMIER
    assert z.read("EXTRACT.INF") == EXTRACT_INF


def test_premier_unpack_pack_lossless(premier_mye, tmp_path):
    mye = mye_tool.load(premier_mye)
    work = str(tmp_path / "work")
    exporters.unpack(mye, work)
    assert os.path.exists(os.path.join(work, "BASLINK.TXT"))
    rebuilt = exporters.pack_dir(work)
    assert rebuilt.data_text_bytes() == MYOBAO_PREMIER
    assert rebuilt.extra_members["BASLINK.TXT"] == BASLINK
    assert rebuilt.company_fields[2] == "12345678901"


def test_parse(sample_mye):
    mye = mye_tool.load(sample_mye)
    assert mye.company_name == "Test Company Pty Ltd"
    assert mye.period_start == "01/07/2024"
    assert mye.period_end == "30/06/2025"
    assert [a.code for a in mye.accounts] == ["200", "406", "680", "820"]
    assert mye.account_map()["406"] == "Bank Fees"
    assert len(mye.entries) == 2
    assert [len(e.lines) for e in mye.entries] == [3, 2]
    line = mye.entries[0].lines[1]
    assert (line.account_code, line.amount) == ("200", Decimal("100"))
    assert line.debit == Decimal("100") and line.credit == 0
    assert mye.extract_info()["DataFileName"] == "Test Company Pty Ltd"


def test_roundtrip_bytes(sample_mye):
    mye = mye_tool.load(sample_mye)
    assert mye.data_text_bytes() == MYOBAO


def test_save_and_reload(sample_mye, tmp_path):
    mye = mye_tool.load(sample_mye)
    out = str(tmp_path / "resaved.mye")
    mye.save(out)
    again = mye_tool.load(out)
    assert again.data_text_bytes() == MYOBAO
    assert again.extract_inf == EXTRACT_INF


def test_validate_clean(sample_mye):
    assert mye_tool.load(sample_mye).validate() == []


def test_validate_catches_problems(sample_mye):
    mye = mye_tool.load(sample_mye)
    mye.entries[0].lines[0].amount += Decimal("1")  # unbalance
    mye.entries[1].lines[0].account_code = "999"  # unknown account
    mye.entries[1].lines[1].date = "01/01/2030"  # outside period
    problems = "\n".join(mye.validate())
    assert "does not balance" in problems
    assert "not in the chart" in problems
    assert "outside the export period" in problems


def test_trial_balance(sample_mye):
    mye = mye_tool.load(sample_mye)
    tb = {code: net for code, _, _, _, net in mye.trial_balance()}
    assert tb["680"] == Decimal("-120")
    assert tb["200"] == Decimal("100")
    assert tb["406"] == Decimal("10")
    assert tb["820"] == Decimal("10")
    assert sum(tb.values()) == 0


def test_unpack_edit_pack(sample_mye, tmp_path):
    mye = mye_tool.load(sample_mye)
    work = str(tmp_path / "work")
    exporters.unpack(mye, work)

    # untouched round trip is byte exact
    rebuilt = exporters.pack_dir(work)
    assert rebuilt.data_text_bytes() == MYOBAO
    assert rebuilt.extract_inf == EXTRACT_INF

    # edit a memo via the CSV and repack
    journal = os.path.join(work, "journal.csv")
    with open(journal, encoding="utf-8-sig") as fh:
        text = fh.read()
    with open(journal, "w", encoding="utf-8-sig") as fh:
        fh.write(text.replace("BANK FEE", "Account keeping fee"))
    edited = exporters.pack_dir(work)
    assert edited.validate() == []
    memos = {l.memo for l in edited.journal_lines}
    assert "Account keeping fee" in memos and "BANK FEE" not in memos


def test_exports(sample_mye, tmp_path):
    mye = mye_tool.load(sample_mye)
    out = str(tmp_path / "out")
    paths = exporters.export_csv(mye, out)
    assert all(os.path.getsize(p) > 0 for p in paths)

    json_path = exporters.export_json(mye, str(tmp_path / "out.json"))
    import json

    doc = json.load(open(json_path, encoding="utf-8"))
    assert doc["company"]["name"] == "Test Company Pty Ltd"
    assert len(doc["journal"]) == 2

    iif_path = exporters.export_iif(mye, str(tmp_path / "out.iif"))
    iif = open(iif_path, encoding="utf-8").read()
    assert "GENERAL JOURNAL" in iif and iif.count("ENDTRNS") >= 2

    openpyxl = pytest.importorskip("openpyxl")
    xlsx_path = exporters.export_xlsx(mye, str(tmp_path / "out.xlsx"))
    wb = openpyxl.load_workbook(xlsx_path)
    assert set(wb.sheetnames) == {"Company", "Accounts", "Journal", "Trial Balance"}
    assert wb["Journal"].max_row == 1 + 5  # header + 5 lines


def test_cli_smoke(sample_mye, tmp_path, capsys):
    from mye_tool.cli import main

    assert main(["info", sample_mye]) == 0
    assert "Test Company Pty Ltd" in capsys.readouterr().out
    assert main(["check", sample_mye]) == 0
    assert main(["accounts", sample_mye]) == 0
    assert main(["trial-balance", sample_mye]) == 0
    out_dir = str(tmp_path / "exp")
    assert main(["export", sample_mye, "-o", out_dir, "--format", "csv"]) == 0
    work = str(tmp_path / "w")
    assert main(["unpack", sample_mye, "-o", work]) == 0
    packed = str(tmp_path / "packed.mye")
    assert main(["pack", work, "-o", packed]) == 0
    assert mye_tool.load(packed).data_text_bytes() == MYOBAO


def test_not_a_zip(tmp_path):
    bad = tmp_path / "bad.mye"
    bad.write_bytes(b"StuffIt (c)1997")
    with pytest.raises(ValueError):
        mye_tool.load(str(bad))


def test_xero_coa_header_and_taxcode(sample_mye, tmp_path):
    from mye_tool import xero_coa

    mye = mye_tool.load(sample_mye)
    out = str(tmp_path / "coa.csv")
    xero_coa.export_xero_coa(mye, out)
    import csv

    rows = list(csv.reader(open(out, encoding="utf-8-sig")))
    assert rows[0] == [
        "*Code", "*Name", "*Type", "*Tax Code",
        "Description", "Dashboard", "Expense Claims", "Enable Payments",
    ]
    body = rows[1:]
    # GST is a Xero-managed system account and is excluded from the import
    from mye_tool.xero_coa import is_system_account

    expected = [a for a in mye.accounts if not is_system_account(a)]
    assert len(body) == len(expected)
    assert "GST" not in {r[1] for r in body}  # system account excluded
    # every account gets the BAS Excluded default tax code
    assert all(r[3] == "BAS Excluded" for r in body)
    # every type is one of Xero's valid import codes
    valid = {
        "CURRENT", "FIXED", "INVENTORY", "NONCURRENT", "PREPAYMENT", "CURRLIAB",
        "TERMLIAB", "EQUITY", "REVENUE", "SALES", "OTHERINCOME", "DIRECTCOSTS",
        "EXPENSE", "OVERHEADS", "DEPRECIATN", "OTHEREXPENSE",
    }
    assert all(r[2] in valid for r in body)


def test_xero_coa_type_inference():
    from mye_tool.core import Account
    from mye_tool.xero_coa import infer_xero_type

    def t(code, name):
        return infer_xero_type(Account(code=code, name=name))[0]

    assert t("200", "Sales") == "REVENUE"
    assert t("210", "Service Income") == "REVENUE"
    assert t("680", "Westpac Bank Account - Trading") == "CURRENT"
    assert t("406", "Bank Fees") == "EXPENSE"  # not CURRENT despite "bank"
    assert t("820", "GST") == "CURRLIAB"
    assert t("610", "Accounts Receivable") == "CURRENT"
    assert t("416", "Depreciation") == "DEPRECIATN"
    assert t("505", "Income Tax Expense") == "EXPENSE"  # not REVENUE
    assert t("477", "Wages & Salaries") == "EXPENSE"
    assert t("270", "Interest Income") == "OTHERINCOME"
    # 5-digit MYOB-native fallback (name gives no signal)
    assert t("11100", "Zxqv Holding") == "CURRENT"
    assert t("21999", "Zxqv Suspense") == "CURRLIAB"


def test_cli_export_xero_coa(sample_mye, tmp_path):
    from mye_tool.cli import main

    out_dir = str(tmp_path / "x")
    assert main(["export", sample_mye, "-o", out_dir, "--format", "xero-coa"]) == 0
    assert os.path.exists(os.path.join(out_dir, "xero_chart_of_accounts.csv"))
    assert os.path.exists(os.path.join(out_dir, "xero_chart_of_accounts_REVIEW.csv"))


def test_xero_coa_excludes_system_accounts(tmp_path):
    from mye_tool.core import MyeFile, Account
    from mye_tool import xero_coa
    import csv

    mye = MyeFile()
    mye.accounts = [
        Account("200", "Sales"),
        Account("610", "Accounts Receivable"),  # Xero system account
        Account("820", "GST"),                   # Xero system account
        Account("960", "Retained Earnings"),     # Xero system account
        Account("400", "Accounting Fees"),
    ]
    coa = str(tmp_path / "coa.csv")
    rev = str(tmp_path / "rev.csv")
    xero_coa.export_xero_coa(mye, coa)
    xero_coa.export_xero_coa_review(mye, rev)

    imported = [r[1] for r in csv.reader(open(coa, encoding="utf-8-sig"))][1:]
    assert imported == ["Sales", "Accounting Fees"]  # system ones dropped

    review = list(csv.reader(open(rev, encoding="utf-8-sig")))[1:]
    excluded = [r[1] for r in review if r[4].startswith("SYSTEM")]
    assert set(excluded) == {"Accounts Receivable", "GST", "Retained Earnings"}

    # opt-in to keep them
    coa2 = str(tmp_path / "coa2.csv")
    xero_coa.export_xero_coa(mye, coa2, exclude_system=False)
    assert len([r for r in csv.reader(open(coa2, encoding="utf-8-sig"))][1:]) == 5


def test_xero_coa_renumber_3digit(tmp_path):
    import re
    from mye_tool.core import MyeFile, Account
    from mye_tool import xero_coa

    mye = MyeFile()
    mye.accounts = [
        Account("200", "Sales"),                 # valid 3-digit -> kept
        Account("11100", "Cash On Hand"),         # 5-digit -> CURRENT range
        Account("63971", "Wages"),                # 5-digit -> EXPENSE range
        Account("9901", "Dividends Paid - X"),    # 4-digit -> EQUITY range
        Account("820", "GST"),                    # system -> excluded, no code
    ]
    codes = xero_coa.assign_3digit_codes(mye)
    assert codes[0] == "200"  # existing valid 3-digit kept
    assert codes[4] is None   # system account excluded
    kept = [c for c in codes if c]
    assert all(re.fullmatch(r"\d{3}", c) for c in kept)
    assert len(kept) == len(set(kept))  # unique
    # ranges: CURRENT 600-679, EXPENSE 400-579, EQUITY 920-999
    assert 600 <= int(codes[1]) <= 679
    assert 400 <= int(codes[2]) <= 579
    assert 920 <= int(codes[3]) <= 999


def test_xero_coa_renumber_files_and_mapping(tmp_path):
    from mye_tool.core import MyeFile, Account
    from mye_tool import xero_coa
    import csv

    mye = MyeFile()
    mye.accounts = [Account("11100", "Cash On Hand"), Account("820", "GST")]
    coa = str(tmp_path / "coa.csv")
    mapping = str(tmp_path / "map.csv")
    xero_coa.export_xero_coa(mye, coa, renumber=True)
    xero_coa.export_code_mapping(mye, mapping)

    rows = list(csv.reader(open(coa, encoding="utf-8-sig")))[1:]
    assert len(rows) == 1  # GST excluded
    assert 600 <= int(rows[0][0]) <= 679  # Cash renumbered into CURRENT range

    m = {r[0]: r for r in csv.reader(open(mapping, encoding="utf-8-sig"))}
    assert m["11100"][4] == "renumbered"
    assert m["820"][1] == "" and "system" in m["820"][4]
