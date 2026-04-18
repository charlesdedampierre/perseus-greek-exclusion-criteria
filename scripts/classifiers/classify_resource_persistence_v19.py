"""
Resource-persistence classifier for V19 rules.

For every rule in data/rules_classified_v19_full.tsv, call Gemini with
prompt_V19_resource_persistence.md and obtain:
- resource_persistence (int 1-5)
- persistence_reasoning (short string)

Outputs:
- data/resource_persistence_mapping_v19.json    cache keyed by rule_uid
- data/rules_classified_v19_full.tsv            OVERWRITES with the new column.
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
IN_TSV = HERE / "data/rules_classified_v19_full.tsv"
PROMPT_FILE = HERE / "prompt/prompt_V19_resource_persistence.md"
MAP_JSON = HERE / "data/resource_persistence_mapping_v19.json"
OUT_TSV = IN_TSV  # overwrite

MODEL = "google/gemini-2.5-flash"
MAX_WORKERS = 20
BATCH_SIZE = 25


def load_client() -> OpenAI:
    load_dotenv(REPO_ROOT / ".env")
    key = os.getenv("OPEN_ROUTER_API")
    if not key:
        raise RuntimeError("OPEN_ROUTER_API not set in .env")
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)


def truncate(s, n=400):
    if s is None:
        return ""
    s = str(s)
    return s[:n]


def build_item(i: int, row: dict) -> dict:
    return {
        "i": i,
        "group": row.get("group") or "",
        "resource": row.get("resource") or "",
        "rule": row.get("rule") or "",
        "verbatim": truncate(row.get("verbatim"), 400),
        "reasoning": truncate(row.get("reasoning"), 250),
    }


def classify_batch(client: OpenAI, system_prompt: str, batch: list[dict]) -> dict:
    user_msg = (
        "Rate resource persistence for each input rule. Return a JSON list.\n"
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
        m = item.get("resource_persistence")
        reason = item.get("persistence_reasoning", "")
        try:
            m = int(m) if m is not None else None
        except Exception:
            m = None
        out[i] = {"resource_persistence": m, "persistence_reasoning": reason}
    return out


def main():
    system_prompt = PROMPT_FILE.read_text()
    rules = pd.read_csv(IN_TSV, sep="\t")

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
            for fut in tqdm(as_completed(futs), total=len(futs), desc="Persistence"):
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

    rules["resource_persistence"] = rules["rule_uid"].map(
        lambda u: (cache.get(u) or {}).get("resource_persistence")
    )
    rules["persistence_reasoning"] = rules["rule_uid"].map(
        lambda u: (cache.get(u) or {}).get("persistence_reasoning", "")
    )

    rules.to_csv(OUT_TSV, sep="\t", index=False)
    print(f"\nWrote {len(rules):,} rules → {OUT_TSV}")

    print("\nResource persistence distribution:")
    print(
        rules["resource_persistence"].value_counts(dropna=False).sort_index().to_string()
    )


if __name__ == "__main__":
    main()
