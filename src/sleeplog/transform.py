"""Analysis engine: completion summaries, circular sleep statistics, and the
longitudinal SL1..SL{N} daily datasets (ROW1–ROW4)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from sleeplog.astro import precompute_astral_data
from sleeplog.config import (
    COLUMN_MAPPINGS,
    DAY_TYPE_FRISAT,
    DAY_TYPE_SUNDAY,
    DAY_TYPE_WEEKDAY,
    DID_NOT_ANSWER_CODE,
    DID_NOT_ATTEND_CODE,
    EARLY_TERM_DAY1_KEYS,
    EARLY_TERM_LASTDAY_KEYS,
    EARLY_TERMINATION_CODE,
    HOURLY_EVENING,
    HOURLY_MORNING,
    POMS_ITEMS,
    POMS_SUBSCALES,
    SPECIFY_COLUMNS,
    StudyConfig,
)
from sleeplog.decoders import FUNCTION_MAPPER
from sleeplog.parsing import (
    duration_hours_to_hhmm,
    excel_column_number,
    offset_to_time_string,
    time_offset_from_noon,
)

# ---------------------------------------------------------------------------
# 5.1 Weekday & weekend survey completion summary (SL_OUTPUTS)
# ---------------------------------------------------------------------------


def build_completion_summary(df_morning: pd.DataFrame, p_m_idx: int, d_m_idx: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if not df_morning.empty and p_m_idx >= 0 and d_m_idx >= 0:
        p_col = df_morning.columns[p_m_idx]
        d_col = df_morning.columns[d_m_idx]
        for participant_number, p_df in df_morning.groupby(p_col):
            if participant_number == 0:
                continue  # exclude non-participant/separator rows
            dates = pd.to_datetime(p_df[d_col], dayfirst=True, errors="coerce").dropna()
            rows.append(
                {
                    "participant_number": participant_number,
                    "SL_pre_weekdays_selfreport": int((dates.dt.dayofweek < 4).sum()),
                    "SL_pre_weekends_selfreport": int((dates.dt.dayofweek >= 4).sum()),
                }
            )
    if not rows:
        return pd.DataFrame(
            columns=[
                "participant_number",
                "SL_pre_weekdays_selfreport",
                "SL_pre_weekends_selfreport",
            ]
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 5.2 Circular sleep statistics (AVERAGE_AND_SD_OUTPUTS)
# ---------------------------------------------------------------------------


def calculate_time_statistics(series: pd.Series, operation: str, is_bedtime: bool = False) -> str:
    """Circular mean / SD of sleep times via noon-anchored offsets."""
    offsets = series.apply(time_offset_from_noon).dropna()
    if len(offsets) == 0:
        return ""
    if operation == "AVERAGE":
        return offset_to_time_string(offsets.mean(), as_night_time=is_bedtime)
    if operation == "SD":
        if len(offsets) < 2:
            return ""
        return duration_hours_to_hhmm(offsets.std())
    return ""


OPERATIONS = ["AVERAGE", "SD"]
DAY_GROUPINGS = ["WEEK", "WEEKEND", "TOTAL", "WEEKWITHSUNDNIGHT", "WEEKENDWOSUNDNIGHT"]


def _stat_columns() -> list[str]:
    cols = ["participant_number"]
    for op in OPERATIONS:
        for grp in DAY_GROUPINGS:
            for unit in ("BEDTIME", "WOKETIME"):
                cols.append(f"SL_pre_{unit}_{op}_{grp}_selfreport")
    for op in OPERATIONS:
        for grp in DAY_GROUPINGS:
            for unit in ("IN_BED", "OUT_BED"):
                cols.append(f"SL_pre_{unit}_{op}_{grp}_selfreport")
    return cols


def build_circular_stats(df_morning: pd.DataFrame, p_m_idx: int, d_m_idx: int) -> pd.DataFrame:
    stat_columns = _stat_columns()
    stat_rows: list[dict[str, Any]] = []

    if not df_morning.empty and p_m_idx >= 0 and d_m_idx >= 0:
        p_col = df_morning.columns[p_m_idx]
        d_col = df_morning.columns[d_m_idx]

        def _unit_col(key: str, is_bed: bool) -> tuple[Any, bool]:
            idx = excel_column_number(COLUMN_MAPPINGS[key])
            col = df_morning.columns[idx] if 0 <= idx < df_morning.shape[1] else None
            return col, is_bed

        unit_col_map = {
            "BEDTIME": _unit_col("BEDTIME", True),
            "WOKETIME": _unit_col("WOKETIME", False),
            "IN_BED": _unit_col("IN_BED", True),
            "OUT_BED": _unit_col("OUT_BED", False),
        }

        for participant_number, p_df in df_morning.groupby(p_col):
            if participant_number == 0:
                continue
            p_df = p_df.copy()
            p_df["Parsed_Date"] = pd.to_datetime(p_df[d_col], dayfirst=True, errors="coerce")
            p_df = p_df.dropna(subset=["Parsed_Date"])
            p_df["Day_Of_Week"] = p_df["Parsed_Date"].dt.dayofweek

            subsets = {
                "WEEK": p_df[p_df["Day_Of_Week"] < 4],
                "WEEKEND": p_df[p_df["Day_Of_Week"] >= 4],
                "TOTAL": p_df,
                "WEEKWITHSUNDNIGHT": p_df[(p_df["Day_Of_Week"] < 4) | (p_df["Day_Of_Week"] == 6)],
                "WEEKENDWOSUNDNIGHT": p_df[(p_df["Day_Of_Week"] >= 4) & (p_df["Day_Of_Week"] != 6)],
            }

            row_data: dict[str, Any] = {"participant_number": participant_number}
            for op in OPERATIONS:
                for grp in DAY_GROUPINGS:
                    sub_df = subsets[grp]
                    for unit in ("BEDTIME", "WOKETIME", "IN_BED", "OUT_BED"):
                        col_key = f"SL_pre_{unit}_{op}_{grp}_selfreport"
                        c_name, is_bed = unit_col_map[unit]
                        if c_name is not None and not sub_df.empty:
                            row_data[col_key] = calculate_time_statistics(
                                sub_df[c_name], op, is_bedtime=is_bed
                            )
                        else:
                            row_data[col_key] = ""
            stat_rows.append(row_data)

    if not stat_rows:
        return pd.DataFrame(columns=stat_columns)
    return pd.DataFrame(stat_rows, columns=stat_columns)


# ---------------------------------------------------------------------------
# 5.3 Longitudinal daily sleep-log processing (SL1..SL{N}) — ROW1..ROW4
# ---------------------------------------------------------------------------

SchemaTuple = tuple[str, str, str, str]  # (output suffix, column letter, mapper, survey)


def _build_schemas() -> tuple[
    list[SchemaTuple], list[SchemaTuple], list[SchemaTuple], list[SchemaTuple]
]:
    m_keys = list(HOURLY_MORNING.keys())
    e_keys = list(HOURLY_EVENING.keys())
    devices = ["PHONE", "COMPUTER", "TABLET", "VIDGAMES"]

    row1: list[SchemaTuple] = [
        ("pre_BEDTIME_selfreport", COLUMN_MAPPINGS["IN_BED"], "TIME", "MORNING"),
        ("pre_LIGHTSOFF_selfreport", COLUMN_MAPPINGS["BEDTIME"], "TIME", "MORNING"),
        ("pre_NAP_selfreport", COLUMN_MAPPINGS["NAP"], "BOOL", "EVENING"),
        ("pre_NAPTIME_selfreport", COLUMN_MAPPINGS["NAPTIME"], "NUM", "EVENING"),
        ("pre_NAP_START_selfreport", COLUMN_MAPPINGS["NAP_START"], "TIME", "EVENING"),
        ("pre_NAP_END_selfreport", COLUMN_MAPPINGS["NAP_END"], "TIME", "EVENING"),
        ("pre_NAPTIME2_selfreport", COLUMN_MAPPINGS["NAPTIME2"], "NUM", "EVENING"),
        ("pre_NAP2_START_selfreport", COLUMN_MAPPINGS["NAP2_START"], "TIME", "EVENING"),
        ("pre_NAP2_END_selfreport", COLUMN_MAPPINGS["NAP2_END"], "TIME", "EVENING"),
        ("pre_NAP_other_selfreport", COLUMN_MAPPINGS["NAP_OTHER"], "TIME", "EVENING"),
        ("pre_ACTIVITIES_tv_selfreport", COLUMN_MAPPINGS["ACTIVITIES_TV"], "BOOL", "MORNING"),
        ("pre_ACTIVITIES_tv_duration", COLUMN_MAPPINGS["ACTIVITIES_TV_DURATION"], "NUM", "MORNING"),
        (
            "pre_ACTIVITIES_internet_selfreport",
            COLUMN_MAPPINGS["ACTIVITIES_INTERNET"],
            "BOOL",
            "MORNING",
        ),
        (
            "pre_ACTIVITIES_internet_duration",
            COLUMN_MAPPINGS["ACTIVITIES_INTERNET_DURATION"],
            "NUM",
            "MORNING",
        ),
        ("pre_ACTIVITIES_phone_selfreport", COLUMN_MAPPINGS["ACTIVITIES_PHONE"], "BOOL", "MORNING"),
        (
            "pre_ACTIVITIES_phone_duration",
            COLUMN_MAPPINGS["ACTIVITIES_PHONE_DURATION"],
            "NUM",
            "MORNING",
        ),
        (
            "pre_ACTIVITIES_videogames_selfreport",
            COLUMN_MAPPINGS["ACTIVITIES_VIDEOGAMES"],
            "BOOL",
            "MORNING",
        ),
        (
            "pre_ACTIVITIES_videogames_duration",
            COLUMN_MAPPINGS["ACTIVITIES_VIDEOGAMES_DURATION"],
            "NUM",
            "MORNING",
        ),
        ("pre_ACTIVITIES_read_selfreport", COLUMN_MAPPINGS["ACTIVITIES_READ"], "BOOL", "MORNING"),
        (
            "pre_ACTIVITIES_read_duration",
            COLUMN_MAPPINGS["ACTIVITIES_READ_DURATION"],
            "NUM",
            "MORNING",
        ),
        ("pre_ACTIVITIES_music_selfreport", COLUMN_MAPPINGS["ACTIVITIES_MUSIC"], "BOOL", "MORNING"),
        (
            "pre_ACTIVITIES_music_duration",
            COLUMN_MAPPINGS["ACTIVITIES_MUSIC_DURATION"],
            "NUM",
            "MORNING",
        ),
        (
            "pre_ACTIVITIES_other_selfreport",
            COLUMN_MAPPINGS["ACTIVITIES_OTHER"],
            "OTHER",
            "MORNING",
        ),
        (
            "pre_ACTIVITIES_other_duration",
            COLUMN_MAPPINGS["ACTIVITIES_OTHER_DURATION"],
            "NUM",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_other2_selfreport",
            COLUMN_MAPPINGS["ACTIVITIES_OTHER2"],
            "OTHER",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_other2_duration",
            COLUMN_MAPPINGS["ACTIVITIES_OTHER2_DURATION"],
            "NUM",
            "MORNING",
        ),
        ("pre_WOKETIME_selfreport", COLUMN_MAPPINGS["WOKETIME"], "TIME", "MORNING"),
        ("pre_GETUP_selfreport", COLUMN_MAPPINGS["OUT_BED"], "TIME", "MORNING"),
        ("pre_SCHOOL_ATTEND", COLUMN_MAPPINGS["SCHOOL_ATTEND"], "BOOL", "EVENING"),
        ("pre_SCHOOL_START", COLUMN_MAPPINGS["SCHOOL_START"], "TIME", "EVENING"),
        ("pre_SCHOOL_END", COLUMN_MAPPINGS["SCHOOL_END"], "TIME", "EVENING"),
        ("pre_HOME_ARRIVAL", COLUMN_MAPPINGS["HOME_ARRIVAL"], "TIME", "EVENING"),
    ]
    # Legacy hourly device variables (12-1am→5-6am, 6-7am→5-6pm, 6-7pm→11-12am)
    for h_k in m_keys[:6]:
        for dev in devices:
            row1.append((f"pre_{dev}_{h_k}", HOURLY_MORNING[h_k][dev], "OTHER", "MORNING"))
    for h_k in e_keys:
        for dev in devices:
            row1.append((f"pre_{dev}_{h_k}", HOURLY_EVENING[h_k][dev], "OTHER", "EVENING"))
    for h_k in m_keys[6:]:
        for dev in devices:
            row1.append((f"pre_{dev}_{h_k}", HOURLY_MORNING[h_k][dev], "OTHER", "MORNING"))
    for h_k in m_keys[:6]:
        row1.append((f"pre_INDOORS_{h_k}", HOURLY_MORNING[h_k]["INDOORS"], "INDOOR", "MORNING"))
    for h_k in e_keys:
        row1.append((f"pre_INDOORS_{h_k}", HOURLY_EVENING[h_k]["INDOORS"], "INDOOR", "EVENING"))
    for h_k in m_keys[6:]:
        row1.append((f"pre_INDOORS_{h_k}", HOURLY_MORNING[h_k]["INDOORS"], "INDOOR", "MORNING"))
    for h_k in e_keys:
        row1.append((f"pre_OUTDOORS_{h_k}", HOURLY_EVENING[h_k]["OUTDOORS"], "OUTDOOR", "EVENING"))
    for h_k in ["6_7pm", "7_8pm", "8_9pm"]:
        row1.append((f"pre_OUTDOORS_{h_k}", HOURLY_MORNING[h_k]["OUTDOORS"], "OUTDOOR", "MORNING"))

    row2: list[SchemaTuple] = [
        (
            "PRE_ACTIVITIES_lightsoff",
            COLUMN_MAPPINGS["ACTIVITIES_LIGHTSOFF"],
            "LIGHTSOFF",
            "MORNING",
        ),
        ("PRE_ACTIVITIES_tv_pleasure", COLUMN_MAPPINGS["ACTIVITIES_TV_PLEASURE"], "NUM", "MORNING"),
        ("PRE_ACTIVITIES_tv_arousal", COLUMN_MAPPINGS["ACTIVITIES_TV_AROUSAL"], "NUM", "MORNING"),
        (
            "PRE_ACTIVITIES_tv_type_comedy",
            COLUMN_MAPPINGS["ACTIVITIES_TV_TYPE_COMEDY"],
            "OTHER",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_tv_type_horror",
            COLUMN_MAPPINGS["ACTIVITIES_TV_TYPE_HORROR"],
            "OTHER",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_tv_type_romance",
            COLUMN_MAPPINGS["ACTIVITIES_TV_TYPE_ROMANCE"],
            "OTHER",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_tv_type_action",
            COLUMN_MAPPINGS["ACTIVITIES_TV_TYPE_ACTION"],
            "OTHER",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_tv_type_thriller",
            COLUMN_MAPPINGS["ACTIVITIES_TV_TYPE_THRILLER"],
            "OTHER",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_tv_type_fantasy",
            COLUMN_MAPPINGS["ACTIVITIES_TV_TYPE_FANTASY"],
            "OTHER",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_tv_type_mystery",
            COLUMN_MAPPINGS["ACTIVITIES_TV_TYPE_MYSTERY"],
            "OTHER",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_tv_type_drama",
            COLUMN_MAPPINGS["ACTIVITIES_TV_TYPE_DRAMA"],
            "OTHER",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_tv_type_other",
            COLUMN_MAPPINGS["ACTIVITIES_TV_TYPE_OTHER"],
            "OTHER",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_tv_type_other_specify",
            COLUMN_MAPPINGS["ACTIVITIES_TV_TYPE_OTHER_SPECIFY"],
            "OTHER_FULL",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_internet_pleasure",
            COLUMN_MAPPINGS["ACTIVITIES_INTERNET_PLEASURE"],
            "NUM",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_internet_arousal",
            COLUMN_MAPPINGS["ACTIVITIES_INTERNET_AROUSAL"],
            "NUM",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_internet_platform",
            COLUMN_MAPPINGS["ACTIVITIES_INTERNET_PLATFORM"],
            "OTHER",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_phone_pleasure",
            COLUMN_MAPPINGS["ACTIVITIES_PHONE_PLEASURE"],
            "NUM",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_phone_arousal",
            COLUMN_MAPPINGS["ACTIVITIES_PHONE_AROUSAL"],
            "NUM",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_videogames_pleasure",
            COLUMN_MAPPINGS["ACTIVITIES_VIDEOGAMES_PLEASURE"],
            "NUM",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_videogames_arousal",
            COLUMN_MAPPINGS["ACTIVITIES_VIDEOGAMES_AROUSAL"],
            "NUM",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_read_pleasure",
            COLUMN_MAPPINGS["ACTIVITIES_READ_PLEASURE"],
            "NUM",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_read_arousal",
            COLUMN_MAPPINGS["ACTIVITIES_READ_AROUSAL"],
            "NUM",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_read_type_textbook",
            COLUMN_MAPPINGS["ACTIVITIES_READ_TYPE_TEXTBOOK"],
            "OTHER",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_read_type_horror",
            COLUMN_MAPPINGS["ACTIVITIES_READ_TYPE_HORROR"],
            "OTHER",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_read_romance",
            COLUMN_MAPPINGS["ACTIVITIES_READ_ROMANCE"],
            "OTHER",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_read_type_action",
            COLUMN_MAPPINGS["ACTIVITIES_READ_TYPE_ACTION"],
            "OTHER",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_read_type_thriller",
            COLUMN_MAPPINGS["ACTIVITIES_READ_TYPE_THRILLER"],
            "OTHER",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_read_type_fantasy",
            COLUMN_MAPPINGS["ACTIVITIES_READ_TYPE_FANTASY"],
            "OTHER",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_read_type_mystery",
            COLUMN_MAPPINGS["ACTIVITIES_READ_TYPE_MYSTERY"],
            "OTHER",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_read_type_drama",
            COLUMN_MAPPINGS["ACTIVITIES_READ_TYPE_DRAMA"],
            "OTHER",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_read_type_other",
            COLUMN_MAPPINGS["ACTIVITIES_READ_TYPE_OTHER"],
            "OTHER",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_read_type_other_specify",
            COLUMN_MAPPINGS["ACTIVITIES_READ_TYPE_OTHER_SPECIFY"],
            "OTHER_FULL",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_read_format",
            COLUMN_MAPPINGS["ACTIVITIES_READ_FORMAT"],
            "READFORMAT",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_music_type",
            COLUMN_MAPPINGS["ACTIVITIES_MUSIC_TYPE"],
            "OTHER_FULL",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_music_pleasure",
            COLUMN_MAPPINGS["ACTIVITIES_MUSIC_PLEASURE"],
            "NUM",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_music_arousal",
            COLUMN_MAPPINGS["ACTIVITIES_MUSIC_AROUSAL"],
            "NUM",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_other_pleasure",
            COLUMN_MAPPINGS["ACTIVITIES_OTHER_PLEASURE"],
            "NUM",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_other_arousal",
            COLUMN_MAPPINGS["ACTIVITIES_OTHER_AROUSAL"],
            "NUM",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_other2_pleasure",
            COLUMN_MAPPINGS["ACTIVITIES_OTHER2_PLEASURE"],
            "NUM",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_other2_arousal",
            COLUMN_MAPPINGS["ACTIVITIES_OTHER2_AROUSAL"],
            "NUM",
            "MORNING",
        ),
        ("PRE_ACTIVITIES_SleepApp", COLUMN_MAPPINGS["ACTIVITIES_SLEEPAPP"], "BOOL", "MORNING"),
        (
            "PRE_ACTIVITIES_SleepApp_name",
            COLUMN_MAPPINGS["ACTIVITIES_SLEEPAPP_NAME"],
            "OTHER_FULL",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_SleepApp_use_sounds",
            COLUMN_MAPPINGS["ACTIVITIES_SLEEPAPP_USE_SOUNDS"],
            "OTHER",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_SleepApp_use_stories",
            COLUMN_MAPPINGS["ACTIVITIES_SLEEPAPP_USE_STORIES"],
            "OTHER",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_SleepApp_use_relax",
            COLUMN_MAPPINGS["ACTIVITIES_SLEEPAPP_USE_RELAX"],
            "OTHER",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_SleepApp_use_midfulness",
            COLUMN_MAPPINGS["ACTIVITIES_SLEEPAPP_USE_MIDFULNESS"],
            "OTHER",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_SleepApp_use_meditation",
            COLUMN_MAPPINGS["ACTIVITIES_SLEEPAPP_USE_MEDITATION"],
            "OTHER",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_SleepApp_use_other",
            COLUMN_MAPPINGS["ACTIVITIES_SLEEPAPP_USE_OTHER"],
            "OTHER",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_SleepApp_use_specify",
            COLUMN_MAPPINGS["ACTIVITIES_SLEEPAPP_USE_SPECIFY"],
            "OTHER_FULL",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_SleepApp_duration",
            COLUMN_MAPPINGS["ACTIVITIES_SLEEPAPP_DURATION"],
            "NUM",
            "MORNING",
        ),
        (
            "PRE_ACTIVITIES_SleepApp_helped",
            COLUMN_MAPPINGS["ACTIVITIES_SLEEPAPP_HELPED"],
            "BOOL",
            "MORNING",
        ),
    ]
    for h_k in ["12_1am", "1_2am", "2_3am", "3_4am", "4_5am", "5_6am"]:
        row2.append((f"PRE_OTHER_{h_k}", HOURLY_MORNING[h_k]["OTHER"], "OTHER", "MORNING"))
    row2.append(("PRE_OTHER_12_6am_specify", SPECIFY_COLUMNS["12_6am"], "OTHER_FULL", "MORNING"))
    for h_k in ["6_7am", "7_8am", "8_9am", "9_10am", "10_11am", "11_12pm"]:
        row2.append((f"PRE_OTHER_{h_k}", HOURLY_EVENING[h_k]["OTHER"], "OTHER", "EVENING"))
    row2.append(("PRE_OTHER_6_12pm_specify", SPECIFY_COLUMNS["6_12pm"], "OTHER_FULL", "EVENING"))
    for h_k in ["12_1pm", "1_2pm", "2_3pm", "3_4pm", "4_5pm", "5_6pm"]:
        row2.append((f"PRE_OTHER_{h_k}", HOURLY_EVENING[h_k]["OTHER"], "OTHER", "EVENING"))
    row2.append(("PRE_OTHER_12_6pm_specify", SPECIFY_COLUMNS["12_6pm"], "OTHER_FULL", "EVENING"))
    for h_k in ["6_7pm", "7_8pm", "8_9pm", "9_10pm", "10_11pm", "11_12am"]:
        row2.append((f"PRE_OTHER_{h_k}", HOURLY_MORNING[h_k]["OTHER"], "OTHER", "MORNING"))
    row2.append(("PRE_OTHER_6_12am_specify", SPECIFY_COLUMNS["6_12am"], "OTHER_FULL", "MORNING"))

    row2.extend(
        [
            ("PRE_AWL_wear", COLUMN_MAPPINGS["PRE_AWL_WEAR"], "BOOL", "MORNING"),
            ("PRE_AWL_on", COLUMN_MAPPINGS["PRE_AWL_ON"], "TIME", "MORNING"),
            ("PRE_AWL_off", COLUMN_MAPPINGS["PRE_AWL_OFF"], "TIME", "MORNING"),
            ("PRE_AWL_other", COLUMN_MAPPINGS["PRE_AWL_OTHER"], "TIME", "MORNING"),
            ("PRE_AWL_time_1", COLUMN_MAPPINGS["PRE_AWL_TIME_1"], "NUM", "MORNING"),
            ("PRE_AWL_duration_1", COLUMN_MAPPINGS["PRE_AWL_DURATION_1"], "NUM", "MORNING"),
            ("PRE_AWL_time_2", COLUMN_MAPPINGS["PRE_AWL_TIME_2"], "NUM", "MORNING"),
            ("PRE_AWL_duration_2", COLUMN_MAPPINGS["PRE_AWL_DURATION_2"], "NUM", "MORNING"),
            ("PRE_AWL_time_3", COLUMN_MAPPINGS["PRE_AWL_TIME_3"], "NUM", "MORNING"),
            ("PRE_AWL_duration_3", COLUMN_MAPPINGS["PRE_AWL_DURATION_3"], "NUM", "MORNING"),
            ("PRE_AWL_time_4", COLUMN_MAPPINGS["PRE_AWL_TIME_4"], "NUM", "MORNING"),
            ("PRE_AWL_duration_4", COLUMN_MAPPINGS["PRE_AWL_DURATION_4"], "NUM", "MORNING"),
        ]
    )
    for idx_poms, col_letter in enumerate(POMS_ITEMS, start=1):
        row2.append((f"PRE_POMS_A_{idx_poms}", col_letter, "SPEC", "EVENING"))

    row3: list[SchemaTuple] = []
    for h_k in m_keys[:6]:
        for dev in devices:
            row3.append((f"pre_noblf_{dev}_{h_k}", HOURLY_MORNING[h_k][dev], "OTHER", "MORNING"))
    for h_k in e_keys:
        for dev in devices:
            row3.append((f"pre_noblf_{dev}_{h_k}", HOURLY_EVENING[h_k][dev], "OTHER", "EVENING"))
    for h_k in m_keys[6:]:
        for dev in devices:
            row3.append((f"pre_noblf_{dev}_{h_k}", HOURLY_MORNING[h_k][dev], "OTHER", "MORNING"))

    row4: list[SchemaTuple] = [
        ("MEDICATION_QUESTION", COLUMN_MAPPINGS["MEDICATION_QUESTION"], "BOOL", "EVENING"),
        ("MEDICATION_NAME", COLUMN_MAPPINGS["MEDICATION_NAME"], "OTHER_FULL", "EVENING"),
    ]
    return row1, row2, row3, row4


def _legacy_hourly_suffixes() -> frozenset:
    """Suffixes of the legacy hourly device variables (always coded 999 in ROW1)."""
    keys = list(HOURLY_MORNING.keys()) + list(HOURLY_EVENING.keys())
    return {f"_{dev}_{h}" for h in keys for dev in ("PHONE", "COMPUTER", "TABLET", "VIDGAMES")}


def _hour_key(suffix: str) -> str:
    """Extract the 'H_Hxx' hour key from a schema suffix like 'pre_noblf_PHONE_12_1am'."""
    return "_".join(suffix.split("_")[-2:])


def resolve_cell_value(
    m_row: pd.DataFrame,
    e_row: pd.DataFrame,
    m_absent: bool,
    e_absent: bool,
    col_letter: str,
    mapper_key: str,
    survey_type: str,
) -> Any:
    """Extract and decode a survey cell from the matching morning/evening row."""
    if col_letter == "NONE":
        return ""
    is_absent = m_absent if survey_type == "MORNING" else e_absent
    row_df = m_row if survey_type == "MORNING" else e_row
    if is_absent or row_df.empty:
        return FUNCTION_MAPPER[mapper_key](None, True)
    idx = excel_column_number(col_letter)
    if idx < 0 or idx >= row_df.shape[1]:
        return FUNCTION_MAPPER[mapper_key](None, True)
    return FUNCTION_MAPPER[mapper_key](row_df.iloc[0, idx], False)


def build_longitudinal(
    df_morning: pd.DataFrame,
    df_evening: pd.DataFrame,
    config: StudyConfig,
    p_m_idx: int,
    d_m_idx: int,
    p_e_idx: int,
    d_e_idx: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[int]]:
    """Build the SL1..SL{N} daily datasets (ROW1–ROW4) for every participant."""
    dates = config.date_strings
    num_days = len(dates)
    astral_data = precompute_astral_data(config)

    schema_row1, schema_row2, schema_row3, schema_row4 = _build_schemas()
    legacy_suffixes = _legacy_hourly_suffixes()

    p_m_set = (
        set(df_morning[df_morning.columns[p_m_idx]].unique())
        if not df_morning.empty and p_m_idx >= 0
        else set()
    )
    p_e_set = (
        set(df_evening[df_evening.columns[p_e_idx]].unique())
        if not df_evening.empty and p_e_idx >= 0
        else set()
    )
    all_participants = sorted(p for p in (p_m_set | p_e_set) if p != 0)

    grp_m = (
        {k: v for k, v in df_morning.groupby(df_morning.columns[p_m_idx])}
        if not df_morning.empty and p_m_idx >= 0
        else {}
    )
    grp_e = (
        {k: v for k, v in df_evening.groupby(df_evening.columns[p_e_idx])}
        if not df_evening.empty and p_e_idx >= 0
        else {}
    )

    def _date_keys(frame: pd.DataFrame, d_idx: int) -> pd.Series:
        return pd.to_datetime(frame.iloc[:, d_idx], dayfirst=True, errors="coerce").dt.strftime(
            "%d-%m-%Y"
        )

    row1_records, row2_records, row3_records, row4_records = [], [], [], []

    for p_num in all_participants:
        p_m_df = grp_m.get(p_num, pd.DataFrame())
        p_e_df = grp_e.get(p_num, pd.DataFrame())
        m_keys = _date_keys(p_m_df, d_m_idx) if not p_m_df.empty else pd.Series(dtype=str)
        e_keys = _date_keys(p_e_df, d_e_idx) if not p_e_df.empty else pd.Series(dtype=str)

        r1: dict[str, Any] = {"participant_number": p_num}
        r2: dict[str, Any] = {"participant_number": p_num}
        r3: dict[str, Any] = {"participant_number": p_num}
        r4: dict[str, Any] = {"participant_number": p_num}

        for day_idx, cur_date in enumerate(dates, start=1):
            is_first_day = day_idx == 1
            is_last_day = day_idx == num_days

            m_row = p_m_df[m_keys == cur_date] if not p_m_df.empty else pd.DataFrame()
            e_row = p_e_df[e_keys == cur_date] if not p_e_df.empty else pd.DataFrame()
            m_absent = m_row.empty
            e_absent = e_row.empty

            # ROW 1: astronomical & core sleep variables
            r1[f"SL{day_idx}_pre_sunrise_time"] = astral_data[cur_date]["sunrise"]
            r1[f"SL{day_idx}_pre_sunset_time"] = astral_data[cur_date]["sunset"]
            r1[f"SL{day_idx}_pre_daylength"] = astral_data[cur_date]["daylength"]
            r1[f"SL{day_idx}_pre_sunlight"] = ""
            r1[f"SL{day_idx}_pre_moonphase"] = ""
            r1[f"SL{day_idx}_pre_moonlight"] = ""

            cur_dt = datetime.strptime(cur_date, "%d-%m-%Y")
            if not m_absent or not e_absent:
                r1[f"SL{day_idx}_pre_Date_start"] = cur_date
                r1[f"SL{day_idx}_pre_Date_end"] = (cur_dt + timedelta(days=1)).strftime("%d-%m-%Y")
                dw = cur_dt.weekday()
                r1[f"SL{day_idx}_pre_Day"] = (
                    DAY_TYPE_WEEKDAY
                    if dw < 4
                    else (DAY_TYPE_SUNDAY if dw == 6 else DAY_TYPE_FRISAT)
                )
            else:
                r1[f"SL{day_idx}_pre_Date_start"] = ""
                r1[f"SL{day_idx}_pre_Date_end"] = ""
                r1[f"SL{day_idx}_pre_Day"] = ""

            for suffix, col_letter, mapper_k, survey_t in schema_row1:
                col_name = f"SL{day_idx}_{suffix}"
                if any(suffix.endswith(s) for s in legacy_suffixes):
                    r1[col_name] = 999  # legacy hourly variables, IGNORED_VARS convention
                else:
                    r1[col_name] = resolve_cell_value(
                        m_row, e_row, m_absent, e_absent, col_letter, mapper_k, survey_t
                    )

            # ROW 2: activity details, sleep app, actiwatch & POMS-A
            poms_items_day: dict[int, Any] = {}
            for suffix, col_letter, mapper_k, survey_t in schema_row2:
                col_name = f"SL{day_idx}_{suffix}"
                val = resolve_cell_value(
                    m_row, e_row, m_absent, e_absent, col_letter, mapper_k, survey_t
                )
                r2[col_name] = val
                if suffix.startswith("PRE_POMS_A_") and suffix[11:].isdigit():
                    poms_items_day[int(suffix[11:])] = val

            for sub_name, item_nums in POMS_SUBSCALES.items():
                valid_items = [
                    poms_items_day[n]
                    for n in item_nums
                    if poms_items_day.get(n) not in (DID_NOT_ANSWER_CODE, DID_NOT_ATTEND_CODE)
                ]
                score = (
                    sum(valid_items)
                    if valid_items
                    else (DID_NOT_ATTEND_CODE if e_absent else DID_NOT_ANSWER_CODE)
                )
                r2[f"SL{day_idx}_PRE_POMS_A_{sub_name}"] = score

            valid_subs = [
                s
                for s in [r2[f"SL{day_idx}_PRE_POMS_A_{k}"] for k in POMS_SUBSCALES]
                if s not in (DID_NOT_ANSWER_CODE, DID_NOT_ATTEND_CODE)
            ]
            r2[f"SL{day_idx}_PRE_POMS_A_total"] = (
                sum(valid_subs)
                if valid_subs
                else (DID_NOT_ATTEND_CODE if e_absent else DID_NOT_ANSWER_CODE)
            )

            # ROW 3: hourly screen usage (boundary early-termination codes)
            for suffix, col_letter, mapper_k, survey_t in schema_row3:
                col_name = f"SL{day_idx}_{suffix}"
                h_key = _hour_key(suffix)
                is_early_term = (is_first_day and h_key in EARLY_TERM_DAY1_KEYS) or (
                    is_last_day and h_key in EARLY_TERM_LASTDAY_KEYS
                )
                r3[col_name] = (
                    EARLY_TERMINATION_CODE
                    if is_early_term
                    else resolve_cell_value(
                        m_row, e_row, m_absent, e_absent, col_letter, mapper_k, survey_t
                    )
                )

            # ROW 4: medication logs
            for suffix, col_letter, mapper_k, survey_t in schema_row4:
                col_name = f"SL{day_idx}_{suffix}"
                r4[col_name] = resolve_cell_value(
                    m_row, e_row, m_absent, e_absent, col_letter, mapper_k, survey_t
                )

        row1_records.append(r1)
        row2_records.append(r2)
        row3_records.append(r3)
        row4_records.append(r4)

    def _frame(records: list[dict[str, Any]]) -> pd.DataFrame:
        return pd.DataFrame(records) if records else pd.DataFrame(columns=["participant_number"])

    return (
        _frame(row1_records),
        _frame(row2_records),
        _frame(row3_records),
        _frame(row4_records),
        all_participants,
    )
