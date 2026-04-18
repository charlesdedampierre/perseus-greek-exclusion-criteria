"""
Build the V19 annotation sample and explorer CSV.

V19 output already contains `criteria` from the LLM (fixed list), so no
post-hoc classifier step is needed. This script:
- Loads all V19 JSONs from data/llm_results/gemini_v19/.
- Builds a rule-level table with one row per extracted rule.
- Samples 5 rules per criterion (12 criteria) -> 60 rules total, preferring
  author diversity.
- Writes the explorer CSV with the same schema as sample60_v18.csv.
"""

import json
import random
from collections import Counter
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
V19_DIR = HERE / "data/llm_results/gemini_v19"
META_TSV = HERE / "data/processed_data/perseus_works_wikidata.tsv"
RULES_TSV = HERE / "data/rules_classified_v19.tsv"
SAMPLE_TSV = HERE / "data/sample60_v19.tsv"
EXPLORER_CSV = HERE / "data-exploration/explorer-app/public/data/sample60_v19.csv"

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
SEED = 42


def norm_criteria(v) -> list[str]:
    """V19 may output criteria as a single string or a list."""
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    s = str(v).strip()
    if not s:
        return []
    if "|" in s:
        return [x.strip() for x in s.split("|") if x.strip()]
    if "," in s:
        return [x.strip() for x in s.split(",") if x.strip()]
    return [s]


def norm_verbatim(v) -> str:
    if v is None:
        return ""
    if isinstance(v, list):
        return " | ".join(str(x) for x in v)
    return str(v)


def build_rules_table() -> pd.DataFrame:
    rows = []
    for fp in sorted(V19_DIR.glob("tlg*.json")):
        d = json.loads(fp.read_text())
        fid = d.get("_file_id", fp.stem)
        for i, r in enumerate(d.get("extracted_rules", [])):
            if not isinstance(r, dict):
                continue
            crits = norm_criteria(r.get("criteria"))
            crits = [c for c in crits if c in CRITERIA]
            rows.append({
                "rule_uid": f"{fid}#{i}",
                "file_id": fid,
                "criteria": "|".join(crits),
                "rule": r.get("rule") or r.get("rule_name") or "",
                "group": r.get("group") or "",
                "resource": r.get("resource") or "",
                "directionality": r.get("directionality") or "",
                "verbatim": norm_verbatim(r.get("verbatim") or r.get("proof")),
                "contemporary": r.get("contemporary"),
                "factuality": r.get("factuality"),
                "reasoning": r.get("reasoning") or "",
                "confidence": r.get("confidence"),
            })
    return pd.DataFrame(rows)


def resample(rules: pd.DataFrame, author_map: dict) -> pd.DataFrame:
    def tags(s):
        return [c for c in str(s or "").split("|") if c]

    pool = rules[rules["criteria"].apply(lambda s: bool(tags(s)))].copy()
    pool["author"] = pool["file_id"].map(lambda f: author_map.get(f, {}).get("author"))
    pool = pool[pool["author"].notna()].reset_index(drop=True)
    print(f"Pool: {len(pool):,} rules with non-empty criteria (total V19 rules: {len(rules):,})")

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
    return sample


def write_explorer_csv(sample: pd.DataFrame, author_map: dict):
    meta = sample["file_id"].map(
        lambda f: author_map.get(f, {"author": "", "work_title": "", "author_impact_date": None})
    )
    out = pd.DataFrame({
        "work_name": meta.map(lambda m: m.get("work_title", "")),
        "author": meta.map(lambda m: m.get("author", "")),
        "impact_year": pd.to_numeric(
            meta.map(lambda m: m.get("author_impact_date")), errors="coerce"
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
        "extraction_method": "gemini_v19",
        "extraction_cost_usd": "",
        "prompt_tokens": "",
        "completion_tokens": "",
        "rule_uid": sample["rule_uid"],
        "file_id": sample["file_id"],
        "rule_category": "",
        "reasoning": sample["reasoning"],
        "specificity": "",
        "specificity_reasoning": "",
        "confidence": sample["confidence"],
        "factuality": sample["factuality"],
    })
    EXPLORER_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(EXPLORER_CSV, index=False)
    print(f"\nExplorer CSV: {EXPLORER_CSV}")


def main():
    meta = pd.read_csv(META_TSV, sep="\t")
    author_map = {
        row["file_id"]: {
            "author": row.get("perseus_author"),
            "work_title": row.get("wikidata_work_label") or row.get("perseus_title"),
            "author_impact_date": row.get("author_impact_date"),
        }
        for _, row in meta.iterrows()
    }

    rules = build_rules_table()
    rules.to_csv(RULES_TSV, sep="\t", index=False)
    print(f"Rules table: {len(rules):,} rules -> {RULES_TSV}")

    crit_counts = Counter()
    for s in rules["criteria"]:
        for c in str(s).split("|"):
            if c:
                crit_counts[c] += 1
    print("\nRule-weighted criterion counts:")
    for c, n in crit_counts.most_common():
        print(f"  {c!r:<25}  {n}")

    sample = resample(rules, author_map)
    sample.to_csv(SAMPLE_TSV, sep="\t", index=False)
    print(f"\nSample TSV: {SAMPLE_TSV}")

    write_explorer_csv(sample, author_map)


if __name__ == "__main__":
    main()
