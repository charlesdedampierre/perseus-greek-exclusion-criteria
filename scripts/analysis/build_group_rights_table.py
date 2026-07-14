"""BUN-1002 — Group × rights comparison tables for the preprint.

Produces the deliverable the ticket asks for: a table comparing groups of individuals,
each row an emic group (or archetype cell) in one region and period, each right a column
holding 1 (has) / 0 (lacks) / blank (no evidence) / X (genuinely contested).

It addresses the three asks, plus the follow-up on the four top groups:

  1. LINK groups to criteria and CHECK the linking. Two independent criterion vectors —
     label-grounded (`cell_sig`) and text-grounded (`rule_criterion_vectors.tsv`) — are
     audited axis-by-axis for agreement.

  2. FIND THE RIGHT LEVEL of rights. Three candidates are scored on comparability
     (does a right reach many groups?) vs contradiction rate: `resource_meta` (coarse),
     `resource` (raw/fine), and `resource_granular` (the LLM group-independent
     reclassification from classify_resource_granular.py). `resource_granular` is the
     comparison level.

  3. CONTRADICTIONS. For a group, a right asserted both MORE and LESS is a
     contradiction. We classify each residual contradiction at the granular level as:
       - genuine partial right (the resource truly varies for the cell), or
       - sub-cell exception (the LESS rules apply to a sub-population defined by an
         extra criterion — wealth class, age — or by atimia / conduct), which no right
         granularity can remove; it is a fact about the *group*, not the right.

  4. TOP FOUR CELLS. Citizen males, citizen females, slaves, foreigners — keyed by
     criteria, compared on the granular rights, with the exceptions annotated.

Outputs (data/clean/final/):
  - group_rights_matrix.tsv            wide: emic group instance × granular rights
  - top_cells_rights_matrix.tsv        the four archetype cells × granular rights
  - group_rights_long.tsv              tidy long form with MORE/LESS counts
  - rights_contradictions.tsv          residual contradictions, classified + refined
  - right_level_diagnostic.tsv         comparability vs contradiction per right level
  - group_criteria_linking_audit.tsv   label-vs-text criterion agreement per axis
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FINAL = ROOT / "data/clean/final"

AXES = ["c_sex", "c_age", "c_ownership_status", "c_ancestry", "c_residence", "c_wealth"]
GROUP_KEYS = ["group_meta", "rule_polity", "period"]
RIGHT_COL = "resource_granular"  # the chosen comparison level
UNSPEC = {"", "any", "unspecified", "nan", "none"}

# words in a LESS rule's group label that mark a sub-population of the cell
WEALTH_WORDS = {"thetes", "thete", "poor", "pentacosiomedimni", "zeugitae", "knights",
                "wealthy", "rich", "hippeis"}
AGE_WORDS = {"old", "young", "younger", "elder", "boys", "minor", "aged"}
ATIMIA_WORDS = {"prostitut", "atimia", "atimos", "disenfranchis", "debtor", "deserter",
                "outlaw", "convicted", "exile", "banish", "secess", "eleusis",
                "father", "squander", "coward", "shield"}


def norm(v) -> str:
    if pd.isna(v):
        return "*"
    t = str(v).strip().lower()
    return "*" if t in UNSPEC else t


# --------------------------------------------------------------------------- #
# Load + link
# --------------------------------------------------------------------------- #
def load() -> pd.DataFrame:
    df = pd.read_csv(FINAL / "rules_with_criteria.tsv", sep="\t")
    df = df[df["directionality"].isin(["MORE", "LESS"])].dropna(subset=GROUP_KEYS).copy()

    gran = pd.read_csv(FINAL / "rule_resource_granular.tsv", sep="\t")
    df = df.merge(gran[["rule_id", "resource_granular"]], on="rule_id", how="left")
    df["resource_granular"] = df["resource_granular"].fillna(df["resource_meta"])

    text = pd.read_csv(FINAL / "rule_criterion_vectors.tsv", sep="\t")
    tcols = [c for c in AXES if c in text.columns]
    text = text[["rule_id"] + tcols].rename(columns={c: f"{c}__text" for c in tcols})
    df = df.merge(text, on="rule_id", how="left")
    return df


# --------------------------------------------------------------------------- #
# Right-level diagnostic
# --------------------------------------------------------------------------- #
def right_level_diagnostic(df: pd.DataFrame, keys, right_col: str) -> dict:
    g = df.groupby(keys + [right_col])["directionality"].agg(set)
    both = g.apply(lambda s: "MORE" in s and "LESS" in s)
    groups_per_right = df.groupby(right_col).apply(
        lambda d: d.groupby(keys).ngroups, include_groups=False)
    return {
        "right_level": right_col,
        "n_distinct_rights": int(df[right_col].nunique()),
        "n_cells": int(len(g)),
        "n_contradictions": int(both.sum()),
        "contradiction_rate": round(float(both.mean()), 4),
        "median_groups_per_right": round(float(groups_per_right.median()), 1),
    }


# --------------------------------------------------------------------------- #
# Linking audit
# --------------------------------------------------------------------------- #
def linking_audit(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for axis in AXES:
        lab, txt = df[axis].map(norm), df[f"{axis}__text"].map(norm)
        both = (lab != "*") & (txt != "*")
        agree = (lab == txt) & both
        rows.append({"axis": axis, "n_both_specified": int(both.sum()),
                     "agreement_where_both": round(float(agree.sum() / max(both.sum(), 1)), 3)})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Archetype cells (the four top groups, keyed by criteria)
# --------------------------------------------------------------------------- #
def archetypes(row) -> list[str]:
    sex = norm(row["c_sex"]); own = norm(row["c_ownership_status"]); anc = norm(row["c_ancestry"])
    out = []
    if own in ("free", "*") and anc in ("native", "*"):
        if sex == "male":
            out.append("citizen_male")
        elif sex == "female":
            out.append("citizen_female")
    if own == "enslaved":
        out.append("slave")
    if anc == "foreign":
        out.append("foreigner")
    return out


def classify_exception(less_groups: list[str]) -> str:
    """Why might the LESS rules apply only to a sub-population of the cell?"""
    blob = " ".join(str(g).lower() for g in less_groups)
    tags = []
    if any(w in blob for w in ATIMIA_WORDS):
        tags.append("atimia/conduct")
    if any(w in blob for w in WEALTH_WORDS):
        tags.append("wealth-class")
    if any(w in blob for w in AGE_WORDS):
        tags.append("age")
    return "; ".join(tags) if tags else "genuine/unexplained"


def is_subpopulation_exception(row, arch: str) -> bool:
    """True if this rule's GROUP LABEL names a sub-population of the archetype cell —
    a wealth class (Thetes), an age band (old men), or an atimia/conduct status
    (prostitutes, deserters, exiles). A LESS on such a label is an exception that
    removes the right from part of the cell, not a denial to the whole cell.

    We key on the group label only — never on the criterion axes — because a cell like
    slaves carries c_wealth=low intrinsically, which must not be read as a sub-class."""
    blob = str(row.get("group", "")).lower()
    return any(w in blob for w in ATIMIA_WORDS | WEALTH_WORDS | AGE_WORDS)


# --------------------------------------------------------------------------- #
# Matrix builders
# --------------------------------------------------------------------------- #
def modal(s):
    s = s.dropna()
    return s.mode().iloc[0] if not s.empty else np.nan


def bits_long(df: pd.DataFrame, keys, right_col: str) -> pd.DataFrame:
    long = (df.groupby(keys + [right_col])["directionality"]
              .agg(n_more=lambda s: int((s == "MORE").sum()),
                   n_less=lambda s: int((s == "LESS").sum()))
              .reset_index())
    # net-direction bit; X ONLY for an exact tie (genuinely contested)
    def bit(r):
        if r["n_more"] == r["n_less"]:
            return "X"
        return "1" if r["n_more"] > r["n_less"] else "0"
    long["bit"] = long.apply(bit, axis=1)
    long["contested"] = long["n_more"] == long["n_less"]
    return long


def build_wide(df: pd.DataFrame, long: pd.DataFrame, keys, right_col: str) -> pd.DataFrame:
    ident = (df.groupby(keys)
               .agg(emic_label=("emic_label", modal), cell_sig=("cell_sig", modal),
                    n_rules=("rule_id", "size"),
                    **{a: (a, modal) for a in AXES})
               .reset_index())
    wide = long.pivot_table(index=keys, columns=right_col, values="bit",
                            aggfunc="first").reset_index()
    wide.columns.name = None
    right_order = [r for r in df[right_col].value_counts().index if r in wide.columns]
    front = keys[:1] + ["emic_label"] + keys[1:] + ["cell_sig"] + AXES + ["n_rules"]
    out = (ident.merge(wide, on=keys, how="left")[front + right_order]
                .sort_values("n_rules", ascending=False).reset_index(drop=True))
    return out


# --------------------------------------------------------------------------- #
def main():
    df = load()
    print(f"Loaded {len(df)} directional rules | {df.groupby(GROUP_KEYS).ngroups} group instances")

    # 1. linking audit
    audit = linking_audit(df)
    audit.to_csv(FINAL / "group_criteria_linking_audit.tsv", sep="\t", index=False)
    print("\n=== Linking audit (label vs text-grounded) ===")
    print(audit.to_string(index=False))

    # 2. right-level diagnostic (on the four archetype cells, where comparability matters)
    df["arch"] = df.apply(archetypes, axis=1)
    arch_df = df.explode("arch").dropna(subset=["arch"])
    arch_df = arch_df[arch_df["arch"].isin(["citizen_male", "citizen_female", "slave", "foreigner"])]
    diag = pd.DataFrame([
        right_level_diagnostic(arch_df, ["arch", "rule_polity", "period"], lvl)
        for lvl in ["resource_meta", "resource", "resource_granular"]])
    diag.to_csv(FINAL / "right_level_diagnostic.tsv", sep="\t", index=False)
    print("\n=== Right-level diagnostic (four top cells) ===")
    print(diag.to_string(index=False))

    # 3. emic-group matrix at the granular level
    long = bits_long(df, GROUP_KEYS, RIGHT_COL)
    long.to_csv(FINAL / "group_rights_long.tsv", sep="\t", index=False)
    matrix = build_wide(df, long, GROUP_KEYS, RIGHT_COL)
    matrix.to_csv(FINAL / "group_rights_matrix.tsv", sep="\t", index=False)

    # 4. four-cell matrix with EXCEPTION-AWARE resolution.
    #    A right is held by the cell if its broad members have it; LESS rules that apply
    #    only to a sub-population (atimia / wealth-class / age) are exceptions, not denials.
    akeys = ["arch", "rule_polity", "period"]
    arch_df = arch_df.copy()
    arch_df["is_exc"] = arch_df.apply(lambda r: is_subpopulation_exception(r, r["arch"]), axis=1)

    g = (arch_df.groupby(akeys + [RIGHT_COL])
         .apply(lambda d: pd.Series({
             "n_more": int((d["directionality"] == "MORE").sum()),
             "n_less": int((d["directionality"] == "LESS").sum()),
             # denials that hit the WHOLE cell (not a sub-population exception)
             "broad_less": int(((d["directionality"] == "LESS") & (~d["is_exc"])).sum()),
             "exc_less": int(((d["directionality"] == "LESS") & (d["is_exc"])).sum()),
             "exc_groups": " | ".join(sorted(set(
                 str(x) for x in d.loc[(d["directionality"] == "LESS") & d["is_exc"], "group"]))),
         }), include_groups=False)
         .reset_index())

    def arch_bit(r):
        if r["n_more"] > 0 and r["broad_less"] == 0:
            return "1"            # held; any denials are sub-population exceptions
        if r["n_more"] == 0 and r["broad_less"] == 0 and r["exc_less"] > 0:
            return "1"            # only sub-pop exceptions seen → right exists for the cell at large
        if r["n_more"] == 0 and r["broad_less"] > 0:
            return "0"            # denied to the whole cell
        if r["n_more"] > r["broad_less"]:
            return "1"
        if r["broad_less"] > r["n_more"]:
            return "0"
        return "X"                # genuinely contested at the cell level
    g["bit"] = g.apply(arch_bit, axis=1)
    g["has_exceptions"] = g["exc_less"] > 0

    along2 = g.rename(columns={"arch": "group_meta"})
    arch_df2 = arch_df.drop(columns=["group_meta"]).rename(columns={"arch": "group_meta"})
    amatrix = build_wide(arch_df2, along2, GROUP_KEYS, RIGHT_COL)
    amatrix = amatrix.rename(columns={"group_meta": "archetype"})
    amatrix.to_csv(FINAL / "top_cells_rights_matrix.tsv", sep="\t", index=False)

    # contradiction report: only the genuinely contested (X) cells survive
    contra = g[g["bit"] == "X"].copy()
    contra = contra.rename(columns={"arch": "archetype", "rule_polity": "region"})
    contra["explanation"] = contra["exc_groups"].map(
        lambda s: classify_exception(s.split(" | ")) if s else "genuine/unexplained")
    contra[["archetype", "region", "period", RIGHT_COL, "n_more", "n_less",
            "broad_less", "exc_groups", "explanation"]].to_csv(
        FINAL / "rights_contradictions.tsv", sep="\t", index=False)

    n_exc = int(g["has_exceptions"].sum())
    print(f"\n=== Deliverables ===")
    print(f"group_rights_matrix.tsv    : {matrix.shape[0]} emic group instances × "
          f"{matrix.shape[1]} cols ({df[RIGHT_COL].nunique()} granular rights)")
    print(f"top_cells_rights_matrix.tsv: {amatrix.shape[0]} archetype rows")
    print(f"\nFour top cells, granular rights, exception-aware:")
    print(f"  resolved cells: {len(g)} | with documented sub-pop exceptions: {n_exc}")
    print(f"  genuinely contested (X) after exception handling: {(g['bit']=='X').sum()}")
    if (g["bit"] == "X").sum():
        print(contra[["archetype", "region", "period", RIGHT_COL, "n_more", "broad_less"]]
              .to_string(index=False))
    print("\nWrote 6 TSVs to data/clean/final/")


if __name__ == "__main__":
    main()
