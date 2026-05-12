"""
Plot whether rights expand across the four periods.

Expansion = more groups × more rights per group. We decompose the signal:
  (a) total granted (group, right) mass per period
  (b) the two factors driving it: # groups, mean rights/group (bootstrap 95% CI)
  (c) rank-rights curves per period — shows whether gains are at the top
      (already-privileged groups) or at the bottom (true expansion)

Outputs a PNG next to the notebook so it can be opened directly.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# --- Config ---------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "rules_dataset_april_2026.tsv"
OUT_PATH = ROOT / "notebooks" / "figure_rights_expansion.png"

GRANT_THRESHOLD = 1
MIN_RULES_PER_GROUP = 5
SEED = 42
N_BOOT = 1000

PERIOD_ORDER = [
    "Classical (500–360 BCE)",
    "Late Classical (354–165 BCE)",
    "Hellenistic & Early Roman (165 BCE – 105 CE)",
    "High Roman Empire (135–205 CE)",
]
PERIOD_SHORT = {
    "Classical (500–360 BCE)":                       "Classical",
    "Late Classical (354–165 BCE)":                  "Late Classical",
    "Hellenistic & Early Roman (165 BCE – 105 CE)":  "Hellenistic / E. Roman",
    "High Roman Empire (135–205 CE)":                "High Roman",
}

plt.rcParams.update({
    "figure.dpi": 130,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.titlesize": 11,
    "axes.labelsize": 10,
    "font.family": "DejaVu Sans",
})

PERIOD_COLORS = plt.cm.viridis(np.linspace(0.15, 0.85, len(PERIOD_ORDER)))


# --- Load + atomize -------------------------------------------------------

def split_atoms(s):
    if pd.isna(s):
        return []
    return [x.strip() for x in str(s).split(";") if x.strip()]


df_raw = pd.read_csv(DATA_PATH, sep="\t")
df = df_raw.drop(columns=["group", "resource", "resource_type"], errors="ignore").copy()
df["group"]    = df_raw["group_meta"].apply(split_atoms)
df["resource"] = df_raw["resource_type"].apply(split_atoms)
df = df.explode("group").explode("resource")
df = df.dropna(subset=["group", "resource", "directionality", "period"])
df = df[df["period"].isin(PERIOD_ORDER)]


# --- Net rights -> rights sets per period ---------------------------------

counts = (
    df.groupby(["period", "group", "resource", "directionality"])
      .size()
      .unstack("directionality", fill_value=0)
      .reindex(columns=["MORE", "LESS"], fill_value=0)
      .rename(columns={"MORE": "n_more", "LESS": "n_less"})
      .reset_index()
)
counts["net"] = counts["n_more"] - counts["n_less"]

rules_per_pg = df.groupby(["period", "group"]).size().rename("n").reset_index()
keep = set(map(tuple, rules_per_pg[rules_per_pg["n"] >= MIN_RULES_PER_GROUP][["period", "group"]].values))
counts = counts[counts.set_index(["period", "group"]).index.isin(keep)].reset_index(drop=True)

granted = counts[counts["net"] >= GRANT_THRESHOLD]

rights_sets = {
    p: {g: set(granted[(granted["period"] == p) & (granted["group"] == g)]["resource"])
        for g in granted[granted["period"] == p]["group"].unique()}
    for p in PERIOD_ORDER
}


# --- Three expansion metrics ---------------------------------------------

n_groups = np.array([len(rights_sets[p]) for p in PERIOD_ORDER])
total_mass = np.array([sum(len(s) for s in rights_sets[p].values()) for p in PERIOD_ORDER])

rng = np.random.default_rng(SEED)
mean_rights, ci_lo, ci_hi = [], [], []
for p in PERIOD_ORDER:
    sizes = np.array([len(s) for s in rights_sets[p].values()])
    if len(sizes) == 0:
        mean_rights.append(0.0); ci_lo.append(0.0); ci_hi.append(0.0); continue
    boots = rng.choice(sizes, size=(N_BOOT, len(sizes)), replace=True).mean(axis=1)
    mean_rights.append(sizes.mean())
    ci_lo.append(np.quantile(boots, 0.025))
    ci_hi.append(np.quantile(boots, 0.975))
mean_rights = np.array(mean_rights)
ci_lo = np.array(ci_lo); ci_hi = np.array(ci_hi)


# --- Figure ---------------------------------------------------------------

fig = plt.figure(figsize=(13, 9))
gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.1], hspace=0.45, wspace=0.3)

ax_mass    = fig.add_subplot(gs[0, 0])
ax_factors = fig.add_subplot(gs[0, 1])
ax_rank    = fig.add_subplot(gs[1, :])

x = np.arange(len(PERIOD_ORDER))
labels_short = [PERIOD_SHORT[p] for p in PERIOD_ORDER]

# (a) Total mass = # groups × mean rights/group
bars = ax_mass.bar(x, total_mass, color=PERIOD_COLORS, edgecolor="white", linewidth=1.2)
for xi, val in zip(x, total_mass):
    ax_mass.text(xi, val + max(total_mass) * 0.02, f"{val}", ha="center", fontsize=9)
ax_mass.set_xticks(x); ax_mass.set_xticklabels(labels_short, rotation=15, ha="right")
ax_mass.set_ylabel("total granted (group × right) pairs")
ax_mass.set_title("(a) Volume of granted rights per period")
ax_mass.set_ylim(0, max(total_mass) * 1.15)

# (b) Two factors — # groups and mean rights/group, dual y-axes
ax_factors.plot(x, n_groups, marker="o", color="#2c3e50", linewidth=2,
                label="# groups (left)")
ax_factors.set_ylabel("# groups with ≥ 1 right", color="#2c3e50")
ax_factors.tick_params(axis="y", labelcolor="#2c3e50")
ax_factors.set_xticks(x); ax_factors.set_xticklabels(labels_short, rotation=15, ha="right")
ax_factors.set_ylim(0, max(n_groups) * 1.25)

ax_factors_r = ax_factors.twinx()
ax_factors_r.plot(x, mean_rights, marker="s", color="#1f77b4", linewidth=2,
                  label="mean rights / group (right)")
ax_factors_r.fill_between(x, ci_lo, ci_hi, color="#1f77b4", alpha=0.15)
ax_factors_r.set_ylabel("mean # rights per group  (95% CI)", color="#1f77b4")
ax_factors_r.tick_params(axis="y", labelcolor="#1f77b4")
ax_factors_r.spines["top"].set_visible(False)
ax_factors_r.set_ylim(0, max(ci_hi) * 1.25 if max(ci_hi) > 0 else 1)

# Combined legend
h1, l1 = ax_factors.get_legend_handles_labels()
h2, l2 = ax_factors_r.get_legend_handles_labels()
ax_factors.legend(h1 + h2, l1 + l2, frameon=False, fontsize=8, loc="upper right")
ax_factors.set_title("(b) Decomposition: who is gaining, and how much?")

# (c) Rank-rights curves — one per period
for k, p in enumerate(PERIOD_ORDER):
    sizes = sorted([len(s) for s in rights_sets[p].values()])
    if not sizes:
        continue
    ranks = np.arange(1, len(sizes) + 1)
    ax_rank.plot(ranks, sizes, marker="o", color=PERIOD_COLORS[k],
                 linewidth=2, label=PERIOD_SHORT[p])

ax_rank.set_xlabel("group rank (sorted from least- to most-privileged)")
ax_rank.set_ylabel("# rights granted to the group")
ax_rank.set_title("(c) Rank-rights curve — does the floor rise, or only the ceiling?")
ax_rank.legend(frameon=False, fontsize=9, loc="upper left")
ax_rank.grid(True, alpha=0.25, linewidth=0.5)

fig.suptitle("Expansion of rights across the four periods", fontsize=13, y=0.995)
fig.savefig(OUT_PATH, bbox_inches="tight")
print(f"saved -> {OUT_PATH}")

# Also dump the underlying numbers so they're easy to inspect
table = pd.DataFrame({
    "period": labels_short,
    "n_groups": n_groups,
    "mean_rights_per_group": mean_rights.round(2),
    "ci95_low": np.array(ci_lo).round(2),
    "ci95_high": np.array(ci_hi).round(2),
    "total_granted_mass": total_mass,
})
print()
print(table.to_string(index=False))
