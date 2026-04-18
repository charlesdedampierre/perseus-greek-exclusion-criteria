"""
Exclusion criteria over time — normalized for uneven author coverage.

Periods are grouped until each has >= 3 authors.
A criterion counts only if attested by >= 50% of authors in the group.

Outputs saved to graphs/
"""

import csv
import os
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(
    BASE_DIR, "data", "llm_results", "exclusion_criteria_verbatims_v7.csv"
)
OUT_DIR = os.path.join(BASE_DIR, "graphs")
os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Load & deduplicate by (author, criterion_category, year)
# ---------------------------------------------------------------------------
with open(CSV_PATH, "r", encoding="utf-8") as f:
    raw = list(csv.DictReader(f))

seen = set()
data = []
for d in raw:
    key = (d["author"], d["criterion_category"], int(d["impact_year"]))
    if key not in seen:
        seen.add(key)
        data.append({**d, "year": int(d["impact_year"])})

data.sort(key=lambda d: d["year"])

ALL_CATS = sorted(set(d["criterion_category"] for d in data))

CAT_COLORS = {
    "MORAL_CONDUCT": "#e11d48",
    "BIRTH_LINEAGE": "#7c3aed",
    "ACHIEVEMENTS": "#d97706",
    "CITIZENSHIP": "#2563eb",
    "PROPERTY_WEALTH": "#059669",
    "AGE": "#0d9488",
    "GENDER": "#db2777",
    "FREEDOM_STATUS": "#ea580c",
    "OCCUPATION": "#475569",
    "PHYSICAL_STATUS": "#78350f",
    "LEGAL_STANDING": "#0891b2",
}

# Stable order for stacking (most frequent first overall)
CAT_ORDER = [
    "GENDER",
    "FREEDOM_STATUS",
    "BIRTH_LINEAGE",
    "CITIZENSHIP",
    "PROPERTY_WEALTH",
    "MORAL_CONDUCT",
    "AGE",
]

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.size": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.grid": True,
        "grid.alpha": 0.15,
        "grid.linestyle": "--",
    }
)

# ---------------------------------------------------------------------------
# Period groupings (>= 3 authors each)
# ---------------------------------------------------------------------------
GROUPS = [
    ("Archaic\n740-500 BCE", -740, -499),
    ("Early Classical\n489-400 BCE", -489, -399),
    ("Late Classical\n384-348 BCE", -384, -347),
    ("Early Roman\n36-105 CE", 36, 106),
    ("Late Roman\n135-205 CE", 135, 206),
]

# Short labels for inline use
SHORT_LABELS = [
    "Archaic",
    "Early Classical",
    "Late Classical",
    "Early Roman",
    "Late Roman",
]

# ---------------------------------------------------------------------------
# Compute stats per group
# ---------------------------------------------------------------------------
group_stats = []

for (name, lo, hi), short in zip(GROUPS, SHORT_LABELS):
    items = [d for d in data if lo <= d["year"] <= hi]
    authors = sorted(set(d["author"] for d in items))
    T = len(authors)
    threshold = T / 2

    cat_auths = defaultdict(set)
    for d in items:
        cat_auths[d["criterion_category"]].add(d["author"])

    passing = {}
    failing = {}
    for cat, auths in cat_auths.items():
        if len(auths) >= threshold:
            passing[cat] = len(auths)
        else:
            failing[cat] = len(auths)

    group_stats.append(
        {
            "name": name,
            "short": short,
            "n_authors": T,
            "threshold": threshold,
            "total_observed": len(cat_auths),
            "n_passing": len(passing),
            "passing": passing,
            "failing": failing,
            "cat_auths": {k: len(v) for k, v in cat_auths.items()},
            "authors": authors,
        }
    )


# ---------------------------------------------------------------------------
# GRAPH 1: Criteria shared by >= 50% of authors (main result)
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(12, 6))

x = np.arange(len(group_stats))
n_passing = [g["n_passing"] for g in group_stats]
n_observed = [g["total_observed"] for g in group_stats]
n_authors = [g["n_authors"] for g in group_stats]

# Faded bars = total observed
ax.bar(
    x,
    n_observed,
    width=0.55,
    color="#e2e8f0",
    edgecolor="#cbd5e1",
    linewidth=1,
    label="All observed (any author)",
    zorder=2,
)

# Solid bars = passing threshold
bars = ax.bar(
    x,
    n_passing,
    width=0.55,
    color="#1e293b",
    edgecolor="white",
    linewidth=0.5,
    label="Shared by >= 50% of authors",
    zorder=3,
)

# Annotations
for i, (p, o, na) in enumerate(zip(n_passing, n_observed, n_authors)):
    ax.text(
        i, p + 0.15, str(p), ha="center", fontsize=14, fontweight="700", color="#1e293b"
    )
    if o > p:
        ax.text(i, o + 0.15, f"({o})", ha="center", fontsize=9, color="#94a3b8")
    ax.text(
        i,
        -0.55,
        f"{na} authors",
        ha="center",
        fontsize=8.5,
        color="#64748b",
        style="italic",
    )

ax.set_xticks(x)
ax.set_xticklabels([g["name"] for g in group_stats], fontsize=9.5)
ax.set_ylabel("Number of exclusion criteria categories", fontsize=11)
ax.set_title(
    "Exclusion Criteria Shared by a Majority of Authors\n"
    "Only criteria attested by >= 50% of authors in each period are counted",
    fontweight="bold",
    pad=15,
    fontsize=12,
)
ax.axhline(len(ALL_CATS), color="#94a3b8", linewidth=0.8, linestyle=":", alpha=0.4)
ax.text(
    len(group_stats) - 0.5,
    len(ALL_CATS) + 0.1,
    f"Max = {len(ALL_CATS)}",
    fontsize=8,
    color="#94a3b8",
    ha="right",
)
ax.legend(fontsize=9, loc="upper right")
ax.set_ylim(-1, len(ALL_CATS) + 1.5)

fig.tight_layout()
fig.savefig(os.path.join(OUT_DIR, "shared_criteria_over_time.png"), dpi=200)
plt.close(fig)
print("Saved: shared_criteria_over_time.png")


# ---------------------------------------------------------------------------
# GRAPH 2: Which categories pass/fail per period (dot chart)
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(13, 5))

cats_display = CAT_ORDER
y_cats = np.arange(len(cats_display))

for j, g in enumerate(group_stats):
    for i, cat in enumerate(cats_display):
        n = g["cat_auths"].get(cat, 0)
        T = g["n_authors"]
        threshold = g["threshold"]

        if n == 0:
            continue

        passing = n >= threshold
        size = (n / T) * 250 + 30
        color = CAT_COLORS.get(cat, "#475569") if passing else "#e2e8f0"
        edge = CAT_COLORS.get(cat, "#475569")

        ax.scatter(j, i, s=size, color=color, edgecolor=edge, linewidth=1.5, zorder=3)
        ax.text(
            j,
            i - 0.35,
            f"{n}/{T}",
            ha="center",
            fontsize=6.5,
            color="#475569" if passing else "#cbd5e1",
        )

ax.set_xticks(range(len(group_stats)))
ax.set_xticklabels([g["name"] for g in group_stats], fontsize=9)
ax.set_yticks(y_cats)
ax.set_yticklabels([c.replace("_", " ").title() for c in cats_display], fontsize=9.5)

# Legend
from matplotlib.lines import Line2D

legend_elements = [
    Line2D(
        [0],
        [0],
        marker="o",
        color="w",
        markerfacecolor="#1e293b",
        markersize=10,
        label="Shared (>= 50% of authors)",
    ),
    Line2D(
        [0],
        [0],
        marker="o",
        color="w",
        markerfacecolor="#e2e8f0",
        markeredgecolor="#94a3b8",
        markersize=10,
        label="Weak (< 50% of authors)",
    ),
]
ax.legend(handles=legend_elements, fontsize=8.5, loc="lower right")

ax.set_title(
    "Category Attestation Across Periods\n"
    "Filled = shared by majority of authors, hollow = single-author attestation. Size = share of authors.",
    fontweight="bold",
    pad=15,
    fontsize=11,
)
ax.set_xlim(-0.5, len(group_stats) - 0.5)
ax.invert_yaxis()

fig.tight_layout()
fig.savefig(os.path.join(OUT_DIR, "category_attestation_dot_chart.png"), dpi=200)
plt.close(fig)
print("Saved: category_attestation_dot_chart.png")


# ---------------------------------------------------------------------------
# GRAPH 3: Stacked bar — only passing categories, colored
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(12, 6))

bottoms = np.zeros(len(group_stats))
for cat in CAT_ORDER:
    vals = []
    for g in group_stats:
        if cat in g["passing"]:
            vals.append(1)
        else:
            vals.append(0)
    vals = np.array(vals, dtype=float)
    if vals.sum() == 0:
        continue
    color = CAT_COLORS.get(cat, "#94a3b8")
    ax.bar(
        x,
        vals,
        bottom=bottoms,
        width=0.55,
        color=color,
        label=cat.replace("_", " ").title(),
        edgecolor="white",
        linewidth=0.8,
    )
    # Label inside each segment
    for i, v in enumerate(vals):
        if v > 0:
            n = group_stats[i]["cat_auths"].get(cat, 0)
            T = group_stats[i]["n_authors"]
            ax.text(
                i,
                bottoms[i] + 0.5,
                f"{n}/{T}",
                ha="center",
                va="center",
                fontsize=7,
                color="white",
                fontweight="600",
            )
    bottoms += vals

# Total on top
for i, p in enumerate(n_passing):
    ax.text(
        i, p + 0.15, str(p), ha="center", fontsize=13, fontweight="700", color="#1e293b"
    )
    ax.text(
        i,
        -0.5,
        f"{n_authors[i]} authors",
        ha="center",
        fontsize=8.5,
        color="#64748b",
        style="italic",
    )

ax.set_xticks(x)
ax.set_xticklabels([g["name"] for g in group_stats], fontsize=9.5)
ax.set_ylabel("Criteria shared by >= 50% of authors")
ax.set_title(
    "Which Exclusion Criteria Are Broadly Shared in Each Period?\n"
    "Each block = 1 criterion category, labeled with n_attesting / n_total authors",
    fontweight="bold",
    pad=15,
    fontsize=12,
)
ax.legend(
    loc="upper right",
    fontsize=7.5,
    ncol=2,
    framealpha=0.9,
    borderpad=0.7,
    handlelength=1.0,
)
ax.set_ylim(-1, max(n_passing) + 1.5)

fig.tight_layout()
fig.savefig(os.path.join(OUT_DIR, "shared_criteria_stacked.png"), dpi=200)
plt.close(fig)
print("Saved: shared_criteria_stacked.png")


# ---------------------------------------------------------------------------
# Print summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("SUMMARY: Criteria shared by >= 50% of authors per period")
print("=" * 70)
for g in group_stats:
    label = g["name"].replace("\n", " ")
    passing_cats = sorted(g["passing"].keys())
    failing_cats = sorted(g["failing"].keys())
    print(f"\n{label} ({g['n_authors']} authors) — {g['n_passing']} shared criteria")
    for cat in passing_cats:
        n = g["cat_auths"][cat]
        print(f"  + {cat:20s}  {n}/{g['n_authors']} authors")
    for cat in failing_cats:
        n = g["cat_auths"][cat]
        print(f"  - {cat:20s}  {n}/{g['n_authors']} authors  (weak)")

print(f"\nAll graphs saved to {OUT_DIR}/")
