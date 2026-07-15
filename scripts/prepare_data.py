"""Builds the aggregate tables behind the Women in STEM retention study.

Reads the NSCG 2023 public use file (epcg23.csv, from the NCSES microdata
site) and writes precomputed JSON aggregates that the dashboard loads.
Everything downstream of this script is derived from those aggregates, so
this is the only place where the microdata gets touched.

Usage:
    python prepare_data.py
Expects the extracted survey file at ../data/pcg23Public/epcg23.csv
"""

import json
import os

import numpy as np
import pandas as pd

DATA = os.path.join(os.path.dirname(__file__), "..", "data", "pcg23Public", "epcg23.csv")
OUT = os.path.join(os.path.dirname(__file__), "..", "output")

# Field-of-study codes for the first bachelor's degree (N2BAMED, "best code").
# Labels come from the NSCG 2023 codebook (Ppcg23.html).
MAJORS = {
    "Computer Science": ["116710", "116730", "116740", "116760", "116770"],
    "Mathematics": ["128410", "128420", "128440", "128450"],  # includes statistics
    "Physics": ["338710", "338780"],  # physics + astronomy/astrophysics
    "Chemistry": ["318730"],  # chemistry except biochemistry
    "Engineering": [
        "517210", "527250", "537230", "537260", "547270", "547280",
        "557330", "567350", "577220", "577240", "577290", "577300",
        "577310", "577340", "577360", "577380", "577390", "577400",
        "577410",
    ],
}

# Occupation minor groups (N3OCPRNG) that count as working in the same field
# as the degree. Postsecondary teaching groups span two fields, so they are
# credited to both (18 covers computer and math sciences, 38 covers the
# physical sciences).
SAME_FIELD_OCC = {
    "Computer Science": {"11", "18"},
    "Mathematics": {"12", "18"},
    "Physics": {"33", "34", "38"},
    "Chemistry": {"31", "38"},
    "Engineering": {"51", "52", "53", "54", "55", "56", "57", "58"},
}

# Cohort labels follow the study brief; intervals are half-open so each
# cohort covers exactly five award years and no year lands in two cohorts.
COHORTS = [
    ("2005-2010", 2005, 2009),
    ("2010-2015", 2010, 2014),
    ("2015-2020", 2015, 2019),
]

# Primary reason for working outside the field of the highest degree (NRREA).
NRREA_LABELS = {
    "1": "Pay, promotion opportunities",
    "2": "Working conditions",
    "3": "Job location",
    "4": "Change in career or professional interests",
    "5": "Family-related reasons",
    "6": "Job in field not available",
    "7": "Other",
}

def weighted_share(mask, weights):
    total = weights.sum()
    return float((weights[mask]).sum() / total) if total > 0 else None


def load():
    cols = ["SEX_2023", "BAYR", "N2BAMED", "N2OCPRMG", "N3OCPRNG",
            "LFSTAT", "BADGRUS", "AGE", "WTSURVY", "NRREA"]
    df = pd.read_csv(DATA, usecols=cols,
                     dtype={"SEX_2023": str, "N2BAMED": str, "N2OCPRMG": str,
                            "N3OCPRNG": str, "LFSTAT": str, "BADGRUS": str,
                            "NRREA": str})

    df["BAYR"] = pd.to_numeric(df["BAYR"], errors="coerce")
    df["WTSURVY"] = pd.to_numeric(df["WTSURVY"], errors="coerce")

    # Bachelor's earned at a US institution, award years 2005-2019, so the
    # population is exactly the three five-year cohorts.
    df = df[(df["BADGRUS"] == "Y") & df["BAYR"].between(2005, 2019)]

    code_to_major = {c: m for m, codes in MAJORS.items() for c in codes}
    df["major"] = df["N2BAMED"].map(code_to_major)
    df = df.dropna(subset=["major", "WTSURVY"]).copy()

    df["female"] = df["SEX_2023"] == "F"
    df["employed"] = df["LFSTAT"] == "1"
    # NCSES convention: occupation major groups 1-5 are S&E occupations.
    df["in_stem"] = df["employed"] & df["N2OCPRMG"].isin(list("12345"))
    df["same_field"] = df.apply(
        lambda r: r["employed"] and r["N3OCPRNG"] in SAME_FIELD_OCC[r["major"]],
        axis=1)

    def cohort(yr):
        for name, lo, hi in COHORTS:
            if lo <= yr <= hi:
                return name
        return None
    df["cohort"] = df["BAYR"].apply(cohort)
    df["yrs_since_ba"] = 2023 - df["BAYR"]
    return df


def build(df):
    out = {"source": "NSF NCSES, National Survey of College Graduates 2023 public use file",
           "note": "Weighted estimates using WTSURVY. Population: first bachelor's degree "
                   "earned at a US institution, award years 2005-2020, in the five majors studied.",
           "majors": list(MAJORS.keys())}

    # Retention by major, cohort and sex: share of graduates currently working
    # in any S&E occupation, plus the stricter same-field share.
    rows = []
    for (major, cohort, female), g in df.groupby(["major", "cohort", "female"]):
        w = g["WTSURVY"].values
        rows.append({
            "major": major, "cohort": cohort,
            "sex": "Women" if female else "Men",
            "n_sample": int(len(g)),
            "pop_est": float(w.sum()),
            "in_stem": weighted_share(g["in_stem"].values, w),
            "same_field": weighted_share(g["same_field"].values, w),
            "employed": weighted_share(g["employed"].values, w),
        })
    out["retention"] = rows

    # Current status breakdown for women, by major (all cohorts pooled).
    status_rows = []
    for major, g in df[df["female"]].groupby("major"):
        w = g["WTSURVY"].values
        in_field = g["same_field"].values
        other_stem = (g["in_stem"] & ~g["same_field"]).values
        se_related = (g["employed"] & (g["N2OCPRMG"] == "6")).values
        non_se = (g["employed"] & (g["N2OCPRMG"] == "7")).values
        not_emp = (~g["employed"]).values
        status_rows.append({
            "major": major, "n_sample": int(len(g)),
            "in_field": weighted_share(in_field, w),
            "other_stem": weighted_share(other_stem, w),
            "se_related": weighted_share(se_related, w),
            "non_se": weighted_share(non_se, w),
            "not_employed": weighted_share(not_emp, w),
        })
    out["women_status"] = status_rows

    # Share still in STEM by years since the bachelor's, the closest a single
    # cross-section gets to a time-to-exit curve. Every bucket with at least a
    # handful of respondents is kept; the dashboard fades the low-confidence
    # ones (n < 30) rather than dropping them, so every field shows a full line.
    buckets = [(3, 7, "3-7"), (8, 12, "8-12"), (13, 18, "13-18")]
    curve = []
    for major, g in df.groupby("major"):
        for female, gg in g.groupby("female"):
            for lo, hi, label in buckets:
                sel = gg[gg["yrs_since_ba"].between(lo, hi)]
                if len(sel) < 10:
                    continue
                curve.append({
                    "major": major, "sex": "Women" if female else "Men",
                    "years_since_ba": label,
                    "in_stem": weighted_share(sel["in_stem"].values, sel["WTSURVY"].values),
                    "n_sample": int(len(sel)),
                })
    out["stem_by_years_since_ba"] = curve

    # Why people work outside their degree field, in the survey's own words.
    # NRREA is asked of everyone employed whose principal job is not related
    # to their highest degree; here it is broken out for the women in the
    # study population.
    reasons = []
    nr = df[df["female"] & df["NRREA"].isin(NRREA_LABELS)]
    for major, g in nr.groupby("major"):
        w = g["WTSURVY"].values
        row = {"major": major, "n_sample": int(len(g))}
        for code, label in NRREA_LABELS.items():
            row[label] = weighted_share((g["NRREA"] == code).values, w)
        reasons.append(row)
    out["women_outside_field_reasons"] = reasons

    # Overall headline numbers.
    women = df[df["female"]]
    out["headline"] = {
        "women_sample": int(len(women)),
        "women_pop_est": float(women["WTSURVY"].sum()),
        "women_in_stem": weighted_share(women["in_stem"].values, women["WTSURVY"].values),
        "men_in_stem": weighted_share(df.loc[~df["female"], "in_stem"].values,
                                      df.loc[~df["female"], "WTSURVY"].values),
    }
    return out


def main():
    df = load()
    print("analysis sample:", len(df), "records")
    print(df.groupby(["major", "female"]).size())
    result = build(df)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "stem_aggregates.json")
    with open(path, "w") as f:
        json.dump(result, f, indent=1)
    print("wrote", path)


if __name__ == "__main__":
    main()
