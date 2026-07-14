"""Operationalise the criterion-prior-to-rights framework on the rules dataset.

After re-encoding every (group, rule_polity) pair along rights-independent
criteria (see scripts/classifiers/classify_group_criteria.py), this script
joins those vectors back to the rules table and produces four analytical
artefacts:

  1. criterion_cell_rights_profile.tsv
       For every criterion-cell (the partition cell induced by sex × age ×
       ownership × ancestry × residence × wealth), list the resources
       observed on that cell and the count of MORE / LESS rules. This is
       the *empirical* rights profile ρ(G) per the framework — observed,
       not stipulated.

  2. emic_vs_criterion_partition.tsv
       For every emic label (group_meta — Athenian/Greek/Latin term used
       in the corpus), show how its instances spread over criterion-cells.
       Single-cell emic labels are clean; multi-cell labels diagnose where
       the native vocabulary aggregates etically-distinct groups.

  3. athens_snapshot.tsv
       Classical Athens specifically: criterion-cells with their rights
       profiles, ordered by cell complexity. This is the worked example
       from the framework, rebuilt non-tautologically.

  4. contingent_rights.tsv
       Kripkean counterfactual test. For each (criterion-cell,
       resource_meta), list directionality across every polity in which
       the cell is observed. If the directionality differs across
       polities, the (cell, right) pair is **contingent** (the empirical
       content the framework promises). If it is stable, the cell-right
       link is invariant in our corpus.

Inputs
------
  - data/rules_dataset_april_2026.tsv
  - data/clean/final/group_criterion_vectors.tsv

Outputs
-------
  - data/clean/final/criterion_cell_rights_profile.tsv
  - data/clean/final/emic_vs_criterion_partition.tsv
  - data/clean/final/athens_snapshot.tsv
  - data/clean/final/contingent_rights.tsv
  - data/clean/final/rules_with_criteria.tsv   (rules joined with criterion vectors)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

RULES_SRC = ROOT / "data/rules_dataset_april_2026.tsv"
CRITERIA_SRC = ROOT / "data/clean/final/group_criterion_vectors.tsv"

OUT_DIR = ROOT / "data/clean/final"
OUT_JOINED = OUT_DIR / "rules_with_criteria.tsv"
OUT_CELL_PROFILE = OUT_DIR / "criterion_cell_rights_profile.tsv"
OUT_EMIC_VS_CRIT = OUT_DIR / "emic_vs_criterion_partition.tsv"
OUT_ATHENS = OUT_DIR / "athens_snapshot.tsv"
OUT_CONTINGENT = OUT_DIR / "contingent_rights.tsv"

CRITERION_AXES = [
    "c_sex",
    "c_age",
    "c_ownership_status",
    "c_ancestry",
    "c_residence",
    "c_wealth",
]


def _short(val: str) -> str:
    """Compact one-char code for cell signatures."""
    if pd.isna(val):
        return "?"
    val = str(val)
    if val in ("any", "unspecified"):
        return "*"
    return val[0].upper()


def cell_signature(row: pd.Series) -> str:
    return "-".join(_short(row[c]) for c in CRITERION_AXES)


def cell_long(row: pd.Series) -> str:
    return " | ".join(f"{c.removeprefix('c_')}={row[c]}" for c in CRITERION_AXES)


def load() -> pd.DataFrame:
    rules = pd.read_csv(RULES_SRC, sep="\t")
    crit = pd.read_csv(CRITERIA_SRC, sep="\t")
    joined = rules.merge(crit, on=["group", "rule_polity"], how="left")
    joined["cell_sig"] = joined.apply(cell_signature, axis=1)
    joined["cell_long"] = joined.apply(cell_long, axis=1)
    return joined


def build_cell_profile(df: pd.DataFrame) -> pd.DataFrame:
    """For each criterion-cell, count MORE/LESS rules per resource_meta.

    Filters out rules whose group requires_rights_definition=True (those are
    intrinsically office-defined and can't be cleanly compared as cells),
    and rules flagged as tautological (where the rule restates the group's
    definition).
    """
    mask = (df["requires_rights_definition"] != True) & (df["tautology"] != 1)  # noqa: E712
    f = df[mask].copy()
    grp = (
        f.groupby(["cell_sig", "cell_long", "resource_meta", "directionality"])
        .size()
        .reset_index(name="n_rules")
    )
    pivot = (
        grp.pivot_table(
            index=["cell_sig", "cell_long", "resource_meta"],
            columns="directionality",
            values="n_rules",
            fill_value=0,
        )
        .reset_index()
    )
    pivot.columns.name = None
    for col in ("MORE", "LESS"):
        if col not in pivot.columns:
            pivot[col] = 0
    pivot["n_total"] = pivot["MORE"] + pivot["LESS"]
    pivot["net_direction"] = pivot.apply(
        lambda r: "MORE" if r["MORE"] > r["LESS"]
        else ("LESS" if r["LESS"] > r["MORE"] else "MIXED"),
        axis=1,
    )
    pivot = pivot.sort_values(["cell_sig", "n_total"], ascending=[True, False])
    return pivot[
        ["cell_sig", "cell_long", "resource_meta", "MORE", "LESS",
         "n_total", "net_direction"]
    ]


def build_emic_vs_criterion(df: pd.DataFrame) -> pd.DataFrame:
    """For each emic group_meta, show its spread across criterion-cells.

    A clean emic→cell mapping (one cell per emic label) means the native
    vocabulary aligns with the etic partition. Spread indicates aggregation
    in the emic vocabulary that the criteria split apart.
    """
    f = df.dropna(subset=["group_meta"]).copy()
    by = (
        f.groupby(["group_meta", "cell_sig", "cell_long"])
        .size()
        .reset_index(name="n_rules")
    )
    totals = by.groupby("group_meta")["n_rules"].sum().rename("emic_total")
    distinct = (
        by.groupby("group_meta")["cell_sig"].nunique().rename("n_distinct_cells")
    )
    by = by.merge(totals, left_on="group_meta", right_index=True)
    by = by.merge(distinct, left_on="group_meta", right_index=True)
    by["share_of_emic"] = (by["n_rules"] / by["emic_total"]).round(3)
    by = by.sort_values(["n_distinct_cells", "group_meta", "n_rules"],
                        ascending=[False, True, False])
    return by[
        ["group_meta", "n_distinct_cells", "emic_total",
         "cell_sig", "cell_long", "n_rules", "share_of_emic"]
    ]


def build_athens_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    """Classical Athens (broad — including sub-regimes like Solonic, Thirty Tyrants).

    Rebuilds the Athenian rights map from criterion-cells: each cell is
    defined in rights-independent terms; the rights are observed empirically.
    """
    athens_polities = [
        p for p in df["rule_polity"].dropna().unique()
        if "Athens" in p or p == "Athens"
    ]
    f = df[df["rule_polity"].isin(athens_polities)].copy()
    mask = (f["requires_rights_definition"] != True) & (f["tautology"] != 1)  # noqa: E712
    f = f[mask]

    by = (
        f.groupby(["cell_sig", "cell_long", "resource_meta", "directionality"])
        .size()
        .reset_index(name="n")
    )
    pivot = (
        by.pivot_table(
            index=["cell_sig", "cell_long", "resource_meta"],
            columns="directionality",
            values="n",
            fill_value=0,
        )
        .reset_index()
    )
    pivot.columns.name = None
    for col in ("MORE", "LESS"):
        if col not in pivot.columns:
            pivot[col] = 0
    pivot["n_total"] = pivot["MORE"] + pivot["LESS"]

    emic_per_cell = (
        f.dropna(subset=["emic_label"])
        .groupby("cell_sig")["emic_label"]
        .apply(lambda s: "; ".join(sorted(set(s))))
        .rename("emic_labels_observed")
    )
    pivot = pivot.merge(emic_per_cell, on="cell_sig", how="left")

    pivot["pretty_direction"] = pivot.apply(
        lambda r: ("+" * int(r["MORE"]) + "-" * int(r["LESS"])),
        axis=1,
    )
    pivot = pivot.sort_values(
        ["cell_sig", "n_total"], ascending=[True, False]
    )
    return pivot[
        ["cell_sig", "cell_long", "emic_labels_observed",
         "resource_meta", "MORE", "LESS", "n_total", "pretty_direction"]
    ]


def build_contingent_rights(df: pd.DataFrame) -> pd.DataFrame:
    """Kripkean test: same criterion-cell across polities → same rights or not?

    For every (cell_sig, resource_meta) observed in ≥2 polities, report the
    polities, the directionality each time, and whether the cell-right link
    is stable (always MORE or always LESS) or contingent (differs).
    """
    mask = (df["requires_rights_definition"] != True) & (df["tautology"] != 1)  # noqa: E712
    f = df[mask].copy()
    by = (
        f.groupby(["cell_sig", "cell_long", "resource_meta", "rule_polity"])
        ["directionality"]
        .agg(lambda s: ",".join(sorted(set(s))))
        .reset_index()
        .rename(columns={"directionality": "directionality_in_polity"})
    )
    agg = (
        by.groupby(["cell_sig", "cell_long", "resource_meta"])
        .agg(
            n_polities=("rule_polity", "nunique"),
            polities=("rule_polity",
                      lambda s: "; ".join(sorted(set(s)))),
            directionalities=("directionality_in_polity",
                              lambda s: "; ".join(s)),
        )
        .reset_index()
    )
    multi = agg[agg["n_polities"] >= 2].copy()
    dir_set = multi["directionalities"].apply(
        lambda x: set(d.strip() for piece in x.split(";") for d in piece.split(","))
    )
    multi["status"] = dir_set.apply(
        lambda s: ("stable_MORE" if s == {"MORE"}
                   else "stable_LESS" if s == {"LESS"}
                   else "contingent")
    )
    return multi.sort_values(
        ["status", "n_polities", "cell_sig"], ascending=[True, False, True]
    )[
        ["status", "cell_sig", "cell_long", "resource_meta",
         "n_polities", "polities", "directionalities"]
    ]


def main() -> None:
    df = load()
    df.to_csv(OUT_JOINED, sep="\t", index=False)
    print(f"Joined rules+criteria: {len(df)} rows → {OUT_JOINED.relative_to(ROOT)}")

    cells = build_cell_profile(df)
    cells.to_csv(OUT_CELL_PROFILE, sep="\t", index=False)
    n_cells = cells["cell_sig"].nunique()
    print(f"Cell rights profile:  {len(cells)} (cell × resource) rows, "
          f"{n_cells} distinct cells → {OUT_CELL_PROFILE.relative_to(ROOT)}")

    emic = build_emic_vs_criterion(df)
    emic.to_csv(OUT_EMIC_VS_CRIT, sep="\t", index=False)
    n_emic = emic["group_meta"].nunique()
    n_split = emic[emic["n_distinct_cells"] >= 2]["group_meta"].nunique()
    print(f"Emic vs criterion:    {n_emic} emic labels, {n_split} span ≥2 cells "
          f"→ {OUT_EMIC_VS_CRIT.relative_to(ROOT)}")

    athens = build_athens_snapshot(df)
    athens.to_csv(OUT_ATHENS, sep="\t", index=False)
    print(f"Athens snapshot:      {len(athens)} (cell × resource) rows "
          f"→ {OUT_ATHENS.relative_to(ROOT)}")

    contingent = build_contingent_rights(df)
    contingent.to_csv(OUT_CONTINGENT, sep="\t", index=False)
    n_cont = (contingent["status"] == "contingent").sum()
    n_stable = (contingent["status"].str.startswith("stable_")).sum()
    print(f"Counterfactual test:  {len(contingent)} (cell × resource) cross-polity, "
          f"{n_cont} contingent, {n_stable} stable "
          f"→ {OUT_CONTINGENT.relative_to(ROOT)}")

    print("\n--- top 12 most-populated criterion-cells ---")
    pop = (
        df.groupby(["cell_sig", "cell_long"])
        .size().reset_index(name="n_rules")
        .sort_values("n_rules", ascending=False)
        .head(12)
    )
    for _, r in pop.iterrows():
        print(f"  [{r['cell_sig']:14s}] {r['n_rules']:>4d} rules — {r['cell_long']}")

    print("\n--- emic labels whose extension is split (top 10) ---")
    split = (
        emic[emic["n_distinct_cells"] >= 2][
            ["group_meta", "n_distinct_cells", "emic_total"]
        ]
        .drop_duplicates()
        .sort_values(["n_distinct_cells", "emic_total"], ascending=False)
        .head(10)
    )
    for _, r in split.iterrows():
        print(f"  {r['group_meta']:25s} spans {r['n_distinct_cells']:>2d} cells "
              f"({r['emic_total']} rules)")

    print("\n--- contingent (cell, right) pairs — Kripkean test, top 10 ---")
    head = contingent[contingent["status"] == "contingent"].head(10)
    for _, r in head.iterrows():
        print(f"  [{r['cell_sig']:14s}] {r['resource_meta'][:30]:30s}  "
              f"{r['n_polities']} polities  ({r['directionalities'][:60]})")


if __name__ == "__main__":
    main()
