"""
Batch-2 resample for V19 annotation.

Uses the secondary-classified rules table. Applies two filters:
- is_historical != 1        (drop rules that reference a distant past)
- group_specificity != 1    (drop rules with non-group / behavioural groups)

Then excludes rule_uids already annotated in batch 1 (sample60_v19.tsv) and
resamples 5 per criterion (60 total, 12 criteria) with author-diversity bias.

Writes:
- data/sample60_v19_batch2.tsv
- data-exploration/explorer-app/public/data/sample60_v19.csv   (OVERWRITES,
  so the explorer app loads batch 2)
"""

import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
RULES_TSV = HERE / "data/rules_classified_v19_full.tsv"
META_TSV = HERE / "data/processed_data/perseus_works_wikidata.tsv"
FACT_TSV = HERE / "data/works_factuality_v18.tsv"
BATCH1_TSV = HERE / "data/sample60_v19_batch1.tsv"
BATCH2_TSV = HERE / "data/sample60_v19_batch2.tsv"
SAMPLE_TSV = HERE / "data/sample60_v19_batch3.tsv"
EXPLORER_CSV = HERE / "data-exploration/explorer-app/public/data/sample60_v19.csv"

CRITERIA = [
    "Gender", "Citizenship", "Occupation", "Age", "Lineage", "Nobility",
    "Wealth / Properties", "Ethnicity", "Education", "Freedom", "Religion", "Health",
]
PER_CRITERION = 5
SEED = 2027


def tags(s):
    return [c for c in str(s or "").split("|") if c]


def main():
    rules = pd.read_csv(RULES_TSV, sep="\t")
    n0 = len(rules)
    print(f"Start: {n0:,} rules")

    # Work-level factuality filter (drop fact==1, mythic/speculative works)
    fact = pd.read_csv(FACT_TSV, sep="\t")[["perseus_id", "factuality"]].rename(
        columns={"factuality": "work_factuality"}
    )
    rules["perseus_id"] = rules["file_id"].str.rsplit(".", n=1).str[0]
    rules = rules.merge(fact, on="perseus_id", how="left")
    before = len(rules)
    rules = rules[rules["work_factuality"] != 1].copy()
    print(f"After dropping work factuality==1 (mythic): {len(rules):,} (was {before:,})")

    # Rule-level contemporary filter (drop contemporary==0, historical/mythical)
    before = len(rules)
    rules = rules[rules["contemporary"] != 0].copy()
    print(f"After dropping contemporary==0 (historical/mythical): {len(rules):,} (was {before:,})")

    before = len(rules)
    rules = rules[rules["is_historical"] != 1].copy()
    print(f"After dropping is_historical==1: {len(rules):,} (was {before:,})")

    before = len(rules)
    rules = rules[rules["group_specificity"] != 1].copy()
    print(f"After dropping group_specificity==1: {len(rules):,} (was {before:,})")

    batch1 = pd.read_csv(BATCH1_TSV, sep="\t")
    batch2 = pd.read_csv(BATCH2_TSV, sep="\t")
    exclude_uids = set(batch1["rule_uid"]) | set(batch2["rule_uid"])
    before = len(rules)
    rules = rules[~rules["rule_uid"].isin(exclude_uids)].copy()
    print(f"After excluding batch-1 + batch-2 rule_uids ({len(exclude_uids)}): {len(rules):,} (was {before:,})")

    meta = pd.read_csv(META_TSV, sep="\t")
    author_map = {
        row["file_id"]: {
            "author": row.get("perseus_author"),
            "work_title": row.get("wikidata_work_label") or row.get("perseus_title"),
            "author_impact_date": row.get("author_impact_date"),
        }
        for _, row in meta.iterrows()
    }

    pool = rules[rules["criteria"].apply(lambda s: bool(tags(s)))].copy()
    pool["author"] = pool["file_id"].map(lambda f: author_map.get(f, {}).get("author"))
    pool = pool[pool["author"].notna()].reset_index(drop=True)

    picked_uids = set()
    picked = []
    authors_used = set()
    fill = {c: 0 for c in CRITERIA}

    pool_shuffled = pool.sample(frac=1, random_state=SEED).reset_index(drop=True)

    for crit in CRITERIA:
        eligible = pool_shuffled[
            pool_shuffled["criteria"].apply(lambda s: crit in tags(s))
            & ~pool_shuffled["rule_uid"].isin(picked_uids)
        ].copy()
        eligible["_new_author"] = eligible["author"].map(
            lambda a: 0 if a not in authors_used else 1
        )
        eligible = eligible.sort_values("_new_author").drop(columns="_new_author")

        for _, row in eligible.iterrows():
            if fill[crit] >= PER_CRITERION:
                break
            picked_uids.add(row["rule_uid"])
            d = row.to_dict()
            d["sampled_for"] = crit
            picked.append(d)
            authors_used.add(row["author"])
            fill[crit] += 1

    sample = pd.DataFrame(picked).sort_values(
        ["sampled_for", "author", "file_id"]
    ).reset_index(drop=True)
    print(f"\nSample size: {len(sample)} rules / {len(authors_used)} unique authors")
    print(f"Per-criterion fill (target={PER_CRITERION}):")
    for c in CRITERIA:
        print(f"  {c!r:<25}  {fill[c]}")

    sample.to_csv(SAMPLE_TSV, sep="\t", index=False)
    print(f"\nBatch-3 TSV: {SAMPLE_TSV}")

    # Explorer CSV — same schema as batch 1.
    meta_cols = sample["file_id"].map(
        lambda f: author_map.get(f, {"author": "", "work_title": "", "author_impact_date": None})
    )
    out = pd.DataFrame({
        "work_name": meta_cols.map(lambda m: m.get("work_title", "")),
        "author": meta_cols.map(lambda m: m.get("author", "")),
        "impact_year": pd.to_numeric(
            meta_cols.map(lambda m: m.get("author_impact_date")), errors="coerce"
        ).astype("Int64"),
        "polity": "",
        "criteria": sample["criteria"],
        "sampled_for": sample["sampled_for"],
        "is_contemporary": sample["contemporary"],
        "verbatim_type": sample["factuality"].map(
            lambda v: "fact" if v == 1 else ("opinion" if v == 0 else "")
        ),
        "criterion_label": sample["rule"],
        "in_group": sample["group"],
        "out_group": "",
        "resource": sample["resource"],
        "resource_std": "",
        "speaker": sample["directionality"],
        "verbatim": sample["verbatim"],
        "matched_keywords": sample["rule"],
        "extraction_method": "gemini_v19_batch3",
        "extraction_cost_usd": "",
        "prompt_tokens": "",
        "completion_tokens": "",
        "rule_uid": sample["rule_uid"],
        "file_id": sample["file_id"],
        "rule_category": "",
        "reasoning": sample["reasoning"],
        "group_generality": sample["group_specificity"].astype("Int64"),
        "generality_reasoning": sample["secondary_reasoning"],
        "confidence": sample["confidence"],
        "factuality": sample["work_factuality"].astype("Int64"),
        "resource_materiality": sample["resource_materiality"].astype("Int64"),
        "materiality_reasoning": sample["materiality_reasoning"],
        "resource_generality": sample["resource_generality"].astype("Int64"),
        "resource_generality_reasoning": sample["resource_generality_reasoning"],
        "resource_persistence": sample["resource_persistence"].astype("Int64"),
        "persistence_reasoning": sample["persistence_reasoning"],
        "group_immutability": sample["group_immutability"].astype("Int64"),
        "immutability_reasoning": sample["immutability_reasoning"],
        "tautological": sample["tautological"].astype("Int64"),
        "tautology_reasoning": sample["tautology_reasoning"],
    })
    EXPLORER_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(EXPLORER_CSV, index=False)
    print(f"Explorer CSV (batch 3): {EXPLORER_CSV}")


if __name__ == "__main__":
    main()
