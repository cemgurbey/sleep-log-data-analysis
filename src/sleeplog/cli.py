"""Command-line interface: generate synthetic data or run the full pipeline."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from sleeplog.config import SiteLocation, StudyConfig
from sleeplog.pipeline import run
from sleeplog.synthetic import generate_survey_workbooks


def _date(s: str) -> date:
    return date.fromisoformat(s)


def _base_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--start", type=_date, default="2022-03-22", help="Study start date (YYYY-MM-DD)"
    )
    p.add_argument("--end", type=_date, default="2022-03-28", help="Study end date (YYYY-MM-DD)")
    return p


def generate_main() -> None:
    p = _base_parser()
    p.description = "Generate artificial Morning/Evening sleep survey workbooks."
    p.add_argument("--out", type=Path, default=Path("data"), help="Output directory")
    p.add_argument("--participants", type=int, default=12)
    p.add_argument("--seed", type=int, default=7)
    args = p.parse_args()

    config = StudyConfig(start_date=args.start, end_date=args.end, location=SiteLocation())
    morning, evening = generate_survey_workbooks(args.out, config, args.participants, args.seed)
    print(f"Morning: {morning}")
    print(f"Evening: {evening}")


def run_main() -> None:
    p = _base_parser()
    p.description = "Run the sleep-log analysis pipeline on survey workbooks."
    p.add_argument("--morning", type=Path, required=True, help="Morning survey .xlsx/.csv")
    p.add_argument("--evening", type=Path, required=True, help="Evening survey .xlsx/.csv")
    p.add_argument("--out", type=Path, default=Path("outputs"), help="Output directory")
    args = p.parse_args()

    config = StudyConfig(start_date=args.start, end_date=args.end, location=SiteLocation())
    run(config, args.morning, args.evening, args.out)
