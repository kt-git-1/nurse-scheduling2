import pandas as pd
from pathlib import Path

from utils.reader import load_request_csv, parse_shift_requests
from initial_assignment import solve_initial_model
from refine_schedule import optimize_final_schedule
from utils.writer import write_to_excel
from utils.validator import validate_constraints, summarize_violations
from utils.constants import REQUEST_CSV_PATH, OUTPUT_EXCEL_PATH


def main() -> None:
    """Run the full scheduling pipeline."""
    # Step 1: Load requests
    requests_df = parse_shift_requests(load_request_csv(REQUEST_CSV_PATH))
    requests_df.set_index("nurse", inplace=True)

    # Step 2: Generate initial hard-constrained schedule
    initial_schedule = solve_initial_model(REQUEST_CSV_PATH)

    # Step 3: Optimize final schedule with soft constraints
    final_schedule = optimize_final_schedule(REQUEST_CSV_PATH)

    # Step 4: Write results to Excel
    write_to_excel(final_schedule, OUTPUT_EXCEL_PATH)

    # Step 5: Validate and summarize violations
    violations = validate_constraints(final_schedule)
    summarize_violations(violations)


if __name__ == "__main__":
    main()
