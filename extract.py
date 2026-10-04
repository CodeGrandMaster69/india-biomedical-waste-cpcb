"""
Extract Annexure-I (state-wise BMW table) from CPCB Annual Reports 2020-2024.

Usage:  python scripts/extract.py
Input:  raw_pdfs/AR_BMWM_<year>.pdf
Output: data/raw_extract.csv  (all 23 annexure columns, one row per state per year, raw strings)

Approach: pdfplumber's table finder returns a fixed grid per page. Cells that wrap
onto an extra line produce "continuation rows" with no serial number; these are
merged into the neighbouring record whose cells at those column positions are empty.
"""
import csv
import re
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent

# Annexure-I page numbers (1-based) in each report
PAGES = {
    2020: [17, 18],
    2021: [21, 22],
    2022: [46, 47, 48],
    2023: [39, 40, 41],
    2024: [41, 42, 43],
}

# Canonical column order of Annexure-I (identical in all five reports)
COLS = [
    "sno", "state_raw", "bedded_hcf", "nonbedded_hcf", "total_hcf", "beds",
    "hcf_applied_auth", "hcf_granted_auth", "hcf_without_auth", "hcf_using_cbwtf",
    "generated_kg_day", "treated_kg_day", "hcf_with_captive", "captive_incinerators",
    "cbwtf_operational", "cbwtf_under_construction", "deep_burial_hcf", "deep_burial_cbwtf",
    "treated_by_captive_kg_day", "treated_by_cbwtf_kg_day", "violations", "show_cause_notices",
    "cbwtf_with_ocems",
]

# 2020's grid has 74 physical columns; these are the ones that hold data
COLMAP_2020 = [0, 1, 4, 7, 11, 14, 17, 20, 23, 27, 30, 33, 37, 41, 45, 48, 51, 54, 57, 61, 64, 67, 71]


def clean(cell):
    return re.sub(r"\s+", " ", (cell or "").replace("\n", " ")).strip()


def page_rows(pdf, pages, year):
    for pn in pages:
        for table in pdf.pages[pn - 1].extract_tables():
            for row in table:
                cells = [clean(c) for c in row]
                if year == 2020:
                    cells = [cells[i] if i < len(cells) else "" for i in COLMAP_2020]
                yield (cells + [""] * 23)[:23]


def is_record_start(cells):
    return bool(re.fullmatch(r"\d{1,2}", cells[0])) and 1 <= int(cells[0]) <= 37


def is_total(cells):
    return any(c.lower() == "total" for c in cells[:2])


def is_value(cell):
    """A real data cell: a number, or one of the report's no-data tokens."""
    return bool(re.search(r"\d", cell)) and not re.fullmatch(r"[IVX]+\.?", cell) \
        or cell.lower() in {"nil", "inp", "na"}


def is_header_text(cell):
    return bool(re.search(r"Name of|State/UT|Total|^[IVX]+\.?$", cell))


def fits(record, cont):
    """Continuation row fits a record if every data cell it carries is empty in the record."""
    return all(not record[i] for i in range(2, 23) if cont[i])


def merge(record, cont):
    for i in range(1, 23):
        if cont[i]:
            record[i] = (record[i] + " " + cont[i]).strip() if i == 1 else cont[i]


def extract_year(year):
    with pdfplumber.open(ROOT / "raw_pdfs" / f"AR_BMWM_{year}.pdf") as pdf:
        rows = list(page_rows(pdf, PAGES[year], year))

    records, pending = [], []  # pending = continuation rows seen before their record
    in_body = False
    for cells in rows:
        if is_total(cells):
            break
        if is_record_start(cells):
            in_body = True
            rec = list(cells)
            for cont in pending:
                merge(rec, cont)
            pending = []
            records.append(rec)
            continue
        if not any(is_value(c) for c in cells[2:]):
            # Repeated page headers / roman-numeral rows carry no values; name fragments still count
            if in_body and cells[1] and not is_header_text(cells[1]) and not any(cells[2:]):
                merge(records[-1], cells)
            continue
        # A continuation row: attach to previous record if it fits, else hold for the next one
        has_data = any(cells[2:])
        if records and (not has_data or fits(records[-1], cells)):
            merge(records[-1], cells)
        else:
            pending.append(cells)
    return records


def main():
    out = ROOT / "data" / "raw_extract.csv"
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["year"] + COLS)
        for year in PAGES:
            recs = extract_year(year)
            print(f"{year}: {len(recs)} rows")
            for r in recs:
                w.writerow([year] + r)
    print("wrote", out)


if __name__ == "__main__":
    main()
