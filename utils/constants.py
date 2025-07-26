# -*- coding: utf-8 -*-
"""Constants for nurse scheduling."""

from pathlib import Path

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

# 看護師名のリスト
NURSES = [
    "樋渡",
    "中山",
    "三好",
    "川原田",
    "板川",
    "友枝",
    "奥平",
    "前野",
    "森園",
    "御書",
    "久保",
    "小嶋",
    "久保（千）",
    "田浦",
]

# 勤務内容の種類
SHIFT_TYPES = [
    "休",
    "夜",
    "早",
    "残",
    "〇",
    "1",
    "2",
    "3",
    "4",
    "×",
    "/訪",
    "CT",
    "早日",
    "残日",
    "1/",
    "2/",
    "3/",
    "4/",
    "/休",
    "休/",
    "F",
    "2・CT",
]

# Mapping from shift code string to its index for safety
SHIFT_CODE = {code: idx for idx, code in enumerate(SHIFT_TYPES)}

# 曜日ごとの休み設定
# 木・日: 全休, 土: 午後休
HOLIDAY_MAP = {
    "木": "休",
    "日": "休",
    "土": "午後休",
}

# 対象月（例: 8月）
TARGET_MONTH = 8

# 月の日数
NUM_DAYS = 31

# 夜勤希望者（現状空のリスト、必要に応じて設定）
NIGHT_SHIFT_PREFERRED = []

# Common file paths
REQUEST_CSV_PATH = DATA_DIR / "req_shift_8.csv"
TEMPLATE_PATH = DATA_DIR / "shift_template.xlsx"
OUTPUT_EXCEL_PATH = BASE_DIR / "shift_output.xlsx"

# Solver time limit in seconds
SOLVER_TIMEOUT = 10
