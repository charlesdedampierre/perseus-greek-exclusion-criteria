"""Reclassify each rule's resource into a GROUP-INDEPENDENT granular right.

Motivation (BUN-1002). Coarse meta-rights conflate distinct resources and produce
false contradictions — e.g. "Protection from corporal punishment" lumps protection
from private assault (slaves partly had it) with exposure to judicial torture (slaves
did not). At the right granularity, the four top cells (citizen males, citizen females,
slaves, foreigners) should not be both granted and denied the *same* right in the same
region and period.

Two passes:
  A. Taxonomy induction — one LLM call over the 44 resource_meta buckets + sampled
     (resource, verbatim) examples → a controlled vocabulary of granular rights, each
     defined by the kind of resource, never by the group.
  B. Per-rule assignment — batch the 1011 rules, give the taxonomy, assign each rule
     to one granular right from it (or a new label, flagged).

Follows MODEL.md: Gemini 3 Flash Preview via OpenRouter, key in .env as OPEN_ROUTER_API.

Reads
-----
  - data/clean/final/rules_with_criteria.tsv
  - scripts/classifiers/prompt/prompt_resource_granular.md

Writes
------
  - data/clean/classifications/resource_granular/_taxonomy.json
  - data/clean/classifications/resource_granular/_batch_NNNN.json
  - data/clean/classifications/resource_granular/_run_log.json
  - data/clean/final/rule_resource_granular.tsv     (rule_id, resource_granular, ...)
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
SRC = ROOT / "data/clean/final/rules_with_criteria.tsv"
PROMPT_FILE = ROOT / "scripts/classifiers/prompt/prompt_resource_granular.md"
CACHE_DIR = ROOT / "data/clean/classifications/resource_granular"
TAX_PATH = CACHE_DIR / "_taxonomy.json"
OUT_TSV = ROOT / "data/clean/final/rule_resource_granular.tsv"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

MODEL = "google/gemini-3-flash-preview"
PRICE_IN, PRICE_OUT = 0.50, 3.00
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


def lenient_json(raw: str):
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        try:
            return json.loads(_TRAILING_COMMA_RE.sub(r"\1", raw))
        except json.JSONDecodeError:
            return {"_parse_error": True, "_raw": raw[:500]}


def verbatim_str(v) -> str:
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


# --------------------------------------------------------------------------- #
# Pass A — taxonomy induction
# --------------------------------------------------------------------------- #
def induce_taxonomy(df: pd.DataFrame, force: bool = False) -> dict:
    if TAX_PATH.exists() and not force:
        return json.loads(TAX_PATH.read_text())

    # one compact example bundle per meta-right: its distinct raw resources + a verbatim
    bundles = []
    for meta, sub in df.groupby("resource_meta"):
        examples = []
        for res, ssub in sub.groupby("resource"):
            examples.append({
                "resource": str(res),
                "n": int(len(ssub)),
                "verbatim": verbatim_str(ssub.iloc[0]["verbatim"])[:200],
            })
        examples.sort(key=lambda e: -e["n"])
        bundles.append({"resource_meta": str(meta), "n_rules": int(len(sub)),
                        "raw_resources": examples[:12]})
    bundles.sort(key=lambda b: -b["n_rules"])

    user_msg = (
        "Build the controlled vocabulary of granular rights. For each `resource_meta` "
        "below you are shown its distinct raw `resource` labels (with counts) and a "
        "sample verbatim. Split each meta-right into the minimal set of "
        "GROUP-INDEPENDENT granular rights needed so that genuinely different resources "
        "(e.g. judicial torture vs private assault; archonship vs generalship) are "
        "separated, while mere group restrictions are NOT split out.\n\n"
        "Return JSON only: {\"taxonomy\": [{\"right\": str, \"parent_meta\": str, "
        "\"definition\": str}]}. Keep labels short, group-independent noun phrases. "
        "Aim for 1-5 granular rights per meta-right.\n\n"
        f"INPUT:\n{json.dumps(bundles, ensure_ascii=False)}"
    )
    resp = client.chat.completions.create(
        model=MODEL, max_tokens=MAX_OUTPUT_TOKENS,
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": user_msg}],
    )
    parsed = lenient_json(resp.choices[0].message.content)
    tax = parsed.get("taxonomy", parsed) if isinstance(parsed, dict) else parsed
    out = {
        "taxonomy": tax,
        "input_tokens": getattr(resp.usage, "prompt_tokens", 0) or 0,
        "output_tokens": getattr(resp.usage, "completion_tokens", 0) or 0,
    }
    TAX_PATH.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    return out


# --------------------------------------------------------------------------- #
# Pass B — per-rule assignment
# --------------------------------------------------------------------------- #
def build_payload(batch: list[dict]) -> list[dict]:
    return [{
        "i": i,
        "resource": str(r.get("resource") or ""),
        "resource_meta": str(r.get("resource_meta") or ""),
        "rule": str(r.get("rule") or "")[:200],
        "verbatim": verbatim_str(r.get("verbatim"))[:900],
        "rule_polity": r.get("rule_polity"),
    } for i, r in enumerate(batch)]


def call_assign(batch: list[dict], taxonomy: list) -> dict:
    tax_min = [{"right": t.get("right"), "parent_meta": t.get("parent_meta")}
               for t in taxonomy if isinstance(t, dict)]
    user_msg = (
        "Assign each rule to one granular right from the taxonomy. Use the verbatim as "
        "the primary evidence. Return JSON only — a list of objects keyed by `i`.\n\n"
        f"TAXONOMY ({len(tax_min)} rights):\n{json.dumps(tax_min, ensure_ascii=False)}\n\n"
        f"RULES ({len(batch)}):\n{json.dumps(build_payload(batch), ensure_ascii=False)}"
    )
    resp = client.chat.completions.create(
        model=MODEL, max_tokens=MAX_OUTPUT_TOKENS,
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": user_msg}],
    )
    parsed = lenient_json(resp.choices[0].message.content)
    if isinstance(parsed, dict) and isinstance(parsed.get("results"), list):
        parsed = parsed["results"]
    return {"parsed": parsed,
            "input_tokens": getattr(resp.usage, "prompt_tokens", 0) or 0,
            "output_tokens": getattr(resp.usage, "completion_tokens", 0) or 0}


def run_batch(batch_idx: int, batch: list[dict], taxonomy: list) -> dict:
    cache = CACHE_DIR / f"_batch_{batch_idx:04d}.json"
    if cache.exists():
        return {**json.loads(cache.read_text()), "status": "cached"}
    try:
        out = call_assign(batch, taxonomy)
        res = {"batch_idx": batch_idx, "rule_ids": [r["rule_id"] for r in batch],
               "scores": out["parsed"], "input_tokens": out["input_tokens"],
               "output_tokens": out["output_tokens"], "status": "ok"}
        cache.write_text(json.dumps(res, indent=2, ensure_ascii=False))
        return res
    except Exception as e:
        return {"batch_idx": batch_idx, "rule_ids": [r["rule_id"] for r in batch],
                "status": "error", "error": str(e)}


def estimate(n: int, n_tax: int) -> None:
    n_batches = -(-n // BATCH_SIZE)
    in_tot = n_batches * (len(SYSTEM_PROMPT) / 4 + n_tax * 12 + BATCH_SIZE * 280)
    out_tot = n_batches * BATCH_SIZE * 70
    cost = in_tot / 1e6 * PRICE_IN + out_tot / 1e6 * PRICE_OUT
    rounds = -(-n_batches // MAX_PARALLEL)
    print("--- assignment estimate ---")
    print(f"  rules: {n} | batches: {n_batches} | taxonomy size: {n_tax}")
    print(f"  wall-clock (rough): {rounds * 12 / 60:.1f} min  ({MAX_PARALLEL} workers)")
    print(f"  input tok (est):  {in_tot:>10,.0f}")
    print(f"  output tok (est): {out_tot:>10,.0f}")
    print(f"  cost (USD, est):  ${cost:.4f}")
    print("---------------------------\n")


def assemble(rules: list[dict], batches: list[dict], tax_lookup: dict) -> pd.DataFrame:
    rid_to = {}
    for b in batches:
        if b.get("status") not in ("ok", "cached"):
            continue
        scores, rids = b.get("scores"), b["rule_ids"]
        if not isinstance(scores, list):
            continue
        for s in scores:
            if isinstance(s, dict) and s.get("i") is not None and s["i"] < len(rids):
                rid_to[rids[s["i"]]] = s
    rows = []
    for r in rules:
        s = rid_to.get(r["rule_id"], {})
        right = s.get("right")
        rows.append({
            "rule_id": r["rule_id"],
            "resource_meta": r.get("resource_meta"),
            "resource": r.get("resource"),
            "resource_granular": right,
            "granular_is_new": bool(s.get("is_new", False)),
            "granular_parent_meta": s.get("parent_meta") or tax_lookup.get(right),
            "granular_reasoning": s.get("reasoning"),
        })
    return pd.DataFrame(rows)


def main() -> None:
    df = pd.read_csv(SRC, sep="\t")
    rules = df.to_dict("records")
    print(f"Loaded {len(rules)} rules | meta-rights: {df['resource_meta'].nunique()}")

    print("\n[Pass A] inducing granular taxonomy...")
    tax_out = induce_taxonomy(df)
    taxonomy = tax_out["taxonomy"]
    tax_lookup = {t.get("right"): t.get("parent_meta") for t in taxonomy if isinstance(t, dict)}
    print(f"  taxonomy: {len(taxonomy)} granular rights "
          f"(in {tax_out.get('input_tokens',0)} / out {tax_out.get('output_tokens',0)} tok)")

    print("\n[Pass B] assigning rules...")
    estimate(len(rules), len(taxonomy))
    batches = [rules[i:i + BATCH_SIZE] for i in range(0, len(rules), BATCH_SIZE)]
    start = time.time()
    outputs = []
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as ex:
        futs = {ex.submit(run_batch, i, b, taxonomy): i for i, b in enumerate(batches)}
        for f in tqdm(as_completed(futs), total=len(futs), desc="granular"):
            outputs.append(f.result())
    elapsed = time.time() - start

    ok = [o for o in outputs if o["status"] in ("ok", "cached")]
    bad = [o for o in outputs if o["status"] not in ("ok", "cached")]
    tin = sum(o.get("input_tokens", 0) for o in ok) + tax_out.get("input_tokens", 0)
    tout = sum(o.get("output_tokens", 0) for o in ok) + tax_out.get("output_tokens", 0)
    cost = tin / 1e6 * PRICE_IN + tout / 1e6 * PRICE_OUT

    merged = assemble(rules, outputs, tax_lookup)
    missing = int(merged["resource_granular"].isna().sum())
    merged.to_csv(OUT_TSV, sep="\t", index=False)

    print(f"\n{'='*60}")
    print(f"Done in {elapsed:.0f}s | OK {len(ok)} | errored {len(bad)}")
    print(f"Assigned: {len(merged)-missing}/{len(merged)} ({missing} missing)")
    print(f"Distinct granular rights used: {merged['resource_granular'].nunique()}")
    print(f"New labels proposed: {int(merged['granular_is_new'].sum())}")
    print(f"Input tok {tin:,} | Output tok {tout:,} | Cost ${cost:.4f}")
    for e in bad[:5]:
        print(f"  batch {e['batch_idx']} error: {e.get('error','')[:120]}")

    (CACHE_DIR / "_run_log.json").write_text(json.dumps({
        "model": MODEL, "prompt": PROMPT_FILE.name, "n_rules": len(rules),
        "taxonomy_size": len(taxonomy), "ok_batches": len(ok), "errored_batches": len(bad),
        "assigned": len(merged) - missing, "missing": missing,
        "distinct_granular_rights": int(merged["resource_granular"].nunique()),
        "input_tokens": tin, "output_tokens": tout, "cost_usd": round(cost, 4),
        "elapsed_sec": round(elapsed, 1),
    }, indent=2))
    print(f"\nOut: {OUT_TSV.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
