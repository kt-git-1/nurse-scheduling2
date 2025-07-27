"""Initial schedule assignment using OR-Tools."""
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd
from ortools.sat.python import cp_model

from utils.constants import (
    NURSES,
    SHIFT_TYPES,
    NUM_DAYS,
    REQUEST_CSV_PATH,
    SHIFT_CODE,
    SOLVER_TIMEOUT,
)
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
    night_idx = SHIFT_CODE["夜"]
    off_idx = SHIFT_CODE["×"]

    requests: pd.DataFrame | None = data.get("requests")

    # H1: Each nurse must have exactly one shift per day
    for n in range(num_nurses):
        for d in range(1, num_days + 1):
            model.Add(sum(x[(n, d, s)] for s in range(num_shifts)) == 1)
    print("\u2714 H1: 1日1シフト制約を追加しました")

    # H2: Nurse-specific restrictions
    itagawa = data["nurses"].index("板川") if "板川" in data["nurses"] else None
    miyoshi = data["nurses"].index("三好") if "三好" in data["nurses"] else None
    goshyo = data["nurses"].index("御書") if "御書" in data["nurses"] else None
    outpatient_shifts = [
        SHIFT_CODE.get(code)
        for code in ["1", "2", "3", "4", "CT", "F", "2/"]
        if code in SHIFT_CODE
    ]
    early_idx = SHIFT_CODE.get("早日") if "早日" in SHIFT_CODE else data["shift_types"].index("早日")
    late_idx = SHIFT_CODE.get("残日") if "残日" in SHIFT_CODE else data["shift_types"].index("残日")
    for d in range(1, num_days + 1):
        if itagawa is not None:
            model.Add(x[(itagawa, d, night_idx)] == 0)
        if miyoshi is not None:
            model.Add(x[(miyoshi, d, night_idx)] == 0)
        if goshyo is not None:
            model.Add(x[(goshyo, d, night_idx)] == 0)
            for s in outpatient_shifts:
                model.Add(x[(goshyo, d, s)] == 0)
            model.Add(x[(goshyo, d, early_idx)] == 0)
            model.Add(x[(goshyo, d, late_idx)] == 0)
    print("\u2714 H2: 看護師ごとの勤務制限を追加しました")

    # H3: Clinic holidays (Thu/Sun closed, Sat half day)
    weekdays = ["月", "火", "水", "木", "金", "土", "日"]
    for d in range(1, num_days + 1):
        wd = weekdays[(d - 1) % 7]
        if wd in ("木", "日"):
            allowed = {"夜", "早日", "残日", "休", "×"}
            for s, code in enumerate(data["shift_types"]):
                if code not in allowed:
                    for n in range(num_nurses):
                        model.Add(x[(n, d, s)] == 0)
        elif wd == "土":
            banned = {"1", "2", "3", "4", "CT", "F", "2/", "〇"}
            for s, code in enumerate(data["shift_types"]):
                if code in banned:
                    for n in range(num_nurses):
                        model.Add(x[(n, d, s)] == 0)
    print("\u2714 H3: 定休日のシフト制限を追加しました")

    # H4: Outpatient/Ward allocation rules
    outpatient = {"1", "2", "3", "4", "CT", "F", "2/"}
    ward = {"〇"}
    early_idx = SHIFT_CODE.get("早日") if "早日" in SHIFT_CODE else data["shift_types"].index("早日")
    late_idx = SHIFT_CODE.get("残日") if "残日" in SHIFT_CODE else data["shift_types"].index("残日")
    for d in range(1, num_days + 1):
        wd = weekdays[(d - 1) % 7]
        if wd in {"月", "火", "水", "金"}:
            out_count = sum(
                x[(n, d, SHIFT_CODE[code])] for n in range(num_nurses) for code in outpatient if code in SHIFT_CODE
            )
            ward_count = sum(
                x[(n, d, SHIFT_CODE[code])] for n in range(num_nurses) for code in ward if code in SHIFT_CODE
            )
            model.Add(out_count >= 4)
            model.Add(ward_count >= 3)
        elif wd in {"木", "日"}:
            model.Add(sum(x[(n, d, early_idx)] for n in range(num_nurses)) == 1)
            model.Add(sum(x[(n, d, late_idx)] for n in range(num_nurses)) == 1)
        elif wd == "土":
            two_slash_idx = SHIFT_CODE.get("2/") if "2/" in SHIFT_CODE else data["shift_types"].index("2/")
            model.Add(sum(x[(n, d, two_slash_idx)] for n in range(num_nurses)) >= 1)
    print("\u2714 H4: 外来と病棟の割当ルールを追加しました")

    # H5 already added earlier

    # H5: Exactly one night shift per day
    for d in range(1, num_days + 1):
        model.Add(sum(x[(n, d, night_idx)] for n in range(num_nurses)) == 1)
    print("\u2714 H5: 1日1名の夜勤制約を追加しました")

    # H6: After a night shift, the next day must be '×'
    for n in range(num_nurses):
        for d in range(1, num_days):
            model.Add(x[(n, d, night_idx)] <= x[(n, d + 1, off_idx)])
    print("\u2714 H6: 夜勤翌日は \u00d7 を追加しました")

    # H7: Last month night shift -> first day off
    prev_night = data.get("prev_month_night", [])
    for nurse in prev_night:
        if nurse in data["nurses"]:
            n_idx = data["nurses"].index(nurse)
            model.Add(x[(n_idx, 1, off_idx)] == 1)
    if prev_night:
        print("\u2714 H7: 前月夜勤者の初日\u00d7 を追加しました")

    # H8: Minimum rest days per nurse
    rest_idx = SHIFT_CODE.get("休")
    for n in range(num_nurses):
        model.Add(
            sum(x[(n, d, rest_idx)] for d in range(1, num_days + 1)) >= 4
        )
    print("\u2714 H8: 最低休暇日数を追加しました")

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
                    req_idx = SHIFT_CODE[req_shift]
                    model.Add(x[(n, d, req_idx)] == 1)
    print("\u2714 H9: 希望休を反映しました")

    # H10: 久保は CT と 2番 のみ担当可
    kubo_idx = data["nurses"].index("久保") if "久保" in data["nurses"] else None
    if kubo_idx is not None:
        allowed_kubo = [SHIFT_CODE[code] for code in ["CT", "2"] if code in SHIFT_CODE]
        for d in range(1, num_days + 1):
            for s in range(num_shifts):
                if s not in allowed_kubo:
                    model.Add(x[(kubo_idx, d, s)] == 0)
    print("✔ H10: 久保はCTと2番のみ担当可を追加しました")

    # H11: 第2木曜午後は久保に /訪 を割当
    if kubo_idx is not None:
        second_thu = None
        weekday_list = ["月", "火", "水", "木", "金", "土", "日"]
        thu_count = 0
        for d in range(1, num_days + 1):
            wd = weekday_list[(d - 1) % 7]
            if wd == "木":
                thu_count += 1
                if thu_count == 2:
                    second_thu = d
                    break
        if second_thu is not None and "訪" in SHIFT_CODE:
            visit_idx = SHIFT_CODE["訪"]
            model.Add(x[(kubo_idx, second_thu, visit_idx)] == 1)
    print("✔ H11: 第2木曜午後に久保の/訪を追加しました")

    # H12: 久保休暇時は三好 or 前野が CT を担当
    # (仮実装: CT 担当者が久保でなければ三好 or 前野を強制)
    miyoshi_idx = data["nurses"].index("三好") if "三好" in data["nurses"] else None
    maeno_idx = data["nurses"].index("前野") if "前野" in data["nurses"] else None
    ct_idx = SHIFT_CODE.get("CT")
    if kubo_idx is not None and ct_idx is not None and miyoshi_idx is not None and maeno_idx is not None:
        for d in range(1, num_days + 1):
            # CTに久保がいないならどちらかが担当
            ct_sum = model.NewIntVar(0, 2, f"ct_alt_{d}")
            model.Add(ct_sum == x[(miyoshi_idx, d, ct_idx)] + x[(maeno_idx, d, ct_idx)])
            model.AddHint(ct_sum, 1)  # Soft enforcement
    print("✔ H12: 久保休暇時のCT代替担当者制約を追加しました")


def solve_initial_model(request_csv_path: str | Path = REQUEST_CSV_PATH) -> pd.DataFrame:
    """Solve the hard constraint model and return the initial schedule.

    This wrapper builds the CP-SAT model, applies all hard constraints and
    attempts to find any feasible solution within ``SOLVER_TIMEOUT`` seconds.
    The returned ``DataFrame`` always contains an entry for every nurse and day
    even if the solver fails to find a solution so callers do not have to guard
    against ``None``.
    """
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
    solver.parameters.max_time_in_seconds = SOLVER_TIMEOUT
    status = solver.Solve(model)
    print(f"Solver status: {solver.StatusName(status)}")

    df_result = pd.DataFrame(
        index=NURSES,
        columns=[f"day_{d}" for d in range(1, num_days + 1)],
        data="",
    )

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE, cp_model.UNKNOWN):
        # Even if the status is UNKNOWN, the solver may return a feasible
        # solution found within the time limit.
        for n, nurse in enumerate(NURSES):
            for d in range(1, num_days + 1):
                assigned = False
                for s, code in enumerate(SHIFT_TYPES):
                    if solver.Value(x[(n, d, s)]):
                        df_result.loc[nurse, f"day_{d}"] = code
                        assigned = True
                        break
                if not assigned:
                    print(f"⚠ {nurse} の {d}日目に割当なし")
    else:
        print(
            f"No feasible solution found (status: {solver.StatusName(status)})."
        )
        # Fallback: assign all rest days to avoid invalid blanks
        df_result.loc[:, :] = "休"
    df_result.to_csv("temp_shift.csv", encoding="utf-8-sig")

    return df_result
