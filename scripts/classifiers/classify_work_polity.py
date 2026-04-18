"""
Rule-level polity + time-reference + date classifier (V2).

Prompt is loaded from ``prompt/prompt_polity_time_V2.md`` so it can be tuned
without touching code. V2 revises the original (V1) after manual annotation:

- dropped the ``timeless`` and ``future`` categories
  (every rule is contemporary to its author unless it describes an earlier
  historical society; a stated prophecy is contemporary to its stating)
- dropped ``Generic / abstract (no specific polity)`` — default polity is the
  author's polity
- added ``rule_date``: a year or narrow year-range documenting when the rule
  was in force

For each rule in ``rules_classified_v19_full.tsv`` whose ``file_id`` belongs
to the 318-work sample in ``final_dataset_for_criteria.tsv``, annotate:

- ``rule_polity``           specific polity the rule documents (see V2 prompt)
- ``rule_polity_reasoning`` one short sentence (<=250 chars)
- ``rule_time_reference``   exactly one of {contemporary, past, mixed}
- ``rule_date``             a year or narrow year-range (negative = BCE)
- ``rule_time_reasoning``   one short sentence (<=250 chars)

OpenRouter + ``google/gemini-2.5-flash``, batched via a thread pool. Cached to
``data/llm_results/rules_polity_time_mapping_v2.json`` keyed by ``rule_uid``
so re-runs only classify new rules. Writes the exploration table to
``data/processed_data/rules_full_dataset.tsv``.
"""

import json
import os
import pathlib
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from tqdm import tqdm

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
RULES_TSV = REPO_ROOT / "data" / "llm_results" / "rules_classified_v19_full.tsv"
FINAL_TSV = REPO_ROOT / "data" / "processed_data" / "final_dataset_for_criteria.tsv"
AUTHORS_TSV = REPO_ROOT / "data" / "processed_data" / "perseus_authors_cleaned.tsv"
MAP_JSON = REPO_ROOT / "data" / "llm_results" / "rules_polity_time_mapping_v2.json"
OUT_TSV = REPO_ROOT / "data" / "processed_data" / "rules_full_dataset.tsv"
PROMPT_MD = HERE / "prompt" / "prompt_polity_time_V2.md"

MAX_WORKERS = 15
BATCH_SIZE = 15

VALID_TIME = {"contemporary", "past", "mixed"}

SYSTEM_PROMPT = PROMPT_MD.read_text() + (
    "\n\nReturn ONLY valid JSON — a list of objects, one per input item "
    "(or an object wrapping the list under \"results\"). Each object MUST "
    "include the integer index \"i\" from the input, plus the fields "
    "\"rule_polity\", \"rule_polity_reasoning\", \"rule_time_reference\" "
    "(one of \"contemporary\", \"past\", \"mixed\"), \"rule_date\" "
    "(a year, a year range \"start to end\", \"start|end\", or the string "
    "\"mythological\"), and \"rule_time_reasoning\"."
)


def _s(v, limit=None):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    if not s or s.lower() == "nan":
        return None
    if limit:
        s = s[:limit]
    return s


def build_item(row):
    floruit = row.get("impact_year")
    if pd.notna(floruit):
        try:
            floruit = int(floruit)
        except (TypeError, ValueError):
            floruit = None
    else:
        floruit = None
    return {
        "i": row["_i"],
        "author": _s(row.get("author")),
        "author_floruit_year": floruit,
        "author_polity": _s(row.get("cliopatria_polity")),
        "author_description": _s(row.get("description"), 250),
        "work_title": _s(row.get("work_title")) or _s(row.get("perseus_title")),
        "work_genre": _s(row.get("genre")) or _s(row.get("form_of_creative_work")),
        "rule": _s(row.get("rule")),
        "criteria": _s(row.get("criteria")),
        "group": _s(row.get("group")),
        "resource": _s(row.get("resource")),
        "verbatim": _s(row.get("verbatim"), 600),
    }


def parse_results(text):
    parsed = json.loads(text)
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        for key in ("results", "classifications", "items", "rules"):
            if isinstance(parsed.get(key), list):
                return parsed[key]
        for v in parsed.values():
            if isinstance(v, list):
                return v
    raise RuntimeError(f"Unexpected response shape: {text[:400]}")


def classify_batch(client, batch):
    user_msg = (
        "Classify the following rules (return one object per input item):\n"
        + json.dumps(batch, ensure_ascii=False)
    )
    resp = client.chat.completions.create(
        model="google/gemini-2.5-flash",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    text = resp.choices[0].message.content.strip()
    results = parse_results(text)

    out = {}
    for it in results:
        try:
            i = int(it["i"])
        except (KeyError, TypeError, ValueError):
            continue
        tref = str(it.get("rule_time_reference", "")).strip().lower()
        if tref not in VALID_TIME:
            tref = "contemporary"
        # rule_date may come in as int, float, or string (e.g. "-350", "-350 to -340",
        # "-40|+40", "mythological"). Store as a trimmed string.
        raw_date = it.get("rule_date")
        if raw_date is None:
            rule_date = ""
        else:
            rule_date = str(raw_date).strip()
        out[i] = {
            "rule_polity": _s(it.get("rule_polity"), 200) or "",
            "rule_polity_reasoning": _s(it.get("rule_polity_reasoning"), 300) or "",
            "rule_time_reference": tref,
            "rule_date": rule_date[:80],
            "rule_time_reasoning": _s(it.get("rule_time_reasoning"), 300) or "",
        }
    return out


def main():
    load_dotenv(REPO_ROOT / ".env")
    api_key = os.getenv("OPEN_ROUTER_API")
    if not api_key:
        raise RuntimeError(f"OPEN_ROUTER_API not set in .env at {REPO_ROOT / '.env'}")
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

    rules = pd.read_csv(RULES_TSV, sep="\t")
    final = pd.read_csv(FINAL_TSV, sep="\t")
    keep_ids = set(final["file_id"].tolist())
    rules = rules[rules["file_id"].isin(keep_ids)].reset_index(drop=True)
    print(
        f"Rules scoped to the {len(keep_ids)} filtered works: "
        f"{len(rules):,} rules / {rules['file_id'].nunique()} files / "
        f"{rules['author'].nunique()} authors"
    )

    # Attach author metadata (polity / description / occupations / wikidata).
    authors = pd.read_csv(AUTHORS_TSV, sep="\t")[
        [
            "perseus_author",
            "cliopatria_polity",
            "description",
            "occupations",
            "wikidata_id",
            "wikidata_name",
            "birthdate",
            "deathdate",
            "impact_date",
            "impact_date_precision",
        ]
    ].drop_duplicates("perseus_author")
    rules = rules.merge(
        authors, left_on="author", right_on="perseus_author", how="left"
    )

    # Attach per-work metadata from the final 318-work sample so each rule row
    # is self-contained: title / genre / period / language / size.
    work_meta_cols = [
        "file_id",
        "perseus_id",
        "perseus_title",
        "wikidata_work_id",
        "wikidata_work_label",
        "period",
        "genre",
        "form_of_creative_work",
        "instance_of",
        "factuality",
        "main_language",
        "editors",
        "pub_date",
        "n_words",
        "n_characters",
        "n_pages",
    ]
    work_meta_cols = [c for c in work_meta_cols if c in final.columns]
    rules = rules.merge(
        final[work_meta_cols].drop_duplicates("file_id"),
        on="file_id",
        how="left",
        suffixes=("", "_work"),
    )

    cache = {}
    if MAP_JSON.exists():
        try:
            cache = json.loads(MAP_JSON.read_text())
            print(f"Loaded {len(cache):,} cached classifications")
        except Exception:
            cache = {}

    todo = rules[~rules["rule_uid"].isin(cache)].reset_index(drop=True)
    print(f"Rules to classify: {len(todo):,} / {len(rules):,}")

    if len(todo):
        items = []
        for i, row in todo.iterrows():
            d = row.to_dict()
            d["_i"] = i
            items.append(build_item(d))
        batches = [items[s : s + BATCH_SIZE] for s in range(0, len(items), BATCH_SIZE)]
        idx_to_uid = dict(zip(todo.index.tolist(), todo["rule_uid"].tolist()))

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {pool.submit(classify_batch, client, b): b for b in batches}
            for fut in tqdm(
                as_completed(futures), total=len(batches), desc="Classifying rules"
            ):
                try:
                    res = fut.result()
                except Exception as e:
                    print(f"Batch failed: {e}")
                    continue
                for i, v in res.items():
                    uid = idx_to_uid.get(i)
                    if uid is not None:
                        cache[uid] = v

        MAP_JSON.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
        print(f"Saved {len(cache):,} classifications to {MAP_JSON}")

    def pick(uid, key):
        entry = cache.get(uid)
        return entry.get(key) if isinstance(entry, dict) else None

    for col in (
        "rule_polity",
        "rule_polity_reasoning",
        "rule_time_reference",
        "rule_date",
        "rule_time_reasoning",
    ):
        rules[col] = rules["rule_uid"].map(lambda u, c=col: pick(u, c))

    # Reorder columns for exploration: identity -> rule -> polity/time ->
    # author metadata -> work metadata -> V19 classifier outputs.
    preferred = [
        # identity
        "rule_uid",
        "file_id",
        "perseus_id",
        # rule content
        "criteria",
        "rule",
        "group",
        "resource",
        "directionality",
        "verbatim",
        "reasoning",
        "confidence",
        # new polity + time + date annotations (the point of this script)
        "rule_polity",
        "rule_polity_reasoning",
        "rule_time_reference",
        "rule_date",
        "rule_time_reasoning",
        # existing rule-level classifier outputs
        "contemporary",
        "factuality",
        "factuality_work",
        "is_historical",
        "group_specificity",
        "group_immutability",
        "immutability_reasoning",
        "resource_materiality",
        "materiality_reasoning",
        "resource_generality",
        "resource_generality_reasoning",
        "resource_persistence",
        "persistence_reasoning",
        "tautological",
        "tautology_reasoning",
        "secondary_reasoning",
        # author metadata
        "author",
        "wikidata_id",
        "wikidata_name",
        "cliopatria_polity",
        "impact_year",
        "impact_date",
        "impact_date_precision",
        "birthdate",
        "deathdate",
        "occupations",
        "description",
        # work metadata
        "work_title",
        "perseus_title",
        "wikidata_work_id",
        "wikidata_work_label",
        "period",
        "genre",
        "form_of_creative_work",
        "instance_of",
        "main_language",
        "editors",
        "pub_date",
        "n_words",
        "n_characters",
        "n_pages",
    ]
    ordered = [c for c in preferred if c in rules.columns]
    extras = [c for c in rules.columns if c not in ordered and c != "perseus_author"]
    rules = rules[ordered + extras]

    OUT_TSV.parent.mkdir(parents=True, exist_ok=True)
    rules.to_csv(OUT_TSV, sep="\t", index=False)
    print(
        f"Wrote exploration-ready dataset ({len(rules):,} rows x "
        f"{len(rules.columns)} cols) to {OUT_TSV}"
    )

    n_missing = int(rules["rule_polity"].isna().sum())
    print(f"\nSummary:  classified={len(rules) - n_missing:,}  missing={n_missing:,}")

    print("\nTime-reference distribution:")
    print(rules["rule_time_reference"].value_counts(dropna=False).to_string())

    print("\nTop 20 polities:")
    print(rules["rule_polity"].value_counts(dropna=False).head(20).to_string())

    print("\nTop 20 rule_date values:")
    print(rules["rule_date"].value_counts(dropna=False).head(20).to_string())

    print("\nPer-author time-reference share:")
    print(
        rules.groupby("author")["rule_time_reference"]
        .value_counts(normalize=True)
        .unstack(fill_value=0)
        .round(2)
        .to_string()
    )


if __name__ == "__main__":
    main()
