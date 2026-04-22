"""Round-4 annotation sample: 60 rules from the random-100 corpus.

Applies the strict filter
  `mat >= 3 AND gen >= 3 AND imm >= 2 AND fact >= 4`
(= the round-2-derived filter, minus the `tautological==0` guard which
round-3 showed adds little) to the 946-rule random-100 output, excludes
any rule_uids already annotated in prior rounds, and picks 60 rules
stratified per period with round-robin over (file_id, first-criterion).

Adds work-level polity/time priors so the Rule-setting and Work-setting
rows show up in the annotator.

Reads:
  - data/processed_data/rules_random100_with_polity_time.tsv
  - data/annotation/user_comments_sample60_v20.csv         (round 1)
  - data/annotation/user_comments_sample60_v20_round2.csv  (round 2)
  - data/annotation/user_comments_sample30_v20_round3.csv  (round 3)
  - data/processed_data/final_dataset_for_criteria.tsv     (for `year`)

Writes:
  - exploring interface/explorer-app/public/data/sample60_v20_round4.csv
  - data/annotation/sample60_v20_round4_raw.tsv
"""

from __future__ import annotations

import ast
import json
import pathlib
import random

import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
SRC = REPO / "data/processed_data/rules_random100_with_polity_time.tsv"
META = REPO / "data/processed_data/final_dataset_for_criteria.tsv"
PRIOR_ANNOTATIONS = [
    REPO / "data/annotation/user_comments_sample60_v20.csv",
    REPO / "data/annotation/user_comments_sample60_v20_round2.csv",
    REPO / "data/annotation/user_comments_sample30_v20_round3.csv",
]
APP_CSV = REPO / "exploring interface/explorer-app/public/data/sample60_v20_round4.csv"
RAW_TSV = REPO / "data/annotation/sample60_v20_round4_raw.tsv"

TARGET_TOTAL = 60
TARGET_PER_PERIOD = 15
SEED = 45

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
    # Rule- and work-level polity/time
    "rule_polity", "rule_polity_reasoning", "rule_date", "rule_time_reasoning",
    "work_author_polity_cliopatria", "work_polity", "work_polity_reasoning",
    "work_time_reference", "work_time_start", "work_time_end", "work_time_reasoning",
]


def parse_list_field(value) -> list[str]:
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
    if len(pool) <= n:
        return pool.sample(frac=1, random_state=seed).reset_index(drop=True)
    rng = random.Random(seed)
    pool = pool.copy()
    pool["_first_crit"] = pool["criteria"].map(first_criterion)
    remaining = pool.index.tolist()
    rng.shuffle(remaining)
    picked, used_pairs, used_crits = [], set(), set()
    for idx in remaining:
        if len(picked) >= n: break
        f = pool.at[idx, "file_id"]; c = pool.at[idx, "_first_crit"]
        if (f, c) in used_pairs: continue
        picked.append(idx); used_pairs.add((f, c)); used_crits.add(c)
    for idx in remaining:
        if len(picked) >= n: break
        if idx in picked: continue
        if pool.at[idx, "_first_crit"] not in used_crits:
            picked.append(idx); used_crits.add(pool.at[idx, "_first_crit"])
    for idx in remaining:
        if len(picked) >= n: break
        if idx not in picked: picked.append(idx)
    return pool.loc[picked].drop(columns="_first_crit").reset_index(drop=True)


def allocate_quotas(df: pd.DataFrame, per_period: int, total: int) -> dict:
    counts = df["period"].value_counts(dropna=False).to_dict()
    periods = list(counts.keys())
    quota = {p: min(per_period, counts[p]) for p in periods}
    shortfall = total - sum(quota.values())
    while shortfall > 0:
        has_spare = [p for p in periods if counts[p] > quota[p]]
        if not has_spare: break
        p = max(has_spare, key=lambda p: counts[p] - quota[p])
        quota[p] += 1; shortfall -= 1
    overshoot = sum(quota.values()) - total
    while overshoot > 0:
        p = max(periods, key=lambda p: quota[p])
        quota[p] -= 1; overshoot -= 1
    return quota


def derive_verbatim_type(opinion_vs_fact) -> str:
    try:
        v = int(float(opinion_vs_fact))
    except (ValueError, TypeError):
        return ""
    if v >= 4: return "fact"
    if v == 3: return "mixed"
    if v >= 1: return "opinion"
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
        "sampled_for": "gemini_v20_sample60_round4",
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
        "extraction_method": "gemini_v20_core_v1_random100",
        "extraction_cost_usd": "",
        "prompt_tokens": "",
        "completion_tokens": "",
        "rule_polity": row.get("rule_polity"),
        "rule_polity_reasoning": row.get("rule_polity_reasoning"),
        "rule_date": row.get("rule_date"),
        "rule_time_reasoning": row.get("rule_time_reasoning"),
        "work_author_polity_cliopatria": row.get("work_author_polity_cliopatria"),
        "work_polity": row.get("work_polity"),
        "work_polity_reasoning": row.get("work_polity_reasoning"),
        "work_time_reference": row.get("work_time_reference"),
        "work_time_start": row.get("work_time_start"),
        "work_time_end": row.get("work_time_end"),
        "work_time_reasoning": row.get("work_time_reasoning"),
    }


def main() -> None:
    df = pd.read_csv(SRC, sep="\t")
    df = df[df["resource_materiality"].notna()].copy()

    meta = pd.read_csv(META, sep="\t")[["file_id", "year", "genre"]]
    df = df.merge(meta, on="file_id", how="left")
    print(f"Loaded {len(df):,} rules from random-100 corpus")

    # Exclude previously annotated rule_uids
    prior = set()
    for p in PRIOR_ANNOTATIONS:
        if p.exists():
            a = pd.read_csv(p)
            a = a[a["rule_uid"].notna() & a["rule_uid"].astype(str).str.startswith("tlg")]
            prior.update(a["rule_uid"].tolist())
    print(f"Prior annotations to exclude: {len(prior)}")

    mask = (
        (df["resource_materiality"] >= 3)
        & (df["resource_generality"] >= 3)
        & (df["group_immutability"] >= 2)
        & (df["opinion_vs_fact"] >= 4)
    )
    pool = df[mask & ~df["rule_uid"].isin(prior)].copy()
    print(f"Strict-filter pool: {len(pool)} / {len(df)} rules")
    print("\nPool per period:")
    print(pool["period"].value_counts(dropna=False).to_string())

    quotas = allocate_quotas(pool, TARGET_PER_PERIOD, TARGET_TOTAL)
    print("\nQuotas:")
    for p, q in quotas.items():
        print(f"  {p}: {q}")

    parts = []
    for period, q in quotas.items():
        subset = pool[pool["period"] == period] if pd.notna(period) \
            else pool[pool["period"].isna()]
        picked = diverse_pick(subset, q, seed=SEED + (hash(str(period)) % 1000))
        parts.append(picked)
        print(f"  picked {len(picked):>3} from {period}  "
              f"works={picked['file_id'].nunique()}  "
              f"criteria={picked['criteria'].map(first_criterion).nunique()}")

    sample = pd.concat(parts, ignore_index=True)
    sample = sample.sample(frac=1, random_state=SEED).reset_index(drop=True)
    assert len(sample) == TARGET_TOTAL, f"wanted {TARGET_TOTAL}, got {len(sample)}"
    assert not (set(sample["rule_uid"]) & prior), "overlap with prior rounds!"

    print(f"\nFinal sample: {len(sample)} rules / "
          f"{sample['file_id'].nunique()} works / "
          f"{sample['perseus_author'].nunique()} authors")

    RAW_TSV.parent.mkdir(parents=True, exist_ok=True)
    sample.to_csv(RAW_TSV, sep="\t", index=False)
    print(f"Wrote raw TSV : {RAW_TSV.relative_to(REPO)}")

    app_rows = [row_to_app_csv(r) for _, r in sample.iterrows()]
    APP_CSV.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(app_rows, columns=APP_HEADERS).to_csv(APP_CSV, index=False)
    print(f"Wrote app CSV : {APP_CSV.relative_to(REPO)}")


if __name__ == "__main__":
    main()
