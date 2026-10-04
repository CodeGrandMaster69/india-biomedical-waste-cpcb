# Bio-Medical Waste Management in India (2020–2024)

**Which Indian states generate more bio-medical waste than they can treat, and where would a new
Common Bio-Medical Waste Treatment Facility (CBWTF) make the biggest difference?**

The data exists only as tables inside the Central Pollution Control Board's (CPCB) annual PDF reports.
I extracted five years of state-wise data from those PDFs, reconciled it against the reports' own
totals, flagged problems in the source, and built an interactive dashboard and a facility-siting
recommendation on top of it.

**[▶ Open the interactive dashboard](https://codegrandmaster69.github.io/india-biomedical-waste-cpcb/dashboard/)**

[![Dashboard preview](charts/dashboard_preview.png)](https://codegrandmaster69.github.io/india-biomedical-waste-cpcb/dashboard/)

## Headline results

| Metric (national) | 2020 | 2024 |
|---|---|---|
| Waste generated | 656.7 t/day | **815.2 t/day** (+24%) |
| Share treated | 90.0% | **99.4%** |
| Untreated waste | 65.7 t/day | **4.8 t/day** (−93%) |
| CBWTFs in operation | 208 | **245** |
| Hospital beds per CBWTF | 11,932 | **12,645** |

1. **Reported treatment has improved sharply,** but the improvement was not steady. Untreated waste
   rose again in 2023 (48.8 t/day) before nearly vanishing in 2024.
2. **Three states account for 91% of all untreated waste over five years:** Karnataka (110 t/day-years),
   Bihar (50) and Assam (11.5).
3. **Assam is the only state that left more than 12% of its waste untreated every year.** Manipur (30%)
   and Puducherry (20%) were the largest untreated shares in 2024.
4. **Kerala is the biggest capacity outlier:** 2 CBWTFs for 1.42 lakh beds, which is **71,089 beds per facility**
   (5.6× the national ratio and more than double any other state).
5. **Bihar's 2024 jump needs checking.** It treated only 37–65% of its waste in 2020–23, then reported
   100% in 2024 with the same 4 facilities.
6. **Eight small or remote states/UTs have no CBWTF at all** (A&N, Arunachal, DNH & DD, Ladakh, Lakshadweep,
   Mizoram, Nagaland, Sikkim). They rely on captive plants and deep burial.

![National trend](charts/1_national_trend.png)

![Untreated share by state](charts/2_untreated_share_heatmap.png)

| | |
|---|---|
| ![Beds per CBWTF map](charts/3_beds_per_cbwtf_map.png) | ![Where to build](charts/4_siting_scatter.png) |

## Recommendation: where to build

I ranked states with a simple, transparent score (`data/state_priority.csv`):
**50%** capacity shortfall in 2024 (CBWTFs the state should have at the national beds-per-CBWTF ratio,
minus what it has), **30%** cumulative untreated waste 2020–24, and **20%** the number of years with a gap.

| Rank | State | Score | Beds per CBWTF | CBWTF shortfall | Untreated (t/day-yrs) | Years with gap |
|---|---|---|---|---|---|---|
| 1 | Kerala | 0.60 | 71,089 | 9.2 | 6.0 | 2 of 5 |
| 2 | Bihar | 0.55 | 27,430 | 4.7 | 50.4 | 4 of 5 |
| 3 | Karnataka | 0.46 | 9,436 | 0.0 | 109.9 | 4 of 5 |
| 4 | Tamil Nadu | 0.36 | 20,316 | 6.7 | 0.0 | 0 of 5 |
| 5 | Rajasthan | 0.32 | 19,444 | 5.9 | 0.0 | 0 of 5 |
| 6 | Assam | 0.25 | 14,666 | 0.3 | 11.5 | 5 of 5 |

- **Kerala: add capacity.** It reports full treatment, so the risk is overload and single-point failure, not an open gap.
- **Bihar: build and verify.** It is high on both capacity shortfall and past gaps, and its sudden 2024 improvement should be audited.
- **Karnataka: monitor.** It had the largest untreated volume, but it already has 27 CBWTFs (more than its bed count
  implies) and reported closing the gap in 2024. The issue looks operational rather than a lack of facilities.
- **Assam: close a persistent gap.** The volume is small (~7 t/day), so one extra facility could fix it.
- Tamil Nadu, Rajasthan and West Bengal sit 4–7 facilities below the trend line but report full treatment.
  They need headroom, not emergency action.

## Data

**Source:** CPCB, *Annual Report on Biomedical Waste Management*, 2020–2024, Annexure-I (state-wise
information submitted by State Pollution Control Boards and Committees):
`https://cpcb.nic.in/uploads/Projects/Bio-Medical-Waste/AR_BMWM_<year>.pdf`

| Year | Annexure-I pages |
|---|---|
| 2020 | 17–18 |
| 2021 | 21–22 |
| 2022 | 46–48 |
| 2023 | 39–41 |
| 2024 | 41–43 |

**Output table `data/bmw_clean.csv`:** one row per state/UT per year (37 × 5 = 185 rows).

| Column | Meaning |
|---|---|
| year, state, state_type | Report year, standardised state/UT name, State or UT |
| healthcare_facilities, beds | Total healthcare facilities (bedded + non-bedded) and total beds |
| waste_generated_kg_day, waste_treated_kg_day | Bio-medical waste generated, and treated and disposed, in kg/day |
| cbwtfs, captive_plants | CBWTFs in operation; facilities with their own treatment plant |
| bedded_hcf, nonbedded_hcf, cbwtf_under_construction, treated_by_captive_kg_day, treated_by_cbwtf_kg_day | Extra columns used for validation |
| is_mappable | FALSE for DGAFMS (Armed Forces), a national body. Kept in totals, left off the map |
| data_flag | Plain-English caveat when a row failed a check |

A blank means "information not provided" (INP/NA in the report). It is **not** zero.

## How I got clean data out of the PDFs

1. **Locate:** every report's Annexure-I has the same 23 columns and the same 37 rows in the same order.
2. **Extract by position, not by text:** `pdfplumber` returns each page as a fixed grid of cells. Plain
   text extraction shifts values left whenever a cell is blank or a name wraps onto two lines. Using the grid
   keeps every value in its column (2020's grid has 74 physical columns; a column map reduces them to the 23 real ones).
3. **Merge wrapped rows:** long names like "Daman & Diu and Dadra & Nagar Haveli" and "Nil" cells spill onto
   extra lines with no serial number. Each spill row is merged into the neighbouring record, and repeated page headers are dropped.
4. **Reconcile:** I summed every column and compared it with the report's printed *Total* row. HCFs, beds,
   generated, treated, CBWTFs and captive plants match exactly for all five years, apart from errors in CPCB's own totals (below).
5. **Validate:** rule checks produce `data/validation_report.csv` (28 findings). I changed a value only when the PDF
   itself gives the correct figure. Everything else is flagged, not "fixed". All 44 rules and fixes are in `data/cleaning_log.csv`.

### Cleaning decisions

| Issue | Decision |
|---|---|
| "Telengana" (all 5 years), "J & K", "Andaman Nicobar" | Standardised names |
| Daman & Diu + Dadra & Nagar Haveli (merged 26 Jan 2020; old names still used in reports) | One entity under the merged name. It uses Gujarat's CBWTFs, so `cbwtfs = 0` |
| J&K / Ladakh split (31 Oct 2019) | Already separate in all five years |
| 2020 and 2021 national COVID-19 waste line (118 and 80 t/day, no state split) | Excluded. State rows are non-COVID, so national totals are 656.7 / 683.9 t/day, not the 774 / 764 headline |
| CPCB's printed bed totals omit Bihar (2021) and Gujarat (2022, where one cell is stored as the text "2,23,997") | Totals recomputed from state rows |
| Ladakh 2020: total-HCF cell missing | 389 = 333 + 56, which matches the table on p.9 |
| Tamil Nadu 2022: 19,114 beds (145,848 the year before, 204,717 the year after) | Set blank, not guessed |
| Kerala 2022: treated 29,175 vs its own breakdown 2,372 + 59,750 = 62,122 | Used the breakdown sum (logged) |
| "Nil" | 0. "INP", "NA" and leftover placeholders become blank |

### What validation found in the source data

| Check | Findings |
|---|---|
| bedded + non-bedded = total HCFs | 9 rows don't add up (e.g. Karnataka 2020: 8,404 + 32,402 ≠ 41,709). Kept as reported |
| treated ≤ generated | Manipur 2021 reports treating more than it generated |
| treated ≈ captive-treated + CBWTF-treated | 6 rows disagree (e.g. Nagaland 2024) |
| Identical beds and HCFs to the previous year | Bihar 2023, Manipur 2022, Lakshadweep 2024, DGAFMS 2023: likely copied forward because the state didn't report |
| Waste generated changes more than 40% year on year | Meghalaya +121% (2022), Goa +89% (2022), Odisha +76% (2024), Kerala +51% (2021) and +42% (2024) |
| Waste per bed > 2 kg/day | Lakshadweep 2020: 8.1 kg/bed/day (1,137 kg/day for 140 beds, probably COVID waste) |

## Repository layout

```
raw_pdfs/                    CPCB annual reports, 2020–2024 (source)
scripts/extract.py           PDF → data/raw_extract.csv (all 23 Annexure-I columns, raw strings)
scripts/clean.py             raw → clean table, cleaning log, validation report
scripts/analyze.py           clean table → charts/ + national and priority tables
scripts/build_dashboard.py   clean table → dashboard/index.html (uses scripts/dashboard_template.html)
data/bmw_clean.csv           ★ analysis table (also as bmw_clean.xlsx with log and validation sheets)
data/raw_extract.csv         untouched extraction, kept for audit
data/cleaning_log.csv        every rule and every individual fix, with the reason
data/validation_report.csv   source-data issues found by the rule checks
data/national_summary.csv    national totals by year
data/state_priority.csv      priority score inputs and ranking
dashboard/index.html         interactive dashboard (single page, opens in any browser)
charts/                      static charts used in this README
geo/india_states.json        simplified state boundaries for the maps
powerbi/measures.dax         the same metrics as DAX measures, for a Power BI version of the dashboard
```

**Reproduce**

```bash
pip install -r requirements.txt
python scripts/extract.py && python scripts/clean.py
python scripts/analyze.py && python scripts/build_dashboard.py
```

Then open `dashboard/index.html` in a browser.

## Limitations

- **The data is self-reported.** SPCBs compile healthcare facilities' own annual returns, and CPCB does not audit them.
  Unauthorised facilities (about 91,000 in 2024) are invisible in these tables.
- **"Treated" often just equals "generated"** (100% in most states), which looks like a default rather than a measurement.
- **Non-reporting states get last year's numbers copied forward** (detected above).
- **The published tables contain arithmetic errors** (row sums and national totals), which suggests limited quality checks.
- **CBWTF capacity isn't reported,** so beds per CBWTF stands in for capacity. A facility's real throughput in kg/day would be a better measure.
- **Definitions shift:** COVID-19 waste was split out in 2020–21 only.

## Interview prep

**How did you get reliable data out of PDFs?**
I extracted by cell position instead of by text, so blank cells and wrapped names couldn't shift values into the
wrong column. Then I proved the extraction was right by reconciling every column against the report's own printed totals.

**Why flag bad values instead of fixing them?**
A guessed value looks exactly like a real one in a dashboard. I only corrected a value when the PDF itself gave
the right number (for example, a breakdown that sums correctly). Everything else carries a `data_flag`, and the dashboard shows it in tooltips.

**Why "beds per CBWTF"?**
The reports don't give facility capacity, but beds drive most bio-medical waste. So beds per facility is a
reasonable proxy for how much load each facility carries, and it lets me compare states of very different sizes on one yardstick.

**Why is untreated waste summed state by state?**
Manipur reported treating more than it generated in 2021. If I subtracted national totals, that over-report would hide
other states' real gaps. Flooring each state's gap at zero before summing prevents that.

**What would you do next?**
Get CBWTF capacity data (kg/day per facility) from SPCB websites, add district-level detail for the priority states,
and cross-check self-reported treatment against CBWTF throughput.
