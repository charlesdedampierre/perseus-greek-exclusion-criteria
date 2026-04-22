"""Build a 60-rule annotation sample from the V1 core + V1 dimensions output.

Reads:
  - data/llm_results/core_v1_dimensions/rules_scored.tsv

Writes:
  - exploring interface/explorer-app/public/data/sample60_v20.csv
      CSV in the schema expected by the explorer-app React annotator
      (column names renamed: perseus_author → author, perseus_title → work_name,
       year → impact_year, rule → criterion_label, group → in_group,
       directionality → speaker, criteria list → pipe-separated,
       verbatim list → joined text, rule_contemporarity → is_contemporary,
       opinion_vs_fact → factuality, tautology → tautological,
       generality_reasoning → resource_generality_reasoning).
  - data/annotation/sample60_v20_raw.tsv
      The same sample with the native V20 schema, for inspection.

Stratification:
  - Target 15 rules per period. If a stratum has fewer rules than 15, take them
    all and redistribute the shortfall to periods with spare rules.
  - Within each stratum, pick diverse (file_id, first-criterion) pairs
    round-robin so no single work or criterion dominates.
"""

from __future__ import annotations

import ast
import json
import pathlib
import random

import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
SRC = REPO / "data/llm_results/core_v1_dimensions/rules_scored.tsv"
META = REPO / "data/processed_data/final_dataset_for_criteria.tsv"
APP_CSV = REPO / "exploring interface/explorer-app/public/data/sample60_v20.csv"
RAW_TSV = REPO / "data/annotation/sample60_v20_raw.tsv"

TARGET_TOTAL = 60
TARGET_PER_PERIOD = 15
SEED = 42

# Columns the explorer-app expects (as declared in vite.config.js saveAnnotationsPlugin).
APP_HEADERS = [
    "rule_uid", "file_id",
    "work_name", "author", "impact_year", "polity",
    "criteria",
    "sampled_for",
    "is_contemporary",
    "verbatim_type",
    "factuality",
    "criterion_label",
    "in_group", "out_group",
    "resource", "resource_std",
    "speaker", "verbatim", "matched_keywords",
    "rule_category", "reasoning",
    "group_generality", "generality_reasoning",
    "resource_materiality", "materiality_reasoning",
    "resource_generality", "resource_generality_reasoning",
    "resource_persistence", "persistence_reasoning",
    "group_immutability", "immutability_reasoning",
    "tautological", "tautology_reasoning",
    "confidence",
    "extraction_method", "extraction_cost_usd",
    "prompt_tokens", "completion_tokens",
]


def parse_list_field(value) -> list[str]:
    """Our TSV stores `criteria` and `verbatim` as Python-list-repr strings."""
    if pd.isna(value):
        return []
    txt = str(value).strip()
    if not txt or txt in ("[]", "None"):
        return []
    if txt.startswith("["):
        try:
            return [str(x).strip() for x in ast.literal_eval(txt)]
        except (ValueError, SyntaxError):
            pass
    return [txt]


def first_criterion(value) -> str:
    lst = parse_list_field(value)
    return lst[0] if lst else ""


def diverse_pick(pool: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    """Round-robin pick maximising (file_id, first-criterion) diversity."""
    if len(pool) <= n:
        return pool.sample(frac=1, random_state=seed).reset_index(drop=True)

    rng = random.Random(seed)
    pool = pool.copy()
    pool["_first_crit"] = pool["criteria"].map(first_criterion)
    remaining = pool.index.tolist()
    rng.shuffle(remaining)

    picked, used_pairs, used_crits = [], set(), set()
    for idx in remaining:
        if len(picked) >= n:
            break
        f = pool.at[idx, "file_id"]
        c = pool.at[idx, "_first_crit"]
        if (f, c) in used_pairs:
            continue
        picked.append(idx)
        used_pairs.add((f, c))
        used_crits.add(c)

    for idx in remaining:
        if len(picked) >= n:
            break
        if idx in picked:
            continue
        if pool.at[idx, "_first_crit"] not in used_crits:
            picked.append(idx)
            used_crits.add(pool.at[idx, "_first_crit"])

    for idx in remaining:
        if len(picked) >= n:
            break
        if idx not in picked:
            picked.append(idx)

    return pool.loc[picked].drop(columns="_first_crit").reset_index(drop=True)


def allocate_quotas(df: pd.DataFrame, per_period: int, total: int) -> dict:
    counts = df["period"].value_counts().to_dict()
    periods = list(counts.keys())
    quota = {p: min(per_period, counts[p]) for p in periods}
    shortfall = total - sum(quota.values())
    while shortfall > 0:
        has_spare = [p for p in periods if counts[p] > quota[p]]
        if not has_spare:
            break
        p = max(has_spare, key=lambda p: counts[p] - quota[p])
        quota[p] += 1
        shortfall -= 1
    return quota


def derive_verbatim_type(opinion_vs_fact) -> str:
    """Map 1–5 opinion_vs_fact to the string enum the UI renders as a badge."""
    try:
        v = int(float(opinion_vs_fact))
    except (ValueError, TypeError):
        return ""
    if v >= 4:
        return "fact"
    if v == 3:
        return "mixed"
    if v >= 1:
        return "opinion"
    return ""


def row_to_app_csv(row: pd.Series) -> dict:
    criteria_list = parse_list_field(row.get("criteria"))
    verbatim_list = parse_list_field(row.get("verbatim"))
    return {
        "rule_uid": row.get("rule_uid"),
        "file_id": row.get("file_id"),
        "work_name": row.get("perseus_title"),
        "author": row.get("perseus_author"),
        "impact_year": row.get("year"),
        "polity": "",
        "criteria": "|".join(criteria_list),
        "sampled_for": "gemini_v20_sample60",
        "is_contemporary": row.get("rule_contemporarity"),
        "verbatim_type": derive_verbatim_type(row.get("opinion_vs_fact")),
        "factuality": row.get("opinion_vs_fact"),
        "criterion_label": row.get("rule"),
        "in_group": row.get("group"),
        "out_group": "",
        "resource": row.get("resource"),
        "resource_std": "",
        "speaker": row.get("directionality"),
        "verbatim": " ".join(verbatim_list) if verbatim_list else "",
        "matched_keywords": "",
        "rule_category": "",
        "reasoning": row.get("reasoning"),
        # V20 does not have a separate group_generality dimension; we keep it
        # empty so the UI row renders blank rather than misattributing a score.
        "group_generality": "",
        "generality_reasoning": "",
        "resource_materiality": row.get("resource_materiality"),
        "materiality_reasoning": row.get("materiality_reasoning"),
        "resource_generality": row.get("resource_generality"),
        "resource_generality_reasoning": row.get("generality_reasoning"),
        "resource_persistence": row.get("resource_persistence"),
        "persistence_reasoning": row.get("persistence_reasoning"),
        "group_immutability": row.get("group_immutability"),
        "immutability_reasoning": row.get("immutability_reasoning"),
        "tautological": row.get("tautology"),
        "tautology_reasoning": row.get("tautology_reasoning"),
        "confidence": row.get("confidence"),
        "extraction_method": "gemini_v20_core_v1",
        "extraction_cost_usd": "",
        "prompt_tokens": "",
        "completion_tokens": "",
    }


def main() -> None:
    df = pd.read_csv(SRC, sep="\t")
    df = df[df["resource_materiality"].notna()].copy()

    # Join back to the main metadata table to pick up `year`, `genre`, etc.
    # that the scored TSV does not carry.
    meta = pd.read_csv(META, sep="\t")[["file_id", "year", "genre"]]
    df = df.merge(meta, on="file_id", how="left")
    print(f"Loaded {len(df):,} scored rules")
    print("\nAvailable per period:")
    print(df["period"].value_counts().to_string())

    quotas = allocate_quotas(df, TARGET_PER_PERIOD, TARGET_TOTAL)
    print("\nQuotas:")
    for p, q in quotas.items():
        print(f"  {p}: {q}")

    parts = []
    for period, q in quotas.items():
        subset = df[df["period"] == period]
        picked = diverse_pick(subset, q, seed=SEED + (hash(period) % 1000))
        parts.append(picked)
        print(f"  picked {len(picked):>3} from {period}  "
              f"works={picked['file_id'].nunique()}  "
              f"criteria={picked['criteria'].map(first_criterion).nunique()}")

    sample = pd.concat(parts, ignore_index=True)
    sample = sample.sample(frac=1, random_state=SEED).reset_index(drop=True)

    print(f"\nFinal sample: {len(sample)} rules / "
          f"{sample['file_id'].nunique()} works / "
          f"{sample['perseus_author'].nunique()} authors")

    # Raw (native V20 schema) for inspection.
    RAW_TSV.parent.mkdir(parents=True, exist_ok=True)
    sample.to_csv(RAW_TSV, sep="\t", index=False)
    print(f"Wrote raw TSV  : {RAW_TSV.relative_to(REPO)}")

    # Explorer-app schema CSV.
    app_rows = [row_to_app_csv(r) for _, r in sample.iterrows()]
    APP_CSV.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(app_rows, columns=APP_HEADERS).to_csv(APP_CSV, index=False)
    print(f"Wrote app CSV  : {APP_CSV.relative_to(REPO)}")

    print("\nNext steps:")
    print("  cd 'exploring interface/explorer-app'")
    print("  npm install   # if not already done")
    print("  npm run dev   # starts Vite + /api/save_annotations middleware")


if __name__ == "__main__":
    main()
