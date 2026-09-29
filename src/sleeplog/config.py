"""Study configuration, research coding schema, and survey column mappings."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

# ---------------------------------------------------------------------------
# Standardized research missing & boundary value codes
# ---------------------------------------------------------------------------
DID_NOT_ATTEND_CODE: int = 999  # Participant did not complete survey on this day
DID_NOT_ATTEND_TIME_CODE: str = "99:00"
DID_NOT_ANSWER_CODE: int = 999  # Survey completed but question was skipped
DID_NOT_ANSWER_TIME_CODE: str = "99:00"
NOT_VALID_ANSWER_CODE: int = 999  # Unintelligible response
NOT_VALID_TIME_CODE: str = "99:00"
EARLY_TERMINATION_CODE: int = 888  # Not applicable due to study boundary (Day 1 / Last Day)

# Day-type coding used in longitudinal outputs: 1 = Mon-Thu, 2 = Fri/Sat, 3 = Sunday
DAY_TYPE_WEEKDAY = 1
DAY_TYPE_FRISAT = 2
DAY_TYPE_SUNDAY = 3

# POMS-A mood subscale item numbers (1-based into POMS_ITEMS)
POMS_SUBSCALES: dict[str, list[int]] = {
    "anger": [7, 11, 19, 22],
    "confusion": [3, 9, 17, 24],
    "depression": [5, 6, 12, 16],
    "fatigue": [4, 8, 10, 21],
    "tension": [1, 13, 14, 18],
    "vigour": [2, 15, 20, 23],
}

# Early-termination hour keys: day 1 loses evening hours, last day loses night hours
EARLY_TERM_DAY1_KEYS = frozenset(
    {
        "6_7am",
        "7_8am",
        "8_9am",
        "9_10am",
        "10_11am",
        "11_12pm",
        "6_7pm",
        "7_8pm",
        "8_9pm",
        "9_10pm",
        "10_11pm",
        "11_12am",
    }
)
EARLY_TERM_LASTDAY_KEYS = frozenset({"12_1am", "1_2am", "2_3am", "3_4am", "4_5am", "5_6am"})


@dataclass(frozen=True)
class SiteLocation:
    """Geographic site used for sunrise/sunset photoperiod calculation."""

    name: str = "Montreal"
    region: str = "Canada"
    timezone: str = "America/Montreal"
    latitude: float = 45.5017
    longitude: float = -73.5673


@dataclass(frozen=True)
class StudyConfig:
    """Run configuration for the sleep-log pipeline."""

    start_date: date = date(2022, 3, 22)
    end_date: date = date(2022, 3, 28)
    location: SiteLocation = field(default_factory=SiteLocation)

    def __post_init__(self) -> None:
        if self.start_date > self.end_date:
            raise ValueError(
                f"SURVEY_START_DATE ({self.start_date}) is after "
                f"SURVEY_END_DATE ({self.end_date}). Please verify your date inputs."
            )

    @property
    def date_strings(self) -> list[str]:
        """Inclusive study dates as 'DD-MM-YYYY' strings (legacy pipeline format)."""
        from datetime import timedelta

        days = (self.end_date - self.start_date).days
        return [(self.start_date + timedelta(days=i)).strftime("%d-%m-%Y") for i in range(days + 1)]


# ---------------------------------------------------------------------------
# Excel column-letter mappings (verbatim research schema — do not reorder)
# ---------------------------------------------------------------------------
COLUMN_MAPPINGS: dict[str, str] = {
    "MORNING_PARTICIPANT_NUMBER": "J",
    "EVENING_PARTICIPANT_NUMBER": "J",
    "MORNING_DATE": "K",
    "EVENING_DATE": "K",
    "IN_BED": "L",
    "BEDTIME": "N",
    "WOKETIME": "O",
    "OUT_BED": "P",
    "SCHOOL_ATTEND": "L",
    "SCHOOL_START": "O",
    "SCHOOL_END": "Q",
    "HOME_ARRIVAL": "S",
    "NAP": "M",
    "NAPTIME": "T",
    "NAP_START": "V",
    "NAP_END": "W",
    "NAPTIME2": "U",
    "NAP2_START": "X",
    "NAP2_END": "Y",
    "NAP_OTHER": "NONE",
    "ACTIVITIES_LIGHTSOFF": "M",
    "ACTIVITIES_TV": "Q",
    "ACTIVITIES_TV_DURATION": "Y",
    "ACTIVITIES_TV_PLEASURE": "Z",
    "ACTIVITIES_TV_AROUSAL": "AA",
    "ACTIVITIES_TV_TYPE_COMEDY": "AB",
    "ACTIVITIES_TV_TYPE_HORROR": "AC",
    "ACTIVITIES_TV_TYPE_ROMANCE": "AD",
    "ACTIVITIES_TV_TYPE_ACTION": "AE",
    "ACTIVITIES_TV_TYPE_THRILLER": "AF",
    "ACTIVITIES_TV_TYPE_FANTASY": "AG",
    "ACTIVITIES_TV_TYPE_MYSTERY": "AH",
    "ACTIVITIES_TV_TYPE_DRAMA": "AI",
    "ACTIVITIES_TV_TYPE_OTHER": "AJ",
    "ACTIVITIES_TV_TYPE_OTHER_SPECIFY": "AJ",
    "ACTIVITIES_INTERNET": "R",
    "ACTIVITIES_INTERNET_DURATION": "AK",
    "ACTIVITIES_INTERNET_PLEASURE": "AL",
    "ACTIVITIES_INTERNET_AROUSAL": "AM",
    "ACTIVITIES_INTERNET_PLATFORM": "AN",
    "ACTIVITIES_PHONE": "S",
    "ACTIVITIES_PHONE_DURATION": "AO",
    "ACTIVITIES_PHONE_PLEASURE": "AP",
    "ACTIVITIES_PHONE_AROUSAL": "AQ",
    "ACTIVITIES_VIDEOGAMES": "T",
    "ACTIVITIES_VIDEOGAMES_DURATION": "AR",
    "ACTIVITIES_VIDEOGAMES_PLEASURE": "AS",
    "ACTIVITIES_VIDEOGAMES_AROUSAL": "AT",
    "ACTIVITIES_READ": "U",
    "ACTIVITIES_READ_DURATION": "AU",
    "ACTIVITIES_READ_PLEASURE": "AV",
    "ACTIVITIES_READ_AROUSAL": "AW",
    "ACTIVITIES_READ_TYPE_TEXTBOOK": "AX",
    "ACTIVITIES_READ_TYPE_HORROR": "AY",
    "ACTIVITIES_READ_ROMANCE": "AZ",
    "ACTIVITIES_READ_TYPE_ACTION": "BA",
    "ACTIVITIES_READ_TYPE_THRILLER": "BB",
    "ACTIVITIES_READ_TYPE_FANTASY": "BC",
    "ACTIVITIES_READ_TYPE_MYSTERY": "BD",
    "ACTIVITIES_READ_TYPE_DRAMA": "BE",
    "ACTIVITIES_READ_TYPE_OTHER": "BF",
    "ACTIVITIES_READ_TYPE_OTHER_SPECIFY": "BF",
    "ACTIVITIES_READ_FORMAT": "BG",
    "ACTIVITIES_MUSIC": "V",
    "ACTIVITIES_MUSIC_DURATION": "BH",
    "ACTIVITIES_MUSIC_TYPE": "BI",
    "ACTIVITIES_MUSIC_PLEASURE": "BJ",
    "ACTIVITIES_MUSIC_AROUSAL": "BK",
    "ACTIVITIES_OTHER": "BM",
    "ACTIVITIES_OTHER_DURATION": "BO",
    "ACTIVITIES_OTHER_PLEASURE": "BQ",
    "ACTIVITIES_OTHER_AROUSAL": "BR",
    "ACTIVITIES_OTHER2": "BN",
    "ACTIVITIES_OTHER2_DURATION": "BP",
    "ACTIVITIES_OTHER2_PLEASURE": "BS",
    "ACTIVITIES_OTHER2_AROUSAL": "BT",
    "ACTIVITIES_SLEEPAPP": "BU",
    "ACTIVITIES_SLEEPAPP_NAME": "BV",
    "ACTIVITIES_SLEEPAPP_USE_SOUNDS": "BW",
    "ACTIVITIES_SLEEPAPP_USE_STORIES": "BX",
    "ACTIVITIES_SLEEPAPP_USE_RELAX": "BY",
    "ACTIVITIES_SLEEPAPP_USE_MIDFULNESS": "BZ",
    "ACTIVITIES_SLEEPAPP_USE_MEDITATION": "CA",
    "ACTIVITIES_SLEEPAPP_USE_OTHER": "CB",
    "ACTIVITIES_SLEEPAPP_USE_SPECIFY": "CB",
    "ACTIVITIES_SLEEPAPP_DURATION": "CC",
    "ACTIVITIES_SLEEPAPP_HELPED": "CD",
    "PRE_AWL_WEAR": "FD",
    "PRE_AWL_ON": "FE",
    "PRE_AWL_OFF": "FF",
    "PRE_AWL_OTHER": "FG",
    "PRE_AWL_TIME_1": "FH",
    "PRE_AWL_DURATION_1": "FI",
    "PRE_AWL_TIME_2": "FJ",
    "PRE_AWL_DURATION_2": "FK",
    "PRE_AWL_TIME_3": "FL",
    "PRE_AWL_DURATION_3": "FM",
    "PRE_AWL_TIME_4": "FN",
    "PRE_AWL_DURATION_4": "FO",
    "MEDICATION_QUESTION": "EU",
    "MEDICATION_NAME": "EV",
}

HOURLY_MORNING: dict[str, dict[str, str]] = {
    "12_1am": {
        "PHONE": "DS",
        "COMPUTER": "DT",
        "TABLET": "DU",
        "VIDGAMES": "DV",
        "OTHER": "DW",
        "INDOORS": "FV",
    },
    "1_2am": {
        "PHONE": "DY",
        "COMPUTER": "DZ",
        "TABLET": "EA",
        "VIDGAMES": "EB",
        "OTHER": "EC",
        "INDOORS": "FW",
    },
    "2_3am": {
        "PHONE": "EE",
        "COMPUTER": "EF",
        "TABLET": "EG",
        "VIDGAMES": "EH",
        "OTHER": "EI",
        "INDOORS": "FX",
    },
    "3_4am": {
        "PHONE": "EK",
        "COMPUTER": "EL",
        "TABLET": "EM",
        "VIDGAMES": "EN",
        "OTHER": "EO",
        "INDOORS": "FY",
    },
    "4_5am": {
        "PHONE": "EQ",
        "COMPUTER": "ER",
        "TABLET": "ES",
        "VIDGAMES": "ET",
        "OTHER": "EU",
        "INDOORS": "FZ",
    },
    "5_6am": {
        "PHONE": "EW",
        "COMPUTER": "EX",
        "TABLET": "EY",
        "VIDGAMES": "EZ",
        "OTHER": "FA",
        "INDOORS": "GA",
    },
    "6_7pm": {
        "PHONE": "CG",
        "COMPUTER": "CH",
        "TABLET": "CI",
        "VIDGAMES": "CJ",
        "OTHER": "CK",
        "INDOORS": "FP",
        "OUTDOORS": "GC",
    },
    "7_8pm": {
        "PHONE": "CM",
        "COMPUTER": "CN",
        "TABLET": "CO",
        "VIDGAMES": "CP",
        "OTHER": "CQ",
        "INDOORS": "FQ",
        "OUTDOORS": "GD",
    },
    "8_9pm": {
        "PHONE": "CS",
        "COMPUTER": "CT",
        "TABLET": "CU",
        "VIDGAMES": "CV",
        "OTHER": "CW",
        "INDOORS": "FR",
        "OUTDOORS": "GE",
    },
    "9_10pm": {
        "PHONE": "CY",
        "COMPUTER": "CZ",
        "TABLET": "DA",
        "VIDGAMES": "DB",
        "OTHER": "DC",
        "INDOORS": "FS",
    },
    "10_11pm": {
        "PHONE": "DE",
        "COMPUTER": "DF",
        "TABLET": "DG",
        "VIDGAMES": "DH",
        "OTHER": "DI",
        "INDOORS": "FT",
    },
    "11_12am": {
        "PHONE": "DK",
        "COMPUTER": "DL",
        "TABLET": "DM",
        "VIDGAMES": "DN",
        "OTHER": "DO",
        "INDOORS": "FU",
    },
}

HOURLY_EVENING: dict[str, dict[str, str]] = {
    "6_7am": {
        "PHONE": "AA",
        "COMPUTER": "AB",
        "TABLET": "AC",
        "VIDGAMES": "AD",
        "OTHER": "AE",
        "INDOORS": "CX",
        "OUTDOORS": "DK",
    },
    "7_8am": {
        "PHONE": "AG",
        "COMPUTER": "AH",
        "TABLET": "AI",
        "VIDGAMES": "AJ",
        "OTHER": "AK",
        "INDOORS": "CY",
        "OUTDOORS": "DL",
    },
    "8_9am": {
        "PHONE": "AM",
        "COMPUTER": "AN",
        "TABLET": "AO",
        "VIDGAMES": "AP",
        "OTHER": "AQ",
        "INDOORS": "CZ",
        "OUTDOORS": "DM",
    },
    "9_10am": {
        "PHONE": "AS",
        "COMPUTER": "AT",
        "TABLET": "AU",
        "VIDGAMES": "AV",
        "OTHER": "AW",
        "INDOORS": "DA",
        "OUTDOORS": "DN",
    },
    "10_11am": {
        "PHONE": "AY",
        "COMPUTER": "AZ",
        "TABLET": "BA",
        "VIDGAMES": "BB",
        "OTHER": "BC",
        "INDOORS": "DB",
        "OUTDOORS": "DO",
    },
    "11_12pm": {
        "PHONE": "BE",
        "COMPUTER": "BF",
        "TABLET": "BG",
        "VIDGAMES": "BH",
        "OTHER": "BI",
        "INDOORS": "DC",
        "OUTDOORS": "DP",
    },
    "12_1pm": {
        "PHONE": "BM",
        "COMPUTER": "BN",
        "TABLET": "BO",
        "VIDGAMES": "BP",
        "OTHER": "BQ",
        "INDOORS": "DD",
        "OUTDOORS": "DQ",
    },
    "1_2pm": {
        "PHONE": "BS",
        "COMPUTER": "BT",
        "TABLET": "BU",
        "VIDGAMES": "BV",
        "OTHER": "BW",
        "INDOORS": "DE",
        "OUTDOORS": "DR",
    },
    "2_3pm": {
        "PHONE": "BY",
        "COMPUTER": "BZ",
        "TABLET": "CA",
        "VIDGAMES": "CB",
        "OTHER": "CC",
        "INDOORS": "DF",
        "OUTDOORS": "DS",
    },
    "3_4pm": {
        "PHONE": "CE",
        "COMPUTER": "CF",
        "TABLET": "CG",
        "VIDGAMES": "CH",
        "OTHER": "CI",
        "INDOORS": "DG",
        "OUTDOORS": "DT",
    },
    "4_5pm": {
        "PHONE": "CK",
        "COMPUTER": "CL",
        "TABLET": "CM",
        "VIDGAMES": "CN",
        "OTHER": "CO",
        "INDOORS": "DH",
        "OUTDOORS": "DU",
    },
    "5_6pm": {
        "PHONE": "CQ",
        "COMPUTER": "CR",
        "TABLET": "CS",
        "VIDGAMES": "CT",
        "OTHER": "CU",
        "INDOORS": "DI",
        "OUTDOORS": "DV",
    },
}

SPECIFY_COLUMNS: dict[str, str] = {"12_6am": "FC", "6_12pm": "BK", "12_6pm": "CW", "6_12am": "DQ"}

POMS_ITEMS: list[str] = [
    "DW",
    "DX",
    "DY",
    "DZ",
    "EA",
    "EB",
    "EC",
    "ED",
    "EE",
    "EF",
    "EG",
    "EH",
    "EI",
    "EJ",
    "EK",
    "EL",
    "EM",
    "EN",
    "EO",
    "EP",
    "EQ",
    "ER",
    "ES",
    "ET",
]
