"""
Clean data/raw_extract.csv into the analysis table and write the cleaning log.

Usage:  python scripts/clean.py
Output: data/bmw_clean.csv, data/bmw_clean.xlsx, data/cleaning_log.csv, data/validation_report.csv
"""
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# Annexure-I lists the same 37 entities in the same order every year (2020-2024).
# Canonical names follow the current official spelling (and the Survey of India map names).
CANON = {
    1: "Andaman & Nicobar Islands", 2: "Andhra Pradesh", 3: "Arunachal Pradesh", 4: "Assam",
    5: "Bihar", 6: "Chandigarh", 7: "Chhattisgarh",
    8: "Dadra & Nagar Haveli and Daman & Diu", 9: "Delhi", 10: "Goa", 11: "Gujarat",
    12: "Haryana", 13: "Himachal Pradesh", 14: "Jharkhand", 15: "Jammu & Kashmir",
    16: "Karnataka", 17: "Kerala", 18: "Ladakh", 19: "Lakshadweep", 20: "Madhya Pradesh",
    21: "Maharashtra", 22: "Manipur", 23: "Meghalaya", 24: "Mizoram", 25: "Nagaland",
    26: "Odisha", 27: "Puducherry", 28: "Punjab", 29: "Rajasthan", 30: "Sikkim",
    31: "Tamil Nadu", 32: "Telangana", 33: "Tripura", 34: "Uttarakhand", 35: "Uttar Pradesh",
    36: "West Bengal", 37: "DGAFMS (Armed Forces)",
}
UT = {1, 6, 8, 9, 15, 18, 19, 27}
NOT_A_STATE = {37}  # Directorate General Armed Forces Medical Services: national, not mappable

# Genuine naming variants found in the PDFs (as opposed to fragments of names that wrap
# across lines, which are matched by serial number and not worth logging individually).
NAME_VARIANTS = {
    "Andaman Nicobar": "Shortened name; official name is Andaman & Nicobar Islands",
    "Telengana": "Misspelling in CPCB tables (all five years)",
    "J & K": "Abbreviation",
    "Dadra & Nagar Haveli": "Report lists merged UT under old pre-2020 names",
    "Daman &Diu and Dadra & Nagar Haveli": "UTs merged on 26-Jan-2020 into "
                                           "'Dadra & Nagar Haveli and Daman & Diu'; use the merged name",
    "DGAFMS": "Armed Forces Medical Services: a national body, not a state. Kept for totals, "
              "is_mappable = FALSE",
}

# Rules applied to every cell (logged once, not per cell)
RULES = [
    ("Nil / NIL / nil", "0", "rule", "'Nil' in the report means none reported -> 0"),
    ("INP / NA / ask / M", "blank", "rule",
     "INP = information not provided, NA = not applicable; 'ask' and 'M' are placeholders "
     "left in the published tables -> blank (NULL), never 0"),
    ("1,23,456", "123456", "rule", "Indian digit grouping removed"),
    ("state names", "canonical", "rule",
     "Every year lists the same 37 entities in the same order; rows matched on serial no. "
     "and checked against the name text"),
    ("Jammu & Kashmir / Ladakh", "kept separate", "rule",
     "Split into two UTs on 31-Oct-2019, so all five years already report them separately"),
    ("COVID-19 BMW row", "excluded", "rule",
     "2020 and 2021 Annexures add a national-only COVID-19 BMW line (118 and 80 t/day) with no "
     "state split. State rows are non-COVID only, so 2020-21 totals are 656.7 and 683.9 t/day, "
     "not the 774 and 764 t/day headline figures"),
    ("Printed 'Total' rows", "not used", "rule",
     "Totals are recomputed from state rows. CPCB's printed bed totals omit Bihar in 2021 "
     "(-104,391) and Gujarat in 2022 (-223,997, the one cell stored as text '2,23,997')"),
    ("Orissa", "Odisha", "rule",
     "Renamed in 2011; not present in 2020-24 tables, mapping kept for older reports"),
]

KEEP = {
    "total_hcf": "healthcare_facilities",
    "beds": "beds",
    "generated_kg_day": "waste_generated_kg_day",
    "treated_kg_day": "waste_treated_kg_day",
    "cbwtf_operational": "cbwtfs",
    "hcf_with_captive": "captive_plants",
}
EXTRA = ["bedded_hcf", "nonbedded_hcf", "cbwtf_under_construction",
         "treated_by_captive_kg_day", "treated_by_cbwtf_kg_day"]

ZERO_TOKENS = {"nil", "0l"}            # reported as nothing -> 0
NULL_TOKENS = {"inp", "na", "ask", "m", ""}  # information not provided / not applicable / junk -> blank

# Manual corrections, each checked by eye against the PDF page. (year, sno, column): (value, reason)
OVERRIDES = {
    (2020, 18, "total_hcf"): (389, "Cell missing in Annexure-I row; = bedded 333 + non-bedded 56, "
                                   "matches HCF table on p.9 and the printed national total"),
    (2021, 8, "cbwtf_operational"): (0, "Cell blank; report says waste is handed over to a Gujarat "
                                        "CBWTF (same as 2020, 2022-24), so 0 own CBWTFs"),
    (2022, 31, "beds"): (None, "19,114 beds is a typo (145,848 in 2021; 204,717 in 2023). "
                               "Set blank rather than guess; beds-per-CBWTF is blank for TN 2022"),
    (2022, 17, "treated_kg_day"): (62122.15, "Reported treated 29,175 contradicts the same row's "
                                             "breakdown (captive 2,372.15 + CBWTF 59,750 = 62,122.15) "
                                             "and 2021/2023 (~100% treated). Used the breakdown sum. "
                                             "Note: national total for 2022 will differ from "
                                             "CPCB's printed 645,411.85 by +32,947"),
}

log = []


def note(year, state, field, before, after, kind, reason):
    log.append(dict(year=year, state=state, field=field, original=before,
                    cleaned=after, fix_type=kind, reason=reason))


def to_num(raw, year, state, field):
    s = str(raw).strip() if pd.notna(raw) else ""
    low = s.lower().rstrip("*")
    if low in ZERO_TOKENS:
        if low != "nil":
            note(year, state, field, s, 0, "value", "OCR artefact '0l' read as 0")
        return 0.0
    if low in NULL_TOKENS:
        if low:
            note(year, state, field, s, "", "missing",
                 {"inp": "INP = information not provided", "na": "NA = not applicable",
                  "ask": "Placeholder 'ask' left in published table"}.get(low, "Non-numeric junk in cell"))
        return None
    t = s.replace(",", "").replace(" ", "")
    if re.fullmatch(r"\d+(\.\d+)?", t):
        if "," in s:
            note(year, state, field, s, float(t), "format", "Indian digit grouping removed")
        return float(t)
    # Text in a numeric column (e.g. 'Utilising CBWTF of Gujarat')
    note(year, state, field, s, "" if field != "cbwtf_operational" else 0, "value",
         "Text in numeric cell" + ("; waste handed to another state's CBWTF, so 0 own CBWTFs"
                                   if field == "cbwtf_operational" else ""))
    return 0.0 if field == "cbwtf_operational" else None


def main():
    raw = pd.read_csv(DATA / "raw_extract.csv", dtype=str)
    out = []
    for _, r in raw.iterrows():
        year, sno = int(r.year), int(r.sno)
        state = CANON[sno]
        raw_name = r.state_raw.strip() if isinstance(r.state_raw, str) else ""
        for variant, why in NAME_VARIANTS.items():
            if raw_name.startswith(variant) and variant != state:
                note(year, state, "state", variant, state, "name", why)
                break
        rec = dict(year=year, state=state, state_type="UT" if sno in UT else "State",
                   is_mappable=sno not in NOT_A_STATE)
        for col in list(KEEP) + EXTRA:
            key = (year, sno, col)
            if key in OVERRIDES:
                val, why = OVERRIDES[key]
                note(year, state, col, r[col], "" if val is None else val, "manual", why)
                rec[col] = None if val is None else float(val)
            else:
                rec[col] = to_num(r[col], year, state, col)
        out.append(rec)

    df = pd.DataFrame(out).rename(columns=KEEP)
    df = validate_and_fix(df)
    df["geo_name"] = df.state + ", India"  # unambiguous string for Power BI's map geocoder
    for (y, sno, col), (_, why) in OVERRIDES.items():
        i = df.index[(df.year == y) & (df.state == CANON[sno])][0]
        df.at[i, "data_flag"] = (df.at[i, "data_flag"] + f"; {col} corrected/blanked, see log").strip("; ")

    cols = ["year", "state", "geo_name", "state_type", "is_mappable", "healthcare_facilities", "beds",
            "waste_generated_kg_day", "waste_treated_kg_day", "cbwtfs", "captive_plants"] \
        + EXTRA + ["data_flag"]
    df = df[cols].sort_values(["year", "state"])
    df.to_csv(DATA / "bmw_clean.csv", index=False)
    lg = pd.DataFrame(
        [dict(year="all", state="all", field="all", original=o, cleaned=c, fix_type=k, reason=why)
         for o, c, k, why in RULES] + log)
    lg.to_csv(DATA / "cleaning_log.csv", index=False)
    with pd.ExcelWriter(DATA / "bmw_clean.xlsx") as xw:
        df.to_excel(xw, sheet_name="bmw_clean", index=False)
        lg.to_excel(xw, sheet_name="cleaning_log", index=False)
        pd.read_csv(DATA / "validation_report.csv").to_excel(xw, sheet_name="validation", index=False)
    print(f"{len(df)} rows -> bmw_clean.csv; {len(lg)} log entries")


def validate_and_fix(df):
    """Rule checks. Failures are logged and flagged; values are only changed when the
    PDF itself provides the correct figure (e.g. a component breakdown)."""
    df["data_flag"] = ""
    checks = []

    def flag(i, msg):
        df.at[i, "data_flag"] = (df.at[i, "data_flag"] + "; " + msg).strip("; ")

    for i, r in df.iterrows():
        y, s = r.year, r.state
        # 1. bedded + non-bedded = total HCFs
        if pd.notna(r.bedded_hcf) and pd.notna(r.nonbedded_hcf) and pd.notna(r.healthcare_facilities):
            if abs(r.bedded_hcf + r.nonbedded_hcf - r.healthcare_facilities) > 1:
                checks.append((y, s, "hcf_sum", f"{r.bedded_hcf:.0f}+{r.nonbedded_hcf:.0f}"
                               f"≠{r.healthcare_facilities:.0f}"))
        # 2. treated must not exceed generated
        g, t = r.waste_generated_kg_day, r.waste_treated_kg_day
        if pd.notna(g) and pd.notna(t) and t > g * 1.001:
            checks.append((y, s, "treated>generated", f"{t} > {g}"))
            flag(i, "treated reported above generated")
        # 3. treated ≈ captive-treated + CBWTF-treated
        c1, c2 = r.treated_by_captive_kg_day, r.treated_by_cbwtf_kg_day
        if pd.notna(t) and pd.notna(c2):
            comp = (c1 or 0) + c2
            if abs(comp - t) > max(5, 0.02 * t):
                checks.append((y, s, "treated_components", f"treated {t} vs captive+CBWTF {comp:.2f}"))
                flag(i, "treated ≠ captive + CBWTF breakdown")
        # 4. Waste per bed far outside the national range (~0.2-0.6 kg/bed/day incl. non-bedded HCFs)
        if pd.notna(g) and pd.notna(r.beds) and r.beds > 0 and g / r.beds > 2:
            checks.append((y, s, "waste_per_bed_outlier", f"{g / r.beds:.2f} kg/bed/day"))
            flag(i, f"waste per bed outlier ({g / r.beds:.1f} kg/day)")

    # 5. Year-on-year jumps in beds (>50% or <-50%) suggest typos
    df = df.sort_values(["state", "year"]).reset_index(drop=True)
    for s, g in df.groupby("state"):
        g = g.sort_values("year")
        prev = None
        for i, r in g.iterrows():
            if prev is not None and pd.notna(r.beds) and pd.notna(prev.beds) and prev.beds > 1000:
                ch = r.beds / prev.beds - 1
                if abs(ch) > 0.5:
                    checks.append((r.year, s, "beds_jump", f"{prev.beds:.0f} -> {r.beds:.0f} ({ch:+.0%})"))
                    flag(i, "beds changed >50% vs previous year")
            # Generation jumps >40% are worth a look (methodology or reporting changes)
            g0, g1 = prev.waste_generated_kg_day if prev is not None else None, r.waste_generated_kg_day
            if prev is not None and pd.notna(g0) and pd.notna(g1) and g0 > 1000 and abs(g1 / g0 - 1) > 0.4:
                checks.append((r.year, s, "generated_jump", f"{g0:,.0f} -> {g1:,.0f} kg/day ({g1 / g0 - 1:+.0%})"))
                flag(i, "waste generated changed >40% vs previous year")
            # 6. Carried-forward data: identical beds AND HCFs as previous year
            if prev is not None and r.beds == prev.beds and r.healthcare_facilities == prev.healthcare_facilities \
                    and pd.notna(r.beds) and r.beds > 0:
                checks.append((r.year, s, "carried_forward", f"beds {r.beds:.0f} & HCFs identical to {prev.year}"))
                flag(i, f"likely carried forward from {prev.year}")
            prev = r

    pd.DataFrame(checks, columns=["year", "state", "check", "detail"]) \
        .to_csv(DATA / "validation_report.csv", index=False)
    print(f"{len(checks)} validation findings -> validation_report.csv")
    return df


if __name__ == "__main__":
    main()
