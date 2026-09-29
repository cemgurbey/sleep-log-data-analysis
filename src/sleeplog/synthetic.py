"""Artificial sleep-diary survey data generator.

Produces realistic Morning/Evening survey workbooks in the exact column layout
the pipeline expects, so the notebook runs end-to-end with zero manual input.
A few invalid entries are injected on purpose so the QA report has something
to flag.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
from openpyxl import Workbook

from sleeplog.config import (
    COLUMN_MAPPINGS,
    HOURLY_EVENING,
    HOURLY_MORNING,
    POMS_ITEMS,
    SPECIFY_COLUMNS,
    StudyConfig,
)

N_COLUMNS = 187  # covers the highest mapped column (GE)

POMS_OPTIONS = ["Not at all", "A little", "Moderately", "Quite a bit", "Extremely"]
INDOOR_OPTIONS = ["NO LIGHTS", "NIGHTLIGHT", "LIGHTS ON"]
LIGHTSOFF_OPTIONS = [
    "I turned off lights and devices",
    "I turned off lights but not devices",
    "I did NOT turn off lights",
]
READ_FORMATS = ["A physical book", "Tablet", "Ebook"]
SLEEP_APP_NAMES = ["Calm", "Headspace", "Loops"]
MEDICATIONS = ["Melatonin 3mg", "Vitamin D", "Antihistamine"]


def _col(letter: str) -> int:
    n = 0
    for c in letter.strip().upper():
        n = n * 26 + (ord(c) - ord("A") + 1)
    return n - 1


def _hhmm(hours: float) -> str:
    """Decimal hours -> 'HH:MM' 24h string, wrapping past midnight."""
    total_min = int(round((hours % 24) * 60))
    return f"{total_min // 60:02d}:{total_min % 60:02d}"


def _headers(survey: str) -> tuple[list[str], list[str]]:
    """Two-row headers for the workbook. Column letters are positional; the
    same letter can mean different questions in the morning vs evening survey."""
    h1 = [""] * N_COLUMNS
    h2 = [""] * N_COLUMNS

    def put(letter: str, cat: str, question: str) -> None:
        h1[_col(letter)] = cat
        h2[_col(letter)] = question

    put("J", "Participant", "Participant Number")
    put("K", "Participant", "Date (DD/MM/YYYY)")

    if survey == "morning":
        put("L", "Sleep", "What time did you get into bed?")
        put("M", "Sleep", "Did you turn off lights and devices before bed?")
        put("N", "Sleep", "What time did you try to go to sleep (lights out)?")
        put("O", "Sleep", "What time did you wake up?")
        put("P", "Sleep", "What time did you get out of bed?")
        for letter, label in [
            ("Q", "TV"),
            ("Y", "TV minutes"),
            ("Z", "TV pleasure"),
            ("AA", "TV arousal"),
            ("R", "Internet"),
            ("AK", "Internet minutes"),
            ("S", "Phone"),
            ("AO", "Phone minutes"),
            ("T", "Videogames"),
            ("AR", "Videogames minutes"),
            ("U", "Reading"),
            ("AU", "Reading minutes"),
            ("BG", "Reading format"),
            ("V", "Music"),
            ("BH", "Music minutes"),
            ("BI", "Music type"),
        ]:
            put(letter, "Pre-bed activities", label)
        put("BU", "Sleep app", "Used a sleep app?")
        put("BV", "Sleep app", "App name")
        put("CC", "Sleep app", "App minutes")
        put("FD", "Actiwatch", "Wore the Actiwatch?")
        put("FE", "Actiwatch", "Time put on")
        put("FF", "Actiwatch", "Time taken off")
    else:
        put("L", "School", "Did you attend school today?")
        put("M", "Naps", "Did you take a nap today?")
        put("O", "School", "School start time")
        put("Q", "School", "School end time")
        put("S", "School", "Home arrival time")
        put("T", "Naps", "Nap 1 duration (min)")
        put("V", "Naps", "Nap 1 start")
        put("W", "Naps", "Nap 1 end")
        for i, letter in enumerate(POMS_ITEMS, start=1):
            put(letter, "POMS-A", f"Mood item {i}")
        put("EU", "Medication", "Took medication?")
        put("EV", "Medication", "Medication name")
    return h1, h2


class _ParticipantModel:
    """Per-participant sleep behaviour with a chronotype and weekend shift."""

    def __init__(self, rng: np.random.Generator, pid: int):
        self.pid = pid
        self.bedtime_base = float(rng.normal(23.3, 1.0))  # decimal hours
        self.weekend_shift = float(rng.uniform(0.5, 1.6))  # later on Fri/Sat nights
        self.duration_mean = float(rng.normal(7.8, 0.7))  # sleep hours
        self.nap_prob = float(rng.uniform(0.05, 0.25))
        self.screen_prob = float(rng.uniform(0.5, 0.9))

    def night_times(self, rng: np.random.Generator, day: date) -> dict[str, str]:
        weekend_night = day.weekday() in (4, 5)  # Fri/Sat nights
        bedtime = self.bedtime_base + (self.weekend_shift if weekend_night else 0.0)
        bedtime += float(rng.normal(0, 0.42))
        in_bed = bedtime - float(rng.uniform(0.08, 0.65))
        attempt = in_bed + float(rng.uniform(0.08, 0.75))
        duration = float(np.clip(rng.normal(self.duration_mean, 0.8), 5.0, 11.0))
        wake = attempt + duration
        out_bed = wake + float(rng.uniform(0.0, 0.4))
        return {
            "in_bed": _hhmm(in_bed),
            "attempt": _hhmm(attempt),
            "wake": _hhmm(wake),
            "out_bed": _hhmm(out_bed),
        }


def _pre_bed_activities(rng: np.random.Generator, row: list, screen_prob: float) -> None:
    def yes_no(p: float) -> str:
        return "Yes" if rng.random() < p else "No"

    acts = [
        ("Q", "Y", "Z", "AA", 0.45),  # TV
        ("R", "AK", "AL", "AM", 0.60),  # internet
        ("S", "AO", "AP", "AQ", screen_prob),  # phone
        ("T", "AR", "AS", "AT", 0.25),  # videogames
        ("U", "AU", "AV", "AW", 0.30),  # reading
        ("V", "BH", "BJ", "BK", 0.35),  # music
    ]
    for use_c, dur_c, plea_c, aro_c, p in acts:
        if rng.random() < p:
            row[_col(use_c)] = "Yes"
            row[_col(dur_c)] = int(rng.integers(5, 121))
            row[_col(plea_c)] = int(rng.integers(1, 6))
            row[_col(aro_c)] = int(rng.integers(1, 6))
        else:
            row[_col(use_c)] = "No"
    if rng.random() < 0.25:  # reading format detail
        row[_col("BG")] = str(rng.choice(READ_FORMATS))
    if rng.random() < 0.30:  # sleep app
        row[_col("BU")] = "Yes"
        row[_col("BV")] = str(rng.choice(SLEEP_APP_NAMES))
        row[_col("BW")] = yes_no(0.6)
        row[_col("CC")] = int(rng.integers(5, 46))
        row[_col("CD")] = yes_no(0.7)
    else:
        row[_col("BU")] = "No"
    if rng.random() < 0.85:  # actiwatch
        row[_col("FD")] = "Yes"
        row[_col("FE")] = _hhmm(rng.uniform(20.5, 22.5))
        row[_col("FF")] = _hhmm(rng.uniform(6.5, 8.5))
    else:
        row[_col("FD")] = "No"


def _hourly_block(
    rng: np.random.Generator,
    row: list,
    mapping: dict[str, dict[str, str]],
    asleep_prob: float,
) -> None:
    """Fill one hourly media/lighting block; asleep hours are mostly blank."""
    for block in mapping.values():
        asleep = rng.random() < asleep_prob
        for dev in ("PHONE", "COMPUTER", "TABLET", "VIDGAMES"):
            row[_col(block[dev])] = 1 if (not asleep and rng.random() < 0.35) else ""
        if "INDOORS" in block:
            row[_col(block["INDOORS"])] = (
                str(rng.choice(["NO LIGHTS", "NIGHTLIGHT"], p=[0.7, 0.3]))
                if asleep
                else "LIGHTS ON"
            )
        if "OUTDOORS" in block:
            row[_col(block["OUTDOORS"])] = "Yes" if rng.random() < 0.4 else "No"


def generate_survey_workbooks(
    out_dir: str | Path,
    config: StudyConfig,
    n_participants: int = 12,
    seed: int = 7,
) -> tuple[Path, Path]:
    """Generate artificial Morning/Evening survey workbooks.

    Returns the (morning_path, evening_path). A couple of invalid entries are
    injected deliberately so the QA validation step has realistic flags.
    """
    rng = np.random.default_rng(seed)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    h1, h2 = _headers("morning")
    m_rows: list[list] = [h1, h2]
    h1e, h2e = _headers("evening")
    e_rows: list[list] = [h1e, h2e]

    dates = [
        config.start_date + timedelta(days=i)
        for i in range((config.end_date - config.start_date).days + 1)
    ]
    models = [_ParticipantModel(rng, 101 + i) for i in range(n_participants)]

    for mi, model in enumerate(models):
        # random missed days exercise the 999 "did not attend" path
        missed_m = set(rng.choice(len(dates), size=int(rng.integers(0, 2)), replace=False))
        missed_e = set(rng.choice(len(dates), size=int(rng.integers(0, 2)), replace=False))

        for di, day in enumerate(dates):
            if di not in missed_m:
                row: list = [""] * N_COLUMNS
                row[_col("J")] = model.pid
                row[_col("K")] = day
                times = model.night_times(rng, day)
                row[_col(COLUMN_MAPPINGS["IN_BED"])] = times["in_bed"]
                row[_col(COLUMN_MAPPINGS["BEDTIME"])] = times["attempt"]
                row[_col(COLUMN_MAPPINGS["WOKETIME"])] = times["wake"]
                row[_col(COLUMN_MAPPINGS["OUT_BED"])] = times["out_bed"]
                row[_col(COLUMN_MAPPINGS["ACTIVITIES_LIGHTSOFF"])] = str(
                    rng.choice(LIGHTSOFF_OPTIONS, p=[0.55, 0.25, 0.20])
                )
                _pre_bed_activities(rng, row, model.screen_prob)
                _hourly_block(rng, row, HOURLY_MORNING, asleep_prob=0.92)
                if rng.random() < 0.15:
                    row[_col(SPECIFY_COLUMNS["12_6am"])] = "Checked phone briefly"
                # injected invalid entries for QA demonstration
                if mi == 2 and di == 3:
                    row[_col(COLUMN_MAPPINGS["IN_BED"])] = "twenty five oclock"
                m_rows.append(row)

            if di not in missed_e:
                row = [""] * N_COLUMNS
                row[_col("J")] = model.pid
                row[_col("K")] = day
                weekday = day.weekday() < 5
                row[_col(COLUMN_MAPPINGS["SCHOOL_ATTEND"])] = (
                    "Yes" if (weekday and rng.random() < 0.92) else "No"
                )
                if weekday and rng.random() < 0.9:
                    row[_col(COLUMN_MAPPINGS["SCHOOL_START"])] = "08:30"
                    row[_col(COLUMN_MAPPINGS["SCHOOL_END"])] = "15:30"
                    row[_col(COLUMN_MAPPINGS["HOME_ARRIVAL"])] = _hhmm(rng.uniform(15.75, 16.75))
                if rng.random() < model.nap_prob:
                    row[_col(COLUMN_MAPPINGS["NAP"])] = "Yes"
                    start = rng.uniform(13.0, 17.5)
                    dur_min = int(rng.integers(15, 91))
                    row[_col(COLUMN_MAPPINGS["NAPTIME"])] = dur_min
                    row[_col(COLUMN_MAPPINGS["NAP_START"])] = _hhmm(start)
                    row[_col(COLUMN_MAPPINGS["NAP_END"])] = _hhmm(start + dur_min / 60)
                else:
                    row[_col(COLUMN_MAPPINGS["NAP"])] = "No"
                _hourly_block(rng, row, HOURLY_EVENING, asleep_prob=0.0)
                for letter in POMS_ITEMS:
                    row[_col(letter)] = str(
                        rng.choice(POMS_OPTIONS, p=[0.45, 0.30, 0.15, 0.07, 0.03])
                    )
                if rng.random() < 0.08:
                    row[_col(COLUMN_MAPPINGS["MEDICATION_QUESTION"])] = "Yes"
                    row[_col(COLUMN_MAPPINGS["MEDICATION_NAME"])] = str(rng.choice(MEDICATIONS))
                else:
                    row[_col(COLUMN_MAPPINGS["MEDICATION_QUESTION"])] = "No"
                if mi == 4 and di == 5:
                    row[_col("K")] = "not-a-date"  # invalid date for QA
                e_rows.append(row)

    def _write(path: Path, rows: list[list]) -> None:
        wb = Workbook()
        ws = wb.active
        for r in rows:
            ws.append(r)
        wb.save(path)

    morning_path = out_dir / "Sleep and Activity Log - Morning (synthetic).xlsx"
    evening_path = out_dir / "Sleep and Activity Log - Evening (synthetic).xlsx"
    _write(morning_path, m_rows)
    _write(evening_path, e_rows)
    return morning_path, evening_path
