"""
Transaction Log - Record and track all portfolio transactions.

Features:
- Record BUY, SELL, DIVIDEND transactions
- Automatic realized gains/loss calculation
- Transaction history with filtering
- FIFO/LIFO cost base tracking
- CGT event recording
- Transaction import/export
"""

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import json
import csv

from .models import Portfolio, Holding

logger = logging.getLogger(__name__)


class TransactionType(Enum):
    """Types of portfolio transactions."""
    BUY = "buy"
    SELL = "sell"
    DIVIDEND = "dividend"
    DRP = "drp"  # Dividend Reinvestment
    SPLIT = "split"
    CONSOLIDATION = "consolidation"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    BONUS = "bonus"  # Bonus issue


class CostMethod(Enum):
    """Cost base calculation methods."""
    FIFO = "fifo"  # First In, First Out
    LIFO = "lifo"  # Last In, First Out
    AVERAGE = "average"  # Average cost


@dataclass
class Transaction:
    """Represents a single transaction."""
    id: Optional[int]
    code: str
    transaction_type: TransactionType
    date: date
    quantity: int
    price: Decimal  # Price per share
    total_value: Decimal  # Total transaction value
    fees: Decimal = Decimal("0")
    notes: str = ""

    # For sells - realized gain/loss
    cost_base: Optional[Decimal] = None
    realized_gain: Optional[Decimal] = None
    cgt_discount_eligible: bool = False

    # For dividends
    franking_credits: Optional[Decimal] = None
    drp_shares: Optional[int] = None

    # Metadata
    created_at: Optional[datetime] = None

    @property
    def net_value(self) -> Decimal:
        """Net value after fees."""
        if self.transaction_type in (TransactionType.BUY, TransactionType.DRP):
            return self.total_value + self.fees
        elif self.transaction_type == TransactionType.SELL:
            return self.total_value - self.fees
        else:
            return self.total_value


@dataclass
class RealizedGain:
    """Realized gain/loss from a sale."""
    code: str
    sell_date: date
    quantity: int
    proceeds: Decimal
    cost_base: Decimal
    fees: Decimal
    gain_loss: Decimal
    holding_period_days: int
    cgt_discount_eligible: bool
    discounted_gain: Decimal

    @property
    def is_gain(self) -> bool:
        return self.gain_loss > 0


@dataclass
class TransactionSummary:
    """Summary of transactions for a stock or portfolio."""
    code: Optional[str]  # None for portfolio-wide
    total_buys: int
    total_sells: int
    total_dividends: int
    total_invested: Decimal
    total_proceeds: Decimal
    total_dividends_received: Decimal
    total_fees: Decimal
    realized_gains: Decimal
    realized_losses: Decimal
    net_realized: Decimal
    average_buy_price: Optional[Decimal]
    average_sell_price: Optional[Decimal]


class TransactionLog:
    """
    Manages transaction logging and history.

    Stores transactions in SQLite database.
    """

    def __init__(self, db_path: Path):
        """Initialize transaction log with database path."""
        self.db_path = db_path
        self._init_database()

    def _init_database(self) -> None:
        """Initialize the transactions table."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL,
                    transaction_type TEXT NOT NULL,
                    date TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    price TEXT NOT NULL,
                    total_value TEXT NOT NULL,
                    fees TEXT DEFAULT '0',
                    notes TEXT DEFAULT '',
                    cost_base TEXT,
                    realized_gain TEXT,
                    cgt_discount_eligible INTEGER DEFAULT 0,
                    franking_credits TEXT,
                    drp_shares INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create index for faster queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_transactions_code
                ON transactions(code)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_transactions_date
                ON transactions(date)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_transactions_type
                ON transactions(transaction_type)
            """)
            conn.commit()

    def add_transaction(self, transaction: Transaction) -> int:
        """Add a transaction to the log. Returns the transaction ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO transactions (
                    code, transaction_type, date, quantity, price,
                    total_value, fees, notes, cost_base, realized_gain,
                    cgt_discount_eligible, franking_credits, drp_shares
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                transaction.code.upper(),
                transaction.transaction_type.value,
                transaction.date.isoformat(),
                transaction.quantity,
                str(transaction.price),
                str(transaction.total_value),
                str(transaction.fees),
                transaction.notes,
                str(transaction.cost_base) if transaction.cost_base else None,
                str(transaction.realized_gain) if transaction.realized_gain else None,
                1 if transaction.cgt_discount_eligible else 0,
                str(transaction.franking_credits) if transaction.franking_credits else None,
                transaction.drp_shares,
            ))
            conn.commit()
            return cursor.lastrowid

    def get_transaction(self, transaction_id: int) -> Optional[Transaction]:
        """Get a single transaction by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM transactions WHERE id = ?",
                (transaction_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_transaction(row)
            return None

    def get_transactions(
        self,
        code: Optional[str] = None,
        transaction_type: Optional[TransactionType] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: Optional[int] = None,
    ) -> List[Transaction]:
        """Get transactions with optional filters."""
        query = "SELECT * FROM transactions WHERE 1=1"
        params = []

        if code:
            query += " AND code = ?"
            params.append(code.upper())

        if transaction_type:
            query += " AND transaction_type = ?"
            params.append(transaction_type.value)

        if start_date:
            query += " AND date >= ?"
            params.append(start_date.isoformat())

        if end_date:
            query += " AND date <= ?"
            params.append(end_date.isoformat())

        query += " ORDER BY date DESC, id DESC"

        if limit:
            query += f" LIMIT {limit}"

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [self._row_to_transaction(row) for row in cursor.fetchall()]

    def delete_transaction(self, transaction_id: int) -> bool:
        """Delete a transaction. Returns True if deleted."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM transactions WHERE id = ?",
                (transaction_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def _row_to_transaction(self, row: sqlite3.Row) -> Transaction:
        """Convert database row to Transaction object."""
        return Transaction(
            id=row["id"],
            code=row["code"],
            transaction_type=TransactionType(row["transaction_type"]),
            date=date.fromisoformat(row["date"]),
            quantity=row["quantity"],
            price=Decimal(row["price"]),
            total_value=Decimal(row["total_value"]),
            fees=Decimal(row["fees"]) if row["fees"] else Decimal("0"),
            notes=row["notes"] or "",
            cost_base=Decimal(row["cost_base"]) if row["cost_base"] else None,
            realized_gain=Decimal(row["realized_gain"]) if row["realized_gain"] else None,
            cgt_discount_eligible=bool(row["cgt_discount_eligible"]),
            franking_credits=Decimal(row["franking_credits"]) if row["franking_credits"] else None,
            drp_shares=row["drp_shares"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
        )

    def record_buy(
        self,
        code: str,
        date: date,
        quantity: int,
        price: Decimal,
        fees: Decimal = Decimal("0"),
        notes: str = "",
    ) -> int:
        """Record a buy transaction."""
        total = price * Decimal(str(quantity))
        transaction = Transaction(
            id=None,
            code=code.upper(),
            transaction_type=TransactionType.BUY,
            date=date,
            quantity=quantity,
            price=price,
            total_value=total,
            fees=fees,
            notes=notes,
        )
        return self.add_transaction(transaction)

    def record_sell(
        self,
        code: str,
        date: date,
        quantity: int,
        price: Decimal,
        fees: Decimal = Decimal("0"),
        notes: str = "",
        cost_method: CostMethod = CostMethod.FIFO,
    ) -> Tuple[int, RealizedGain]:
        """
        Record a sell transaction and calculate realized gain/loss.

        Returns transaction ID and realized gain details.
        """
        total = price * Decimal(str(quantity))

        # Calculate cost base using specified method
        cost_base, holding_days = self._calculate_cost_base(
            code, quantity, date, cost_method
        )

        # Calculate gain/loss
        proceeds = total - fees
        gain_loss = proceeds - cost_base

        # CGT discount: 50% if held > 12 months
        cgt_eligible = holding_days >= 365
        discounted_gain = gain_loss / Decimal("2") if cgt_eligible and gain_loss > 0 else gain_loss

        transaction = Transaction(
            id=None,
            code=code.upper(),
            transaction_type=TransactionType.SELL,
            date=date,
            quantity=quantity,
            price=price,
            total_value=total,
            fees=fees,
            notes=notes,
            cost_base=cost_base,
            realized_gain=gain_loss,
            cgt_discount_eligible=cgt_eligible,
        )

        tx_id = self.add_transaction(transaction)

        realized = RealizedGain(
            code=code.upper(),
            sell_date=date,
            quantity=quantity,
            proceeds=proceeds,
            cost_base=cost_base,
            fees=fees,
            gain_loss=gain_loss,
            holding_period_days=holding_days,
            cgt_discount_eligible=cgt_eligible,
            discounted_gain=discounted_gain,
        )

        return tx_id, realized

    def record_dividend(
        self,
        code: str,
        date: date,
        amount: Decimal,
        franking_credits: Optional[Decimal] = None,
        drp_shares: Optional[int] = None,
        drp_price: Optional[Decimal] = None,
        notes: str = "",
    ) -> int:
        """Record a dividend payment."""
        transaction = Transaction(
            id=None,
            code=code.upper(),
            transaction_type=TransactionType.DRP if drp_shares else TransactionType.DIVIDEND,
            date=date,
            quantity=drp_shares or 0,
            price=drp_price or Decimal("0"),
            total_value=amount,
            notes=notes,
            franking_credits=franking_credits,
            drp_shares=drp_shares,
        )
        return self.add_transaction(transaction)

    def _calculate_cost_base(
        self,
        code: str,
        quantity: int,
        sell_date: date,
        method: CostMethod,
    ) -> Tuple[Decimal, int]:
        """
        Calculate cost base for sold shares.

        Returns (cost_base, average_holding_days).
        """
        # Get all buy transactions for this stock
        buys = self.get_transactions(
            code=code,
            transaction_type=TransactionType.BUY,
            end_date=sell_date,
        )

        # Also include DRP
        drps = self.get_transactions(
            code=code,
            transaction_type=TransactionType.DRP,
            end_date=sell_date,
        )

        # Combine and sort
        all_buys = buys + drps

        if method == CostMethod.FIFO:
            all_buys.sort(key=lambda x: x.date)
        elif method == CostMethod.LIFO:
            all_buys.sort(key=lambda x: x.date, reverse=True)

        # Get previous sells to know what's already been sold
        sells = self.get_transactions(
            code=code,
            transaction_type=TransactionType.SELL,
            end_date=sell_date,
        )

        # Calculate remaining shares from each lot
        lots = []
        for buy in all_buys:
            lots.append({
                "date": buy.date,
                "quantity": buy.quantity,
                "price": buy.price,
                "fees": buy.fees,
                "remaining": buy.quantity,
            })

        # Apply previous sells
        for sell in sells:
            remaining_to_sell = sell.quantity
            for lot in lots:
                if remaining_to_sell <= 0:
                    break
                if lot["remaining"] > 0:
                    sold = min(lot["remaining"], remaining_to_sell)
                    lot["remaining"] -= sold
                    remaining_to_sell -= sold

        # Now calculate cost base for this sale
        cost_base = Decimal("0")
        total_days = 0
        shares_counted = 0
        remaining_to_sell = quantity

        for lot in lots:
            if remaining_to_sell <= 0:
                break
            if lot["remaining"] > 0:
                sold = min(lot["remaining"], remaining_to_sell)

                # Cost per share including proportional fees
                cost_per_share = lot["price"] + (lot["fees"] / Decimal(str(lot["quantity"])))
                cost_base += cost_per_share * Decimal(str(sold))

                # Track holding period
                holding_days = (sell_date - lot["date"]).days
                total_days += holding_days * sold
                shares_counted += sold

                remaining_to_sell -= sold

        avg_days = total_days // shares_counted if shares_counted > 0 else 0

        # If we couldn't find enough shares, use average cost
        if remaining_to_sell > 0 and method != CostMethod.AVERAGE:
            # Fall back to average cost for unknown shares
            if lots:
                avg_cost = sum(l["price"] for l in lots) / len(lots)
                cost_base += avg_cost * Decimal(str(remaining_to_sell))

        return cost_base, avg_days

    def get_summary(
        self,
        code: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> TransactionSummary:
        """Get transaction summary for a stock or entire portfolio."""
        transactions = self.get_transactions(
            code=code,
            start_date=start_date,
            end_date=end_date,
        )

        buys = [t for t in transactions if t.transaction_type in (TransactionType.BUY, TransactionType.DRP)]
        sells = [t for t in transactions if t.transaction_type == TransactionType.SELL]
        dividends = [t for t in transactions if t.transaction_type == TransactionType.DIVIDEND]

        total_invested = sum(t.net_value for t in buys)
        total_proceeds = sum(t.net_value for t in sells)
        total_dividends = sum(t.total_value for t in dividends)
        total_fees = sum(t.fees for t in transactions)

        gains = sum(t.realized_gain for t in sells if t.realized_gain and t.realized_gain > 0)
        losses = sum(t.realized_gain for t in sells if t.realized_gain and t.realized_gain < 0)

        total_buy_shares = sum(t.quantity for t in buys)
        total_sell_shares = sum(t.quantity for t in sells)

        avg_buy = total_invested / Decimal(str(total_buy_shares)) if total_buy_shares > 0 else None
        avg_sell = total_proceeds / Decimal(str(total_sell_shares)) if total_sell_shares > 0 else None

        return TransactionSummary(
            code=code,
            total_buys=len(buys),
            total_sells=len(sells),
            total_dividends=len(dividends),
            total_invested=total_invested,
            total_proceeds=total_proceeds,
            total_dividends_received=total_dividends,
            total_fees=total_fees,
            realized_gains=gains,
            realized_losses=abs(losses),
            net_realized=gains + losses,  # losses are negative
            average_buy_price=avg_buy,
            average_sell_price=avg_sell,
        )

    def get_realized_gains(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[RealizedGain]:
        """Get all realized gains/losses in a period."""
        sells = self.get_transactions(
            transaction_type=TransactionType.SELL,
            start_date=start_date,
            end_date=end_date,
        )

        gains = []
        for sell in sells:
            if sell.cost_base is not None and sell.realized_gain is not None:
                discounted = sell.realized_gain / Decimal("2") if (
                    sell.cgt_discount_eligible and sell.realized_gain > 0
                ) else sell.realized_gain

                gains.append(RealizedGain(
                    code=sell.code,
                    sell_date=sell.date,
                    quantity=sell.quantity,
                    proceeds=sell.total_value - sell.fees,
                    cost_base=sell.cost_base,
                    fees=sell.fees,
                    gain_loss=sell.realized_gain,
                    holding_period_days=0,  # Would need to recalculate
                    cgt_discount_eligible=sell.cgt_discount_eligible,
                    discounted_gain=discounted,
                ))

        return gains

    def export_to_csv(self, output_path: Path, code: Optional[str] = None) -> Path:
        """Export transactions to CSV."""
        transactions = self.get_transactions(code=code)

        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "ID", "Code", "Type", "Date", "Quantity", "Price",
                "Total Value", "Fees", "Cost Base", "Realized Gain/Loss",
                "CGT Discount", "Franking Credits", "Notes"
            ])

            for t in transactions:
                writer.writerow([
                    t.id,
                    t.code,
                    t.transaction_type.value,
                    t.date.isoformat(),
                    t.quantity,
                    f"{float(t.price):.4f}",
                    f"{float(t.total_value):.2f}",
                    f"{float(t.fees):.2f}",
                    f"{float(t.cost_base):.2f}" if t.cost_base else "",
                    f"{float(t.realized_gain):.2f}" if t.realized_gain else "",
                    "Yes" if t.cgt_discount_eligible else "No",
                    f"{float(t.franking_credits):.2f}" if t.franking_credits else "",
                    t.notes,
                ])

        return output_path

    def import_from_csv(self, csv_path: Path) -> int:
        """
        Import transactions from CSV.

        Expected columns: Code, Type, Date, Quantity, Price, Fees, Notes
        Returns number of transactions imported.
        """
        count = 0

        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)

            for row in reader:
                try:
                    tx_type = TransactionType(row.get("Type", "buy").lower())
                    tx_date = date.fromisoformat(row["Date"])
                    quantity = int(row.get("Quantity", 0))
                    price = Decimal(row.get("Price", "0"))
                    fees = Decimal(row.get("Fees", "0"))
                    notes = row.get("Notes", "")
                    code = row["Code"].upper()

                    if tx_type == TransactionType.BUY:
                        self.record_buy(code, tx_date, quantity, price, fees, notes)
                    elif tx_type == TransactionType.SELL:
                        self.record_sell(code, tx_date, quantity, price, fees, notes)
                    elif tx_type == TransactionType.DIVIDEND:
                        amount = Decimal(row.get("Total Value", "0"))
                        franking = Decimal(row.get("Franking Credits", "0")) if row.get("Franking Credits") else None
                        self.record_dividend(code, tx_date, amount, franking, notes=notes)

                    count += 1

                except (ValueError, KeyError) as e:
                    logger.warning(f"Skipping invalid row: {e}")
                    continue

        return count


def format_transaction_history(
    transactions: List[Transaction],
    show_gains: bool = True,
) -> str:
    """Format transactions as a readable report."""
    lines = []

    lines.append("=" * 80)
    lines.append("TRANSACTION HISTORY")
    lines.append("=" * 80)

    if not transactions:
        lines.append("  No transactions found.")
        return "\n".join(lines)

    # Group by code
    by_code: Dict[str, List[Transaction]] = {}
    for t in transactions:
        if t.code not in by_code:
            by_code[t.code] = []
        by_code[t.code].append(t)

    for code in sorted(by_code.keys()):
        txs = by_code[code]
        lines.append("")
        lines.append(f"  {code}")
        lines.append("  " + "-" * 76)
        lines.append(f"  {'Date':<12} {'Type':<10} {'Qty':>8} {'Price':>10} {'Value':>12} {'Gain/Loss':>12}")
        lines.append("  " + "-" * 76)

        for t in txs:
            type_str = t.transaction_type.value.upper()
            gain_str = ""
            if show_gains and t.realized_gain is not None:
                gain = float(t.realized_gain)
                if t.cgt_discount_eligible:
                    gain_str = f"${gain:>+,.0f}*"
                else:
                    gain_str = f"${gain:>+,.0f}"

            lines.append(
                f"  {t.date.isoformat():<12} {type_str:<10} {t.quantity:>8,} "
                f"${float(t.price):>9,.2f} ${float(t.total_value):>10,.0f} {gain_str:>12}"
            )

        # Subtotal
        buys = sum(t.net_value for t in txs if t.transaction_type in (TransactionType.BUY, TransactionType.DRP))
        sells = sum(t.net_value for t in txs if t.transaction_type == TransactionType.SELL)
        divs = sum(t.total_value for t in txs if t.transaction_type == TransactionType.DIVIDEND)

        lines.append("  " + "-" * 76)
        lines.append(f"  Total: Invested ${float(buys):,.0f} | Sold ${float(sells):,.0f} | Dividends ${float(divs):,.0f}")

    lines.append("")
    lines.append("  * CGT discount eligible (held >12 months)")
    lines.append("")

    return "\n".join(lines)


def format_transaction_summary(summary: TransactionSummary) -> str:
    """Format transaction summary."""
    lines = []

    title = f"TRANSACTION SUMMARY - {summary.code}" if summary.code else "PORTFOLIO TRANSACTION SUMMARY"
    lines.append("=" * 60)
    lines.append(title)
    lines.append("=" * 60)
    lines.append("")

    lines.append(f"  Buy Transactions:        {summary.total_buys:>8}")
    lines.append(f"  Sell Transactions:       {summary.total_sells:>8}")
    lines.append(f"  Dividend Payments:       {summary.total_dividends:>8}")
    lines.append("")

    lines.append(f"  Total Invested:          ${float(summary.total_invested):>12,.0f}")
    lines.append(f"  Total Proceeds:          ${float(summary.total_proceeds):>12,.0f}")
    lines.append(f"  Dividends Received:      ${float(summary.total_dividends_received):>12,.0f}")
    lines.append(f"  Total Fees Paid:         ${float(summary.total_fees):>12,.0f}")
    lines.append("")

    lines.append("-" * 60)
    lines.append("  REALIZED GAINS/LOSSES")
    lines.append("-" * 60)
    lines.append(f"  Realized Gains:          ${float(summary.realized_gains):>12,.0f}")
    lines.append(f"  Realized Losses:         ${float(summary.realized_losses):>12,.0f}")
    net = float(summary.net_realized)
    net_str = f"${net:>+12,.0f}" if net != 0 else "$           0"
    lines.append(f"  Net Realized:            {net_str}")
    lines.append("")

    if summary.average_buy_price:
        lines.append(f"  Average Buy Price:       ${float(summary.average_buy_price):>12,.4f}")
    if summary.average_sell_price:
        lines.append(f"  Average Sell Price:      ${float(summary.average_sell_price):>12,.4f}")

    lines.append("")

    return "\n".join(lines)


def format_realized_gains_report(
    gains: List[RealizedGain],
    financial_year: Optional[str] = None,
) -> str:
    """Format realized gains for tax reporting."""
    lines = []

    fy_title = f" - FY{financial_year}" if financial_year else ""
    lines.append("=" * 70)
    lines.append(f"CAPITAL GAINS TAX REPORT{fy_title}")
    lines.append("=" * 70)

    if not gains:
        lines.append("  No realized gains/losses in this period.")
        return "\n".join(lines)

    # Separate gains and losses
    capital_gains = [g for g in gains if g.is_gain]
    capital_losses = [g for g in gains if not g.is_gain]

    lines.append("")
    lines.append(f"  {'Code':<6} {'Date':<12} {'Qty':>8} {'Proceeds':>12} {'Cost':>12} {'Gain/Loss':>12}")
    lines.append("  " + "-" * 66)

    for g in sorted(gains, key=lambda x: x.sell_date):
        discount_marker = "*" if g.cgt_discount_eligible else " "
        lines.append(
            f"  {g.code:<6} {g.sell_date.isoformat():<12} {g.quantity:>8,} "
            f"${float(g.proceeds):>10,.0f} ${float(g.cost_base):>10,.0f} "
            f"${float(g.gain_loss):>+10,.0f}{discount_marker}"
        )

    lines.append("")
    lines.append("-" * 70)

    # Summary
    total_gains = sum(g.gain_loss for g in capital_gains)
    total_losses = sum(g.gain_loss for g in capital_losses)  # Already negative

    # Discounted gains
    discounted = sum(g.discounted_gain for g in capital_gains if g.cgt_discount_eligible)
    non_discounted = sum(g.gain_loss for g in capital_gains if not g.cgt_discount_eligible)

    lines.append(f"  Total Capital Gains:     ${float(total_gains):>12,.0f}")
    lines.append(f"    - CGT Discount (50%):  ${float(discounted):>12,.0f}")
    lines.append(f"    - No Discount:         ${float(non_discounted):>12,.0f}")
    lines.append(f"  Total Capital Losses:    ${float(total_losses):>12,.0f}")
    lines.append("")

    # Net taxable
    net_taxable = discounted + non_discounted + total_losses
    lines.append(f"  Net Taxable Gain/Loss:   ${float(net_taxable):>+12,.0f}")
    lines.append("")
    lines.append("  * CGT discount eligible (held >12 months)")
    lines.append("")

    return "\n".join(lines)
