"""
Secondary classifier for V19 rules.

For every rule in data/rules_classified_v19.tsv (built by build_sample_v19.py),
call Gemini with prompt_V19_secondary.md and obtain:
- group_specificity (int 1-5)
- is_historical     (int 0 or 1)
- reasoning         (short string)

Outputs:
- data/secondary_mapping_v19.json    cache keyed by rule_uid
- data/rules_classified_v19_secondary.tsv  same rules table + 3 new columns

Re-runs only classify rule_uids not yet in the cache.
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
RULES_TSV = HERE / "data/rules_classified_v19.tsv"
META_TSV = HERE / "data/processed_data/perseus_works_wikidata.tsv"
PROMPT_FILE = HERE / "prompt/prompt_V19_secondary.md"
MAP_JSON = HERE / "data/secondary_mapping_v19.json"
OUT_TSV = HERE / "data/rules_classified_v19_secondary.tsv"

MODEL = "google/gemini-2.5-flash"
MAX_WORKERS = 20
BATCH_SIZE = 25


def load_client() -> OpenAI:
    load_dotenv(REPO_ROOT / ".env")
    key = os.getenv("OPEN_ROUTER_API")
    if not key:
        raise RuntimeError("OPEN_ROUTER_API not set in .env")
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)


def truncate(s, n=500):
    if s is None:
        return ""
    s = str(s)
    return s[:n]


def build_item(i: int, row: dict) -> dict:
    return {
        "i": i,
        "author": row.get("author") or "",
        "impact_year": (
            int(row["impact_year"]) if pd.notna(row.get("impact_year")) else None
        ),
        "work_title": row.get("work_title") or "",
        "criteria": row.get("criteria") or "",
        "group": row.get("group") or "",
        "resource": row.get("resource") or "",
        "rule": row.get("rule") or "",
        "verbatim": truncate(row.get("verbatim"), 500),
        "reasoning": truncate(row.get("reasoning"), 300),
    }


def classify_batch(client: OpenAI, system_prompt: str, batch: list[dict]) -> dict:
    user_msg = (
        "Classify each rule. Return a JSON list, one object per input item.\n"
        + json.dumps(batch, ensure_ascii=False)
    )
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    raw = (resp.choices[0].message.content or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
    parsed = json.loads(raw)

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
        raise RuntimeError(f"Unexpected response shape: {raw[:400]}")

    out = {}
    for item in results:
        i = item.get("i")
        gs = item.get("group_specificity")
        ih = item.get("is_historical")
        reason = item.get("reasoning", "")
        try:
            gs = int(gs) if gs is not None else None
        except Exception:
            gs = None
        try:
            ih = int(ih) if ih is not None else None
        except Exception:
            ih = None
        out[i] = {"group_specificity": gs, "is_historical": ih, "reasoning": reason}
    return out


def build_author_map() -> dict:
    meta = pd.read_csv(META_TSV, sep="\t")
    return {
        row["file_id"]: {
            "author": row.get("perseus_author"),
            "work_title": row.get("wikidata_work_label") or row.get("perseus_title"),
            "impact_year": row.get("author_impact_date"),
        }
        for _, row in meta.iterrows()
    }


def main():
    system_prompt = PROMPT_FILE.read_text()
    rules = pd.read_csv(RULES_TSV, sep="\t")
    author_map = build_author_map()

    rules["author"] = rules["file_id"].map(
        lambda f: author_map.get(f, {}).get("author")
    )
    rules["work_title"] = rules["file_id"].map(
        lambda f: author_map.get(f, {}).get("work_title")
    )
    rules["impact_year"] = pd.to_numeric(
        rules["file_id"].map(lambda f: author_map.get(f, {}).get("impact_year")),
        errors="coerce",
    )

    cache = {}
    if MAP_JSON.exists():
        try:
            cache = json.loads(MAP_JSON.read_text())
            print(f"Cache: {len(cache)} rules already classified")
        except Exception:
            pass

    todo_rows = [row for _, row in rules.iterrows() if row["rule_uid"] not in cache]
    print(f"New rules to classify: {len(todo_rows):,} / {len(rules):,}")

    if todo_rows:
        client = load_client()
        batches = [
            todo_rows[i : i + BATCH_SIZE] for i in range(0, len(todo_rows), BATCH_SIZE)
        ]

        def run_batch(batch_rows):
            payload = [build_item(i, r.to_dict()) for i, r in enumerate(batch_rows)]
            try:
                res = classify_batch(client, system_prompt, payload)
            except Exception as e:
                return {"error": str(e), "rows": batch_rows}
            return {"rows": batch_rows, "results": res}

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futs = [ex.submit(run_batch, b) for b in batches]
            for fut in tqdm(as_completed(futs), total=len(futs), desc="Secondary"):
                out = fut.result()
                if "error" in out:
                    print(f"Batch failed: {out['error']}")
                    continue
                for i, row in enumerate(out["rows"]):
                    r = out["results"].get(i)
                    if r is None:
                        continue
                    cache[row["rule_uid"]] = r
                MAP_JSON.write_text(json.dumps(cache, ensure_ascii=False, indent=2))

    rules["group_specificity"] = rules["rule_uid"].map(
        lambda u: (cache.get(u) or {}).get("group_specificity")
    )
    rules["is_historical"] = rules["rule_uid"].map(
        lambda u: (cache.get(u) or {}).get("is_historical")
    )
    rules["secondary_reasoning"] = rules["rule_uid"].map(
        lambda u: (cache.get(u) or {}).get("reasoning", "")
    )

    rules.to_csv(OUT_TSV, sep="\t", index=False)
    print(f"\nWrote {len(rules):,} rules → {OUT_TSV}")

    print("\nGroup specificity distribution:")
    print(rules["group_specificity"].value_counts(dropna=False).sort_index().to_string())
    print("\nis_historical distribution:")
    print(rules["is_historical"].value_counts(dropna=False).sort_index().to_string())


if __name__ == "__main__":
    main()
