"""Apply prompt_polity_time.md to every rule in rules_all_scored.tsv.

For every extracted rule, produces four fields describing where and when
the rule *itself* is set (as distinct from the work-level polity/time):

  rule_polity            specific polity label
  rule_polity_reasoning  ≤250-char sentence
  rule_date              single integer year (BCE negative / CE positive)
  rule_time_reasoning    ≤1-sentence date justification

Reads:
  - data/processed_data/rules_all_scored.tsv
  - scripts/classifiers/prompt/prompt_polity_time.md

Writes:
  - data/llm_results/rule_polity_time/_batch_NNNN.json   per-batch cache
  - data/processed_data/rules_all_scored_with_polity_time.tsv  (merged TSV)
  - data/llm_results/rule_polity_time/_run_log.json
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


def _resolve(env_key: str, default: Path) -> Path:
    val = os.getenv(env_key)
    if val is None:
        return default
    p = Path(val)
    return p if p.is_absolute() else (ROOT / p)


# Env overrides: SRC=... OUT_DIR=... OUT_TSV=... python classify_rule_polity_time.py
SRC = _resolve("SRC", ROOT / "data/processed_data/rules_all_scored.tsv")
PROMPT_FILE = ROOT / "scripts/classifiers/prompt/prompt_polity_time.md"
CACHE_DIR = _resolve("OUT_DIR", ROOT / "data/llm_results/rule_polity_time")
OUT_TSV = _resolve("OUT_TSV",
                   ROOT / "data/processed_data/rules_all_scored_with_polity_time.tsv")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

MODEL = "google/gemini-3-flash-preview"
PRICE_IN = 0.50
PRICE_OUT = 3.00
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
    """Compact input the polity/time prompt needs per rule.

    Includes optional work-level priors (from the work-level polity/time
    annotation pass) when they are present in the merged TSV. The prompt
    uses these as strong hints for historian works.
    """
    out = []
    for r in batch:
        item = {
            "rule": r.get("rule"),
            "group": r.get("group"),
            "resource": r.get("resource"),
            "directionality": r.get("directionality"),
            "verbatim": r.get("verbatim"),
            "reasoning": r.get("reasoning"),
            "author": r.get("perseus_author"),
            "work_title": r.get("perseus_title"),
            "author_impact_date": r.get("author_impact_date"),
        }
        # Work-level priors — only attach when the row has them filled in
        # (historian works have them via works_polity_time_dataset; others leave null).
        for key in (
            "work_polity",
            "work_polity_reasoning",
            "work_time_reference",
            "work_time_start",
            "work_time_end",
            "work_time_reasoning",
            "work_author_polity_cliopatria",
        ):
            val = r.get(key)
            if val is not None and not (isinstance(val, float) and pd.isna(val)):
                item[key] = val
        out.append(item)
    return out


def call_model(batch: list[dict]) -> dict:
    payload = build_payload(batch)
    user_msg = (
        "For each of the following rules, produce its `rule_polity`, "
        "`rule_polity_reasoning`, `rule_date` (single integer year, BCE "
        "negative / CE positive), and `rule_time_reasoning`. Return JSON "
        "only — a list of objects with key `i` equal to the input index.\n\n"
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
    # Accept both `[...]` and `{"results": [...]}` shapes.
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


def estimate(rules: list[dict]) -> None:
    n = len(rules)
    n_batches = -(-n // BATCH_SIZE)
    sys_tok = len(SYSTEM_PROMPT) / 4
    sample = build_payload(rules[:BATCH_SIZE] if n >= BATCH_SIZE else rules)
    content_tok = len(json.dumps(sample, ensure_ascii=False)) / 4
    in_per_batch = sys_tok + content_tok
    out_per_batch = 150 * BATCH_SIZE  # ~150 tokens/rule for 4 fields
    in_tot = in_per_batch * n_batches
    out_tot = out_per_batch * n_batches
    cost = in_tot / 1e6 * PRICE_IN + out_tot / 1e6 * PRICE_OUT
    rounds = -(-n_batches // MAX_PARALLEL)
    SEC_PER_CALL = 15
    eta = rounds * SEC_PER_CALL / 60
    print("--- pre-run estimate ---")
    print(f"  rules:                 {n}")
    print(f"  batches (B={BATCH_SIZE}):          {n_batches}")
    print(f"  parallel workers:      {MAX_PARALLEL}  (~{rounds} rounds)")
    print(f"  wall-clock (rough):    {eta:.1f} min  (~{SEC_PER_CALL}s/call)")
    print(f"  input tokens (est.):   {in_tot:>12,.0f}  ({in_per_batch:.0f}/batch)")
    print(f"  output tokens (est.):  {out_tot:>12,.0f}  ({out_per_batch:.0f}/batch)")
    print(f"  cost (USD, est.):      ${cost:.4f}")
    print("------------------------\n")


def assemble(rules: list[dict], batches: list[dict]) -> pd.DataFrame:
    uid_to_score = {}
    for b in batches:
        if b.get("status") not in ("ok", "cached"):
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
        out = dict(r)
        out["rule_polity"] = s.get("rule_polity")
        out["rule_polity_reasoning"] = s.get("rule_polity_reasoning")
        out["rule_date"] = s.get("rule_date")
        out["rule_time_reasoning"] = s.get("rule_time_reasoning")
        rows.append(out)
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
        for fut in tqdm(as_completed(futures), total=len(futures), desc="polity_time"):
            outputs.append(fut.result())
    elapsed = time.time() - start

    ok = [o for o in outputs if o["status"] in ("ok", "cached")]
    bad = [o for o in outputs if o["status"] not in ("ok", "cached")]
    tin = sum(o.get("input_tokens", 0) for o in ok)
    tout = sum(o.get("output_tokens", 0) for o in ok)
    cost = tin / 1e6 * PRICE_IN + tout / 1e6 * PRICE_OUT

    merged = assemble(rules, outputs)
    missing = merged[merged["rule_polity"].isna()]
    merged.to_csv(OUT_TSV, sep="\t", index=False)

    print(f"\n{'=' * 60}")
    print(f"Done in {elapsed / 60:.1f} min  ({elapsed:.0f}s)")
    print(f"OK batches: {len(ok)}  |  Errored: {len(bad)}")
    print(f"Rules scored: {len(merged) - len(missing)} / {len(merged)}  "
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
