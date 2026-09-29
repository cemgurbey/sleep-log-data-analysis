"""Astronomical calculations: sunrise, sunset, and photoperiod per study date."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from astral import LocationInfo
from astral.sun import sun

from sleeplog.config import StudyConfig


def precompute_astral_data(config: StudyConfig) -> dict[str, dict[str, str]]:
    """Calculate sunrise/sunset/daylength once per study date (cached)."""
    loc = config.location
    city = LocationInfo(
        name=loc.name,
        region=loc.region,
        timezone=loc.timezone,
        latitude=loc.latitude,
        longitude=loc.longitude,
    )
    tz = ZoneInfo(loc.timezone)
    cache: dict[str, dict[str, str]] = {}
    for d_str in config.date_strings:
        d_obj = datetime.strptime(d_str, "%d-%m-%Y")
        try:
            s = sun(city.observer, date=d_obj.date(), tzinfo=tz)
            sunrise_str = s["sunrise"].strftime("%H:%M")
            sunset_str = s["sunset"].strftime("%H:%M")
            diff_secs = int((s["sunset"] - s["sunrise"]).total_seconds())
            daylength_str = f"{diff_secs // 3600:02d}:{(diff_secs % 3600) // 60:02d}"
        except Exception:
            sunrise_str, sunset_str, daylength_str = "", "", ""
        cache[d_str] = {"sunrise": sunrise_str, "sunset": sunset_str, "daylength": daylength_str}
    return cache


def study_dates(config: StudyConfig) -> list[str]:
    """Alias for the study's 'DD-MM-YYYY' date strings."""
    return config.date_strings
