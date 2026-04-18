"""
Classify every rule in rules_classified_v18.tsv as "contemporary" (1) or not (0).

Definition of contemporary: the event / subject-matter the rule describes
happened within ~100 years of the author's impact_date (before or after).

Runs batched Gemini calls in parallel via a thread pool. Progress is cached
to data/contemporary_mapping.json keyed by rule_uid so re-runs only classify
new rules.
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
META_TSV = HERE / "data/processed_data/perseus_works_wikidata.tsv"
MAP_JSON = HERE / "data/contemporary_mapping.json"
SAMPLE_TSV = HERE / "data/sample60_v18.tsv"
EXPLORER_CSV = HERE / "data-exploration/explorer-app/public/data/sample60_v18.csv"

MAX_WORKERS = 20
BATCH_SIZE = 30

SYSTEM_PROMPT = """You decide whether a described social rule is about CONTEMPORARY events of its author.

"Contemporary" = the event/subject of the rule happened within ~100 years of the author's floruit (impact_year). Before or after both count.
"Not contemporary" = the event is from a much earlier era (e.g. Homer describing Homeric Bronze Age myth centuries before his time, a 2nd-century CE author quoting Archaic lawgivers, a Christian father discussing Old Testament figures).

Guidance:
- Anchor on the author's impact_year (the date associated with each item).
- The rule itself (rule_name, reasoning, proof) may reference a specific period, mythological setting, historical figure, or legal code — use those clues.
- Purely abstract / timeless reasoning (e.g. "the elderly recover less from disease") written AS OBSERVATION by the author about their own world counts as contemporary.
- Tragic/epic/mythological content explicitly set in the distant heroic past is NOT contemporary.
- New Testament / apostolic-father content is contemporary to those authors (1st–2nd c. CE).

Return ONLY valid JSON: a list of objects, each {"i": <int>, "is_contemporary": 0 or 1}."""


def build_item(row):
    """Compact rule payload for the LLM."""
    return {
        "i": row["_i"],
        "author": row["author"],
        "impact_year": (
            int(row["impact_year"]) if pd.notna(row["impact_year"]) else None
        ),
        "work_title": row["work_title"],
        "rule_name": row["rule_name"],
        "rule_category": row["rule_category"],
        "reasoning": (row["reasoning"] or "")[:500],
        "proof": (row["proof"] or "")[:500],
    }


def classify_batch(client, batch):
    user_msg = (
        "Classify each rule below as contemporary (1) or not (0):\n"
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
    return {
        int(it.get("i")): 1 if int(it.get("is_contemporary", 0)) == 1 else 0
        for it in results
    }


def main():
    load_dotenv(REPO_ROOT / ".env")
    api_key = os.getenv("OPEN_ROUTER_API")
    if not api_key:
        raise RuntimeError("OPEN_ROUTER_API not set in .env")
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

    # Load rules + attach author / impact_year / work_title via meta sidecar
    rules = pd.read_csv(RULES_TSV, sep="\t")
    meta = pd.read_csv(META_TSV, sep="\t").set_index("file_id")
    sidecar = meta[
        ["perseus_author", "author_impact_date", "wikidata_work_label", "perseus_title"]
    ].to_dict("index")

    def get_sidecar(fid, field):
        s = sidecar.get(fid, {})
        if field == "author":
            return s.get("perseus_author")
        if field == "impact_year":
            v = pd.to_numeric(s.get("author_impact_date"), errors="coerce")
            return v
        if field == "work_title":
            return s.get("wikidata_work_label") or s.get("perseus_title")
        return None

    rules["author"] = rules["file_id"].map(lambda f: get_sidecar(f, "author"))
    rules["impact_year"] = rules["file_id"].map(lambda f: get_sidecar(f, "impact_year"))
    rules["work_title"] = rules["file_id"].map(lambda f: get_sidecar(f, "work_title"))
    rules["proof"] = rules["proof"].fillna("")
    rules["reasoning"] = rules["reasoning"].fillna("")
    rules["rule_category"] = rules["rule_category"].fillna("")

    cache = {}
    if MAP_JSON.exists():
        try:
            cache = {k: int(v) for k, v in json.loads(MAP_JSON.read_text()).items()}
            print(f"Loaded {len(cache):,} cached classifications")
        except Exception:
            pass

    todo = rules[~rules["rule_uid"].isin(cache)].reset_index(drop=True)
    print(f"Rules to classify: {len(todo):,} / {len(rules):,}")
    if len(todo) == 0:
        print("Nothing to do, all cached.")
    else:
        # Build batches
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
                    if uid is not None:
                        cache[uid] = v

        MAP_JSON.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
        print(f"\nSaved {len(cache):,} classifications to {MAP_JSON}")

    # Join back
    rules_out = pd.read_csv(RULES_TSV, sep="\t")
    rules_out["is_contemporary"] = rules_out["rule_uid"].map(cache).astype("Int64")
    rules_out.to_csv(RULES_TSV, sep="\t", index=False)
    print(f"\nWrote {len(rules_out):,} rules to {RULES_TSV}")

    n1 = int((rules_out["is_contemporary"] == 1).sum())
    n0 = int((rules_out["is_contemporary"] == 0).sum())
    n_missing = int(rules_out["is_contemporary"].isna().sum())
    print(f"  contemporary=1 : {n1:,} ({n1/len(rules_out)*100:.1f}%)")
    print(f"  contemporary=0 : {n0:,} ({n0/len(rules_out)*100:.1f}%)")
    print(f"  unclassified   : {n_missing:,}")

    # Per-author contemporary rate
    print("\nTop 15 authors by rule count, with % contemporary:")
    per_author = (
        rules_out.merge(rules[["rule_uid", "author"]], on="rule_uid")
        .groupby("author")["is_contemporary"]
        .agg(["count", "mean"])
        .sort_values("count", ascending=False)
        .head(15)
    )
    for a, r in per_author.iterrows():
        print(f"  {a:<28}  n={int(r['count']):>4}  contemporary={r['mean']*100:>5.1f}%")

    # Update the sample + explorer CSV
    if SAMPLE_TSV.exists():
        s = pd.read_csv(SAMPLE_TSV, sep="\t")
        s["is_contemporary"] = s["rule_uid"].map(cache).astype("Int64")
        s.to_csv(SAMPLE_TSV, sep="\t", index=False)
        print(f"\nUpdated {SAMPLE_TSV}")

    if EXPLORER_CSV.exists():
        e = pd.read_csv(EXPLORER_CSV)
        e["is_contemporary"] = e["rule_uid"].map(cache).astype("Int64")
        e.to_csv(EXPLORER_CSV, index=False)
        print(f"Updated {EXPLORER_CSV}")


if __name__ == "__main__":
    main()
