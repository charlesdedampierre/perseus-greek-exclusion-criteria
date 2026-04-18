"""
Re-sample 60 rules for annotation from the filtered corpus:
- is_contemporary == 1
- verbatim_type != 'opinion'
- specificity < 7 (strict)
- at least one criterion, and NOT tagged with Legal Standing

Quota: 5 rules per primary criterion (12 criteria -> 60 total).
Each rule counts toward the quota of exactly one criterion (the one it is
picked for, recorded in `sampled_for`). Within a criterion, rules from
authors not yet sampled are preferred to maximise author diversity.

Reads:  data/rules_classified_v18.tsv
        data/processed_data/perseus_works_wikidata.tsv (for work/author sidecar)
Writes: data/sample60_v18.tsv
        data-exploration/explorer-app/public/data/sample60_v18.csv
"""

import pathlib
import random

import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
RULES_TSV = HERE / "data/rules_classified_v18.tsv"
META_TSV = HERE / "data/processed_data/perseus_works_wikidata.tsv"
SAMPLE_TSV = HERE / "data/sample60_v18.tsv"
EXPLORER_CSV = HERE / "data-exploration/explorer-app/public/data/sample60_v18.csv"

CRITERIA = [
    "Gender",
    "Citizenship",
    "Occupation",
    "Age",
    "Lineage",
    "Nobility",
    "Wealth / Properties",
    "Ethnicity",
    "Education",
    "Freedom",
    "Religion",
    "Health",
]
PER_CRITERION = 5


def tags(s):
    return [c for c in str(s or "").split("|") if c]


def main():
    rules = pd.read_csv(RULES_TSV, sep="\t")
    n0 = len(rules)

    # --- Filters ---
    pool = rules[rules["is_contemporary"] == 1]
    pool = pool[pool["verbatim_type"] != "opinion"]
    pool = pool[pd.to_numeric(pool["specificity"], errors="coerce") < 7]
    pool = pool[
        pool["criteria"].apply(
            lambda s: bool(tags(s)) and "Legal Standing" not in tags(s)
        )
    ].copy()
    print(
        f"Filtered pool: {len(pool):,} / {n0:,} rules "
        f"({len(pool)/n0*100:.1f}% of bulk)"
    )

    # --- Attach author / work_title sidecar ---
    meta = pd.read_csv(META_TSV, sep="\t").set_index("file_id")
    sidecar = meta[
        ["perseus_author", "author_impact_date", "wikidata_work_label", "perseus_title"]
    ].to_dict("index")

    def author_of(fid):
        return sidecar.get(fid, {}).get("perseus_author")

    def work_of(fid):
        s = sidecar.get(fid, {})
        return s.get("wikidata_work_label") or s.get("perseus_title")

    def year_of(fid):
        v = pd.to_numeric(
            sidecar.get(fid, {}).get("author_impact_date"), errors="coerce"
        )
        return v

    pool["author"] = pool["file_id"].map(author_of)
    pool = pool[pool["author"].notna()].reset_index(drop=True)

    # --- Quota sampling ---
    pool_shuffled = pool.sample(frac=1, random_state=42).reset_index(drop=True)
    picked_uids = set()
    authors_used = set()
    picked = []
    fill = {c: 0 for c in CRITERIA}

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
            row = row.to_dict()
            row["sampled_for"] = crit
            picked.append(row)
            authors_used.add(row["author"])
            fill[crit] += 1

    sample = (
        pd.DataFrame(picked)
        .sort_values(["sampled_for", "author", "file_id"])
        .reset_index(drop=True)
    )
    sample = sample.drop(columns=[c for c in ["author"] if c in sample.columns])
    sample["valid"] = ""
    sample["comment"] = ""

    print(f"\nSample size: {len(sample)} rules / {len(authors_used)} unique authors")
    print(f"Per-criterion fill (target = {PER_CRITERION}):")
    for c in CRITERIA:
        tag = "" if fill[c] == PER_CRITERION else "  <- short!"
        print(f"  {c!r:<25}  {fill[c]}{tag}")

    sample.to_csv(SAMPLE_TSV, sep="\t", index=False)
    print(f"\nWrote {len(sample)} rules ({len(sample.columns)} cols) to {SAMPLE_TSV}")

    # --- Explorer CSV (adds work/author/year metadata for UI display) ---
    sample["_work_title"] = sample["file_id"].map(work_of)
    sample["_author"] = sample["file_id"].map(author_of)
    sample["_year"] = pd.to_numeric(
        sample["file_id"].map(year_of), errors="coerce"
    ).astype("Int64")

    out = pd.DataFrame(
        {
            "work_name": sample["_work_title"],
            "author": sample["_author"],
            "impact_year": sample["_year"],
            "polity": "",
            "criteria": sample["criteria"],
            "sampled_for": sample["sampled_for"],
            "is_contemporary": sample["is_contemporary"],
            "verbatim_type": sample["verbatim_type"],
            "criterion_label": sample["rule_name"],
            "in_group": sample["group"],
            "out_group": "",
            "resource": sample["resource"],
            "resource_std": sample["resource_category"],
            "speaker": sample["directionality"],
            "verbatim": sample["proof"],
            "matched_keywords": sample["rule_category"],
            "extraction_method": "gemini_v18",
            "extraction_cost_usd": "",
            "prompt_tokens": "",
            "completion_tokens": "",
            "rule_uid": sample["rule_uid"],
            "file_id": sample["file_id"],
            "rule_category": sample["rule_category"],
            "reasoning": sample["reasoning"],
            "specificity": sample["specificity"],
            "specificity_reasoning": sample["specificity_reasoning"],
            "confidence": sample["confidence"],
        }
    )
    out.to_csv(EXPLORER_CSV, index=False)
    print(f"Wrote explorer CSV to {EXPLORER_CSV}")


if __name__ == "__main__":
    main()
