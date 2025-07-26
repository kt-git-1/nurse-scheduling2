"""Initial schedule assignment using OR-Tools."""
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd
from ortools.sat.python import cp_model

from utils.constants import NURSES, SHIFT_TYPES, NUM_DAYS, REQUEST_CSV_PATH
from utils.reader import load_request_csv, parse_shift_requests


BoolVar = cp_model.IntVar


def build_hard_constraints(model: cp_model.CpModel, x: Dict[Tuple[int, int, int], BoolVar], data: Dict) -> None:
    """Add hard constraints H1-H13 to the CP-SAT model.

    Parameters
    ----------
    model : cp_model.CpModel
        The optimization model.
    x : dict
        Mapping from (nurse_index, day, shift_index) to BoolVar.
    data : dict
        Additional data such as parsed requests.
    """
    num_nurses = len(data["nurses"])
    num_days = data["num_days"]
    num_shifts = len(data["shift_types"])

    # Indices for special shifts
    night_idx = data["shift_types"].index("夜")
    off_idx = data["shift_types"].index("×")

    requests: pd.DataFrame | None = data.get("requests")

    # H1: Each nurse must have exactly one shift per day
    for n in range(num_nurses):
        for d in range(1, num_days + 1):
            model.Add(sum(x[(n, d, s)] for s in range(num_shifts)) == 1)

    # H5: Exactly one night shift per day
    for d in range(1, num_days + 1):
        model.Add(sum(x[(n, d, night_idx)] for n in range(num_nurses)) == 1)

    # H6: After a night shift, the next day must be '×'
    for n in range(num_nurses):
        for d in range(1, num_days):
            model.Add(x[(n, d, night_idx)] <= x[(n, d + 1, off_idx)])

    # H9: Respect shift requests (symbols already converted)
    if requests is not None:
        for n, nurse in enumerate(data["nurses"]):
            if nurse not in requests.index:
                continue
            for d in range(1, num_days + 1):
                col = f"day_{d}"
                if col not in requests.columns:
                    continue
                req_shift = requests.loc[nurse, col]
                if pd.notna(req_shift) and req_shift in data["shift_types"]:
                    req_idx = data["shift_types"].index(req_shift)
                    model.Add(x[(n, d, req_idx)] == 1)

    # Placeholder for additional constraints H2, H3, H4, H7, H8, H10-H13
    # These would incorporate more complex business rules such as weekend
    # restrictions or minimum rest periods.


def solve_initial_model(request_csv_path: str | Path = REQUEST_CSV_PATH) -> pd.DataFrame:
    """Solve the hard constraint model and return the initial schedule."""
    df_requests = parse_shift_requests(load_request_csv(request_csv_path))
    df_requests.set_index("nurse", inplace=True)

    model = cp_model.CpModel()

    num_nurses = len(NURSES)
    num_days = NUM_DAYS
    num_shifts = len(SHIFT_TYPES)

    x: Dict[Tuple[int, int, int], BoolVar] = {}
    for n in range(num_nurses):
        for d in range(1, num_days + 1):
            for s in range(num_shifts):
                x[(n, d, s)] = model.NewBoolVar(f"x_{n}_{d}_{s}")

    data = {
        "nurses": NURSES,
        "num_days": num_days,
        "shift_types": SHIFT_TYPES,
        "requests": df_requests,
    }

    build_hard_constraints(model, x, data)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10
    status = solver.Solve(model)

    df_result = pd.DataFrame(
        index=NURSES,
        columns=[f"day_{d}" for d in range(1, num_days + 1)],
        data="",
    )

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for n, nurse in enumerate(NURSES):
            for d in range(1, num_days + 1):
                for s, code in enumerate(SHIFT_TYPES):
                    if solver.Value(x[(n, d, s)]):
                        df_result.loc[nurse, f"day_{d}"] = code
                        break
    return df_result
