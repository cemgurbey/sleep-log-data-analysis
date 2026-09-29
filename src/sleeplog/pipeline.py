"""Pipeline orchestration: ingest -> analyze -> export -> summarize."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from sleeplog.config import COLUMN_MAPPINGS, StudyConfig
from sleeplog.ingest import ingest
from sleeplog.parsing import excel_column_number
from sleeplog.transform import (
    build_circular_stats,
    build_completion_summary,
    build_longitudinal,
)

OUTPUT_FILES = [
    "AVERAGE_AND_SD_OUTPUTS.xlsx",
    "SL_OUTPUTS.xlsx",
    "SLx_OUTPUTS_ROW1.xlsx",
    "SLx_OUTPUTS_ROW2.xlsx",
    "SLx_OUTPUTS_ROW3.xlsx",
    "SLx_OUTPUTS_ROW4.xlsx",
    "INVALID_DATETIME_ENTRIES_MORNING.xlsx",
    "INVALID_DATETIME_ENTRIES_EVENING.xlsx",
]


def run(
    config: StudyConfig,
    morning_path: str | Path,
    evening_path: str | Path,
    out_dir: str | Path = "outputs",
) -> dict[str, Path]:
    """Run the full pipeline and write all output workbooks to ``out_dir``.

    Returns a mapping of output file name -> written path.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    error_log: list[str] = []

    print(f"Study window: {config.start_date:%d-%m-%Y} to {config.end_date:%d-%m-%Y}")
    print(
        f"Site: {config.location.name}, {config.location.region} "
        f"({config.location.latitude}, {config.location.longitude})"
    )

    df_morning, df_evening, df_morning_invalid, df_evening_invalid = ingest(
        morning_path, evening_path, error_log
    )

    p_m_idx = excel_column_number(COLUMN_MAPPINGS["MORNING_PARTICIPANT_NUMBER"])
    d_m_idx = excel_column_number(COLUMN_MAPPINGS["MORNING_DATE"])
    p_e_idx = excel_column_number(COLUMN_MAPPINGS["EVENING_PARTICIPANT_NUMBER"])
    d_e_idx = excel_column_number(COLUMN_MAPPINGS["EVENING_DATE"])

    sl_outputs = build_completion_summary(df_morning, p_m_idx, d_m_idx)
    print(f"Survey completion counts calculated for {len(sl_outputs)} participants.")

    average_and_sd = build_circular_stats(df_morning, p_m_idx, d_m_idx)
    print(f"Circular sleep statistics calculated for {len(average_and_sd)} participants.")

    row1, row2, row3, row4, all_participants = build_longitudinal(
        df_morning, df_evening, config, p_m_idx, d_m_idx, p_e_idx, d_e_idx
    )
    num_days = len(config.date_strings)
    print(
        f"Daily longitudinal datasets generated for {len(all_participants)} "
        f"participants across {num_days} study days."
    )

    export_mapping = {
        "AVERAGE_AND_SD_OUTPUTS.xlsx": average_and_sd,
        "SL_OUTPUTS.xlsx": sl_outputs,
        "SLx_OUTPUTS_ROW1.xlsx": row1,
        "SLx_OUTPUTS_ROW2.xlsx": row2,
        "SLx_OUTPUTS_ROW3.xlsx": row3,
        "SLx_OUTPUTS_ROW4.xlsx": row4,
        "INVALID_DATETIME_ENTRIES_MORNING.xlsx": df_morning_invalid,
        "INVALID_DATETIME_ENTRIES_EVENING.xlsx": df_evening_invalid,
    }

    written: dict[str, Path] = {}
    success_count = 0
    for out_name, out_df in export_mapping.items():
        dest = out_dir / out_name
        try:
            out_df.to_excel(dest, index=False)
            written[out_name] = dest
            success_count += 1
        except Exception as e:
            msg = f"Export Error: Failed to write '{out_name}': {e}"
            print(f"Error: {msg}")
            error_log.append(msg)

    (out_dir / "ERROR_LOG.txt").write_text(
        "\n".join(error_log) + "\n"
        if error_log
        else "Execution successful. No errors or warnings logged.\n",
        encoding="utf-8",
    )
    print(f"Export complete: {success_count}/{len(export_mapping)} spreadsheets exported.")

    _print_summary(
        config,
        all_participants,
        num_days,
        df_morning,
        df_evening,
        df_morning_invalid,
        df_evening_invalid,
        error_log,
        written,
    )
    return written


def _print_summary(
    config: StudyConfig,
    all_participants: list[int],
    num_days: int,
    df_morning: pd.DataFrame,
    df_evening: pd.DataFrame,
    df_morning_invalid: pd.DataFrame,
    df_evening_invalid: pd.DataFrame,
    error_log: list[str],
    written: dict[str, Path],
) -> None:
    print("=" * 65)
    print("             SLEEP LOG ANALYSIS PIPELINE SUMMARY")
    print("=" * 65)
    print(f"Participants analyzed:          {len(all_participants)}")
    print(
        f"Survey window:                  {config.start_date:%d-%m-%Y} to {config.end_date:%d-%m-%Y} ({num_days} days)"
    )
    print(f"Site for sun calculations:      {config.location.name} ({config.location.region})")
    print(f"Morning survey records:         {len(df_morning)} rows")
    print(f"Evening survey records:         {len(df_evening)} rows")
    print(f"Morning validation flags:       {len(df_morning_invalid)} rows")
    print(f"Evening validation flags:       {len(df_evening_invalid)} rows")
    print(f"Warnings / errors encountered:  {len(error_log)}")
    print("-" * 65)
    print("Files generated:")
    for fname in OUTPUT_FILES:
        path = written.get(fname)
        size = (
            f"{os.path.getsize(path) / 1024:6.1f} KB" if path and path.exists() else "not created"
        )
        print(f"  - {fname:<36} ({size})")
    print("=" * 65)
