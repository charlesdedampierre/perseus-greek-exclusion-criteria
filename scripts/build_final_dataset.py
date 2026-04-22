"""Merge every piece of rule + work + dimension + polity/time + meta-category
data into one flat TSV. One row per extracted rule.

Inputs:
  - data/processed_data/rules_all_scored_with_polity_time.tsv     (662 rules)
  - data/processed_data/rules_random100_with_polity_time.tsv      (946 rules)
  - data/processed_data/group_meta_category_v3.tsv                (466 groups)
  - data/processed_data/resource_meta_category_v3.tsv             (1214 resources)
  - data/processed_data/final_dataset_for_criteria.tsv            (work metadata)

Output:
  - data/processed_data/rules_final_dataset.tsv
  - data/processed_data/rules_final_dataset.csv  (convenience copy)

Columns are grouped and ordered for downstream analysis:
  identity | work metadata | work polity/time | rule extraction |
  meta-categories | rule polity/time | core-prompt flags | 7 dimensions
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RULES_MAIN = ROOT / "data/processed_data/rules_all_scored_with_polity_time.tsv"
RULES_R100 = ROOT / "data/processed_data/rules_random100_with_polity_time.tsv"
GROUP_MAP = ROOT / "data/processed_data/group_meta_category_v3.tsv"
RESOURCE_MAP = ROOT / "data/processed_data/resource_meta_category_v3.tsv"
WORKS_META = ROOT / "data/processed_data/final_dataset_for_criteria.tsv"

OUT_TSV = ROOT / "data/processed_data/rules_final_dataset_130works_april_2026.tsv"
OUT_CSV = ROOT / "data/processed_data/rules_final_dataset_130works_april_2026.csv"

WORK_COLS = [
    "file_id",
    "perseus_id",
    "wikidata_work_id",
    "wikidata_work_label",
    "author_wikidata_id",
    "author_impact_date",
    "year",
    "historian",
    "polity_group",
    "keep_greek_focus",
    "is_scientific",
    "genre",
    "form_of_creative_work",
    "instance_of",
    "main_language",
    "languages",
    "editors",
    "pub_date",
    "n_characters",
    "n_words",
    "n_pages",
    "file_path",
]

FINAL_COLUMNS = [
    # Identity
    "rule_uid",
    "file_id",
    # Work metadata (from final_dataset_for_criteria + the work columns already in the rules TSV)
    "perseus_author",
    "perseus_title",
    "wikidata_work_id",
    "wikidata_work_label",
    "author_wikidata_id",
    "author_impact_date",
    "year",
    "period",
    "historian",
    "polity_group",
    "keep_greek_focus",
    "is_scientific",
    "genre",
    "form_of_creative_work",
    "instance_of",
    "main_language",
    "languages",
    "editors",
    "pub_date",
    "n_characters",
    "n_words",
    "n_pages",
    "file_path",
    # Work polity/time (from works_polity_time_dataset, already merged upstream)
    "work_author_polity_cliopatria",
    "work_polity",
    "work_polity_reasoning",
    "work_time_reference",
    "work_time_start",
    "work_time_end",
    "work_time_reasoning",
    # Rule extraction (core prompt)
    "criteria",
    "rule",
    "group",
    "resource",
    "directionality",
    "verbatim",
    "reasoning",
    # Meta-categories (anchored V3)
    "group_meta",
    "resource_meta",
    # Rule polity/time (rule-level)
    "rule_polity",
    "rule_polity_reasoning",
    "rule_date",
    "rule_time_reasoning",
    # Core-prompt metadata
    "contemporary",
    "factuality",
    "confidence",
    # Dimensions (V1 post-extraction) + per-dim reasoning
    "resource_materiality",
    "materiality_reasoning",
    "resource_generality",
    "generality_reasoning",
    "resource_persistence",
    "persistence_reasoning",
    "group_immutability",
    "immutability_reasoning",
    "rule_contemporarity",
    "contemporarity_reasoning",
    "opinion_vs_fact",
    "opinion_vs_fact_reasoning",
    "tautology",
    "tautology_reasoning",
]


def main() -> None:
    # Merge the two rules corpora
    a = pd.read_csv(RULES_MAIN, sep="\t")
    b = pd.read_csv(RULES_R100, sep="\t")
    assert list(a.columns) == list(b.columns), "schema mismatch"
    rules = pd.concat([a, b], ignore_index=True)
    print(f"Merged rules: {len(a)} + {len(b)} = {len(rules)}")
    dupes = rules["rule_uid"].duplicated()
    if dupes.any():
        print(f"  dropping {int(dupes.sum())} duplicate rule_uids")
        rules = rules[~dupes].copy()

    # Attach meta-categories
    gm = pd.read_csv(GROUP_MAP, sep="\t")
    rm = pd.read_csv(RESOURCE_MAP, sep="\t")
    rules = rules.merge(gm, on="group", how="left")
    rules = rules.merge(rm, on="resource", how="left")
    print(
        f"Attached meta-categories:  group_meta filled {rules['group_meta'].notna().sum()}/{len(rules)}  |  "
        f"resource_meta filled {rules['resource_meta'].notna().sum()}/{len(rules)}"
    )

    # Attach work metadata (what's not already in the rules TSV)
    works = pd.read_csv(WORKS_META, sep="\t")[WORK_COLS]
    rules = rules.merge(works, on="file_id", how="left")
    n_with_work = rules["year"].notna().sum()
    print(f"Attached work metadata:    year filled {n_with_work}/{len(rules)}")

    # Derive the GOLD filter and restrict the dataset to rows that pass it.
    # Gold = mat ≥ 3 AND gen ≥ 3 AND imm ≥ 2 AND fact ≥ 4 AND tautology == 0.
    gold = (
        (rules["resource_materiality"] >= 3)
        & (rules["resource_generality"] >= 3)
        & (rules["group_immutability"] >= 2)
        & (rules["opinion_vs_fact"] >= 4)
        & (rules["tautology"] == 0)
    )
    n_before = len(rules)
    rules = rules[gold].reset_index(drop=True)
    print(
        f"Gold filter applied: {len(rules)}/{n_before} "
        f"({len(rules)/n_before:.1%}) rules kept "
        f"(mat≥3 ∧ gen≥3 ∧ imm≥2 ∧ fact≥4 ∧ tautology==0)"
    )

    # Validate + pick final columns
    missing = [c for c in FINAL_COLUMNS if c not in rules.columns]
    assert not missing, f"missing columns after merge: {missing}"
    out = rules[FINAL_COLUMNS].copy()

    # Write
    out.to_csv(OUT_TSV, sep="\t", index=False)
    out.to_csv(OUT_CSV, index=False)

    # Summary
    print(f"\nWrote {OUT_TSV.relative_to(ROOT)}")
    print(f"Wrote {OUT_CSV.relative_to(ROOT)}")
    print(f"Shape: {out.shape[0]} rows × {out.shape[1]} cols")

    # Quick sanity report
    print("\nColumn-group fill rates:")
    groups = {
        "identity": ["rule_uid", "file_id"],
        "work metadata": ["year", "genre", "n_words", "historian"],
        "work polity/time (historian only)": [
            "work_polity",
            "work_time_start",
            "work_time_end",
        ],
        "rule extraction": ["rule", "group", "resource", "directionality", "verbatim"],
        "meta-categories": ["group_meta", "resource_meta"],
        "rule polity/time": ["rule_polity", "rule_date"],
        "core-prompt flags": ["contemporary", "factuality", "confidence"],
        "dimensions": [
            "resource_materiality",
            "resource_generality",
            "resource_persistence",
            "group_immutability",
            "rule_contemporarity",
            "opinion_vs_fact",
            "tautology",
        ],
    }
    n = len(out)
    for g, cols in groups.items():
        fills = []
        for c in cols:
            fill = out[c].notna().sum()
            fills.append(f"{c}={fill}/{n}")
        print(f"  [{g}]")
        for f in fills:
            print(f"    {f}")

    print("\nRules per work (top 10):")
    print(
        out.groupby(["perseus_author", "perseus_title"])
        .size()
        .sort_values(ascending=False)
        .head(10)
        .to_string()
    )

    print("\nTop 10 group_meta:")
    print(out["group_meta"].value_counts().head(10).to_string())
    print("\nTop 10 resource_meta:")
    print(out["resource_meta"].value_counts().head(10).to_string())


if __name__ == "__main__":
    main()
