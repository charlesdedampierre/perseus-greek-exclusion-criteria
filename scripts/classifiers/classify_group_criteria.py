"""Re-encode every (group, rule_polity) pair along rights-INDEPENDENT criteria.

Operationalises the criterion-prior-to-rights workflow:

    1. Read unique (group, rule_polity) pairs from the rules dataset.
    2. For each pair, ask the LLM (via OpenRouter) to produce a criterion
       vector — sex, age, ownership_status, ancestry, residence, wealth,
       kinship_role, occupation — using ONLY the group label + polity +
       period as input. The rule's resource and verbatim are deliberately
       withheld so rights cannot leak into the criteria.
    3. Persist per-batch cache, merge into a single TSV, and write a run log.

Reads
-----
  - data/rules_dataset_april_2026.tsv         (source rules)
  - scripts/classifiers/prompt/prompt_group_criteria.md

Writes
------
  - data/clean/classifications/group_criteria/_batch_NNNN.json  per-batch cache
  - data/clean/classifications/group_criteria/_run_log.json     run summary
  - data/clean/final/group_criterion_vectors.tsv                merged TSV
"""
from __future__ import annotations

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[2]

SRC = ROOT / "data/rules_dataset_april_2026.tsv"
PROMPT_FILE = ROOT / "scripts/classifiers/prompt/prompt_group_criteria.md"
CACHE_DIR = ROOT / "data/clean/classifications/group_criteria"
OUT_TSV = ROOT / "data/clean/final/group_criterion_vectors.tsv"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
OUT_TSV.parent.mkdir(parents=True, exist_ok=True)

MODEL = "google/gemini-3-flash-preview"
PRICE_IN = 0.50   # USD / 1M input tokens
PRICE_OUT = 3.00  # USD / 1M output tokens
MAX_OUTPUT_TOKENS = 8_000

BATCH_SIZE = 20
MAX_PARALLEL = 10

load_dotenv(ROOT / ".env")
api_key = os.getenv("OPEN_ROUTER_API")
if not api_key:
    raise RuntimeError("OPEN_ROUTER_API not found in .env")

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
SYSTEM_PROMPT = PROMPT_FILE.read_text()

_TRAILING_COMMA_RE = re.compile(r",(\s*[}\]])")


def lenient_json_loads(raw: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        cleaned = _TRAILING_COMMA_RE.sub(r"\1", raw)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"_parse_error": True, "_raw": raw}


def build_payload(batch: list[dict]) -> list[dict]:
    """Compact input for the prompt — group + polity + period ONLY.

    Rights, resources, and verbatim are deliberately withheld to prevent the
    LLM from using rights as a classification signal.
    """
    return [
        {
            "i": i,
            "group": r["group"],
            "rule_polity": r["rule_polity"],
            "period": r.get("period"),
        }
        for i, r in enumerate(batch)
    ]


def call_model(batch: list[dict]) -> dict:
    payload = build_payload(batch)
    user_msg = (
        "For each of the following group labels, produce the criterion "
        "vector specified in the system prompt. Return JSON only — a list "
        "of objects, one per input, with key `i` matching the input index.\n\n"
        f"INPUT (list of {len(payload)} group/polity pairs):\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )
    resp = client.chat.completions.create(
        model=MODEL,
        max_tokens=MAX_OUTPUT_TOKENS,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    )
    content = resp.choices[0].message.content
    raw = (content or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
    parsed = lenient_json_loads(raw)
    if isinstance(parsed, dict) and isinstance(parsed.get("results"), list):
        parsed = parsed["results"]
    return {
        "parsed": parsed,
        "input_tokens": getattr(resp.usage, "prompt_tokens", 0) or 0,
        "output_tokens": getattr(resp.usage, "completion_tokens", 0) or 0,
    }


def run_batch(batch_idx: int, batch: list[dict]) -> dict:
    cache_path = CACHE_DIR / f"_batch_{batch_idx:04d}.json"
    if cache_path.exists():
        cached = json.loads(cache_path.read_text())
        return {**cached, "status": "cached"}
    try:
        out = call_model(batch)
        result = {
            "batch_idx": batch_idx,
            "n_pairs": len(batch),
            "pair_keys": [(r["group"], r["rule_polity"]) for r in batch],
            "scores": out["parsed"],
            "input_tokens": out["input_tokens"],
            "output_tokens": out["output_tokens"],
            "status": "ok",
        }
        cache_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        return result
    except Exception as e:
        return {
            "batch_idx": batch_idx,
            "n_pairs": len(batch),
            "pair_keys": [(r["group"], r["rule_polity"]) for r in batch],
            "status": "error",
            "error": str(e),
        }


def estimate(pairs: list[dict]) -> None:
    n = len(pairs)
    n_batches = -(-n // BATCH_SIZE)
    sys_tok = len(SYSTEM_PROMPT) / 4
    sample = build_payload(pairs[:BATCH_SIZE] if n >= BATCH_SIZE else pairs)
    content_tok = len(json.dumps(sample, ensure_ascii=False)) / 4
    in_per_batch = sys_tok + content_tok
    out_per_batch = 250 * BATCH_SIZE  # ~250 tok/item for 10 fields + reasoning
    in_tot = in_per_batch * n_batches
    out_tot = out_per_batch * n_batches
    cost = in_tot / 1e6 * PRICE_IN + out_tot / 1e6 * PRICE_OUT
    rounds = -(-n_batches // MAX_PARALLEL)
    SEC_PER_CALL = 15
    eta = rounds * SEC_PER_CALL / 60
    print("--- pre-run estimate ---")
    print(f"  unique (group, polity) pairs: {n}")
    print(f"  batches (B={BATCH_SIZE}):     {n_batches}")
    print(f"  parallel workers:             {MAX_PARALLEL}  (~{rounds} rounds)")
    print(f"  wall-clock (rough):           {eta:.1f} min  (~{SEC_PER_CALL}s/call)")
    print(f"  input tokens (est.):          {in_tot:>10,.0f}  ({in_per_batch:.0f}/batch)")
    print(f"  output tokens (est.):         {out_tot:>10,.0f}  ({out_per_batch:.0f}/batch)")
    print(f"  cost (USD, est.):             ${cost:.4f}")
    print("------------------------\n")


CRITERION_FIELDS = [
    "c_sex",
    "c_age",
    "c_ownership_status",
    "c_ancestry",
    "c_residence",
    "c_wealth",
    "c_kinship_role",
    "c_occupation",
    "requires_rights_definition",
    "emic_label",
    "criterion_reasoning",
]


def assemble(pairs: list[dict], batches: list[dict]) -> pd.DataFrame:
    key_to_score: dict[tuple, dict] = {}
    for b in batches:
        if b.get("status") not in ("ok", "cached"):
            continue
        scores = b.get("scores")
        if not isinstance(scores, list):
            continue
        keys = b["pair_keys"]
        for s in scores:
            if not isinstance(s, dict):
                continue
            idx = s.get("i")
            if idx is None or idx >= len(keys):
                continue
            g, p = keys[idx]
            key_to_score[(g, p)] = s

    rows = []
    for r in pairs:
        s = key_to_score.get((r["group"], r["rule_polity"]), {})
        row = {"group": r["group"], "rule_polity": r["rule_polity"]}
        for f in CRITERION_FIELDS:
            row[f] = s.get(f)
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    df = pd.read_csv(SRC, sep="\t")
    pairs_df = (
        df[["group", "rule_polity", "period"]]
        .dropna(subset=["group", "rule_polity"])
        .drop_duplicates(subset=["group", "rule_polity"])
        .reset_index(drop=True)
    )
    pairs = pairs_df.to_dict("records")
    print(f"Loaded {len(df)} rules from {SRC.relative_to(ROOT)}")
    print(f"Unique (group, rule_polity) pairs: {len(pairs)}")
    print(f"Model:   {MODEL}")
    print(f"Prompt:  {PROMPT_FILE.name}")
    print(f"Cache:   {CACHE_DIR.relative_to(ROOT)}")
    print(f"Out:     {OUT_TSV.relative_to(ROOT)}")
    print(f"Batch:   {BATCH_SIZE} pairs per API call")
    print(f"Workers: {MAX_PARALLEL}\n")
    estimate(pairs)

    batches = [pairs[i:i + BATCH_SIZE] for i in range(0, len(pairs), BATCH_SIZE)]
    print(f"Dispatching {len(batches)} batches...\n")

    start = time.time()
    outputs: list[dict] = []
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as ex:
        futures = {ex.submit(run_batch, i, b): i for i, b in enumerate(batches)}
        for fut in tqdm(as_completed(futures), total=len(futures), desc="criteria"):
            outputs.append(fut.result())
    elapsed = time.time() - start

    ok = [o for o in outputs if o["status"] in ("ok", "cached")]
    bad = [o for o in outputs if o["status"] not in ("ok", "cached")]
    tin = sum(o.get("input_tokens", 0) for o in ok)
    tout = sum(o.get("output_tokens", 0) for o in ok)
    cost = tin / 1e6 * PRICE_IN + tout / 1e6 * PRICE_OUT

    merged = assemble(pairs, outputs)
    missing = merged[merged["c_sex"].isna()]
    merged.to_csv(OUT_TSV, sep="\t", index=False)

    print(f"\n{'=' * 60}")
    print(f"Done in {elapsed / 60:.1f} min  ({elapsed:.0f}s)")
    print(f"OK batches: {len(ok)}  |  Errored: {len(bad)}")
    print(f"Pairs scored: {len(merged) - len(missing)} / {len(merged)}  "
          f"({len(missing)} missing)")
    print(f"Input tokens:  {tin:>12,}")
    print(f"Output tokens: {tout:>12,}")
    print(f"Cost (USD):    ${cost:>12.4f}")
    if bad:
        print("\nBatch errors (first 5):")
        for e in bad[:5]:
            print(f"  batch {e['batch_idx']}: {e.get('error', '')[:140]}")

    (CACHE_DIR / "_run_log.json").write_text(json.dumps({
        "model": MODEL,
        "prompt": PROMPT_FILE.name,
        "source": str(SRC.relative_to(ROOT)),
        "batch_size": BATCH_SIZE,
        "max_parallel": MAX_PARALLEL,
        "n_pairs": len(pairs),
        "n_batches": len(batches),
        "ok_batches": len(ok),
        "errored_batches": len(bad),
        "pairs_scored": int(len(merged) - len(missing)),
        "pairs_missing": int(len(missing)),
        "input_tokens": tin,
        "output_tokens": tout,
        "price_in_per_1M": PRICE_IN,
        "price_out_per_1M": PRICE_OUT,
        "cost_usd": round(cost, 4),
        "elapsed_sec": round(elapsed, 1),
    }, indent=2))
    print(f"\nRun log: {(CACHE_DIR / '_run_log.json').relative_to(ROOT)}")
    print(f"Out:     {OUT_TSV.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
