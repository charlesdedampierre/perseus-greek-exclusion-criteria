"""Apply dimension_prompt_V1.md to every rule extracted by classify_core_v1.py.

Each rule gets seven dimension scores plus a per-dimension reasoning:
  resource_materiality   1–5
  resource_generality    1–5
  resource_persistence   1–5
  group_immutability     1–5
  rule_contemporarity    0 / 1
  opinion_vs_fact        1–5
  tautology              0 / 1

Rules are batched (BATCH_SIZE per API call) and batches are executed in
parallel via `ThreadPoolExecutor` (chunk-level parallelism — every batch is
one future, never work-level).

Reads:
  - data/llm_results/core_v1/tlg*.json     output of the core-prompt pass
  - scripts/classifiers/prompt/dimension_prompt_V1.md

Writes:
  - data/llm_results/core_v1_dimensions/rules_scored.tsv
  - data/llm_results/core_v1_dimensions/rules_scored.jsonl
  - data/llm_results/core_v1_dimensions/_run_log.json
"""

from __future__ import annotations

import glob
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

# === Paths ===
ROOT = Path(__file__).resolve().parents[2]


def _resolve(env_key: str, default: Path) -> Path:
    val = os.getenv(env_key)
    if val is None:
        return default
    p = Path(val)
    return p if p.is_absolute() else (ROOT / p)


# Override via env vars: CORE_DIR=path OUT_DIR=path python classify_dimensions_v1.py
CORE_DIR = _resolve("CORE_DIR", ROOT / "data/llm_results/core_v1")
PROMPT_FILE = ROOT / "scripts/classifiers/prompt/dimension_prompt_V1.md"
OUT_DIR = _resolve("OUT_DIR", ROOT / "data/llm_results/core_v1_dimensions")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# === Model (must match MODEL.md) ===
MODEL = "google/gemini-3-flash-preview"
PRICE_IN = 0.50
PRICE_OUT = 3.00
MAX_OUTPUT_TOKENS = 16_000

# === Runtime ===
BATCH_SIZE = 20        # rules per API call
MAX_PARALLEL = 10      # concurrent batches

DIMENSIONS = [
    ("resource_materiality", "materiality_reasoning"),
    ("resource_generality",  "generality_reasoning"),
    ("resource_persistence", "persistence_reasoning"),
    ("group_immutability",   "immutability_reasoning"),
    ("rule_contemporarity",  "contemporarity_reasoning"),
    ("opinion_vs_fact",      "opinion_vs_fact_reasoning"),
    ("tautology",            "tautology_reasoning"),
]

load_dotenv(ROOT / ".env")
api_key = os.getenv("OPEN_ROUTER_API")
if not api_key:
    raise RuntimeError("OPEN_ROUTER_API not found in .env")

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
SYSTEM_PROMPT = PROMPT_FILE.read_text()


def load_rules() -> list[dict]:
    """Flatten all core_v1 per-work JSONs into a single list of rules."""
    rules = []
    for fp in sorted(glob.glob(str(CORE_DIR / "tlg*.json"))):
        work = json.loads(Path(fp).read_text())
        fid = work.get("_file_id") or Path(fp).stem
        for idx, r in enumerate(work.get("extracted_rules", []) or []):
            if not isinstance(r, dict):
                continue
            rules.append({
                "rule_uid": f"{fid}::{idx}",
                "file_id": fid,
                "perseus_author": work.get("_perseus_author"),
                "perseus_title": work.get("_perseus_title"),
                "period": work.get("_period"),
                "criteria": r.get("criteria"),
                "rule": r.get("rule"),
                "group": r.get("group"),
                "resource": r.get("resource"),
                "directionality": r.get("directionality"),
                "verbatim": r.get("verbatim"),
                "reasoning": r.get("reasoning"),
                "contemporary": r.get("contemporary"),
                "factuality": r.get("factuality"),
                "confidence": r.get("confidence"),
            })
    return rules


def build_payload(batch: list[dict]) -> list[dict]:
    """The subset of fields the dimension prompt needs — kept compact."""
    out = []
    for r in batch:
        out.append({
            "criteria": r["criteria"],
            "group": r["group"],
            "resource": r["resource"],
            "rule": r["rule"],
            "directionality": r["directionality"],
            "verbatim": r["verbatim"],
            "reasoning": r["reasoning"],
            "author": r["perseus_author"],
            "work_title": r["perseus_title"],
        })
    return out


_TRAILING_COMMA_RE = re.compile(r",(\s*[}\]])")


def lenient_json_loads(raw: str):
    """Parse JSON, retrying with trailing-comma tolerance if strict parse fails."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        cleaned = _TRAILING_COMMA_RE.sub(r"\1", raw)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"_parse_error": True, "_raw": raw}


def call_model(batch: list[dict]) -> dict:
    payload = build_payload(batch)
    user_msg = (
        "Score each of the following rules along the seven dimensions. "
        "Return JSON only — a list of objects, one per input rule, in input "
        "order, with key `i` equal to the input index.\n\n"
        f"INPUT (list of {len(payload)} rules):\n{json.dumps(payload, ensure_ascii=False)}"
    )
    resp = client.chat.completions.create(
        model=MODEL,
        max_tokens=MAX_OUTPUT_TOKENS,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    )
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
    parsed = lenient_json_loads(raw)
    return {
        "parsed": parsed,
        "input_tokens": getattr(resp.usage, "prompt_tokens", 0) or 0,
        "output_tokens": getattr(resp.usage, "completion_tokens", 0) or 0,
    }


def run_batch(batch_idx: int, batch: list[dict]) -> dict:
    cache_path = OUT_DIR / f"_batch_{batch_idx:04d}.json"
    if cache_path.exists():
        cached = json.loads(cache_path.read_text())
        return {**cached, "status": "cached"}
    try:
        out = call_model(batch)
        result = {
            "batch_idx": batch_idx,
            "n_rules": len(batch),
            "rule_uids": [r["rule_uid"] for r in batch],
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
            "rule_uids": [r["rule_uid"] for r in batch],
            "status": "error",
            "error": str(e),
        }


def assemble(rules: list[dict], batches_out: list[dict]) -> pd.DataFrame:
    """Join dimension scores back onto the original rules by (batch_idx, i)."""
    uid_to_score: dict[str, dict] = {}
    for b in batches_out:
        if b.get("status") == "error":
            continue
        scores = b.get("scores")
        if not isinstance(scores, list):
            continue
        uids = b["rule_uids"]
        for s in scores:
            if not isinstance(s, dict):
                continue
            idx = s.get("i")
            if idx is None or idx >= len(uids):
                continue
            uid_to_score[uids[idx]] = s

    rows = []
    for r in rules:
        s = uid_to_score.get(r["rule_uid"], {})
        row = dict(r)
        for k, kr in DIMENSIONS:
            row[k] = s.get(k)
            row[kr] = s.get(kr)
        rows.append(row)
    return pd.DataFrame(rows)


def estimate_run(rules: list[dict]) -> None:
    n = len(rules)
    n_batches = -(-n // BATCH_SIZE)
    rounds = -(-n_batches // MAX_PARALLEL)
    sys_tok = len(SYSTEM_PROMPT) / 4

    sample_payload = json.dumps(
        build_payload(rules[:BATCH_SIZE] if len(rules) >= BATCH_SIZE else rules),
        ensure_ascii=False,
    )
    content_tok_per_batch = len(sample_payload) / 4
    in_per_batch = sys_tok + content_tok_per_batch
    out_per_batch = 250 * BATCH_SIZE / 4 * 4  # ~250 tokens/rule for 7 scores+reasonings
    # correct: ~250 tokens/rule
    out_per_batch = 250 * BATCH_SIZE

    in_tot = in_per_batch * n_batches
    out_tot = out_per_batch * n_batches
    cost = in_tot / 1e6 * PRICE_IN + out_tot / 1e6 * PRICE_OUT
    SEC_PER_CALL = 25
    eta_min = rounds * SEC_PER_CALL / 60

    print("--- pre-run estimate ---")
    print(f"  rules total:          {n}")
    print(f"  batches (B={BATCH_SIZE}):          {n_batches}")
    print(f"  parallel workers:     {MAX_PARALLEL}  (~{rounds} rounds)")
    print(f"  wall-clock (rough):   {eta_min:.1f} min  (~{SEC_PER_CALL}s/call)")
    print(f"  input tokens (est.):  {in_tot:>12,.0f}  ({in_per_batch:.0f}/batch)")
    print(f"  output tokens (est.): {out_tot:>12,.0f}  ({out_per_batch:.0f}/batch)")
    print(f"  cost (USD, est.):     ${cost:.4f}")
    print("------------------------\n")


def main() -> None:
    rules = load_rules()
    print(f"Loaded {len(rules)} rules from {CORE_DIR.relative_to(ROOT)}")
    print(f"Model:   {MODEL}")
    print(f"Prompt:  {PROMPT_FILE.name}")
    print(f"Out:     {OUT_DIR.relative_to(ROOT)}")
    print(f"Batch:   {BATCH_SIZE} rules per API call")
    print(f"Workers: {MAX_PARALLEL}\n")
    estimate_run(rules)

    batches = [rules[i:i + BATCH_SIZE] for i in range(0, len(rules), BATCH_SIZE)]
    print(f"Dispatching {len(batches)} batches…\n")

    start = time.time()
    outputs: list[dict] = []
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as ex:
        futures = {ex.submit(run_batch, i, b): i for i, b in enumerate(batches)}
        for fut in tqdm(as_completed(futures), total=len(futures), desc="batches"):
            outputs.append(fut.result())
    elapsed = time.time() - start

    ok = [o for o in outputs if o["status"] in ("ok", "cached")]
    bad = [o for o in outputs if o["status"] not in ("ok", "cached")]
    tin = sum(o.get("input_tokens", 0) for o in ok)
    tout = sum(o.get("output_tokens", 0) for o in ok)
    cost = tin / 1e6 * PRICE_IN + tout / 1e6 * PRICE_OUT

    df = assemble(rules, outputs)
    missing = df[df["resource_materiality"].isna()]
    df.to_csv(OUT_DIR / "rules_scored.tsv", sep="\t", index=False)
    (OUT_DIR / "rules_scored.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in df.to_dict("records"))
    )

    print(f"\n{'=' * 60}")
    print(f"Done in {elapsed / 60:.1f} min  ({elapsed:.0f}s)")
    print(f"OK batches: {len(ok)}  |  Errored: {len(bad)}")
    print(f"Rules scored: {len(df) - len(missing)} / {len(df)}  "
          f"({len(missing)} missing)")
    print(f"Input tokens:  {tin:>12,}")
    print(f"Output tokens: {tout:>12,}")
    print(f"Cost (USD):    ${cost:>12.4f}")

    if bad:
        print("\nBatch errors (first 5):")
        for e in bad[:5]:
            print(f"  batch {e['batch_idx']}: {e.get('error','')[:140]}")

    (OUT_DIR / "_run_log.json").write_text(json.dumps({
        "model": MODEL,
        "prompt": PROMPT_FILE.name,
        "parallelism": "chunk-level (per batch)",
        "batch_size": BATCH_SIZE,
        "max_parallel": MAX_PARALLEL,
        "n_rules": len(rules),
        "n_batches": len(batches),
        "ok_batches": len(ok),
        "errored_batches": len(bad),
        "rules_scored": int(len(df) - len(missing)),
        "rules_missing": int(len(missing)),
        "input_tokens": tin,
        "output_tokens": tout,
        "price_in_per_1M": PRICE_IN,
        "price_out_per_1M": PRICE_OUT,
        "cost_usd": round(cost, 4),
        "elapsed_sec": round(elapsed, 1),
    }, indent=2))
    print(f"\nRun log: {(OUT_DIR / '_run_log.json').relative_to(ROOT)}")
    print(f"Scored:  {(OUT_DIR / 'rules_scored.tsv').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
