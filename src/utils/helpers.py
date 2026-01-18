"""
Utility helper functions.
"""

from typing import Any, Optional, Dict


def format_number(n: float, decimals: int = 2) -> str:
    """Format a number with K/M/B suffix."""
    if n >= 1_000_000_000:
        return f"{n/1_000_000_000:.{decimals}f}B"
    elif n >= 1_000_000:
        return f"{n/1_000_000:.{decimals}f}M"
    elif n >= 1_000:
        return f"{n/1_000:.{decimals}f}K"
    else:
        return f"{n:.{decimals}f}"


def format_price(price: float) -> str:
    """Format a price with appropriate decimal places."""
    if price >= 1:
        return f"${price:.2f}"
    elif price >= 0.01:
        return f"${price:.4f}"
    elif price >= 0.0001:
        return f"${price:.6f}"
    else:
        return f"${price:.8f}"


def safe_get(
    d: Dict[str, Any],
    *keys: str,
    default: Any = None,
) -> Any:
    """
    Safely get nested dictionary values.

    Args:
        d: Dictionary to search
        *keys: Keys to traverse
        default: Default value if not found

    Returns:
        Value or default
    """
    for key in keys:
        if isinstance(d, dict):
            d = d.get(key, default)
        else:
            return default
    return d
