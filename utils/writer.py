"""Excel writer for nurse scheduling results."""
from typing import Any

import pandas as pd
from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet


TEMPLATE_PATH = "data/shift_template.xlsx"


def fill_shift_cells(ws: Worksheet, assignments: pd.DataFrame) -> None:
    """Fill each cell in the template sheet with the shift assignments.

    Parameters
    ----------
    ws : Worksheet
        Target worksheet ("シフト表").
    assignments : pandas.DataFrame
        DataFrame indexed by nurse names with columns day_1, day_2, ...
    """
    for row_idx, nurse in enumerate(assignments.index, start=2):
        for col_idx, day in enumerate(assignments.columns, start=2):
            value = assignments.loc[nurse, day]
            ws.cell(row=row_idx, column=col_idx, value=value)


def write_to_excel(df_result: pd.DataFrame, output_path: str, template_path: str = TEMPLATE_PATH) -> None:
    """Write the optimized schedule to an Excel file based on a template.

    Parameters
    ----------
    df_result : pandas.DataFrame
        DataFrame of shift assignments where index is nurse names and
        columns correspond to days (day_1, day_2, ...).
    output_path : str
        Path to save the resulting Excel file.
    template_path : str, optional
        Path to the Excel template, by default ``data/shift_template.xlsx``.
    """
    wb = load_workbook(template_path)
    ws = wb["シフト表"]
    fill_shift_cells(ws, df_result)
    wb.save(output_path)
