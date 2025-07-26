from pathlib import Path
import pandas as pd

from .constants import NURSES


def load_request_csv(path: Path | str) -> pd.DataFrame:
    """Load the shift request CSV into a DataFrame."""
    df = pd.read_csv(path, encoding="utf-8")
    # The first two rows contain date and weekday information.
    df = df.iloc[2:].reset_index(drop=True)
    # Rename the first column to nurse name.
    df.rename(columns={df.columns[0]: "nurse"}, inplace=True)
    # Drop the last column if it's a notes column.
    if df.columns[-1] == "特記事項":
        df = df.iloc[:, :-1]
    # Rename day columns sequentially.
    for i, col in enumerate(df.columns[1:], start=1):
        df.rename(columns={col: f"day_{i}"}, inplace=True)
    return df


def parse_shift_requests(df: pd.DataFrame) -> pd.DataFrame:
    """Convert request symbols like ①~⑥ into internal codes."""
    mapping = {"①": "休", "②": "休", "③": "休", "④": "休", "⑤": "休", "⑥": "休"}
    return df.replace(mapping)
