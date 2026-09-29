# sleep-log-data-analysis

<a href="https://colab.research.google.com/github/cemgurbey/sleep-log-data-analysis/blob/main/notebooks/sleep_log_analysis.ipynb" target="_parent"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/></a>

Standardized processing pipeline for longitudinal sleep diary and activity survey data (Morning and Evening diaries). Reads raw survey workbooks, validates date/time quality, and produces publication-ready datasets for SPSS, R, or Python.

## How it started

The original tool was a single 95 KB Jupyter notebook: every step — configuration, parsing, analysis, export — lived inline in ~23 cells with module-level globals. It worked, but it was hard to test, hard to reuse, and any change to the research schema meant editing a giant cell. It also had no runnable example: without real survey files you couldn't execute it at all (the built-in sample writer hand-rolled `.xlsx` files as raw XML strings and only covered a handful of columns).

## What changed in v2

| Before | After |
|---|---|
| One monolithic notebook | Installable Python package (`src/sleeplog/`) + a lean Colab notebook |
| Hand-rolled `.xlsx` via XML strings | Synthetic data generator built on `openpyxl` with realistic sleep-behavior models |
| No runnable example | `sleeplog.synthetic.generate_survey_workbooks()` — run the notebook as-is, get example results immediately |
| Globals scattered across cells | `StudyConfig` / `SiteLocation` dataclasses, `pathlib` paths, type hints throughout |
| `!pip install`, ad-hoc Colab snippets | `%pip install` from GitHub, `google.colab.files.upload()` / `files.download()` |
| Fixed `astral` timezone handling | `zoneinfo.ZoneInfo`-based tz handling (stdlib, no `pytz` dependency quirks) |
| Boundary early-termination codes (888) never applied — an hour-key parsing bug meant the condition could never match | Fixed: day-1 evening hours and last-day night hours in ROW3 are now correctly coded 888 |
| No linting | `ruff` (lint + format), `pyproject.toml` packaging, CLI entry points |

The research schema itself — column-letter mappings, response decoders, coding conventions (999/888), POMS-A subscales, circular time statistics — is preserved verbatim.

## Quickstart

**Google Colab (recommended):** open the notebook above and run all cells. It installs the package from GitHub, generates synthetic survey data, runs the full pipeline, shows example charts, and lets you download the outputs. To use your own data instead, set `USE_SYNTHETIC = False` and upload your Morning/Evening workbooks when prompted.

**Local:**

```bash
pip install -e .
sleeplog-generate --out data --participants 12 --seed 7
sleeplog-run --morning "data/Sleep and Activity Log - Morning (synthetic).xlsx" \
             --evening "data/Sleep and Activity Log - Evening (synthetic).xlsx" \
             --out outputs
```

Or from Python:

```python
from datetime import date
from sleeplog import SiteLocation, StudyConfig, run
from sleeplog.synthetic import generate_survey_workbooks

config = StudyConfig(start_date=date(2022, 3, 22), end_date=date(2022, 3, 28),
                     location=SiteLocation())  # Montreal by default
morning, evening = generate_survey_workbooks("data", config, n_participants=12, seed=7)
run(config, morning, evening, out_dir="outputs")
```

## Synthetic data

`sleeplog.synthetic` generates artificial Morning/Evening survey workbooks in the exact column layout the pipeline expects:

- 12 participants (configurable) with individual chronotypes, weekend bedtime shifts, and sleep-duration distributions
- Realistic pre-bed activities (TV, phone, reading, …) with durations and pleasure/arousal ratings
- Hourly device-use and indoor/outdoor lighting blocks, school schedules, naps, POMS-A mood items, sleep-app and Actiwatch logs, medications
- A few deliberately invalid entries (bad date, unparseable time) so the QA reports have something to flag
- Seeded (`seed=7` by default) for reproducible example results

## Outputs

| File | Contents |
|---|---|
| `AVERAGE_AND_SD_OUTPUTS.xlsx` | Circular mean & SD of bedtime, waketime, in-bed, out-of-bed — weekday / weekend / total |
| `SL_OUTPUTS.xlsx` | Per-participant survey completion counts (weekday vs weekend) |
| `SLx_OUTPUTS_ROW1.xlsx` | Daily: sunrise/sunset/daylength, sleep timing, naps, school, pre-bed activities, hourly lighting |
| `SLx_OUTPUTS_ROW2.xlsx` | Daily: activity details, sleep-app metrics, Actiwatch logs, POMS-A items + mood subscales |
| `SLx_OUTPUTS_ROW3.xlsx` | Daily: 24-hour hourly media use across devices (888 boundary codes applied) |
| `SLx_OUTPUTS_ROW4.xlsx` | Daily: medication logs |
| `INVALID_DATETIME_ENTRIES_*.xlsx` | QA report of corrupt dates / unparseable times |
| `ERROR_LOG.txt` | Processing audit log |

Research codes: `999` = did not attend / did not answer / invalid, `888` = not applicable due to study boundary, `99:00` = missing time.

## Project structure

```
src/sleeplog/
├── config.py      # StudyConfig/SiteLocation dataclasses, column mappings, research codes
├── parsing.py     # time parsing + circular (noon-anchored) time math
├── decoders.py    # survey response decoders -> standardized codes
├── synthetic.py   # artificial survey data generator
├── ingest.py      # workbook loading + date/time QA validation
├── astro.py       # sunrise/sunset/photoperiod via astral
├── transform.py   # completion summaries, circular stats, ROW1–ROW4 builders
├── pipeline.py    # run(): ingest -> analyze -> export -> summary
└── cli.py         # sleeplog-generate / sleeplog-run
notebooks/
└── sleep_log_analysis.ipynb   # lean Colab notebook: configure -> data -> run -> visualize
```

## Development

```bash
pip install -e ".[dev]"
ruff check src/ && ruff format src/
```

Requires Python 3.10+.
