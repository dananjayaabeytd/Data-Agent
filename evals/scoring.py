"""Result-set comparison for execution accuracy. Pure functions with no agent imports."""

import math
from datetime import date, datetime
from decimal import Decimal
from typing import Any


def _normalize(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (Decimal, float)):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, str):
        return value.strip().lower()
    return value


def _values_equal(actual: Any, expected: Any) -> bool:
    if isinstance(actual, bool) or isinstance(expected, bool):
        return type(actual) is type(expected) and actual == expected  # True == 1 otherwise
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        # Tolerates the agent rounding to 2 decimals (e.g. 64.57 vs 64.5745).
        return math.isclose(actual, expected, rel_tol=1e-3, abs_tol=0.006)
    return actual == expected


def _row_covers(actual_row: list, expected_row: list) -> bool:
    """True when every expected value appears in the actual row; extra columns are allowed."""
    remaining = list(actual_row)
    for expected in expected_row:
        for index, actual in enumerate(remaining):
            if _values_equal(actual, expected):
                del remaining[index]
                break
        else:
            return False
    return True


def results_match(expected_rows: list, actual_rows: list, ordered: bool = False) -> bool:
    """Compare result sets: same row count, and each expected row is covered by an actual row.

    The reference SQL selects only the columns that matter, so the agent may add context
    columns such as names. Row order matters only when the question asks for a ranking.
    """
    expected = [[_normalize(value) for value in row] for row in expected_rows]
    actual = [[_normalize(value) for value in row] for row in actual_rows]
    if len(expected) != len(actual):
        return False
    if ordered:
        return all(_row_covers(a, e) for a, e in zip(actual, expected))
    unused = list(actual)
    for expected_row in expected:
        for index, actual_row in enumerate(unused):
            if _row_covers(actual_row, expected_row):
                del unused[index]
                break
        else:
            return False
    return True
