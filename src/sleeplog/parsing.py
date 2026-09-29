"""Robust parsing utilities for survey time entries and circular time math."""

from __future__ import annotations

import math
import re
from datetime import datetime
from datetime import time as dt_time
from typing import Any

import pandas as pd

from sleeplog.config import DID_NOT_ANSWER_TIME_CODE


def excel_column_number(name: str) -> int:
    """Convert an Excel column letter to a 0-based index ('A' -> 0, 'AA' -> 26, 'NONE' -> -1)."""
    if not name or not isinstance(name, str) or name.strip().upper() == "NONE":
        return -1
    col_str = name.strip().upper()
    n = 0
    for char in col_str:
        if not ("A" <= char <= "Z"):
            return -1
        n = n * 26 + (ord(char) - ord("A") + 1)
    return n - 1


def parse_time_entry(val: Any) -> dt_time | None:
    """Parse raw survey values into ``datetime.time``.

    Supports 24h ('23:15'), 12h AM/PM ('11:15 PM'), dot notation ('23.15'),
    and datetime/Timestamp objects. Returns None if blank or unparseable.
    """
    if val is None or pd.isna(val):
        return None
    if isinstance(val, dt_time):
        return val
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.time()

    val_str = str(val).strip()
    if not val_str or val_str.lower() in ("nat", "nan", "none", ""):
        return None

    # Standardize time separators (e.g. '23.15' -> '23:15')
    clean = re.sub(r"(\d+)\.(\d+)", r"\1:\2", val_str)

    formats = [
        "%H:%M",
        "%H:%M:%S",
        "%I:%M %p",
        "%I:%M:%S %p",
        "%I:%M%p",
        "%I:%M:%S%p",
        "%H:%M %p",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(clean, fmt).time()
        except ValueError:
            continue

    # Regex extraction fallback for informal strings
    m = re.search(r"(\d{1,2}):(\d{2})", clean)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        is_pm = "pm" in clean.lower()
        is_am = "am" in clean.lower()
        if is_pm and h < 12:
            h += 12
        elif is_am and h == 12:
            h = 0
        if 0 <= h < 24 and 0 <= mn < 60:
            return dt_time(h, mn)

    return None


def format_time_hhmm(t_obj: dt_time | None, night_time: bool = False) -> str:
    """Format a time object as 'HH:MM' (24+ hour clock when night_time=True)."""
    if t_obj is None:
        return DID_NOT_ANSWER_TIME_CODE
    if night_time and t_obj.hour < 12:
        return f"{t_obj.hour + 24:02d}:{t_obj.minute:02d}"
    return f"{t_obj.hour:02d}:{t_obj.minute:02d}"


def time_offset_from_noon(t_val: Any) -> float | None:
    """Express a time as decimal hours elapsed since 12:00 PM (noon).

    Maps nocturnal sleep cycles continuously across midnight:
    12:00 PM -> 0.0, 11:00 PM -> 11.0, 12:00 AM -> 12.0, 01:00 AM -> 13.0.
    """
    t_obj = parse_time_entry(t_val)
    if t_obj is None:
        return None
    hrs = t_obj.hour + t_obj.minute / 60.0 + t_obj.second / 3600.0
    return (hrs - 12.0) if hrs >= 12.0 else (hrs + 12.0)


def offset_to_time_string(hours_offset: float, as_night_time: bool = False) -> str:
    """Convert hours elapsed from noon back into an 'HH:MM' time string."""
    if pd.isna(hours_offset) or math.isnan(hours_offset):
        return ""
    total = (12.0 + hours_offset) % 24.0
    h = int(total)
    m = int(round((total - h) * 60.0))
    if m == 60:
        h = (h + 1) % 24
        m = 0
    if as_night_time and h < 12 and hours_offset >= 12.0:
        return f"{h + 24:02d}:{m:02d}"
    return f"{h:02d}:{m:02d}"


def duration_hours_to_hhmm(hours: float) -> str:
    """Convert a standard-deviation duration (decimal hours) to 'HH:MM'."""
    if pd.isna(hours) or math.isnan(hours):
        return ""
    h = int(hours)
    m = int(round((hours - h) * 60.0))
    if m == 60:
        h += 1
        m = 0
    return f"{h:02d}:{m:02d}"
