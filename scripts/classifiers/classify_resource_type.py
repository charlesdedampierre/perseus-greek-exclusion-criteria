"""Map every distinct `resource_meta` canonical to one or more of 8 big
meta-categories:

    Bodily Autonomy, Legal Standing, Household Authority, Material
    Wealth, Education, Political Power, Honor, Religious Standing

Uses prompt_resource_type_V1.md. A resource can belong to several
categories (e.g. `Right to own land` = Material Wealth + Legal
Standing). Unclassifiable items are left blank in the final TSV.

Reads:
  - data/processed_data/rules_final_dataset_130works_april_2026.tsv

Writes:
  - data/processed_data/resource_type_map_v1.tsv
        resource_meta -> resource_type (semicolon-joined)
  - data/processed_data/rules_final_dataset_130works_april_2026.tsv
        same file, with `resource_type` column added / overwritten
  - data/llm_results/resource_type_v1/_batch_NNNN.json per-batch cache
  - data/llm_results/resource_type_v1/_run_log.json
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
PROMPT_FILE = ROOT / "scripts/classifiers/prompt/prompt_resource_type_V1.md"
DATA_FILE = ROOT / "data/processed_data/rules_final_dataset_130works_april_2026.tsv"
CACHE_DIR = ROOT / "data/llm_results/resource_type_v1"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

OUT_MAP = ROOT / "data/processed_data/resource_type_map_v1.tsv"

CATEGORIES_8 = {
    "Bodily Autonomy",
    "Legal Standing",
    "Household Authority",
    "Material Wealth",
    "Education",
    "Political Power",
    "Honor",
    "Religious Standing",
}

MODEL = "google/gemini-3-flash-preview"
PRICE_IN = 0.50
PRICE_OUT = 3.00
MAX_OUTPUT_TOKENS = 4_000

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
        try:
            return json.loads(_TRAILING_COMMA.sub(r"\1", raw))
        except json.JSONDecodeError:
            return {"_parse_error": True, "_raw": raw}


def call_model(batch: list[dict]) -> dict:
    user_msg = (
        "Classify each of the following canonical resource strings into "
        "one or more of the 8 meta-categories per the rules above. "
        "Return JSON only.\n\n"
        f"INPUT ({len(batch)} items):\n"
        f"{json.dumps(batch, ensure_ascii=False)}"
    )
    resp = client.chat.completions.create(
        model=MODEL,
        max_tokens=MAX_OUTPUT_TOKENS,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    )
    raw = (resp.choices[0].message.content or "").strip()
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
    cache = CACHE_DIR / f"_batch_{batch_idx:04d}.json"
    if cache.exists():
        return {**json.loads(cache.read_text()), "status": "cached"}
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
        cache.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        return result
    except Exception as e:
        return {
            "batch_idx": batch_idx,
            "n_items": len(batch),
            "items": batch,
            "status": "error",
            "error": str(e),
        }


def normalize_types(raw) -> list[str]:
    """Return a clean list of valid category labels, preserving order."""
    if raw is None:
        return []
    if isinstance(raw, str):
        parts = [p.strip() for p in re.split(r"[;,]", raw)]
    elif isinstance(raw, list):
        parts = [str(p).strip() for p in raw]
    else:
        return []
    seen, out = set(), []
    for p in parts:
        if not p or p in seen:
            continue
        if p == "UNCLASSIFIABLE":
            return ["UNCLASSIFIABLE"]
        if p in CATEGORIES_8:
            seen.add(p)
            out.append(p)
    return out


def collect_resource_metas() -> list[str]:
    df = pd.read_csv(DATA_FILE, sep="\t")
    vals = (
        df["resource_meta"].dropna().astype(str).str.strip()
        .replace("", pd.NA).dropna().unique().tolist()
    )
    return sorted(vals)


def main() -> None:
    resource_metas = collect_resource_metas()
    print(f"Distinct resource_meta values: {len(resource_metas)}")
    print(f"Model:   {MODEL}")
    print(f"Prompt:  {PROMPT_FILE.name}")
    print(f"Cache:   {CACHE_DIR.relative_to(ROOT)}\n")

    items = [{"i": i, "value": r} for i, r in enumerate(resource_metas)]
    batches = [items[i : i + BATCH_SIZE] for i in range(0, len(items), BATCH_SIZE)]
    batches_local = [
        [{"i": j, "value": it["value"]} for j, it in enumerate(b)]
        for b in batches
    ]

    print(f"Dispatching {len(batches)} batches...\n")
    start = time.time()
    outputs: list[dict] = []
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as ex:
        futures = {
            ex.submit(run_batch, i, b): i for i, b in enumerate(batches_local)
        }
        for fut in tqdm(as_completed(futures), total=len(futures), desc="resource_type"):
            outputs.append(fut.result())
    elapsed = time.time() - start

    mapping: dict[str, list[str]] = {}
    ok, bad, tin, tout = 0, 0, 0, 0
    for o in outputs:
        if o.get("status") == "error":
            bad += 1
            continue
        ok += 1
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
            rt = entry.get("resource_type") or entry.get("resource_types")
            if idx is None or rt is None:
                continue
            try:
                idx = int(idx)
            except (TypeError, ValueError):
                continue
            if idx < 0 or idx >= len(items_b):
                continue
            mapping[items_b[idx]["value"]] = normalize_types(rt)

    cost = tin / 1e6 * PRICE_IN + tout / 1e6 * PRICE_OUT

    # Build map TSV (store joined list; blank string when unclassifiable / missing)
    rows = []
    for rm in resource_metas:
        types = mapping.get(rm, [])
        joined = "" if not types or types == ["UNCLASSIFIABLE"] else "; ".join(types)
        rows.append((rm, joined))
    df_map = pd.DataFrame(rows, columns=["resource_meta", "resource_type"])
    df_map.to_csv(OUT_MAP, sep="\t", index=False)

    # Merge back onto the rules dataset; overwrite if resource_type already exists.
    df = pd.read_csv(DATA_FILE, sep="\t")
    if "resource_type" in df.columns:
        df = df.drop(columns=["resource_type"])
    df = df.merge(df_map, on="resource_meta", how="left")
    df["resource_type"] = df["resource_type"].fillna("")
    df.to_csv(DATA_FILE, sep="\t", index=False)

    # Reporting
    mapped_nonempty = sum(1 for v in mapping.values() if v and v != ["UNCLASSIFIABLE"])
    unclassifiable = sum(1 for v in mapping.values() if v == ["UNCLASSIFIABLE"])
    missing = len(resource_metas) - len(mapping)

    per_cat: dict[str, int] = {c: 0 for c in CATEGORIES_8}
    for v in mapping.values():
        for c in v:
            if c in per_cat:
                per_cat[c] += 1

    # rule-level counts
    exploded = df.assign(
        _types=df["resource_type"].fillna("").str.split(r"\s*;\s*")
    ).explode("_types")
    exploded["_types"] = exploded["_types"].str.strip()
    vc_rules = exploded.loc[exploded["_types"] != "", "_types"].value_counts()

    print(f"\n{'=' * 70}")
    print(f"Done in {elapsed:.1f}s  ({elapsed / 60:.2f} min)")
    print(f"OK batches: {ok}  |  Errored: {bad}")
    print(f"Resource_meta mapped: {mapped_nonempty} "
          f"(unclassifiable: {unclassifiable}, missing: {missing}) "
          f"/ {len(resource_metas)}")
    print(f"Input tokens:  {tin:>12,}")
    print(f"Output tokens: {tout:>12,}")
    print(f"Cost (USD):    ${cost:>12.4f}")

    print(f"\nDistinct resource_meta per category (of 45 canonicals):")
    for c in sorted(per_cat, key=per_cat.get, reverse=True):
        print(f"  {c:<22} {per_cat[c]:>3d}")

    print(f"\nRule-count per category (rows in dataset, multi-count):")
    print(vc_rules.to_string())

    (CACHE_DIR / "_run_log.json").write_text(json.dumps({
        "model": MODEL,
        "prompt": PROMPT_FILE.name,
        "n_resource_metas": len(resource_metas),
        "mapped": mapped_nonempty,
        "unclassifiable": unclassifiable,
        "missing": missing,
        "per_category_distinct": per_cat,
        "per_category_rules": {k: int(v) for k, v in vc_rules.items()},
        "ok_batches": ok,
        "errored_batches": bad,
        "input_tokens": tin,
        "output_tokens": tout,
        "cost_usd": round(cost, 4),
        "elapsed_sec": round(elapsed, 1),
    }, indent=2))

    print(f"\nMap:     {OUT_MAP.relative_to(ROOT)}")
    print(f"Dataset: {DATA_FILE.relative_to(ROOT)} (resource_type column written)")


if __name__ == "__main__":
    main()
