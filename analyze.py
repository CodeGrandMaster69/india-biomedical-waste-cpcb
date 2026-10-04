"""
Analyse the clean CPCB bio-medical waste table and produce the charts and summary tables.

Usage:  python scripts/analyze.py
Input:  data/bmw_clean.csv, geo/india_states.json
Output: charts/*.png, data/national_summary.csv, data/state_priority.csv
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import PatchCollection
from matplotlib.colors import LinearSegmentedColormap, LogNorm
from matplotlib.patches import Patch, Polygon

ROOT = Path(__file__).resolve().parent.parent
DATA, CHARTS = ROOT / "data", ROOT / "charts"
CHARTS.mkdir(exist_ok=True)

# ---- style ---------------------------------------------------------------------------
INK, INK2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
BLUE, ORANGE, NODATA = "#2a78d6", "#eb6834", "#d9d8d2"
BLUES = LinearSegmentedColormap.from_list("blues", ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])
REDS = LinearSegmentedColormap.from_list("reds", ["#fcfcfb", "#f6c9bd", "#e98a72", "#c9452f", "#7d1d12"])
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10, "text.color": INK, "axes.labelcolor": INK2,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.edgecolor": AXIS, "axes.facecolor": SURFACE,
    "figure.facecolor": SURFACE, "savefig.facecolor": SURFACE, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.axisbelow": True, "axes.titleweight": "bold", "axes.titlesize": 12, "axes.titlelocation": "left",
    "figure.dpi": 110, "savefig.dpi": 170,
})


def note(fig, text):
    fig.text(0.01, 0.01, text, fontsize=8, color=MUTED, ha="left", va="bottom")


# ---- load ----------------------------------------------------------------------------
df = pd.read_csv(DATA / "bmw_clean.csv")
df["untreated_kg_day"] = (df.waste_generated_kg_day - df.waste_treated_kg_day).clip(lower=0)
df["untreated_share"] = df.untreated_kg_day / df.waste_generated_kg_day
states = df[df.is_mappable].copy()          # drops DGAFMS (national Armed Forces body) from state views
YEARS = sorted(df.year.unique())
LATEST = YEARS[-1]

# ---- national summary ----------------------------------------------------------------
nat = df.groupby("year").agg(
    generated_kg_day=("waste_generated_kg_day", "sum"),
    treated_kg_day=("waste_treated_kg_day", "sum"),
    untreated_kg_day=("untreated_kg_day", "sum"),   # summed per state: over-reporters can't cancel real gaps
    healthcare_facilities=("healthcare_facilities", "sum"),
    beds=("beds", "sum"),
    cbwtfs=("cbwtfs", "sum"),
    captive_plants=("captive_plants", "sum"),
    flagged_rows=("data_flag", lambda s: int(s.notna().sum())),
)
nat["treated_pct"] = nat.treated_kg_day / nat.generated_kg_day
with_cbwtf = df[df.cbwtfs > 0].groupby("year")
nat["beds_per_cbwtf"] = with_cbwtf.beds.sum() / with_cbwtf.cbwtfs.sum()
nat.round(4).to_csv(DATA / "national_summary.csv")

# ---- state priority score (where would a new CBWTF help most?) --------------------------
# 50% capacity shortfall in the latest year: CBWTFs the state "should" have at the national
#     beds-per-CBWTF ratio, minus what it has
# 30% cumulative untreated waste 2020-24 (t/day-years)
# 20% persistence: years with an untreated gap > 1 kg/day
ratio = nat.at[LATEST, "beds_per_cbwtf"]
last = states[states.year == LATEST].set_index("state")
pr = pd.DataFrame({
    "beds": last.beds,
    "cbwtfs": last.cbwtfs,
    "generated_kg_day": last.waste_generated_kg_day,
    "treated_pct": last.waste_treated_kg_day / last.waste_generated_kg_day,
})
pr["beds_per_cbwtf"] = pr.beds / pr.cbwtfs.replace(0, np.nan)
pr["cbwtf_shortfall"] = (pr.beds / ratio - pr.cbwtfs).clip(lower=0)
pr["untreated_t_day_years"] = states.groupby("state").untreated_kg_day.sum() / 1000
pr["years_with_gap"] = states.assign(g=states.untreated_kg_day > 1).groupby("state").g.sum()
pr["priority_score"] = (0.5 * pr.cbwtf_shortfall / pr.cbwtf_shortfall.max()
                        + 0.3 * pr.untreated_t_day_years / pr.untreated_t_day_years.max()
                        + 0.2 * pr.years_with_gap / len(YEARS))
pr = pr.sort_values("priority_score", ascending=False)
pr.round(3).to_csv(DATA / "state_priority.csv")

# ---- chart 1: national trend ------------------------------------------------------------
fig, (a, b) = plt.subplots(1, 2, figsize=(12, 4.4), gridspec_kw={"width_ratios": [1.35, 1]})
gen, tr = nat.generated_kg_day / 1000, nat.treated_kg_day / 1000
a.plot(YEARS, gen, color=BLUE, lw=2, marker="o", ms=6, mec=SURFACE, mew=2, label="Generated")
a.plot(YEARS, tr, color=ORANGE, lw=2, marker="o", ms=6, mec=SURFACE, mew=2, label="Treated")
a.fill_between(YEARS, tr, gen, color=ORANGE, alpha=0.10, lw=0)
a.text(YEARS[-1] + 0.08, gen.iloc[-1] + 6, f"Generated {gen.iloc[-1]:.0f}", color=INK, va="bottom", fontsize=9)
a.text(YEARS[-1] + 0.08, tr.iloc[-1] - 6, f"Treated {tr.iloc[-1]:.0f}", color=INK, va="top", fontsize=9)
a.set(xticks=YEARS, xlim=(YEARS[0] - 0.2, YEARS[-1] + 0.9), ylim=(540, 850), ylabel="tonnes per day",
      title="Waste generated vs treated, India")
a.legend(frameon=False, loc="upper left")
un = nat.untreated_kg_day / 1000
bars = b.bar(YEARS, un, width=0.45, color=ORANGE)
for x, v in zip(YEARS, un):
    b.text(x, v + 1.2, f"{v:.1f}", ha="center", va="bottom", fontsize=9, color=INK)
b.set(xticks=YEARS, ylabel="tonnes per day", ylim=(0, 75), title=f"Untreated waste, down {1 - un.iloc[-1] / un.iloc[0]:.0%} since {YEARS[0]}")
b.grid(axis="x", visible=False)
note(fig, "Source: CPCB Annual Reports on Bio-Medical Waste Management, Annexure-I. "
          "2020-21 exclude COVID-19 waste, which was reported only as a national total.")
fig.tight_layout(rect=(0, 0.04, 1, 1))
fig.savefig(CHARTS / "1_national_trend.png"); plt.close(fig)

# ---- chart 2: untreated share heatmap ---------------------------------------------------
share = states.pivot_table(index="state", columns="year", values="untreated_share")
gapyrs = states.assign(g=states.untreated_kg_day > 1).pivot_table(index="state", columns="year", values="g")
keep = share[(share > 0.005).any(axis=1)]
keep = keep.loc[keep.mean(axis=1).sort_values(ascending=False).index]
fig, ax = plt.subplots(figsize=(8.2, 0.42 * len(keep) + 1.6))
im = ax.imshow(keep.values, cmap=REDS, vmin=0, vmax=1, aspect="auto")
for i in range(keep.shape[0]):
    for j in range(keep.shape[1]):
        v = keep.values[i, j]
        if np.isnan(v):
            continue
        ax.text(j, i, "0%" if v < 0.0005 else f"{v:.0%}" if v >= 0.01 else "<1%", ha="center", va="center",
                fontsize=8.5, color="white" if v > 0.5 else INK)
ax.set_xticks(range(len(YEARS)), YEARS); ax.set_yticks(range(len(keep)), keep.index)
ax.set_xticks(np.arange(-0.5, len(YEARS)), minor=True); ax.set_yticks(np.arange(-0.5, len(keep)), minor=True)
ax.grid(False); ax.grid(which="minor", color=SURFACE, lw=2); ax.tick_params(which="minor", length=0)
ax.tick_params(axis="y", colors=INK2, length=0); ax.tick_params(axis="x", length=0)
for s in ax.spines.values():
    s.set_visible(False)
ax.set_title("Share of bio-medical waste left untreated", pad=12)
cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02, format=lambda x, _: f"{x:.0%}")
cb.outline.set_visible(False); cb.ax.tick_params(colors=MUTED, length=0)
note(fig, "States with an untreated share above 0.5% in at least one year, sorted by 5-year average.\n"
          "Nagaland generates only ~1 t/day; Bihar, Karnataka and Assam account for most untreated tonnes.")
fig.tight_layout(rect=(0, 0.05, 1, 1))
fig.savefig(CHARTS / "2_untreated_share_heatmap.png"); plt.close(fig)

# ---- chart 3: map of beds per CBWTF ----------------------------------------------------
geo = json.load(open(ROOT / "geo" / "india_states.json"))
bpc = (last.beds / last.cbwtfs.replace(0, np.nan)).rename(lambda s: s.replace(" & ", " and "))
norm = LogNorm(vmin=3000, vmax=75000)
fig, ax = plt.subplots(figsize=(7.4, 8))
for f in geo["features"]:
    g = f["geometry"]
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    v = bpc.get(f["id"], np.nan)
    colour = NODATA if np.isnan(v) else BLUES(norm(v))
    patches = [Polygon(np.array(p[0]), closed=True) for p in polys]
    ax.add_collection(PatchCollection(patches, facecolor=colour, edgecolor=SURFACE, linewidth=0.6,
                                      hatch="////" if np.isnan(v) else None))
ax.autoscale_view(); ax.set_aspect(1 / np.cos(np.radians(22))); ax.axis("off")
for name, (x, y, dx, dy) in {"Kerala": (76.4, 10.0, -8.6, -2.2), "Delhi": (77.1, 28.6, -9.6, 1.6),
                             "Bihar": (85.6, 25.7, 2.6, 3.4)}.items():
    v = bpc[name]
    ax.annotate(f"{name}\n{v:,.0f} beds per CBWTF", (x, y), (x + dx, y + dy), fontsize=8.5, color=INK,
                arrowprops=dict(arrowstyle="-", color=INK2, lw=0.7), ha="left")
sm = plt.cm.ScalarMappable(norm=norm, cmap=BLUES)
cb = fig.colorbar(sm, ax=ax, orientation="horizontal", fraction=0.035, pad=0.02, shrink=0.7,
                  ticks=[3000, 10000, 30000, 70000], format=lambda x, _: f"{x:,.0f}")
cb.ax.xaxis.set_minor_locator(plt.NullLocator())
cb.outline.set_visible(False); cb.ax.tick_params(colors=MUTED, length=0)
cb.set_label("Hospital beds per CBWTF, 2024 (log scale; darker = more load per facility)", color=INK2, fontsize=9)
ax.legend(handles=[Patch(facecolor=NODATA, hatch="////", edgecolor=SURFACE, label="No CBWTF in the state")],
          frameon=False, loc="lower left", fontsize=8.5)
ax.set_title(f"Treatment-facility load by state, {LATEST}")
note(fig, f"National ratio: 1 CBWTF per {ratio:,.0f} beds. Map: state boundaries as depicted by the Government of India.")
fig.tight_layout(rect=(0, 0.02, 1, 1))
fig.savefig(CHARTS / "3_beds_per_cbwtf_map.png"); plt.close(fig)

# ---- chart 4: where to build (beds vs CBWTFs) -------------------------------------------
sc = last[last.cbwtfs > 0]
fig, ax = plt.subplots(figsize=(9.5, 6))
size = 25 + sc.waste_generated_kg_day / 250
ax.scatter(sc.beds, sc.cbwtfs, s=size, color=BLUE, alpha=0.85, edgecolor=SURFACE, linewidth=2, zorder=3)
xs = np.logspace(np.log10(3500), np.log10(7e5), 50)
ax.plot(xs, xs / ratio, color=INK2, lw=1.2, zorder=2)
ax.text(6.5e5, 6.5e5 / ratio * 1.15, f"National ratio:\n1 CBWTF per {ratio:,.0f} beds", color=INK2,
        fontsize=8.5, ha="right", va="bottom")
label = {"Kerala": (12, -12, "left"), "Delhi": (10, -12, "left"), "Bihar": (10, -12, "left"),
         "Tamil Nadu": (12, -12, "left"), "Rajasthan": (-4, 12, "center"), "West Bengal": (10, -14, "left"),
         "Assam": (8, -12, "left"), "Uttar Pradesh": (-14, 10, "right"), "Maharashtra": (12, -3, "left"),
         "Karnataka": (-14, 2, "right"), "Gujarat": (12, -14, "left")}
for s_, (dx, dy, ha) in label.items():
    if s_ in sc.index:
        ax.annotate(s_, (sc.at[s_, "beds"], sc.at[s_, "cbwtfs"]), xytext=(dx, dy), textcoords="offset points",
                    fontsize=8.5, color=INK, ha=ha)
ax.set(xscale="log", yscale="log", xlabel="Hospital beds (log scale)", ylabel="CBWTFs in operation (log scale)",
       title=f"Where to build: states below the line have fewer facilities than their beds imply ({LATEST})")
ax.set_xticks([3000, 10000, 30000, 100000, 300000], ["3k", "10k", "30k", "100k", "300k"])
ax.set_yticks([1, 2, 5, 10, 20, 50], ["1", "2", "5", "10", "20", "50"])
ax.set(xlim=(3500, 8e5), ylim=(0.75, 90)); ax.minorticks_off()
note(fig, "Bubble size = waste generated (kg/day). States with no CBWTF are not shown on a log axis "
          "(8 small or remote states/UTs).")
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig(CHARTS / "4_siting_scatter.png"); plt.close(fig)

# ---- print the headline numbers the README quotes ---------------------------------------
print(nat[["generated_kg_day", "treated_kg_day", "untreated_kg_day", "cbwtfs", "beds_per_cbwtf",
           "treated_pct", "flagged_rows"]].round(3).to_string())
print(f"\nNational beds per CBWTF {LATEST}: {ratio:,.0f}")
print("\nPriority ranking:")
print(pr.head(10).round(3).to_string())
