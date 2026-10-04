"""
Build the interactive dashboard (dashboard/index.html) from the clean data.

Usage:  python scripts/analyze.py && python scripts/build_dashboard.py
Output: dashboard/index.html  (a single self-contained page; Plotly.js loads from cdnjs)
Host it free with GitHub Pages: Settings > Pages > Branch: main, folder: /(root),
then open https://<username>.github.io/<repo>/dashboard/
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dashboard"
OUT.mkdir(exist_ok=True)
PLOTLY = "https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.35.2/plotly.min.js"

df = pd.read_csv(ROOT / "data" / "bmw_clean.csv")
nat = pd.read_csv(ROOT / "data" / "national_summary.csv")
pri = pd.read_csv(ROOT / "data" / "state_priority.csv")
geo = json.loads((ROOT / "geo" / "india_states.json").read_text())

df["untreated_kg_day"] = (df.waste_generated_kg_day - df.waste_treated_kg_day).clip(lower=0)
df["geo_id"] = df.state.str.replace(" & ", " and ", regex=False)


def clean(v):
    if isinstance(v, (float, np.floating)):
        return None if np.isnan(v) else round(float(v), 4)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    return v


rows = [{k: clean(v) for k, v in r.items()} for r in df[[
    "year", "state", "geo_id", "is_mappable", "healthcare_facilities", "beds", "waste_generated_kg_day",
    "waste_treated_kg_day", "untreated_kg_day", "cbwtfs", "captive_plants", "data_flag"]].to_dict("records")]
national = [{k: clean(v) for k, v in r.items()} for r in nat.to_dict("records")]
priority = [{k: clean(v) for k, v in r.items()} for r in pri.head(10).to_dict("records")]
payload = json.dumps({"rows": rows, "national": national, "priority": priority, "geo": geo},
                     separators=(",", ":"), ensure_ascii=False)

html = (ROOT / "scripts" / "dashboard_template.html").read_text()
html = html.replace("__PLOTLY_SRC__", PLOTLY).replace("__DATA__", payload)
(OUT / "index.html").write_text(html)
print(f"wrote dashboard/index.html ({len(html) / 1024:.0f} KB)")
