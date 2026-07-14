"""Per-rule, text-grounded criterion-vector classifier.

Methodological correction to `classify_group_criteria.py`. There, the unit was
the *group label* (e.g. `Citizens` in `Classical Athens`) and the criterion
vector was derived from the LLM's background historical knowledge. Here, the
unit is the **rule itself**: the LLM sees the verbatim text and must mark each
criterion axis as `stated` / `implied` / `unspecified` *strictly on the basis
of the words in the verbatim and the lexical presuppositions of those words*.

The output adds an `evidence` level per axis, so downstream analysis can:

  - take the strict subset (only `stated` axes) for maximally text-grounded
    cell signatures, or
  - take `stated ∪ implied` for the standard analysis, or
  - flag axes that *would* have been filled in by background knowledge but
    are now left `unspecified`.

Reads
-----
  - data/rules_dataset_april_2026.tsv
  - scripts/classifiers/prompt/prompt_rule_criteria_from_text.md

Writes
------
  - data/clean/classifications/rule_criteria_text/_batch_NNNN.json   batch cache
  - data/clean/classifications/rule_criteria_text/_run_log.json      run summary
  - data/clean/final/rule_criterion_vectors.tsv                      merged TSV
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
PROMPT_FILE = ROOT / "scripts/classifiers/prompt/prompt_rule_criteria_from_text.md"
CACHE_DIR = ROOT / "data/clean/classifications/rule_criteria_text"
OUT_TSV = ROOT / "data/clean/final/rule_criterion_vectors.tsv"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
OUT_TSV.parent.mkdir(parents=True, exist_ok=True)

MODEL = "google/gemini-3-flash-preview"
PRICE_IN = 0.50
PRICE_OUT = 3.00
MAX_OUTPUT_TOKENS = 16_000

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


AXES = [
    "c_sex",
    "c_age",
    "c_ownership_status",
    "c_ancestry",
    "c_residence",
    "c_wealth",
    "c_occupation",
]


def _verbatim_str(v) -> str:
    """Verbatim can be a JSON-encoded list of strings or a plain string."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v)
    if s.startswith("[") and s.endswith("]"):
        try:
            arr = json.loads(s)
            if isinstance(arr, list):
                return " ".join(str(x) for x in arr)
        except Exception:
            pass
    return s


def build_payload(batch: list[dict]) -> list[dict]:
    """Compact input for the prompt — verbatim + group_label + polity + rule + reasoning."""
    return [
        {
            "i": i,
            "verbatim": _verbatim_str(r.get("verbatim"))[:1200],
            "rule": str(r.get("rule") or "")[:300],
            "group_label": r.get("group"),
            "rule_polity": r.get("rule_polity"),
            "reasoning": str(r.get("reasoning") or "")[:400],
        }
        for i, r in enumerate(batch)
    ]


def call_model(batch: list[dict]) -> dict:
    payload = build_payload(batch)
    user_msg = (
        "For each of the following rules, produce the text-grounded criterion "
        "vector per the system prompt. Use the verbatim as the only evidence. "
        "Return JSON only — a list of objects, one per input, keyed by `i`.\n\n"
        f"INPUT (list of {len(payload)} rules):\n"
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
            "n_rules": len(batch),
            "rule_ids": [r["rule_id"] for r in batch],
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
            "n_rules": len(batch),
            "rule_ids": [r["rule_id"] for r in batch],
            "status": "error",
            "error": str(e),
        }


def estimate(rules: list[dict]) -> None:
    n = len(rules)
    n_batches = -(-n // BATCH_SIZE)
    sys_tok = len(SYSTEM_PROMPT) / 4
    sample = build_payload(rules[:BATCH_SIZE] if n >= BATCH_SIZE else rules)
    content_tok = len(json.dumps(sample, ensure_ascii=False)) / 4
    in_per_batch = sys_tok + content_tok
    out_per_batch = 320 * BATCH_SIZE  # verbose schema with evidence + reasoning
    in_tot = in_per_batch * n_batches
    out_tot = out_per_batch * n_batches
    cost = in_tot / 1e6 * PRICE_IN + out_tot / 1e6 * PRICE_OUT
    rounds = -(-n_batches // MAX_PARALLEL)
    SEC_PER_CALL = 15
    eta = rounds * SEC_PER_CALL / 60
    print("--- pre-run estimate ---")
    print(f"  rules:                        {n}")
    print(f"  batches (B={BATCH_SIZE}):     {n_batches}")
    print(f"  parallel workers:             {MAX_PARALLEL}  (~{rounds} rounds)")
    print(f"  wall-clock (rough):           {eta:.1f} min  (~{SEC_PER_CALL}s/call)")
    print(f"  input tokens (est.):          {in_tot:>10,.0f}  ({in_per_batch:.0f}/batch)")
    print(f"  output tokens (est.):         {out_tot:>10,.0f}  ({out_per_batch:.0f}/batch)")
    print(f"  cost (USD, est.):             ${cost:.4f}")
    print("------------------------\n")


def _flatten_score(s: dict) -> dict:
    """Flatten the per-rule score (with nested {value, evidence}) into columns."""
    out = {}
    for axis in AXES:
        cell = s.get(axis) if isinstance(s, dict) else None
        if isinstance(cell, dict):
            out[axis] = cell.get("value")
            out[f"{axis}_evidence"] = cell.get("evidence")
        else:
            out[axis] = None
            out[f"{axis}_evidence"] = None
    out["emic_label_in_text"] = s.get("emic_label_in_text") if isinstance(s, dict) else None
    out["criterion_reasoning_text"] = s.get("criterion_reasoning") if isinstance(s, dict) else None
    return out


def assemble(rules: list[dict], batches: list[dict]) -> pd.DataFrame:
    rid_to_score: dict[str, dict] = {}
    for b in batches:
        if b.get("status") not in ("ok", "cached"):
            continue
        scores = b.get("scores")
        if not isinstance(scores, list):
            continue
        rids = b["rule_ids"]
        for s in scores:
            if not isinstance(s, dict):
                continue
            idx = s.get("i")
            if idx is None or idx >= len(rids):
                continue
            rid_to_score[rids[idx]] = s

    rows = []
    for r in rules:
        rid = r["rule_id"]
        s = rid_to_score.get(rid, {})
        flat = _flatten_score(s)
        rows.append({"rule_id": rid, **flat})
    return pd.DataFrame(rows)


def main() -> None:
    df = pd.read_csv(SRC, sep="\t")
    rules = df.to_dict("records")
    print(f"Loaded {len(rules)} rules from {SRC.relative_to(ROOT)}")
    print(f"Model:   {MODEL}")
    print(f"Prompt:  {PROMPT_FILE.name}")
    print(f"Cache:   {CACHE_DIR.relative_to(ROOT)}")
    print(f"Out:     {OUT_TSV.relative_to(ROOT)}")
    print(f"Batch:   {BATCH_SIZE} rules per API call")
    print(f"Workers: {MAX_PARALLEL}\n")
    estimate(rules)

    batches = [rules[i:i + BATCH_SIZE] for i in range(0, len(rules), BATCH_SIZE)]
    print(f"Dispatching {len(batches)} batches...\n")

    start = time.time()
    outputs: list[dict] = []
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as ex:
        futures = {ex.submit(run_batch, i, b): i for i, b in enumerate(batches)}
        for fut in tqdm(as_completed(futures), total=len(futures), desc="rule_criteria"):
            outputs.append(fut.result())
    elapsed = time.time() - start

    ok = [o for o in outputs if o["status"] in ("ok", "cached")]
    bad = [o for o in outputs if o["status"] not in ("ok", "cached")]
    tin = sum(o.get("input_tokens", 0) for o in ok)
    tout = sum(o.get("output_tokens", 0) for o in ok)
    cost = tin / 1e6 * PRICE_IN + tout / 1e6 * PRICE_OUT

    merged = assemble(rules, outputs)
    missing = merged[merged["c_sex"].isna()]
    merged.to_csv(OUT_TSV, sep="\t", index=False)

    print(f"\n{'=' * 60}")
    print(f"Done in {elapsed / 60:.1f} min  ({elapsed:.0f}s)")
    print(f"OK batches: {len(ok)}  |  Errored: {len(bad)}")
    print(f"Rules scored: {len(merged) - len(missing)} / {len(merged)}  ({len(missing)} missing)")
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
        "n_rules": len(rules),
        "n_batches": len(batches),
        "ok_batches": len(ok),
        "errored_batches": len(bad),
        "rules_scored": int(len(merged) - len(missing)),
        "rules_missing": int(len(missing)),
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
