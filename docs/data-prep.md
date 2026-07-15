# How the data was prepared: Women in STEM retention

This describes exactly what `projects/women-in-stem/scripts/prepare_data.py`
does to turn the raw NSCG survey file into the aggregates the dashboard reads.
Anyone should be able to follow this alongside the script and reproduce every
number on the page. Where the executed pipeline is narrower than the full
project plan, that is called out rather than glossed over.

## Where the data comes from

One source, no exceptions: the National Science Foundation's **2023 National
Survey of College Graduates** (NSCG), public use file. The National Center for
Science and Engineering Statistics runs the survey and publishes the microdata
at [ncses.nsf.gov](https://ncses.nsf.gov/explore-data/microdata/national-survey-college-graduates).

`scripts/download_data.py` pulls the file straight from the NSF and unzips it.
The zip is about 61 MB; unzipped it includes `epcg23.csv`, a 140 MB flat file
with one row per respondent (about 94,600 of them) and several hundred columns.
The raw file is not committed to the repository because of its size, so the
download script is the first thing to run.

The survey ships its own documentation, and the preparation leans on three
pieces of it: `LAYOUTPCG23.TXT` (the column list with positions and types),
`Dpcg23.xlsx` (a plain-English data dictionary), and `Ppcg23.html` (the full
codebook with every value label and its weighted frequency). The field and
occupation code lists below were read out of that codebook, not guessed.

## The columns that matter

Out of the several hundred, the analysis touches ten:

| Column | What it holds | Why |
|---|---|---|
| `SEX_2023` | Sex, `F` or `M` | Splits women from men |
| `BAYR` | Exact calendar year the first bachelor's degree was awarded | Assigns the graduation cohort |
| `N2BAMED` | Detailed field of that bachelor's degree, a six-digit code | Picks out the five majors |
| `N2OCPRMG` | Occupation of the current main job, grouped into eight major categories | Broad "works in STEM" test |
| `N3OCPRNG` | Occupation of the current main job, finer minor groups | Strict "works in the same field" test |
| `LFSTAT` | Labour-force status: employed, unemployed, not in the labour force | Employment denominators |
| `BADGRUS` | Whether the bachelor's was earned in the US | Keeps the population US-based |
| `NRREA` | The most important reason the person works outside their degree field | Direct evidence on why women leave |
| `AGE` | Age | Sanity checks |
| `WTSURVY` | The survey weight | Turns 3,400 sampled women into a national estimate |

That last column does a lot of work and deserves a plain explanation. A survey
does not interview everyone, and it does not interview a perfect miniature of
the country. Each respondent stands in for some number of real Americans, and
`WTSURVY` is that number. Every percentage on the dashboard is weighted, so it
describes the roughly 870,000 women the sample represents, not the 3,400 women
actually surveyed. Sample counts are shown alongside so you can see how solid
each estimate is.

## Who ends up in the study

Three filters cut the full file down to the analysis population:

1. The bachelor's degree was earned at a US institution (`BADGRUS == "Y"`).
2. It was awarded between 2005 and 2019 (`BAYR` in that range), so everyone
   falls into one of the three five-year cohorts.
3. Its field is one of the five studied.

That leaves 13,022 people, 3,413 of them women. The five majors are defined by
explicit six-digit `N2BAMED` code lists, taken from the codebook:

- **Computer Science** — computer and information sciences (general, computer
  science, systems analysis, information science, other).
- **Mathematics** — applied mathematics, general mathematics, statistics, other
  mathematics. Statistics is folded in here deliberately; the survey files it
  under mathematical sciences.
- **Physics** — physics (except biophysics) and astronomy/astrophysics. Physics
  and astronomy share a code family in the taxonomy, which happens to match
  Carolina's own background.
- **Chemistry** — chemistry except biochemistry. Biochemistry sits with the
  life sciences in this taxonomy and is left out on purpose.
- **Engineering** — the full set of nineteen engineering discipline codes, from
  aerospace through petroleum.

Using the detailed six-digit codes rather than the coarser major-group column
is a small precision choice: it keeps, for example, computer engineering with
engineering rather than letting it drift into computer science.

## Turning survey codes into the words on the page

Four derived flags do the real work, all built in `load()`:

- **`female`** is simply `SEX_2023 == "F"`.
- **`employed`** is `LFSTAT == "1"`.
- **`in_stem`** (the broad, headline definition) is being employed with a main
  job in occupation major groups 1 through 5. Those five groups are the science
  and engineering occupations under the NSF classification: computer and maths
  scientists, life scientists, physical scientists, social scientists, and
  engineers. A physics graduate working as a data scientist counts as retained
  in STEM under this definition, which is the point of calling it broad.
- **`same_field`** (the strict definition) is being employed in the specific
  occupation minor groups that match the degree. Computer science graduates
  have to be in computer occupations, chemists in chemistry occupations, and so
  on; each field's postsecondary teachers are credited too, and because the
  teaching groups span two fields they are counted for both. This is why the
  "same field" bars on the dashboard are always lower than the broad ones.

Cohorts come from `BAYR` using half-open five-year intervals, so no award year
lands in two cohorts: 2005–2009, 2010–2014, 2015–2019, labelled 2005–2010,
2010–2015 and 2015–2020 on the page to match how the study brief phrased them.
Years since the degree is just `2023 - BAYR`.

## The aggregates the script writes

`build()` produces one JSON file, `output/stem_aggregates.json`, holding every
number the dashboard needs. Nothing individual-level ever leaves this step;
the browser only ever sees weighted shares and counts.

- **Retention** — for every major, cohort and sex, the weighted share employed
  in STEM (broad and strict), plus the sample count so thin cells can be greyed
  out.
- **Women's current status** — where the women who studied each field are now,
  split into same field, other STEM, S&E-related work, outside STEM, and not
  employed. These sum to one and drive the stacked bars.
- **Reasons for leaving** — for women working outside their degree field, the
  weighted breakdown of the single most important reason they gave (`NRREA`):
  changed career interests, working conditions, family reasons, job location,
  no job available in the field, and other. This is the survey speaking in its
  own voice about why women leave, and it is the closest the data comes to a
  cause.
- **Time since degree** — the weighted share still in STEM for graduates 3–7,
  8–12 and 13–18 years out, by field and sex. A single survey cannot follow the
  same people over time, so this compares different graduates at different
  distances from their degree. Every bucket with at least a handful of
  respondents is kept so each field shows a full line; the dashboard fades the
  low-confidence points (fewer than 30 respondents) rather than dropping them.
- **Headline** — the overall weighted share of women and of men in STEM, and
  the population the women represent.

## A one-line summary of the transformation

Read one 140 MB survey file, keep ten columns, filter to US women and men
who earned a bachelor's in five fields between 2005 and 2019, translate the
survey's numeric codes into fields and occupations, weight everything by the
survey weight, and write a single small JSON of shares and counts. The 140 MB
of microdata becomes about 25 KB of aggregates, and only those aggregates ship.

## Where this is narrower than the full plan

The project plan (`docs/project1-plan.md`) lays out a more ambitious build: four
survey waves stitched into a pseudo-panel, a parametric survival model for time
to exit, and an American Community Survey cross-check. What is implemented here
uses the single 2023 wave and answers the time-to-leave question with the
current-status comparison across years-since-degree buckets. That is a genuine
and defensible method for a cross-sectional survey, and it supports the study's
main finding, that most of the gap is present early rather than accumulating
over a decade. The multi-wave panel and the survival model are the natural next
step, and the limitations section on the dashboard says so plainly.
