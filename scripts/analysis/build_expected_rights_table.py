"""BUN-1002 — EXPECTED rights table for Classical Athens (scholarly ground truth).

A hand-authored hypothesis of what the four top cells SHOULD look like, from standard
scholarship on Classical Athens (5th–4th c. BCE): adult male citizen (politēs), adult
female citizen (astē), slave (doulos), and free resident foreigner (metic / xenos).

Purpose: a benchmark to compare the corpus-derived table against. Where the corpus
disagrees with this expectation, the divergence is usually corpus bias — ancient authors
discuss *restrictions and exceptions* far more than the unremarkable default (e.g. they
rarely state "citizens are citizens", so "Right to citizenship" can read as 0 in the
corpus even though it is trivially 1).

Values: 1 = the group has the right; 0 = it does not. Where a right was held only in a
mediated or partial form (women acting through a male guardian; metics through a
prostatēs), we record the dominant fact and flag it in `note`.

Outputs (data/clean/final/):
  - expected_rights_classical_athens.tsv          wide, readable (rights × 4 cells)
  - expected_vs_observed_classical_athens.tsv      cell-by-cell agreement with the corpus
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FINAL = ROOT / "data/clean/final"

CELLS = ["citizen_male", "citizen_female", "slave", "metic"]

# right : (citizen_male, citizen_female, slave, metic, scholarly basis)
# Strictly binary — 1 = the group holds the right as a real capacity, 0 = it does not.
# Where a right existed only in mediated form (women through a kyrios) we score it 0,
# because the group did not hold it independently.
EXPECTED = {
    # ---- political participation ----
    "Voting in the assembly":            (1, 0, 0, 0, "Ekklesia restricted to adult male citizens."),
    "Speaking in the assembly":          (1, 0, 0, 0, "Isēgoria for male citizens; atimoi barred (sub-pop)."),
    "Deliberative authority":            (1, 0, 0, 0, "Boulē / political deliberation: male citizens only."),
    "Eligibility for public office":     (1, 0, 0, 0, "Office reserved to male citizens; some by census class."),
    "Eligibility for the archonship":    (1, 0, 0, 0, "Archonship: male citizens, originally upper census classes."),
    "Eligibility for jury service":      (1, 0, 0, 0, "Dikastai drawn from male citizens over 30."),
    # ---- legal standing & the body ----
    "Right to a trial":                  (1, 0, 0, 1, "Male citizen and metic (via polemarch) have standing; astē acts only through a kyrios → 0; slave none."),
    "Testifying in court":               (1, 0, 0, 1, "Women effectively excluded; slaves only under torture; free metics could testify."),
    "Protection from execution without trial": (1, 1, 0, 1, "Citizens & free persons protected; slaves could be killed/punished without trial."),
    "Protection from judicial torture":  (1, 1, 0, 1, "Basanos applied to slaves; free persons exempt."),
    "Protection from penal corporal punishment": (1, 1, 0, 1, "Citizens not subject to the whip; slaves were."),
    "Protection from private assault":   (1, 1, 0, 1, "Free persons protected by the hubris law; a slave, as property, had no held protection from bodily coercion → 0."),
    "Personal liberty":                  (1, 1, 0, 1, "Free status for citizens & metics; slaves are property."),
    "Freedom of movement":               (1, 1, 0, 1, "Free persons move freely; slaves constrained."),
    # ---- property & economy ----
    "Owning land":                       (1, 0, 0, 0, "Enktēsis (land) limited to citizens; women & metics excluded barring special grant."),
    "Owning and retaining property":     (1, 0, 0, 1, "Men and metics control property; a citizen woman's property is managed by her kyrios (no alienation above trivial value) → 0."),
    "Inheriting property":               (1, 0, 0, 1, "Sons and metics inherit; the epiklēros transmits property to her son but does not inherit in her own right → 0."),
    "Right to engage in business":       (1, 1, 0, 1, "Trade open to free persons incl. women (petty retail) & metics; slaves work for masters, not as a right."),
    # ---- status & family ----
    "Right to citizenship":              (1, 1, 0, 0, "Astē holds citizen status (no political rights); slaves & metics excluded."),
    "Right to marry a citizen":          (1, 1, 0, 0, "After Pericles' 451 law citizen marriage requires two citizen parents; metics excluded."),
    "Freedom of choice in marriage":     (1, 0, 0, 1, "Citizen women's marriages arranged by the kyrios; men & free metics freer."),
}


def build_expected() -> pd.DataFrame:
    rows = []
    for right, (cm, cf, sl, me, note) in EXPECTED.items():
        rows.append({"right": right, "citizen_male": cm, "citizen_female": cf,
                     "slave": sl, "metic": me, "basis": note})
    return pd.DataFrame(rows)


def load_observed() -> pd.DataFrame:
    """Aggregate the corpus four-cell table for Classical Athens across periods."""
    m = pd.read_csv(FINAL / "top_cells_rights_matrix.tsv", sep="\t")
    m = m[m["rule_polity"] == "Classical Athens"]
    meta = {"archetype", "emic_label", "rule_polity", "period", "cell_sig", "n_rules",
            "c_sex", "c_age", "c_ownership_status", "c_ancestry", "c_residence", "c_wealth"}
    right_cols = [c for c in m.columns if c not in meta]
    long = m.melt(id_vars=["archetype"], value_vars=right_cols,
                  var_name="right", value_name="bit").dropna(subset=["bit"])

    # collapse periods: 1 if any period says 1 and none says 0; 0 if any 0 and none 1;
    # X if both appear (period-level contradiction)
    def collapse(s):
        vals = set(s)
        if "1" in vals and "0" in vals:
            return "X"
        if "1" in vals:
            return "1"
        if "0" in vals:
            return "0"
        return "X"
    obs = (long.groupby(["archetype", "right"])["bit"].agg(collapse).reset_index()
               .rename(columns={"bit": "observed"}))
    obs["archetype"] = obs["archetype"].replace({"foreigner": "metic"})
    return obs


def main():
    exp = build_expected()
    exp.to_csv(FINAL / "expected_rights_classical_athens.tsv", sep="\t", index=False)
    print(f"Expected table: {len(exp)} rights × 4 cells")
    print(exp.drop(columns="basis").to_string(index=False))

    exp_long = exp.melt(id_vars=["right"], value_vars=CELLS,
                        var_name="archetype", value_name="expected")
    obs = load_observed()
    cmp = exp_long.merge(obs, on=["archetype", "right"], how="left")

    def verdict(r):
        if pd.isna(r["observed"]):
            return "no_corpus_evidence"
        if r["observed"] == "X":
            return "corpus_contested"
        return "agree" if str(int(r["expected"])) == str(r["observed"]) else "DISAGREE"
    cmp["verdict"] = cmp.apply(verdict, axis=1)
    cmp.to_csv(FINAL / "expected_vs_observed_classical_athens.tsv", sep="\t", index=False)

    print("\n=== Expected vs corpus (Classical Athens) ===")
    print(cmp["verdict"].value_counts().to_string())
    covered = cmp[cmp["verdict"].isin(["agree", "DISAGREE"])]
    if len(covered):
        acc = (covered["verdict"] == "agree").mean()
        print(f"\nAgreement where corpus has a clean bit: {acc:.0%} "
              f"({(covered['verdict']=='agree').sum()}/{len(covered)})")
    dis = cmp[cmp["verdict"] == "DISAGREE"]
    if len(dis):
        print("\nDisagreements (expected ≠ corpus) — usually corpus bias toward exclusions:")
        print(dis[["archetype", "right", "expected", "observed"]].to_string(index=False))


if __name__ == "__main__":
    main()
