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

SALARY_SKIP = 9999998  # logical skip code in the NSCG salary field


def weighted_median(values, weights):
    order = np.argsort(values)
    v, w = np.asarray(values)[order], np.asarray(weights)[order]
    cum = np.cumsum(w)
    if len(v) == 0:
        return None
    return float(v[np.searchsorted(cum, cum[-1] / 2.0)])


def spearman_exact(x, y):
    """Spearman rank correlation with an exact permutation p-value.

    Only five fields go into this correlation, so the full permutation
    distribution is tiny and there is no need for scipy here.
    """
    from itertools import permutations

    def ranks(a):
        order = np.argsort(a)
        r = np.empty(len(a))
        r[order] = np.arange(len(a))
        return r

    rx, ry = ranks(x), ranks(y)

    def rho_of(a, b):
        return float(np.corrcoef(a, b)[0, 1])

    rho = rho_of(rx, ry)
    n = len(x)
    count = 0
    total = 0
    for perm in permutations(range(n)):
        total += 1
        if abs(rho_of(rx, ry[list(perm)])) >= abs(rho) - 1e-12:
            count += 1
    return rho, count / total


def weighted_share(mask, weights):
    total = weights.sum()
    return float((weights[mask]).sum() / total) if total > 0 else None


def load():
    cols = ["SEX_2023", "BAYR", "N2BAMED", "N2OCPRMG", "N3OCPRNG",
            "SALARY", "LFSTAT", "BADGRUS", "AGE", "WTSURVY", "NRREA"]
    df = pd.read_csv(DATA, usecols=cols,
                     dtype={"SEX_2023": str, "N2BAMED": str, "N2OCPRMG": str,
                            "N3OCPRNG": str, "LFSTAT": str, "BADGRUS": str,
                            "NRREA": str})

    df["BAYR"] = pd.to_numeric(df["BAYR"], errors="coerce")
    df["SALARY"] = pd.to_numeric(df["SALARY"], errors="coerce")
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

    # Median salaries and the gender pay gap among graduates of each major
    # currently working in S&E occupations.
    sal = df[df["in_stem"] & df["SALARY"].gt(0) & df["SALARY"].lt(SALARY_SKIP)]
    gap_rows = []
    for major, g in sal.groupby("major"):
        med = {}
        for female, gg in g.groupby("female"):
            med["Women" if female else "Men"] = weighted_median(
                gg["SALARY"].values, gg["WTSURVY"].values)
        if "Men" in med and "Women" in med and med["Men"]:
            gap = (med["Men"] - med["Women"]) / med["Men"]
        else:
            gap = None
        gap_rows.append({"major": major,
                         "median_salary_women": med.get("Women"),
                         "median_salary_men": med.get("Men"),
                         "pay_gap": gap,
                         "n_sample": int(len(g))})
    out["pay_gap"] = gap_rows

    # Pay gap vs female attrition, the scatter behind the correlation question.
    att = {}
    for major, g in df[df["female"]].groupby("major"):
        att[major] = 1.0 - weighted_share(g["in_stem"].values, g["WTSURVY"].values)
    scatter = []
    for row in gap_rows:
        if row["pay_gap"] is not None:
            scatter.append({"major": row["major"], "pay_gap": row["pay_gap"],
                            "female_attrition": att[row["major"]]})
    out["gap_vs_attrition"] = scatter
    if len(scatter) >= 3:
        x = np.array([s["pay_gap"] for s in scatter])
        y = np.array([s["female_attrition"] for s in scatter])
        out["gap_attrition_pearson"] = float(np.corrcoef(x, y)[0, 1])
        rho, p = spearman_exact(x, y)
        out["gap_attrition_spearman"] = {"rho": rho, "p": p}

    # Share still in STEM by years since the bachelor's, the closest a single
    # cross-section gets to a time-to-exit curve. Bucketed to keep cells stable.
    buckets = [(3, 7, "3-7"), (8, 12, "8-12"), (13, 18, "13-18")]
    curve = []
    for major, g in df.groupby("major"):
        for female, gg in g.groupby("female"):
            for lo, hi, label in buckets:
                sel = gg[gg["yrs_since_ba"].between(lo, hi)]
                if len(sel) < 30:
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
