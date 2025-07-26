"""Validation utilities for nurse scheduling."""

from typing import List

import pandas as pd

from .constants import SHIFT_TYPES


def validate_constraints(assignments: pd.DataFrame) -> List[str]:
    """Validate hard constraints for the schedule.

    Parameters
    ----------
    assignments : pandas.DataFrame
        DataFrame where index corresponds to nurse names and columns are
        day_1, day_2, ... with shift codes.

    Returns
    -------
    list of str
        A list containing description of each violation found.
    """
    violations: List[str] = []

    day_numbers = [int(col.split("_")[1]) for col in assignments.columns]
    max_day = max(day_numbers)

    for nurse in assignments.index:
        for col in assignments.columns:
            shift = assignments.loc[nurse, col]
            if shift not in SHIFT_TYPES:
                violations.append(
                    f"Invalid shift '{shift}' for {nurse} on {col}"
                )

        for day in day_numbers:
            if assignments.loc[nurse, f"day_{day}"] == "夜" and day < max_day:
                next_shift = assignments.loc[nurse, f"day_{day + 1}"]
                if next_shift != "×":
                    violations.append(
                        f"Night shift not followed by '×' for {nurse} on day {day + 1}"
                    )

    return violations


def summarize_violations(violations: List[str], log_path: str = "violation_log.txt") -> None:
    """Output the list of violations and save them to a log file."""
    if not violations:
        message = "No violations found."
        print(message)
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(message + "\n")
        return

    for msg in violations:
        print(msg)
    with open(log_path, "w", encoding="utf-8") as f:
        for msg in violations:
            f.write(msg + "\n")
