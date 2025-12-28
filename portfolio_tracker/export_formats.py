"""
Export Formats - Additional export options for portfolio data.

Supports:
- Excel (.xlsx) with multiple worksheets
- PDF report with professional formatting
- Tax package for accountants
"""

import csv
import logging
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import Portfolio, Holding
from .sector_lookup import get_sector_summary
from .tax_reporting import (
    generate_tax_report, analyze_unrealised_gains,
    get_financial_year, calculate_franking_credit
)

logger = logging.getLogger(__name__)

# Check for optional dependencies
try:
    import openpyxl
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.chart import PieChart, BarChart, Reference
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm, cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, Image
    )
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False


# ============================================================================
# EXCEL EXPORT
# ============================================================================

def export_to_excel(
    portfolio: Portfolio,
    output_path: Path,
    include_charts: bool = True,
) -> Optional[Path]:
    """
    Export portfolio to Excel with multiple worksheets.

    Worksheets:
    - Summary: Portfolio overview and key metrics
    - Holdings: Detailed holdings table
    - Sectors: Sector allocation breakdown
    - Performance: Best/worst performers
    - Tax: Unrealised gains/losses for tax planning

    Args:
        portfolio: Portfolio to export
        output_path: Output file path
        include_charts: Include charts in worksheets

    Returns:
        Path to created file, or None if failed
    """
    if not EXCEL_AVAILABLE:
        raise ImportError("openpyxl required for Excel export. Install with: pip install openpyxl")

    wb = openpyxl.Workbook()

    # Styles
    header_font = Font(bold=True, size=12)
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_font_white = Font(bold=True, size=12, color="FFFFFF")
    money_format = '$#,##0.00'
    percent_format = '0.00%'
    number_format = '#,##0'

    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    # -------------------------------------------------------------------------
    # SUMMARY WORKSHEET
    # -------------------------------------------------------------------------
    ws_summary = wb.active
    ws_summary.title = "Summary"

    # Title
    ws_summary['A1'] = "Portfolio Summary"
    ws_summary['A1'].font = Font(bold=True, size=18)
    ws_summary.merge_cells('A1:D1')

    # Portfolio name if set
    if portfolio.name:
        ws_summary['A2'] = f"Name: {portfolio.name}"
        ws_summary['A2'].font = Font(italic=True, size=12)

    ws_summary['A3'] = f"As of: {portfolio.snapshot_date.strftime('%d %B %Y')}"
    ws_summary['A3'].font = Font(size=11)

    # Key metrics
    metrics = [
        ("", ""),
        ("Key Metrics", ""),
        ("Total Market Value", float(portfolio.total_market_value)),
        ("Total Cost Base", float(portfolio.total_cost_base)),
        ("Total Profit/Loss", float(portfolio.total_profit_loss)),
        ("Return %", float(portfolio.total_profit_loss_percent) / 100),
        ("", ""),
        ("Holdings Summary", ""),
        ("Total Holdings", portfolio.holding_count),
        ("Profitable Holdings", len(portfolio.profitable_holdings)),
        ("Losing Holdings", len(portfolio.losing_holdings)),
        ("", ""),
        ("Income", ""),
        ("Dividends Received", float(portfolio.total_dividends)),
        ("Franking Credits", float(portfolio.total_franking_credits)),
    ]

    for i, (label, value) in enumerate(metrics, start=5):
        ws_summary[f'A{i}'] = label
        if label and not label.endswith("Summary") and label != "Key Metrics" and label != "Income":
            ws_summary[f'B{i}'] = value
            if "Value" in label or "Base" in label or "Profit" in label or "Dividend" in label or "Credit" in label:
                ws_summary[f'B{i}'].number_format = money_format
            elif "%" in label:
                ws_summary[f'B{i}'].number_format = percent_format
        if label.endswith("Summary") or label in ("Key Metrics", "Income"):
            ws_summary[f'A{i}'].font = Font(bold=True, size=12)

    # Column widths
    ws_summary.column_dimensions['A'].width = 25
    ws_summary.column_dimensions['B'].width = 18

    # -------------------------------------------------------------------------
    # HOLDINGS WORKSHEET
    # -------------------------------------------------------------------------
    ws_holdings = wb.create_sheet("Holdings")

    # Headers
    headers = [
        "Code", "Name", "Quantity", "Avg Cost", "Current Price",
        "Cost Base", "Market Value", "P/L $", "P/L %", "Weight %",
        "Sector", "Dividends", "Franking Credits"
    ]

    for col, header in enumerate(headers, start=1):
        cell = ws_holdings.cell(row=1, column=col, value=header)
        cell.font = header_font_white
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')
        cell.border = thin_border

    # Data
    sorted_holdings = sorted(portfolio.holdings, key=lambda h: h.market_value, reverse=True)
    for row, h in enumerate(sorted_holdings, start=2):
        data = [
            h.code,
            h.name[:40],
            h.quantity,
            float(h.avg_cost),
            float(h.current_price),
            float(h.cost_base),
            float(h.market_value),
            float(h.profit_loss),
            float(h.profit_loss_percent) / 100,
            float(h.portfolio_weight) / 100,
            h.sector.value if h.sector else "Unknown",
            float(h.dividends_received),
            float(h.franking_credits),
        ]
        for col, value in enumerate(data, start=1):
            cell = ws_holdings.cell(row=row, column=col, value=value)
            cell.border = thin_border
            # Apply formats
            if col == 4 or col == 5:  # Prices
                cell.number_format = '$#,##0.0000'
            elif col in (6, 7, 8, 12, 13):  # Money
                cell.number_format = money_format
            elif col in (9, 10):  # Percentages
                cell.number_format = percent_format
            elif col == 3:  # Quantity
                cell.number_format = number_format

    # Auto-fit columns
    for col in range(1, len(headers) + 1):
        ws_holdings.column_dimensions[get_column_letter(col)].width = 14
    ws_holdings.column_dimensions['B'].width = 35  # Name column wider

    # Freeze header row
    ws_holdings.freeze_panes = 'A2'

    # -------------------------------------------------------------------------
    # SECTORS WORKSHEET
    # -------------------------------------------------------------------------
    ws_sectors = wb.create_sheet("Sectors")

    sectors = get_sector_summary(portfolio)

    # Headers
    sector_headers = ["Sector", "Holdings", "Market Value", "Weight %", "P/L $", "P/L %"]
    for col, header in enumerate(sector_headers, start=1):
        cell = ws_sectors.cell(row=1, column=col, value=header)
        cell.font = header_font_white
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')
        cell.border = thin_border

    # Data
    row = 2
    for sector_name, data in sorted(sectors.items(), key=lambda x: x[1]['market_value'], reverse=True):
        ws_sectors.cell(row=row, column=1, value=sector_name).border = thin_border
        ws_sectors.cell(row=row, column=2, value=data['count']).border = thin_border

        cell = ws_sectors.cell(row=row, column=3, value=data['market_value'])
        cell.number_format = money_format
        cell.border = thin_border

        cell = ws_sectors.cell(row=row, column=4, value=data['weight'] / 100)
        cell.number_format = percent_format
        cell.border = thin_border

        cell = ws_sectors.cell(row=row, column=5, value=data['profit_loss'])
        cell.number_format = money_format
        cell.border = thin_border

        cell = ws_sectors.cell(row=row, column=6, value=data['profit_loss_percent'] / 100)
        cell.number_format = percent_format
        cell.border = thin_border

        row += 1

    # Column widths
    ws_sectors.column_dimensions['A'].width = 25
    for col in range(2, 7):
        ws_sectors.column_dimensions[get_column_letter(col)].width = 15

    # -------------------------------------------------------------------------
    # PERFORMANCE WORKSHEET
    # -------------------------------------------------------------------------
    ws_perf = wb.create_sheet("Performance")

    # Best performers
    ws_perf['A1'] = "Best Performers"
    ws_perf['A1'].font = Font(bold=True, size=14)
    ws_perf.merge_cells('A1:D1')

    perf_headers = ["Code", "Name", "Value", "Return %"]
    for col, header in enumerate(perf_headers, start=1):
        cell = ws_perf.cell(row=2, column=col, value=header)
        cell.font = header_font_white
        cell.fill = PatternFill(start_color="2E7D32", end_color="2E7D32", fill_type="solid")
        cell.border = thin_border

    for row, h in enumerate(portfolio.best_performers[:10], start=3):
        ws_perf.cell(row=row, column=1, value=h.code).border = thin_border
        ws_perf.cell(row=row, column=2, value=h.name[:30]).border = thin_border
        cell = ws_perf.cell(row=row, column=3, value=float(h.market_value))
        cell.number_format = money_format
        cell.border = thin_border
        cell = ws_perf.cell(row=row, column=4, value=float(h.profit_loss_percent) / 100)
        cell.number_format = percent_format
        cell.border = thin_border

    # Worst performers
    start_row = 15
    ws_perf[f'A{start_row}'] = "Worst Performers"
    ws_perf[f'A{start_row}'].font = Font(bold=True, size=14)
    ws_perf.merge_cells(f'A{start_row}:D{start_row}')

    for col, header in enumerate(perf_headers, start=1):
        cell = ws_perf.cell(row=start_row + 1, column=col, value=header)
        cell.font = header_font_white
        cell.fill = PatternFill(start_color="C62828", end_color="C62828", fill_type="solid")
        cell.border = thin_border

    for row, h in enumerate(portfolio.worst_performers[:10], start=start_row + 2):
        ws_perf.cell(row=row, column=1, value=h.code).border = thin_border
        ws_perf.cell(row=row, column=2, value=h.name[:30]).border = thin_border
        cell = ws_perf.cell(row=row, column=3, value=float(h.market_value))
        cell.number_format = money_format
        cell.border = thin_border
        cell = ws_perf.cell(row=row, column=4, value=float(h.profit_loss_percent) / 100)
        cell.number_format = percent_format
        cell.border = thin_border

    # Column widths
    ws_perf.column_dimensions['A'].width = 10
    ws_perf.column_dimensions['B'].width = 30
    ws_perf.column_dimensions['C'].width = 15
    ws_perf.column_dimensions['D'].width = 12

    # -------------------------------------------------------------------------
    # TAX WORKSHEET
    # -------------------------------------------------------------------------
    ws_tax = wb.create_sheet("Tax Planning")

    ws_tax['A1'] = f"Tax Planning - FY {get_financial_year()}"
    ws_tax['A1'].font = Font(bold=True, size=14)
    ws_tax.merge_cells('A1:D1')

    ws_tax['A2'] = "Unrealised Capital Gains Analysis"
    ws_tax['A2'].font = Font(italic=True)

    # Unrealised analysis
    unrealised = analyze_unrealised_gains(portfolio)

    tax_summary = [
        ("", ""),
        ("Summary", ""),
        ("Total Unrealised Gains", unrealised['total_unrealised_gain']),
        ("Total Unrealised Losses", unrealised['total_unrealised_loss']),
        ("Net Unrealised", unrealised['net_unrealised']),
        ("", ""),
        ("CGT Discount (50%)", ""),
        ("Discount Eligible Gains", unrealised['discount_eligible']),
        ("Potential Discount", unrealised['potential_discount']),
        ("Est. Taxable if Sold", unrealised['taxable_if_sold_now']),
        ("", ""),
        ("Position Count", ""),
        ("Holdings in Profit", unrealised['holdings_in_profit']),
        ("Holdings in Loss", unrealised['holdings_in_loss']),
    ]

    for i, (label, value) in enumerate(tax_summary, start=4):
        ws_tax[f'A{i}'] = label
        if isinstance(value, (int, float, Decimal)) and label:
            ws_tax[f'B{i}'] = float(value) if isinstance(value, Decimal) else value
            if "Count" not in label and "Holdings" not in label:
                ws_tax[f'B{i}'].number_format = money_format
        if label in ("Summary", "CGT Discount (50%)", "Position Count"):
            ws_tax[f'A{i}'].font = Font(bold=True)

    # Tax loss harvesting opportunities
    start_row = 20
    ws_tax[f'A{start_row}'] = "Tax Loss Harvesting Opportunities"
    ws_tax[f'A{start_row}'].font = Font(bold=True, size=12)

    loss_headers = ["Code", "Loss $", "Value", "Weight %"]
    for col, header in enumerate(loss_headers, start=1):
        cell = ws_tax.cell(row=start_row + 1, column=col, value=header)
        cell.font = header_font_white
        cell.fill = PatternFill(start_color="C62828", end_color="C62828", fill_type="solid")
        cell.border = thin_border

    losses = sorted([h for h in portfolio.holdings if h.profit_loss < 0], key=lambda x: x.profit_loss)
    for row, h in enumerate(losses[:10], start=start_row + 2):
        ws_tax.cell(row=row, column=1, value=h.code).border = thin_border
        cell = ws_tax.cell(row=row, column=2, value=float(h.profit_loss))
        cell.number_format = money_format
        cell.border = thin_border
        cell = ws_tax.cell(row=row, column=3, value=float(h.market_value))
        cell.number_format = money_format
        cell.border = thin_border
        cell = ws_tax.cell(row=row, column=4, value=float(h.portfolio_weight) / 100)
        cell.number_format = percent_format
        cell.border = thin_border

    # Column widths
    ws_tax.column_dimensions['A'].width = 28
    ws_tax.column_dimensions['B'].width = 18
    ws_tax.column_dimensions['C'].width = 15
    ws_tax.column_dimensions['D'].width = 12

    # Save workbook
    wb.save(output_path)
    logger.info(f"Exported portfolio to Excel: {output_path}")
    return output_path


# ============================================================================
# PDF EXPORT
# ============================================================================

def export_to_pdf(
    portfolio: Portfolio,
    output_path: Path,
) -> Optional[Path]:
    """
    Export portfolio to a professional PDF report.

    Args:
        portfolio: Portfolio to export
        output_path: Output file path

    Returns:
        Path to created file, or None if failed
    """
    if not PDF_AVAILABLE:
        raise ImportError("reportlab required for PDF export. Install with: pip install reportlab")

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )

    styles = getSampleStyleSheet()
    story = []

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=20,
        spaceAfter=10,
        textColor=colors.HexColor('#1F4E79')
    )
    normal_style = styles['Normal']

    # Title
    title = f"Portfolio Report"
    if portfolio.name:
        title = f"{portfolio.name} - Portfolio Report"
    story.append(Paragraph(title, title_style))

    # Date
    story.append(Paragraph(
        f"<para alignment='center'>As of {portfolio.snapshot_date.strftime('%d %B %Y')}</para>",
        normal_style
    ))
    story.append(Spacer(1, 20))

    # Summary section
    story.append(Paragraph("Portfolio Summary", heading_style))

    summary_data = [
        ["Total Market Value", f"${float(portfolio.total_market_value):,.2f}"],
        ["Total Cost Base", f"${float(portfolio.total_cost_base):,.2f}"],
        ["Total Profit/Loss", f"${float(portfolio.total_profit_loss):+,.2f}"],
        ["Return", f"{float(portfolio.total_profit_loss_percent):+.2f}%"],
        ["Number of Holdings", str(portfolio.holding_count)],
        ["Profitable / Losing", f"{len(portfolio.profitable_holdings)} / {len(portfolio.losing_holdings)}"],
    ]

    summary_table = Table(summary_data, colWidths=[150, 150])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E8E8E8')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 20))

    # Top Holdings
    story.append(Paragraph("Top 10 Holdings", heading_style))

    holdings_header = ["Code", "Name", "Value", "Weight", "Return"]
    holdings_data = [holdings_header]
    for h in portfolio.top_holdings[:10]:
        holdings_data.append([
            h.code,
            h.name[:25] + "..." if len(h.name) > 25 else h.name,
            f"${float(h.market_value):,.0f}",
            f"{float(h.portfolio_weight):.1f}%",
            f"{float(h.profit_loss_percent):+.1f}%"
        ])

    holdings_table = Table(holdings_data, colWidths=[50, 180, 80, 60, 60])
    holdings_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F4E79')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F5F5F5')]),
    ]))
    story.append(holdings_table)
    story.append(Spacer(1, 20))

    # Sector Allocation
    story.append(Paragraph("Sector Allocation", heading_style))

    sectors = get_sector_summary(portfolio)
    sector_header = ["Sector", "Value", "Weight", "P/L %"]
    sector_data = [sector_header]
    for name, data in sorted(sectors.items(), key=lambda x: x[1]['market_value'], reverse=True)[:8]:
        sector_data.append([
            name[:20],
            f"${data['market_value']:,.0f}",
            f"{data['weight']:.1f}%",
            f"{data['profit_loss_percent']:+.1f}%"
        ])

    sector_table = Table(sector_data, colWidths=[150, 100, 80, 80])
    sector_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F4E79')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F5F5F5')]),
    ]))
    story.append(sector_table)

    # Page break for performance
    story.append(PageBreak())

    # Best Performers
    story.append(Paragraph("Best Performers", heading_style))

    best_data = [["Code", "Name", "Value", "Return"]]
    for h in portfolio.best_performers[:5]:
        best_data.append([
            h.code,
            h.name[:30],
            f"${float(h.market_value):,.0f}",
            f"{float(h.profit_loss_percent):+.1f}%"
        ])

    best_table = Table(best_data, colWidths=[60, 220, 100, 80])
    best_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E7D32')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(best_table)
    story.append(Spacer(1, 20))

    # Worst Performers
    story.append(Paragraph("Worst Performers", heading_style))

    worst_data = [["Code", "Name", "Value", "Return"]]
    for h in portfolio.worst_performers[:5]:
        worst_data.append([
            h.code,
            h.name[:30],
            f"${float(h.market_value):,.0f}",
            f"{float(h.profit_loss_percent):+.1f}%"
        ])

    worst_table = Table(worst_data, colWidths=[60, 220, 100, 80])
    worst_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#C62828')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(worst_table)
    story.append(Spacer(1, 30))

    # Disclaimer
    disclaimer_style = ParagraphStyle(
        'Disclaimer',
        parent=normal_style,
        fontSize=8,
        textColor=colors.grey
    )
    story.append(Paragraph(
        "This report is for informational purposes only. Consult a qualified financial advisor for investment advice.",
        disclaimer_style
    ))

    # Build PDF
    doc.build(story)
    logger.info(f"Exported portfolio to PDF: {output_path}")
    return output_path


# ============================================================================
# TAX PACKAGE EXPORT
# ============================================================================

def export_tax_package(
    portfolio: Portfolio,
    output_dir: Path,
    financial_year: Optional[str] = None,
) -> Dict[str, Path]:
    """
    Export a tax package for accountants.

    Creates multiple files:
    - tax_summary.csv: CGT summary and totals
    - unrealised_gains.csv: All positions with gains/losses
    - dividend_income.csv: Dividend and franking credit details
    - tax_loss_harvest.csv: Positions eligible for tax loss harvesting

    Args:
        portfolio: Portfolio to export
        output_dir: Output directory
        financial_year: FY string (auto-detected if None)

    Returns:
        Dictionary of created file paths
    """
    if financial_year is None:
        financial_year = get_financial_year()

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    created_files = {}

    # -------------------------------------------------------------------------
    # Tax Summary
    # -------------------------------------------------------------------------
    summary_path = output_dir / f"tax_summary_FY{financial_year.replace('-', '_')}.csv"
    unrealised = analyze_unrealised_gains(portfolio)

    with open(summary_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Tax Summary", f"FY {financial_year}"])
        writer.writerow([])
        writer.writerow(["Category", "Amount"])
        writer.writerow(["Portfolio Value", float(portfolio.total_market_value)])
        writer.writerow(["Cost Base", float(portfolio.total_cost_base)])
        writer.writerow([])
        writer.writerow(["Unrealised Capital Gains", float(unrealised['total_unrealised_gain'])])
        writer.writerow(["Unrealised Capital Losses", float(unrealised['total_unrealised_loss'])])
        writer.writerow(["Net Unrealised", float(unrealised['net_unrealised'])])
        writer.writerow([])
        writer.writerow(["CGT Discount Eligible (50%)", float(unrealised['discount_eligible'])])
        writer.writerow(["Potential CGT Discount", float(unrealised['potential_discount'])])
        writer.writerow(["Est. Taxable Gain if Sold", float(unrealised['taxable_if_sold_now'])])
        writer.writerow([])
        writer.writerow(["Dividend Income", float(portfolio.total_dividends)])
        writer.writerow(["Franking Credits", float(portfolio.total_franking_credits)])
        writer.writerow(["Total Assessable (Div + FC)", float(portfolio.total_dividends + portfolio.total_franking_credits)])

    created_files['summary'] = summary_path

    # -------------------------------------------------------------------------
    # Unrealised Gains Detail
    # -------------------------------------------------------------------------
    gains_path = output_dir / f"unrealised_gains_FY{financial_year.replace('-', '_')}.csv"

    with open(gains_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            "Code", "Name", "Quantity", "Cost Base", "Market Value",
            "Unrealised P/L", "P/L %", "CGT Discount Eligible*"
        ])

        for h in sorted(portfolio.holdings, key=lambda x: x.profit_loss, reverse=True):
            writer.writerow([
                h.code,
                h.name,
                h.quantity,
                float(h.cost_base),
                float(h.market_value),
                float(h.profit_loss),
                float(h.profit_loss_percent),
                "Yes*" if h.profit_loss > 0 else "N/A"
            ])

        writer.writerow([])
        writer.writerow(["* CGT discount assumed for all gains (holdings > 12 months)"])

    created_files['unrealised_gains'] = gains_path

    # -------------------------------------------------------------------------
    # Dividend Income
    # -------------------------------------------------------------------------
    dividend_path = output_dir / f"dividend_income_FY{financial_year.replace('-', '_')}.csv"

    with open(dividend_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            "Code", "Name", "Dividends Received", "Franking Credits",
            "Franking %*", "Gross Dividend", "Assessable Income"
        ])

        for h in sorted(portfolio.holdings, key=lambda x: x.dividends_received, reverse=True):
            if h.dividends_received > 0:
                # Estimate franking percentage
                if h.franking_credits > 0:
                    # Back-calculate franking %
                    franking_pct = 100
                else:
                    franking_pct = 0

                gross = h.dividends_received + h.franking_credits
                assessable = gross  # Gross-up method

                writer.writerow([
                    h.code,
                    h.name,
                    float(h.dividends_received),
                    float(h.franking_credits),
                    f"{franking_pct}%",
                    float(gross),
                    float(assessable)
                ])

        writer.writerow([])
        writer.writerow(["TOTAL", "", float(portfolio.total_dividends),
                        float(portfolio.total_franking_credits), "",
                        float(portfolio.total_dividends + portfolio.total_franking_credits),
                        float(portfolio.total_dividends + portfolio.total_franking_credits)])
        writer.writerow([])
        writer.writerow(["* Franking percentage estimated from credits"])

    created_files['dividends'] = dividend_path

    # -------------------------------------------------------------------------
    # Tax Loss Harvesting
    # -------------------------------------------------------------------------
    harvest_path = output_dir / f"tax_loss_harvest_FY{financial_year.replace('-', '_')}.csv"

    with open(harvest_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Tax Loss Harvesting Opportunities"])
        writer.writerow([])
        writer.writerow([
            "Code", "Name", "Quantity", "Cost Base", "Market Value",
            "Unrealised Loss", "Loss %", "Weight %"
        ])

        losses = [h for h in portfolio.holdings if h.profit_loss < 0]
        total_loss = Decimal("0")

        for h in sorted(losses, key=lambda x: x.profit_loss):
            writer.writerow([
                h.code,
                h.name,
                h.quantity,
                float(h.cost_base),
                float(h.market_value),
                float(h.profit_loss),
                float(h.profit_loss_percent),
                float(h.portfolio_weight)
            ])
            total_loss += h.profit_loss

        writer.writerow([])
        writer.writerow(["TOTAL HARVESTABLE LOSSES", "", "", "", "", float(total_loss), "", ""])
        writer.writerow([])
        writer.writerow(["Note: Be aware of wash sale rules when selling and rebuying"])

    created_files['tax_loss_harvest'] = harvest_path

    logger.info(f"Exported tax package to: {output_dir}")
    return created_files


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def check_export_dependencies() -> Dict[str, bool]:
    """Check which export formats are available."""
    return {
        "excel": EXCEL_AVAILABLE,
        "pdf": PDF_AVAILABLE,
        "csv": True,  # Always available
        "json": True,  # Always available
        "tax_package": True,  # Always available (uses CSV)
    }
