# Do women who study STEM stay in STEM?

A retention study of women in United States STEM fields, built on real National
Science Foundation survey data. It follows women who earned a bachelor's degree
in computer science, mathematics, physics, chemistry or engineering between 2005
and 2020, and asks three questions: how many are actually practising today, how
that varies by field and graduation cohort, whether fields with wider gender pay
gaps lose more women, and how long after graduation the leaving happens.

**Live dashboard:** https://carolina-cenzano.github.io/women-in-stem-retention/

## What it found

- Under half of US women who earned a bachelor's in these five fields work in a
  science or engineering occupation today, against roughly six in ten men with
  the same degrees.
- When women do work outside their field, no single reason dominates. Changing
  career interests, working conditions and family reasons together outweigh any
  one factor, so simple single-cause explanations for the leak fall short.
- Most of the gap is present early. Women three to seven years past their degree
  already practise at rates close to women more than a decade out, which points
  at the entry into the workforce, not a slow mid-career drift, as the main leak.

Every figure is weighted to represent the US population, and any estimate built
on fewer than 30 survey respondents is flagged rather than shown as if it were
solid.

## How it works

The analysis reads the 2023 National Survey of College Graduates public use
file, keeps the columns it needs, filters to US graduates of the five fields
across three cohorts, translates the survey's occupation and field codes into
plain categories, weights everything by the survey weight, and writes a small
set of aggregates that the dashboard reads. The dashboard is plain HTML with
Plotly.js; there is no server and no build framework.

A full, step-by-step account of the data preparation is in
[docs/data-prep.md](docs/data-prep.md).

## Reproduce it

The raw survey file (about 140 MB) is not committed. One script fetches it:

```bash
python scripts/download_data.py     # downloads the NSCG 2023 file from the NSF
python scripts/prepare_data.py      # builds output/stem_aggregates.json
python scripts/build_site_data.py   # wraps it into data.js for the page
```

Requirements: Python 3.10 or newer, with pandas, numpy and openpyxl. To view the
site, open `index.html` or serve the folder with any static server.

## Data source

National Center for Science and Engineering Statistics, National Survey of
College Graduates: 2023. Public use file.
https://ncses.nsf.gov/explore-data/microdata/national-survey-college-graduates

## Limitations, honestly

This is a single cross-sectional survey, not a study that tracks the same people
over time, so the time-since-degree view compares different women at different
career stages rather than following individuals. The results are descriptive:
they show what women who studied these fields are doing now and the reasons they
give for leaving, not why any individual left. The per-field reason breakdowns
rest on small samples and are flagged where they do. This is stated on the
dashboard itself. The analysis and any errors in it are my own.
