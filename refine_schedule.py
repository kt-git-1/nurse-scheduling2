"""Refine schedule with soft constraints using OR-Tools."""
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd
from ortools.sat.python import cp_model

from utils.constants import (
    NURSES,
    SHIFT_TYPES,
    NUM_DAYS,
    NIGHT_SHIFT_PREFERRED,
    REQUEST_CSV_PATH,
)
from utils.reader import load_request_csv, parse_shift_requests
from initial_assignment import solve_initial_model, build_hard_constraints


BoolVar = cp_model.IntVar


def add_soft_constraints(
    model: cp_model.CpModel, x: Dict[Tuple[int, int, int], BoolVar], data: Dict
) -> None:
    """Add soft constraints S1-S5 to the objective function."""
    num_nurses = len(data["nurses"])
    num_days = data["num_days"]
    night_idx = data["shift_types"].index("夜")
    rest_idx = data["shift_types"].index("休")
    off_idx = data["shift_types"].index("×")
    penalties = []

    # S1: Each nurse should have around 13 days off ("休" or "×")
    for n in range(num_nurses):
        off_count = sum(x[(n, d, rest_idx)] for d in range(1, num_days + 1))
        off_count += sum(x[(n, d, off_idx)] for d in range(1, num_days + 1))
        diff = model.NewIntVar(0, num_days, f"off_diff_{n}")
        model.AddAbsEquality(diff, off_count - 13)
        penalties.append(diff)

    # S2: Preferred night shift nurses should work about 5 night shifts
    for n, nurse in enumerate(data["nurses"]):
        if nurse in data.get("night_shift_preferred", []):
            night_count = sum(x[(n, d, night_idx)] for d in range(1, num_days + 1))
            diff_night = model.NewIntVar(0, num_days, f"night_diff_{n}")
            model.Add(night_count - 5 <= diff_night)
            model.Add(5 - night_count <= diff_night)
            penalties.append(diff_night)

    # S3: Balance shift type counts overall (simple average target)
    total_slots = num_nurses * num_days
    avg_per_shift = total_slots // len(data["shift_types"])
    for s, code in enumerate(data["shift_types"]):
        total = sum(x[(n, d, s)] for n in range(num_nurses) for d in range(1, num_days + 1))
        diff_total = model.NewIntVar(0, total_slots, f"shift_diff_{s}")
        model.Add(total - avg_per_shift <= diff_total)
        model.Add(avg_per_shift - total <= diff_total)
        penalties.append(diff_total)

    # S4: Workers with night shifts should have at least one "4" shift (logical variable version)
    if "4" in data["shift_types"]:
        four_idx = data["shift_types"].index("4")
        for n in range(num_nurses):
            night_count = sum(x[(n, d, night_idx)] for d in range(1, num_days + 1))
            four_count = sum(x[(n, d, four_idx)] for d in range(1, num_days + 1))
            flag = model.NewBoolVar(f"four_penalty_{n}")

            has_night = model.NewBoolVar(f"has_night_{n}")
            no_four = model.NewBoolVar(f"no_four_{n}")

            model.Add(night_count >= 1).OnlyEnforceIf(has_night)
            model.Add(night_count < 1).OnlyEnforceIf(has_night.Not())

            model.Add(four_count == 0).OnlyEnforceIf(no_four)
            model.Add(four_count != 0).OnlyEnforceIf(no_four.Not())

            model.AddBoolAnd([has_night, no_four]).OnlyEnforceIf(flag)
            model.AddBoolOr([has_night.Not(), no_four.Not()]).OnlyEnforceIf(flag.Not())

            penalties.append(flag)

    # S5: Prefer not to deviate from the initial solution if provided
    if "initial_solution" in data:
        init_df: pd.DataFrame = data["initial_solution"]
        for n, nurse in enumerate(data["nurses"]):
            for d in range(1, num_days + 1):
                init_shift = init_df.loc[nurse, f"day_{d}"]
                if init_shift in data["shift_types"]:
                    idx = data["shift_types"].index(init_shift)
                    diff_var = model.NewBoolVar(f"change_{n}_{d}")
                    model.Add(x[(n, d, idx)] == 0).OnlyEnforceIf(diff_var)
                    model.Add(x[(n, d, idx)] == 1).OnlyEnforceIf(diff_var.Not())
                    penalties.append(diff_var)

    # ソフト制約ごとの重みを設定
    w1 = 3
    w2 = 2
    w3 = 1
    w4 = 2
    w5 = 1

    weighted_penalties = (
        sum(penalties[:num_nurses]) * w1 +  # S1: 休み
        sum(penalties[num_nurses:num_nurses * 2]) * w2 +  # S2: 夜勤希望
        sum(penalties[num_nurses * 2:num_nurses * 2 + len(data["shift_types"])]) * w3 +  # S3: シフト種
        sum(p for p in penalties if isinstance(p, cp_model.IntVar) and "four_penalty" in p.Name()) * w4 +  # S4
        sum(p for p in penalties if isinstance(p, cp_model.IntVar) and "change_" in p.Name()) * w5  # S5
    )
    model.Minimize(weighted_penalties)


def optimize_final_schedule(
    request_csv_path: Path | str = REQUEST_CSV_PATH,
) -> pd.DataFrame:
    """Optimize the final schedule considering soft constraints."""
    initial_df = solve_initial_model(request_csv_path)

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
        "night_shift_preferred": NIGHT_SHIFT_PREFERRED,
        "initial_solution": initial_df,
    }

    build_hard_constraints(model, x, data)
    add_soft_constraints(model, x, data)

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
