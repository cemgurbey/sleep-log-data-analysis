"""Data ingestion: load survey workbooks and validate date/time quality."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from sleeplog.config import COLUMN_MAPPINGS
from sleeplog.parsing import excel_column_number, parse_time_entry


def merge_two_level_headers(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten two-level MultiIndex headers, propagating merged category cells."""
    flattened = []
    current_parent = ""
    for col in df.columns:
        if isinstance(col, tuple):
            first = str(col[0]).strip() if col[0] is not None else ""
            second = str(col[1]).strip() if col[1] is not None else ""
            if first and "unnamed" not in first.lower():
                current_parent = first
            if not second or "unnamed" in second.lower():
                flattened.append(current_parent)
            else:
                flattened.append(f"{current_parent} {second}".strip() if current_parent else second)
        else:
            flattened.append(str(col).strip())
    df.columns = flattened
    return df


def load_survey_dataframe(
    filename: str | Path, survey_name: str, error_log: list[str]
) -> pd.DataFrame:
    """Load an Excel/CSV survey file and standardize its column headers."""
    path = Path(filename)
    if not filename or not path.exists():
        msg = f"Warning: {survey_name} file '{filename}' was not found. Please verify filepath."
        print(f"Warning: {msg}")
        error_log.append(msg)
        return pd.DataFrame()
    try:
        if path.suffix.lower() == ".csv":
            df = pd.read_csv(path)
        else:
            df = pd.read_excel(path, header=[0, 1])
            df = merge_two_level_headers(df)
        print(f"Loaded {survey_name} survey: {df.shape[0]} rows, {df.shape[1]} columns.")
        return df
    except Exception as err:
        msg = f"Error reading {survey_name} file '{filename}': {err}"
        print(f"Error: {msg}")
        error_log.append(msg)
        return pd.DataFrame()


def validate_survey_entries(
    df: pd.DataFrame,
    participant_col_idx: int,
    date_col_idx: int,
    time_col_indices: list[int],
) -> pd.DataFrame:
    """Flag rows with corrupt dates or unparseable times.

    Legitimate blanks/missing data are not flagged as errors.
    """
    if df.empty:
        return pd.DataFrame()

    p_col = df.columns[participant_col_idx]
    d_col = df.columns[date_col_idx]
    time_cols = [df.columns[i] for i in time_col_indices if i < df.shape[1]]

    anomalies = []
    for row_idx, row in df.iterrows():
        p_val = row[p_col]
        d_val = row[d_col]

        date_bad = False
        if pd.isna(d_val) or str(d_val).strip() == "":
            date_bad = True
        else:
            try:
                # Parse the raw value directly: handles datetime objects without
                # the dayfirst warning, and DD/MM/YYYY strings as before.
                pd.to_datetime(d_val, dayfirst=True)
            except Exception:
                date_bad = True

        bad_times = {}
        for c in time_cols:
            val = row[c]
            if pd.notna(val) and str(val).strip() not in ("", "NaT", "nan"):
                if parse_time_entry(val) is None:
                    bad_times[c] = val

        if date_bad or bad_times:
            entry = {"row_index": row_idx + 1, p_col: p_val, d_col: d_val, "date_error": date_bad}
            for c in time_cols:
                entry[c] = bad_times.get(c, "")
            anomalies.append(entry)

    return pd.DataFrame(anomalies)


def standardize_participant_ids(df: pd.DataFrame, participant_col_idx: int) -> pd.DataFrame:
    """Coerce participant numbers to int, treating blanks as 0 (excluded later)."""
    df = df.copy()
    col_name = df.columns[participant_col_idx]
    df[col_name] = pd.to_numeric(df[col_name], errors="coerce").fillna(0).astype(int)
    return df


def ingest(
    morning_path: str | Path, evening_path: str | Path, error_log: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load both surveys, run QA validation, return (morning, evening, invalid_m, invalid_e)."""
    df_morning = load_survey_dataframe(morning_path, "Morning", error_log)
    df_evening = load_survey_dataframe(evening_path, "Evening", error_log)

    p_m_idx = excel_column_number(COLUMN_MAPPINGS["MORNING_PARTICIPANT_NUMBER"])
    p_e_idx = excel_column_number(COLUMN_MAPPINGS["EVENING_PARTICIPANT_NUMBER"])
    d_m_idx = excel_column_number(COLUMN_MAPPINGS["MORNING_DATE"])
    d_e_idx = excel_column_number(COLUMN_MAPPINGS["EVENING_DATE"])

    df_morning_invalid = pd.DataFrame()
    df_evening_invalid = pd.DataFrame()

    if not df_morning.empty and p_m_idx >= 0 and d_m_idx >= 0:
        time_cols_m = [
            excel_column_number(COLUMN_MAPPINGS[k])
            for k in ("IN_BED", "BEDTIME", "WOKETIME", "OUT_BED")
        ]
        df_morning_invalid = validate_survey_entries(df_morning, p_m_idx, d_m_idx, time_cols_m)
        df_morning = standardize_participant_ids(df_morning, p_m_idx)

    if not df_evening.empty and p_e_idx >= 0 and d_e_idx >= 0:
        time_cols_e = [
            excel_column_number(COLUMN_MAPPINGS[k])
            for k in ("SCHOOL_START", "SCHOOL_END", "HOME_ARRIVAL")
        ]
        df_evening_invalid = validate_survey_entries(df_evening, p_e_idx, d_e_idx, time_cols_e)
        df_evening = standardize_participant_ids(df_evening, p_e_idx)

    print(
        f"Quality assurance: {len(df_morning_invalid)} morning and "
        f"{len(df_evening_invalid)} evening entries flagged."
    )
    return df_morning, df_evening, df_morning_invalid, df_evening_invalid
