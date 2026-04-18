"""
Classify every rule's verbatim as a generic fact, a pure opinion, or mixed.

Definitions:
- fact: a factual / empirical / descriptive claim about the world, or a legal
  or procedural rule stated as established practice. E.g. "Old persons do
  not readily recover from phthisis", "Citizens must be aged 18 or over",
  "Plague spread among youths in the gymnasium".
- opinion: a normative / evaluative / rhetorical stance taken by the author
  or speaker. Moral judgements ("it is shameful that..."), exhortations,
  praise/blame, prescriptions that express the author's view rather than an
  observed fact. E.g. "women should stay home", "the unjust deserve death",
  "the Spartans are the bravest of the Greeks".
- mixed: the verbatim contains both a factual statement AND an evaluative
  stance that can't be cleanly separated.

Runs batched Gemini calls in parallel via a thread pool. Progress is cached
to data/fact_opinion_mapping.json keyed by rule_uid.
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
REPO_ROOT = HERE.parent
RULES_TSV = HERE / "data/rules_classified_v18.tsv"
MAP_JSON = HERE / "data/fact_opinion_mapping.json"
SAMPLE_TSV = HERE / "data/sample60_v18.tsv"
EXPLORER_CSV = HERE / "data-exploration/explorer-app/public/data/sample60_v18.csv"

MAX_WORKERS = 20
BATCH_SIZE = 30

LABELS = {"fact", "opinion", "mixed"}

SYSTEM_PROMPT = """You classify each verbatim passage from Ancient Greek literature as one of:
- "fact": a descriptive, empirical, legal, or procedural claim. Stated practice, observed regularity, or established rule. Not overtly evaluative.
- "opinion": a normative, evaluative, or rhetorical stance — praise, blame, exhortation, moral judgement, prescription expressing the author's / speaker's view.
- "mixed": the passage interleaves factual description AND explicit evaluation in a way that cannot be cleanly separated.

Guidance:
- Anchor on the verbatim itself, using the rule_name and reasoning only as context.
- A stated law (e.g. "citizens must be 18") is "fact".
- Medical observations (e.g. "old persons do not readily recover from phthisis") are "fact".
- Tragic or oratorical passages praising/blaming a group ("women are weak-minded", "the just man is truly happy") are "opinion".
- Ritual prescriptions stated as observed practice ("priests must be chaste") are "fact"; ritual prescriptions with strong moral framing ("none but the pure deserve to sacrifice") are "opinion".
- When in genuine doubt between fact and opinion, choose "mixed".

Respond ONLY with valid JSON: a list of objects, each {"i": <int>, "verbatim_type": "fact" | "opinion" | "mixed"}."""


def build_item(row):
    return {
        "i": row["_i"],
        "rule_name": row["rule_name"],
        "reasoning": (row["reasoning"] or "")[:400],
        "verbatim": (row["proof"] or "")[:700],
    }


def classify_batch(client, batch):
    user_msg = (
        "Classify each verbatim below as fact, opinion, or mixed:\n"
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
    parsed = json.loads(text)
    if isinstance(parsed, list):
        results = parsed
    elif isinstance(parsed, dict):
        results = (
            parsed.get("results")
            or parsed.get("classifications")
            or parsed.get("items")
            or next((v for v in parsed.values() if isinstance(v, list)), None)
        )
    else:
        results = None
    if not isinstance(results, list):
        raise RuntimeError(f"Unexpected response shape: {text[:400]}")
    out = {}
    for it in results:
        try:
            i = int(it.get("i"))
        except (TypeError, ValueError):
            continue
        v = (it.get("verbatim_type") or "").strip().lower()
        out[i] = v if v in LABELS else None
    return out


def main():
    load_dotenv(REPO_ROOT / ".env")
    api_key = os.getenv("OPEN_ROUTER_API")
    if not api_key:
        raise RuntimeError("OPEN_ROUTER_API not set in .env")
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

    rules = pd.read_csv(RULES_TSV, sep="\t")
    rules["proof"] = rules["proof"].fillna("")
    rules["reasoning"] = rules["reasoning"].fillna("")
    rules["rule_name"] = rules["rule_name"].fillna("")

    cache = {}
    if MAP_JSON.exists():
        try:
            cache = {
                k: v for k, v in json.loads(MAP_JSON.read_text()).items() if v in LABELS
            }
            print(f"Loaded {len(cache):,} cached classifications")
        except Exception:
            pass

    todo = rules[~rules["rule_uid"].isin(cache)].reset_index(drop=True)
    print(f"Rules to classify: {len(todo):,} / {len(rules):,}")

    if len(todo) > 0:
        items = []
        for i, row in todo.iterrows():
            row = row.to_dict()
            row["_i"] = i
            items.append(build_item(row))
        batches = [items[s : s + BATCH_SIZE] for s in range(0, len(items), BATCH_SIZE)]
        idx_to_uid = dict(zip(todo.index.tolist(), todo["rule_uid"].tolist()))

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {pool.submit(classify_batch, client, b): b for b in batches}
            for fut in tqdm(
                as_completed(futures), total=len(batches), desc="Classifying"
            ):
                try:
                    res = fut.result()
                except Exception as e:
                    print(f"Batch failed: {e}")
                    continue
                for i, v in res.items():
                    uid = idx_to_uid.get(i)
                    if uid is not None and v is not None:
                        cache[uid] = v

        MAP_JSON.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
        print(f"\nSaved {len(cache):,} classifications to {MAP_JSON}")

    # Join back
    rules_out = pd.read_csv(RULES_TSV, sep="\t")
    rules_out["verbatim_type"] = rules_out["rule_uid"].map(cache)
    rules_out.to_csv(RULES_TSV, sep="\t", index=False)
    print(f"\nWrote {len(rules_out):,} rules to {RULES_TSV}")

    counts = rules_out["verbatim_type"].fillna("(none)").value_counts()
    print("Verbatim-type distribution:")
    for k, v in counts.items():
        print(f"  {k:<10}  {v:>5,}  ({v/len(rules_out)*100:.1f}%)")

    if SAMPLE_TSV.exists():
        s = pd.read_csv(SAMPLE_TSV, sep="\t")
        s["verbatim_type"] = s["rule_uid"].map(cache)
        s.to_csv(SAMPLE_TSV, sep="\t", index=False)
        print(f"\nUpdated {SAMPLE_TSV}")

    if EXPLORER_CSV.exists():
        e = pd.read_csv(EXPLORER_CSV)
        e["verbatim_type"] = e["rule_uid"].map(cache)
        e.to_csv(EXPLORER_CSV, index=False)
        print(f"Updated {EXPLORER_CSV}")


if __name__ == "__main__":
    main()
