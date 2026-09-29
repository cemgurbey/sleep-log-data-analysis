"""Survey question decoders: raw free-text answers -> standardized research codes."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

from sleeplog.config import (
    DID_NOT_ANSWER_CODE,
    DID_NOT_ATTEND_CODE,
    DID_NOT_ATTEND_TIME_CODE,
    NOT_VALID_ANSWER_CODE,
)
from sleeplog.parsing import format_time_hhmm, parse_time_entry


def bool_handle(answer: Any) -> int:
    """Binary responses: 1 for Yes, 0 for No, 3 for "I don't know"."""
    if answer is None or pd.isna(answer):
        return DID_NOT_ANSWER_CODE
    s = str(answer).strip().lower()
    if "yes" in s:
        return 1
    if "no" in s:
        return 0
    if "don't know" in s or "dont know" in s:
        return 3
    return NOT_VALID_ANSWER_CODE


def num_handle(answer: Any) -> int:
    """Extract integer numbers from responses."""
    if answer is None or pd.isna(answer):
        return DID_NOT_ANSWER_CODE
    if isinstance(answer, (int, np.integer)):
        return int(answer)
    if isinstance(answer, (float, np.floating)):
        return int(round(answer)) if not np.isnan(answer) else DID_NOT_ANSWER_CODE
    m = re.search(r"[-+]?(?:\d*\.?\d+)", str(answer).strip())
    if m:
        return int(round(float(m.group())))
    return NOT_VALID_ANSWER_CODE


def other_handle(answer: Any) -> int:
    """Check-box response: 1 if selected/present, else 999."""
    if answer is None or pd.isna(answer) or str(answer).strip() == "":
        return DID_NOT_ANSWER_CODE
    return 1


def other_full_handle(answer: Any) -> str | int:
    """Preserve free-text specifications."""
    if answer is None or pd.isna(answer) or str(answer).strip() == "":
        return DID_NOT_ANSWER_CODE
    return str(answer).strip()


def indoor_handle(answer: Any) -> int:
    """Indoor light status code."""
    if answer is None or pd.isna(answer):
        return DID_NOT_ANSWER_CODE
    s = str(answer).strip().upper()
    if "NO LIGHTS" in s:
        return 1
    if "NIGHTLIGHT" in s:
        return 2
    if "LIGHTS ON" in s or "LIGHTS TURNED ON" in s:
        return 3
    return 0


def outdoor_handle(answer: Any) -> int:
    """Outdoor light exposure code."""
    if answer is None or pd.isna(answer):
        return DID_NOT_ANSWER_CODE
    s = str(answer).strip().lower()
    if "yes" in s:
        return 1
    if "no" in s:
        return 0
    return NOT_VALID_ANSWER_CODE


def lightsoff_handle(answer: Any) -> int:
    """Pre-bed lights turned off response code."""
    if answer is None or pd.isna(answer):
        return DID_NOT_ANSWER_CODE
    s = str(answer).strip().lower()
    if "not engaged" in s:
        return 1
    if "turned off lights and devices" in s:
        return 2
    if "turned off light" in s:
        return 3
    if "not turn off" in s or "did not turn off" in s:
        return 4
    return NOT_VALID_ANSWER_CODE


def readformat_handle(answer: Any) -> int:
    """Reading format code."""
    if answer is None or pd.isna(answer):
        return DID_NOT_ANSWER_CODE
    s = str(answer).strip().lower()
    if "physical book" in s:
        return 1
    if "tablet" in s or "screen" in s:
        return 2
    if "ebook" in s or "kindle" in s:
        return 3
    return NOT_VALID_ANSWER_CODE


def spec_handle(answer: Any) -> int:
    """POMS-A Likert scale parser (0 = Not at all to 4 = Extremely)."""
    if answer is None or pd.isna(answer):
        return DID_NOT_ANSWER_CODE
    s = str(answer).strip().lower()
    if "extremely" in s:
        return 4
    if "quite a bit" in s:
        return 3
    if "moderately" in s:
        return 2
    if "a little" in s:
        return 1
    if "not at all" in s:
        return 0
    if s in ("0", "1", "2", "3", "4"):
        return int(s)
    return NOT_VALID_ANSWER_CODE


def _time_decode(value: Any, absent: bool) -> str:
    if absent:
        return DID_NOT_ATTEND_TIME_CODE
    return format_time_hhmm(parse_time_entry(value))


def _bool_decode(value: Any, absent: bool) -> int:
    return DID_NOT_ATTEND_CODE if absent else bool_handle(value)


def _num_decode(value: Any, absent: bool) -> int:
    return DID_NOT_ATTEND_CODE if absent else num_handle(value)


def _other_decode(value: Any, absent: bool) -> int:
    return DID_NOT_ATTEND_CODE if absent else other_handle(value)


def _other_full_decode(value: Any, absent: bool) -> str | int:
    return DID_NOT_ATTEND_CODE if absent else other_full_handle(value)


def _indoor_decode(value: Any, absent: bool) -> int:
    return DID_NOT_ATTEND_CODE if absent else indoor_handle(value)


def _outdoor_decode(value: Any, absent: bool) -> int:
    return DID_NOT_ATTEND_CODE if absent else outdoor_handle(value)


def _lightsoff_decode(value: Any, absent: bool) -> int:
    return DID_NOT_ATTEND_CODE if absent else lightsoff_handle(value)


def _readformat_decode(value: Any, absent: bool) -> int:
    return DID_NOT_ATTEND_CODE if absent else readformat_handle(value)


def _spec_decode(value: Any, absent: bool) -> int:
    return DID_NOT_ATTEND_CODE if absent else spec_handle(value)


# Maps schema handler keys to (cell value, day-absent) -> research code.
FUNCTION_MAPPER: dict[str, Callable[[Any, bool], Any]] = {
    "TIME": _time_decode,
    "BOOL": _bool_decode,
    "NUM": _num_decode,
    "OTHER": _other_decode,
    "OTHER_FULL": _other_full_decode,
    "INDOOR": _indoor_decode,
    "OUTDOOR": _outdoor_decode,
    "LIGHTSOFF": _lightsoff_decode,
    "READFORMAT": _readformat_decode,
    "SPEC": _spec_decode,
}
