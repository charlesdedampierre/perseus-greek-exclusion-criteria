"""BUN-1002 — Model missing rights + Hasse diagram of groups by rights-inclusion.

Two things the ticket now asks:

  1. MODEL THE MISSING INFORMATION. The corpus does not state every right for every
     group, so the group × rights matrix has blanks. We fill each blank with an inferred
     1 / 0 plus a probability, learned from the corpus: for every criterion axis-value
     (sex=male, ownership=enslaved, …) we estimate P(has right r | that trait) from the
     rules that mention it, then combine a group's traits by the GEOMETRIC MEAN — so if
     any single defining trait denies the right (P≈0) the group is predicted to lack it.
     Each cell is tagged `observed` (the corpus states it) or `inferred` (model fill).

  2. HASSE DIAGRAM. With a complete right-set per group, group A dominates group B
     (A ⪰ B) iff rights(A) ⊇ rights(B). We draw the covering relations only (direct
     dominance steps) — the partial order of who is included in whom by rights.

Groups are interpretable criterion cells (wealthy/poor citizen man, citizen woman,
metic, freedman, slave, …). Rights are the curated set from the expected table.

Outputs (data/clean/final/):
  - group_rights_imputed.tsv     complete group × rights matrix, values like "1" / "0"
                                 with a parallel *_src column (observed / inferred) and
                                 *_p (model probability) — long form for transparency
  - group_rights_hasse.png       the Hasse diagram
"""
from __future__ import annotations

from itertools import product
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[2]
FINAL = ROOT / "data/clean/final"

AXES = ["c_sex", "c_age", "c_ownership_status", "c_ancestry", "c_wealth"]
UNSPEC = {"", "any", "unspecified", "nan", "none", "middle"}
MIN_SUPPORT = 2          # min rules for an axis-value→right estimate to be trusted
IMPUTE_THRESHOLD = 0.5   # geometric-mean probability at/above which we infer a 1

# Curated, interpretable rights (from the expected table) -----------------------------
RIGHTS = [
    "Voting in the assembly", "Speaking in the assembly", "Eligibility for public office",
    "Eligibility for jury service", "Deliberative authority", "Right to a trial",
    "Testifying in court", "Protection from judicial torture",
    "Protection from penal corporal punishment", "Protection from private assault",
    "Personal liberty", "Freedom of movement", "Owning land",
    "Owning and retaining property", "Inheriting property", "Right to citizenship",
]

# Curated groups: readable name -> criterion vector (only the axes that define it) -----
GROUPS = {
    "Wealthy citizen man": dict(c_sex="male", c_age="adult", c_ownership_status="free",
                                c_ancestry="native", c_wealth="high"),
    "Citizen man":         dict(c_sex="male", c_age="adult", c_ownership_status="free",
                                c_ancestry="native"),
    "Poor citizen man (thes)": dict(c_sex="male", c_age="adult", c_ownership_status="free",
                                    c_ancestry="native", c_wealth="low"),
    "Citizen youth":       dict(c_sex="male", c_age="minor", c_ownership_status="free",
                                c_ancestry="native"),
    "Citizen woman":       dict(c_sex="female", c_age="adult", c_ownership_status="free",
                                c_ancestry="native"),
    "Metic man":           dict(c_sex="male", c_age="adult", c_ownership_status="free",
                                c_ancestry="foreign"),
    "Metic woman":         dict(c_sex="female", c_age="adult", c_ownership_status="free",
                                c_ancestry="foreign"),
    "Freedman":            dict(c_sex="male", c_age="adult", c_ownership_status="freed"),
    "Male slave":          dict(c_sex="male", c_age="adult", c_ownership_status="enslaved"),
    "Female slave":        dict(c_sex="female", c_age="adult", c_ownership_status="enslaved"),
}


def tok(v) -> str:
    if pd.isna(v):
        return "*"
    t = str(v).strip().lower()
    return "*" if t in UNSPEC else t


def load() -> pd.DataFrame:
    df = pd.read_csv(FINAL / "rules_with_criteria.tsv", sep="\t")
    gr = pd.read_csv(FINAL / "rule_resource_granular.tsv", sep="\t")
    df = df.merge(gr[["rule_id", "resource_granular"]], on="rule_id", how="left")
    df = df[df["directionality"].isin(["MORE", "LESS"]) & df["resource_granular"].isin(RIGHTS)].copy()
    for a in AXES:
        df[a + "_t"] = df[a].map(tok)
    return df


def learn_axis_value_prob(df: pd.DataFrame) -> tuple[dict, dict, dict]:
    """Estimate, from the corpus:
      - prob[(axis, value, right)]  = P(has right | trait), where attested;
      - backoff[(axis, value)]      = P(a trait grants ANY right) — its overall grant
        rate across all rights (enslaved ≈ low, free ≈ high). Used when a specific
        right has no evidence for that trait, so 'no data about slaves voting' defaults
        to the low enslaved rate, not the high male rate;
      - prior[right]                = P(has right) overall.
    """
    prob, prior, backoff = {}, {}, {}
    for r in RIGHTS:
        sub = df[df["resource_granular"] == r]
        m = int((sub["directionality"] == "MORE").sum())
        l = int((sub["directionality"] == "LESS").sum())
        prior[r] = m / (m + l) if (m + l) else 0.5
        for a in AXES:
            for v, ss in sub.groupby(a + "_t"):
                if v == "*":
                    continue
                mm = int((ss["directionality"] == "MORE").sum())
                ll = int((ss["directionality"] == "LESS").sum())
                if mm + ll >= MIN_SUPPORT:
                    prob[(a, v, r)] = mm / (mm + ll)
    for a in AXES:
        for v, ss in df.groupby(a + "_t"):
            if v == "*":
                continue
            mm = int((ss["directionality"] == "MORE").sum())
            ll = int((ss["directionality"] == "LESS").sum())
            backoff[(a, v)] = mm / (mm + ll) if (mm + ll) else 0.5
    return prob, prior, backoff


def group_refines_rule(group: dict, rule_sig: dict) -> bool:
    """True if the rule's grant/denial genuinely applies to the group: compatible on
    every axis the rule constrains, AND the rule pins down the group's ownership status.

    The ownership requirement stops a generic rule (e.g. one that only says 'males')
    from crediting a slave with a citizen right — a slave bit may come only from rules
    that are actually about enslaved people."""
    for a in AXES:
        rv = rule_sig.get(a, "*")
        if rv == "*":
            continue
        if group.get(a, "*") != rv:
            return False
    own = group.get("c_ownership_status", "*")
    if own != "*" and rule_sig.get("c_ownership_status", "*") != own:
        return False  # rule must be about this ownership class to count as observed
    return True


def observed_bit(df: pd.DataFrame, group: dict, right: str):
    sub = df[df["resource_granular"] == right]
    more = less = 0
    for _, row in sub.iterrows():
        rule_sig = {a: row[a + "_t"] for a in AXES}
        if group_refines_rule(group, rule_sig):
            if row["directionality"] == "MORE":
                more += 1
            else:
                less += 1
    if more + less == 0:
        return None, more, less
    if more == less:
        return None, more, less  # tie → treat as unobserved, let the model decide
    return (1 if more > less else 0), more, less


def impute_prob(group: dict, right: str, prob: dict, prior: dict, backoff: dict) -> float:
    # every specified axis contributes a term: its right-specific estimate where we have
    # one, else its overall grant rate (so an unspoken 'slaves don't vote' still counts).
    ps = []
    for a in AXES:
        v = group.get(a, "*")
        if v == "*":
            continue
        ps.append(prob.get((a, v, right), backoff.get((a, v), prior[right])))
    if not ps:
        return prior[right]
    # geometric mean — a single strong denial (P≈0) pulls the whole product down
    return float(np.exp(np.mean(np.log(np.clip(ps, 1e-6, 1.0)))))


def build_matrix(df, prob, prior, backoff):
    rows = []
    bits = {}       # (group, right) -> 0/1
    for gname, gvec in GROUPS.items():
        for right in RIGHTS:
            obit, more, less = observed_bit(df, gvec, right)
            if obit is not None:
                bit, src, p = obit, "observed", float(more / (more + less))
            else:
                p = impute_prob(gvec, right, prob, prior, backoff)
                bit, src = (1 if p >= IMPUTE_THRESHOLD else 0), "inferred"
            bits[(gname, right)] = bit
            rows.append({"group": gname, "right": right, "bit": bit,
                         "source": src, "p_has": round(p, 3),
                         "n_more": more, "n_less": less})
    return pd.DataFrame(rows), bits


def draw_hasse(bits, groups, rights, out_png, title):
    rset = {g: frozenset(r for r in rights if bits[(g, r)] == 1) for g in groups}
    nrights = {g: len(rset[g]) for g in groups}

    G = nx.DiGraph()
    for g in groups:
        G.add_node(g)
    for a in groups:
        for b in groups:
            if a != b and rset[b] < rset[a]:
                G.add_edge(a, b)
    H = nx.transitive_reduction(G)

    # layout: y = rank in the partial order (longest chain below the node), so that
    # INCOMPARABLE groups share a level and sit side by side (a true Hasse diagram),
    # rather than stacking by raw rights-count.
    # H edge A→B means A ⊋ B (A above B). height = longest chain from a bottom element.
    rank = {}
    for g in reversed(list(nx.topological_sort(H))):    # sinks (bottom) first
        below = list(H.successors(g))                   # groups directly below g
        rank[g] = 0 if not below else 1 + max(rank[b] for b in below)

    band = {}
    for g in groups:
        band.setdefault(rank[g], []).append(g)
    span = max(len(v) for v in band.values())
    pos = {}
    for lvl, gs in band.items():
        gs.sort(key=lambda g: -nrights[g])
        for i, g in enumerate(gs):
            pos[g] = ((i - (len(gs) - 1) / 2) * 3.4 * (span / max(len(gs), 1)), lvl * 2.6)

    fig, ax = plt.subplots(figsize=(15, 11))
    nx.draw_networkx_edges(H, pos, ax=ax, arrows=True, arrowstyle="-|>", arrowsize=18,
                           width=1.4, alpha=0.5, edge_color="#444",
                           min_target_margin=26, min_source_margin=20, node_size=2400)
    ncol = [nrights[g] for g in H.nodes]
    nx.draw_networkx_nodes(H, pos, ax=ax, nodelist=list(H.nodes), node_size=2600,
                           node_color=ncol, cmap="YlGnBu",
                           vmin=0, vmax=len(rights), edgecolors="#111", linewidths=1.6)
    for g in H.nodes:
        x, y = pos[g]
        ax.text(x, y + 0.34, g, ha="center", va="bottom", fontsize=10.5,
                fontweight="bold", color="#1a4280")
        ax.text(x, y, str(nrights[g]), ha="center", va="center", fontsize=12,
                fontweight="bold", color="white")
    ax.set_title(title + "\n(arrow A → B: A holds every right B holds, and more; "
                 "number = rights held)", fontsize=13, pad=16)
    ax.set_ylabel("rank in the rights partial order (bottom = fewest rights)")
    ax.set_xticks([]); ax.set_yticks(sorted({lvl * 2.6 for lvl in band}))
    ax.set_yticklabels([str(lvl) for lvl in sorted(band)])
    ax.grid(axis="y", alpha=0.2, ls=":")
    plt.tight_layout()
    fig.savefig(out_png, dpi=130, bbox_inches="tight")
    return H, rset, nrights


def main():
    df = load()
    prob, prior, backoff = learn_axis_value_prob(df)
    matrix, bits = build_matrix(df, prob, prior, backoff)
    matrix.to_csv(FINAL / "group_rights_imputed.tsv", sep="\t", index=False)

    n_obs = int((matrix["source"] == "observed").sum())
    n_inf = int((matrix["source"] == "inferred").sum())
    print(f"Groups: {len(GROUPS)} | rights: {len(RIGHTS)} | cells: {len(matrix)}")
    print(f"  observed (corpus states it): {n_obs}  ({n_obs/len(matrix):.0%})")
    print(f"  inferred (model fills gap):  {n_inf}  ({n_inf/len(matrix):.0%})")

    H, rset, nrights = draw_hasse(
        bits, list(GROUPS), RIGHTS, FINAL / "group_rights_hasse_corpus.png",
        "Groups by rights-inclusion — corpus (observed + modelled gaps), Classical Athens")
    print(f"\nCorpus Hasse: {H.number_of_nodes()} nodes, {H.number_of_edges()} covering edges")
    for g in sorted(GROUPS, key=lambda x: -nrights[x]):
        print(f"  {nrights[g]:2d}  {g}")

    # Expected (scholarly) Hasse — the clean hierarchy from the benchmark table
    exp = pd.read_csv(FINAL / "expected_rights_classical_athens.tsv", sep="\t")
    exp = exp[exp["right"].isin(RIGHTS)]
    exp_groups = {"citizen_male": "Citizen man", "citizen_female": "Citizen woman",
                  "slave": "Slave", "metic": "Metic"}
    exp_bits = {(lbl, row["right"]): int(row[col])
                for col, lbl in exp_groups.items() for _, row in exp.iterrows()}
    He, _, ne = draw_hasse(exp_bits, list(exp_groups.values()), list(exp["right"]),
                           FINAL / "group_rights_hasse_expected.png",
                           "Groups by rights-inclusion — expected (scholarly), Classical Athens")
    print(f"\nExpected Hasse: {He.number_of_nodes()} nodes, {He.number_of_edges()} covering edges")
    for g in sorted(exp_groups.values(), key=lambda x: -ne[x]):
        print(f"  {ne[g]:2d}  {g}")

    print("\nWrote group_rights_imputed.tsv, group_rights_hasse_corpus.png, "
          "group_rights_hasse_expected.png")


if __name__ == "__main__":
    main()
