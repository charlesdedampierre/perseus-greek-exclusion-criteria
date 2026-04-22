"""Assign a 2-3-word meta-category to every distinct group and resource.

Pools distinct `group` and `resource` strings from both scored corpora
(`rules_all_scored_with_polity_time.tsv` and
`rules_random100_with_polity_time.tsv`), deduplicates, and calls the
model once per (item, type). The resulting map is written to two TSVs
plus an augmented copy of each scored corpus with
`group_meta_category` / `resource_meta_category` columns populated.

Reads:
  - data/processed_data/rules_all_scored_with_polity_time.tsv
  - data/processed_data/rules_random100_with_polity_time.tsv
  - scripts/classifiers/prompt/prompt_meta_category.md

Writes:
  - data/processed_data/group_meta_category.tsv
  - data/processed_data/resource_meta_category.tsv
  - data/processed_data/rules_all_with_meta.tsv                   (662 rules + meta)
  - data/processed_data/rules_random100_with_meta.tsv             (946 rules + meta)
  - data/llm_results/meta_category/_batch_NNNN.json               per-batch cache
  - data/llm_results/meta_category/_run_log.json
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
PROMPT_FILE = ROOT / "scripts/classifiers/prompt/prompt_meta_category.md"
SRC_MAIN = ROOT / "data/processed_data/rules_all_scored_with_polity_time.tsv"
SRC_R100 = ROOT / "data/processed_data/rules_random100_with_polity_time.tsv"
CACHE_DIR = ROOT / "data/llm_results/meta_category"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

OUT_GROUP_MAP = ROOT / "data/processed_data/group_meta_category.tsv"
OUT_RES_MAP   = ROOT / "data/processed_data/resource_meta_category.tsv"
OUT_MAIN      = ROOT / "data/processed_data/rules_all_with_meta.tsv"
OUT_R100      = ROOT / "data/processed_data/rules_random100_with_meta.tsv"

MODEL = "google/gemini-3-flash-preview"
PRICE_IN = 0.50
PRICE_OUT = 3.00
MAX_OUTPUT_TOKENS = 6_000

BATCH_SIZE = 40
MAX_PARALLEL = 10

load_dotenv(ROOT / ".env")
api_key = os.getenv("OPEN_ROUTER_API")
if not api_key:
    raise RuntimeError("OPEN_ROUTER_API not found in .env")

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
SYSTEM_PROMPT = PROMPT_FILE.read_text()

_TRAILING_COMMA = re.compile(r",(\s*[}\]])")


def lenient_json_loads(raw: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        cleaned = _TRAILING_COMMA.sub(r"\1", raw)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"_parse_error": True, "_raw": raw}


def call_model(batch: list[dict]) -> dict:
    user_msg = (
        "Assign a 2-3-word meta-category to each of the following items. "
        "Return JSON only — a list of objects, in input order, each with "
        "keys `i` and `meta_category`.\n\n"
        f"INPUT ({len(batch)} items):\n{json.dumps(batch, ensure_ascii=False)}"
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
            "n_items": len(batch),
            "items": batch,
            "parsed": out["parsed"],
            "input_tokens": out["input_tokens"],
            "output_tokens": out["output_tokens"],
            "status": "ok",
        }
        cache_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        return result
    except Exception as e:
        return {
            "batch_idx": batch_idx,
            "n_items": len(batch),
            "items": batch,
            "status": "error",
            "error": str(e),
        }


def collect_items() -> tuple[list[str], list[str]]:
    """Unique, stripped, non-empty groups and resources from both corpora."""
    groups, resources = set(), set()
    for src in (SRC_MAIN, SRC_R100):
        df = pd.read_csv(src, sep="\t")
        for v in df["group"].dropna().astype(str):
            s = v.strip()
            if s:
                groups.add(s)
        for v in df["resource"].dropna().astype(str):
            s = v.strip()
            if s:
                resources.add(s)
    return sorted(groups), sorted(resources)


def estimate(n_items: int) -> None:
    n_batches = -(-n_items // BATCH_SIZE)
    rounds = -(-n_batches // MAX_PARALLEL)
    sys_tok = len(SYSTEM_PROMPT) / 4
    # Content per batch: ~40 items × ~30 chars = ~1200 chars → ~300 tok
    in_per_batch = sys_tok + 300 + 100  # + user-msg prefix
    out_per_batch = 40 * 15  # ~15 tok per {i, meta_category} entry
    in_tot = in_per_batch * n_batches
    out_tot = out_per_batch * n_batches
    cost = in_tot / 1e6 * PRICE_IN + out_tot / 1e6 * PRICE_OUT
    print("--- pre-run estimate ---")
    print(f"  items:                 {n_items}")
    print(f"  batches (B={BATCH_SIZE}):          {n_batches}")
    print(f"  parallel workers:      {MAX_PARALLEL}  (~{rounds} rounds)")
    print(f"  wall-clock (rough):    ~{rounds*12/60:.1f} min")
    print(f"  input tokens (est.):   {in_tot:>12,.0f}")
    print(f"  output tokens (est.):  {out_tot:>12,.0f}")
    print(f"  cost (USD, est.):      ${cost:.4f}")
    print("------------------------\n")


def main() -> None:
    groups, resources = collect_items()
    print(f"Distinct groups:    {len(groups):>4}")
    print(f"Distinct resources: {len(resources):>4}")
    print(f"Total items:        {len(groups) + len(resources):>4}")
    print(f"Model:   {MODEL}")
    print(f"Prompt:  {PROMPT_FILE.name}")
    print(f"Cache:   {CACHE_DIR.relative_to(ROOT)}\n")

    items = (
        [{"type": "group", "value": g} for g in groups]
        + [{"type": "resource", "value": r} for r in resources]
    )
    for i, it in enumerate(items):
        it["i"] = i  # global index across the whole run, batch-scoped on output

    estimate(len(items))

    batches = [items[i : i + BATCH_SIZE] for i in range(0, len(items), BATCH_SIZE)]
    # Re-index each batch locally so the prompt can reference 0..N-1.
    batches_local = [[{"i": j, "type": it["type"], "value": it["value"]}
                      for j, it in enumerate(b)] for b in batches]

    print(f"Dispatching {len(batches)} batches...\n")
    start = time.time()
    outputs: list[dict] = []
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as ex:
        futures = {ex.submit(run_batch, i, b): i
                   for i, b in enumerate(batches_local)}
        for fut in tqdm(as_completed(futures), total=len(futures), desc="meta"):
            outputs.append(fut.result())
    elapsed = time.time() - start

    # Assemble: for each (type, value) recover the meta_category.
    mapping: dict[tuple[str, str], str] = {}
    ok_batches, bad_batches = 0, 0
    tin = tout = 0
    for o in outputs:
        if o.get("status") == "error":
            bad_batches += 1
            continue
        ok_batches += 1
        tin += o.get("input_tokens", 0)
        tout += o.get("output_tokens", 0)
        parsed = o.get("parsed")
        if not isinstance(parsed, list):
            continue
        items_b = o["items"]
        for entry in parsed:
            if not isinstance(entry, dict):
                continue
            idx = entry.get("i")
            mc = entry.get("meta_category")
            if idx is None or mc is None or idx >= len(items_b):
                continue
            it = items_b[idx]
            mapping[(it["type"], it["value"])] = str(mc).strip().lower()

    cost = tin / 1e6 * PRICE_IN + tout / 1e6 * PRICE_OUT

    # Write group and resource mapping TSVs
    group_map = pd.DataFrame(
        [(v, mapping.get(("group", v), "")) for v in groups],
        columns=["group", "group_meta_category"],
    )
    res_map = pd.DataFrame(
        [(v, mapping.get(("resource", v), "")) for v in resources],
        columns=["resource", "resource_meta_category"],
    )
    group_map.to_csv(OUT_GROUP_MAP, sep="\t", index=False)
    res_map.to_csv(OUT_RES_MAP, sep="\t", index=False)

    # Merge back into both scored corpora
    for src, out in [(SRC_MAIN, OUT_MAIN), (SRC_R100, OUT_R100)]:
        df = pd.read_csv(src, sep="\t")
        df = df.merge(group_map, on="group", how="left")
        df = df.merge(res_map, on="resource", how="left")
        df.to_csv(out, sep="\t", index=False)

    # Report
    print(f"\n{'=' * 60}")
    print(f"Done in {elapsed / 60:.1f} min  ({elapsed:.0f}s)")
    print(f"OK batches:    {ok_batches}  |  Errored: {bad_batches}")
    print(f"Items mapped:  {len(mapping)} / {len(items)}")
    print(f"Input tokens:  {tin:>12,}")
    print(f"Output tokens: {tout:>12,}")
    print(f"Cost (USD):    ${cost:>12.4f}")

    n_distinct_group_cats = group_map["group_meta_category"].replace("", pd.NA).dropna().nunique()
    n_distinct_res_cats = res_map["resource_meta_category"].replace("", pd.NA).dropna().nunique()
    print(f"\nDistinct meta-categories emitted — groups: {n_distinct_group_cats}  "
          f"resources: {n_distinct_res_cats}")

    print(f"\nGroup meta-category top 15:")
    print(group_map["group_meta_category"].value_counts().head(15).to_string())
    print(f"\nResource meta-category top 15:")
    print(res_map["resource_meta_category"].value_counts().head(15).to_string())

    (CACHE_DIR / "_run_log.json").write_text(json.dumps({
        "model": MODEL,
        "prompt": PROMPT_FILE.name,
        "batch_size": BATCH_SIZE,
        "max_parallel": MAX_PARALLEL,
        "n_items": len(items),
        "n_groups": len(groups),
        "n_resources": len(resources),
        "mapped": len(mapping),
        "n_distinct_group_metas": int(n_distinct_group_cats),
        "n_distinct_resource_metas": int(n_distinct_res_cats),
        "ok_batches": ok_batches,
        "errored_batches": bad_batches,
        "input_tokens": tin,
        "output_tokens": tout,
        "cost_usd": round(cost, 4),
        "elapsed_sec": round(elapsed, 1),
    }, indent=2))
    print(f"\nMaps:   {OUT_GROUP_MAP.relative_to(ROOT)}  |  "
          f"{OUT_RES_MAP.relative_to(ROOT)}")
    print(f"Merged: {OUT_MAIN.relative_to(ROOT)}  |  "
          f"{OUT_R100.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
