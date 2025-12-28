"""
Terminal Colors and Formatting - Beautiful CLI output.

Provides color coding, formatting, and styling for terminal output.
Automatically disables colors when output is not a TTY.
"""

import os
import sys
from decimal import Decimal
from typing import Optional, Union

# Check if we're in a terminal that supports colors
COLORS_ENABLED = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()

# Allow override via environment variable
if os.environ.get('NO_COLOR'):
    COLORS_ENABLED = False
if os.environ.get('FORCE_COLOR'):
    COLORS_ENABLED = True


class Colors:
    """ANSI color codes."""
    # Reset
    RESET = '\033[0m'

    # Regular colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'

    # Bright colors
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'

    # Styles
    BOLD = '\033[1m'
    DIM = '\033[2m'
    ITALIC = '\033[3m'
    UNDERLINE = '\033[4m'

    # Background colors
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'


def color(text: str, color_code: str) -> str:
    """Apply color to text if colors are enabled."""
    if not COLORS_ENABLED:
        return text
    return f"{color_code}{text}{Colors.RESET}"


def green(text: str) -> str:
    """Green text for positive values."""
    return color(text, Colors.BRIGHT_GREEN)


def red(text: str) -> str:
    """Red text for negative values."""
    return color(text, Colors.BRIGHT_RED)


def yellow(text: str) -> str:
    """Yellow text for warnings."""
    return color(text, Colors.BRIGHT_YELLOW)


def blue(text: str) -> str:
    """Blue text for info."""
    return color(text, Colors.BRIGHT_BLUE)


def cyan(text: str) -> str:
    """Cyan text for highlights."""
    return color(text, Colors.BRIGHT_CYAN)


def magenta(text: str) -> str:
    """Magenta text for special items."""
    return color(text, Colors.BRIGHT_MAGENTA)


def bold(text: str) -> str:
    """Bold text."""
    return color(text, Colors.BOLD)


def dim(text: str) -> str:
    """Dimmed text."""
    return color(text, Colors.DIM)


def format_money(
    value: Union[Decimal, float, int],
    show_sign: bool = False,
    color_code: bool = True,
) -> str:
    """
    Format a monetary value with optional coloring.

    Args:
        value: The value to format
        show_sign: Whether to show +/- sign
        color_code: Whether to apply color based on value

    Returns:
        Formatted string
    """
    if isinstance(value, Decimal):
        value = float(value)

    if show_sign:
        text = f"${value:+,.2f}"
    else:
        text = f"${value:,.2f}"

    if color_code and COLORS_ENABLED:
        if value > 0:
            return green(text)
        elif value < 0:
            return red(text)

    return text


def format_percent(
    value: Union[Decimal, float],
    show_sign: bool = True,
    color_code: bool = True,
) -> str:
    """
    Format a percentage with optional coloring.

    Args:
        value: The percentage value
        show_sign: Whether to show +/- sign
        color_code: Whether to apply color based on value

    Returns:
        Formatted string
    """
    if isinstance(value, Decimal):
        value = float(value)

    if show_sign:
        text = f"{value:+.2f}%"
    else:
        text = f"{value:.2f}%"

    if color_code and COLORS_ENABLED:
        if value > 0:
            return green(text)
        elif value < 0:
            return red(text)

    return text


def format_change(
    value: Union[Decimal, float],
    is_percent: bool = False,
) -> str:
    """
    Format a change value with arrow indicator.

    Args:
        value: The change value
        is_percent: Whether this is a percentage

    Returns:
        Formatted string with arrow
    """
    if isinstance(value, Decimal):
        value = float(value)

    if value > 0:
        arrow = "▲"
        if is_percent:
            text = f"{arrow} {value:+.2f}%"
        else:
            text = f"{arrow} ${value:+,.2f}"
        return green(text) if COLORS_ENABLED else text
    elif value < 0:
        arrow = "▼"
        if is_percent:
            text = f"{arrow} {value:+.2f}%"
        else:
            text = f"{arrow} ${value:+,.2f}"
        return red(text) if COLORS_ENABLED else text
    else:
        if is_percent:
            return "  0.00%"
        else:
            return "  $0.00"


def progress_bar(
    current: float,
    total: float,
    width: int = 30,
    fill_char: str = "█",
    empty_char: str = "░",
) -> str:
    """
    Create a progress bar.

    Args:
        current: Current value
        total: Total/max value
        width: Width of the bar in characters
        fill_char: Character for filled portion
        empty_char: Character for empty portion

    Returns:
        Progress bar string
    """
    if total <= 0:
        percent = 0
    else:
        percent = min(current / total, 1.0)

    filled = int(width * percent)
    empty = width - filled

    bar = fill_char * filled + empty_char * empty
    percent_text = f"{percent * 100:.0f}%"

    if COLORS_ENABLED:
        bar = cyan(bar)

    return f"[{bar}] {percent_text}"


def header(text: str, width: int = 70, char: str = "═") -> str:
    """Create a styled header."""
    line = char * width
    if COLORS_ENABLED:
        return f"{bold(line)}\n{bold(text)}\n{bold(line)}"
    return f"{line}\n{text}\n{line}"


def subheader(text: str, width: int = 70, char: str = "─") -> str:
    """Create a styled subheader."""
    line = char * width
    if COLORS_ENABLED:
        return f"{dim(line)}\n{bold(text)}\n{dim(line)}"
    return f"{line}\n{text}\n{line}"


def status_badge(status: str) -> str:
    """Create a colored status badge."""
    status_lower = status.lower()

    if status_lower in ('up', 'profit', 'gain', 'positive', 'active', 'ok', 'good'):
        return green(f"● {status}")
    elif status_lower in ('down', 'loss', 'negative', 'error', 'bad', 'critical'):
        return red(f"● {status}")
    elif status_lower in ('warning', 'pending', 'triggered'):
        return yellow(f"● {status}")
    else:
        return blue(f"● {status}")


def sparkline(values: list, width: int = 10) -> str:
    """
    Create a simple sparkline from values.

    Args:
        values: List of numeric values
        width: Target width (will sample if needed)

    Returns:
        Sparkline string
    """
    if not values:
        return ""

    # Sample if too many values
    if len(values) > width:
        step = len(values) / width
        values = [values[int(i * step)] for i in range(width)]

    chars = " ▁▂▃▄▅▆▇█"
    min_val = min(values)
    max_val = max(values)

    if max_val == min_val:
        return chars[4] * len(values)

    result = ""
    for val in values:
        normalized = (val - min_val) / (max_val - min_val)
        idx = int(normalized * (len(chars) - 1))
        result += chars[idx]

    return result


def table_row(columns: list, widths: list, alignments: Optional[list] = None) -> str:
    """
    Format a table row with proper column widths.

    Args:
        columns: List of column values
        widths: List of column widths
        alignments: List of alignments ('l', 'r', 'c') - default left

    Returns:
        Formatted row string
    """
    if alignments is None:
        alignments = ['l'] * len(columns)

    parts = []
    for i, (col, width, align) in enumerate(zip(columns, widths, alignments)):
        col_str = str(col)
        # Strip ANSI codes for width calculation
        visible_len = len(col_str.replace('\033[', '').split('m')[-1]) if '\033[' in col_str else len(col_str)
        # Actually, let's just use the raw length for now

        if align == 'r':
            parts.append(f"{col_str:>{width}}")
        elif align == 'c':
            parts.append(f"{col_str:^{width}}")
        else:
            parts.append(f"{col_str:<{width}}")

    return "  ".join(parts)


# Box drawing characters for nice borders
class Box:
    """Box drawing characters."""
    HORIZONTAL = "─"
    VERTICAL = "│"
    TOP_LEFT = "┌"
    TOP_RIGHT = "┐"
    BOTTOM_LEFT = "└"
    BOTTOM_RIGHT = "┘"
    T_DOWN = "┬"
    T_UP = "┴"
    T_RIGHT = "├"
    T_LEFT = "┤"
    CROSS = "┼"

    # Double lines
    DOUBLE_HORIZONTAL = "═"
    DOUBLE_VERTICAL = "║"


def box(text: str, padding: int = 1) -> str:
    """
    Wrap text in a box.

    Args:
        text: Text to wrap
        padding: Internal padding

    Returns:
        Boxed text
    """
    lines = text.split('\n')
    max_width = max(len(line) for line in lines)

    top = Box.TOP_LEFT + Box.HORIZONTAL * (max_width + padding * 2) + Box.TOP_RIGHT
    bottom = Box.BOTTOM_LEFT + Box.HORIZONTAL * (max_width + padding * 2) + Box.BOTTOM_RIGHT

    result = [top]
    for line in lines:
        padded = " " * padding + line.ljust(max_width) + " " * padding
        result.append(Box.VERTICAL + padded + Box.VERTICAL)
    result.append(bottom)

    return "\n".join(result)
