"""Map every distinct `resource` surface string to one of 39 canonicals.

Uses prompt_resource_meta_V3.md, anchored on 39 canonicals (16 from the
top-20 consolidation + 23 from the top-50-to-100 consolidation). Model
may introduce a new canonical only when the item does not fit any.

Reads:
  - data/processed_data/rules_all_scored_with_polity_time.tsv
  - data/processed_data/rules_random100_with_polity_time.tsv

Writes:
  - data/processed_data/resource_meta_category_v3.tsv    resource → resource_meta
  - data/processed_data/rules_all_with_resource_meta.tsv    662 rules + resource_meta
  - data/processed_data/rules_random100_with_resource_meta.tsv 946 rules + resource_meta
  - data/llm_results/resource_meta_v3/_batch_NNNN.json      per-batch cache
  - data/llm_results/resource_meta_v3/_run_log.json
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
PROMPT_FILE = ROOT / "scripts/classifiers/prompt/prompt_resource_meta_V3.md"
SRC_MAIN = ROOT / "data/processed_data/rules_all_scored_with_polity_time.tsv"
SRC_R100 = ROOT / "data/processed_data/rules_random100_with_polity_time.tsv"
CACHE_DIR = ROOT / "data/llm_results/resource_meta_v3"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

OUT_MAP = ROOT / "data/processed_data/resource_meta_category_v3.tsv"
OUT_MAIN = ROOT / "data/processed_data/rules_all_with_resource_meta.tsv"
OUT_R100 = ROOT / "data/processed_data/rules_random100_with_resource_meta.tsv"

CANONICAL_39 = {
    "Eligibility for public office", "Protection from corporal punishment",
    "Right to retain property", "Right to inherit property", "Political power",
    "Protection from capital punishment", "Right to retain own earnings",
    "Protection from enslavement", "Right to address the assembly",
    "Right to own land", "Right to vote in the Ekklesia",
    "Exemption from compulsory public financing", "Access to the gymnasium",
    "Protection from legal prosecution", "Right to valid professional opinion",
    "Right to reside in the city",
    "Right to citizenship", "Right to free speech", "Access to religious rites",
    "Access to public honors", "Right to burial", "Right to a dowry",
    "Right to adopt", "Right to freedom of movement", "Right to bodily autonomy",
    "Right to bear arms", "Exemption from taxes", "Exemption from manual labor",
    "Right to a legal trial", "Protection from arbitrary banishment",
    "Protection from public libel", "Exemption from legal audit",
    "Right to own property", "Right to dispose of property",
    "Right to speak first in assembly", "Right to remuneration for office",
    "Right to drink wine", "Right to professional judgement",
    "Right to inherit divine covenant",
}

MODEL = "google/gemini-3-flash-preview"
PRICE_IN = 0.50
PRICE_OUT = 3.00
MAX_OUTPUT_TOKENS = 8_000

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
        "Map each of the following resource strings to one canonical "
        "per the rules above. Return JSON only.\n\n"
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


def collect_resources() -> list[str]:
    seen = set()
    for src in (SRC_MAIN, SRC_R100):
        df = pd.read_csv(src, sep="\t")
        for v in df["resource"].dropna().astype(str):
            s = v.strip()
            if s:
                seen.add(s)
    return sorted(seen)


def main() -> None:
    resources = collect_resources()
    print(f"Distinct resources to classify: {len(resources)}")
    print(f"Model:   {MODEL}")
    print(f"Prompt:  {PROMPT_FILE.name}")
    print(f"Cache:   {CACHE_DIR.relative_to(ROOT)}\n")

    items = [{"i": i, "value": r} for i, r in enumerate(resources)]
    batches = [items[i : i + BATCH_SIZE] for i in range(0, len(items), BATCH_SIZE)]
    batches_local = [[{"i": j, "value": it["value"]}
                      for j, it in enumerate(b)] for b in batches]

    print(f"Dispatching {len(batches)} batches...\n")
    start = time.time()
    outputs: list[dict] = []
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as ex:
        futures = {ex.submit(run_batch, i, b): i
                   for i, b in enumerate(batches_local)}
        for fut in tqdm(as_completed(futures), total=len(futures), desc="resource_meta"):
            outputs.append(fut.result())
    elapsed = time.time() - start

    mapping: dict[str, str] = {}
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
            rm = entry.get("resource_meta") or entry.get("meta_category")
            if idx is None or rm is None:
                continue
            try:
                idx = int(idx)
            except (TypeError, ValueError):
                continue
            if idx < 0 or idx >= len(items_b):
                continue
            mapping[items_b[idx]["value"]] = str(rm).strip()

    cost = tin / 1e6 * PRICE_IN + tout / 1e6 * PRICE_OUT

    df_map = pd.DataFrame(
        [(r, mapping.get(r, "")) for r in resources],
        columns=["resource", "resource_meta"],
    )
    df_map.to_csv(OUT_MAP, sep="\t", index=False)

    for src, out in [(SRC_MAIN, OUT_MAIN), (SRC_R100, OUT_R100)]:
        df = pd.read_csv(src, sep="\t")
        df = df.merge(df_map, on="resource", how="left")
        df.to_csv(out, sep="\t", index=False)

    vc = df_map["resource_meta"].replace("", pd.NA).dropna().value_counts()
    canonical_hits = vc[vc.index.isin(CANONICAL_39)]
    new_hits = vc[~vc.index.isin(CANONICAL_39)]

    print(f"\n{'=' * 70}")
    print(f"Done in {elapsed / 60:.1f} min  ({elapsed:.0f}s)")
    print(f"OK batches: {ok}  |  Errored: {bad}")
    print(f"Resources mapped: {len(mapping)} / {len(resources)}")
    print(f"Input tokens:  {tin:>12,}")
    print(f"Output tokens: {tout:>12,}")
    print(f"Cost (USD):    ${cost:>12.4f}")

    print(f"\nCanonical hits (of 39) — distinct resources mapping to each:")
    print(canonical_hits.to_string())

    print(f"\nNew canonicals introduced ({len(new_hits)}):")
    if len(new_hits):
        print(new_hits.head(40).to_string())

    # Rule-count by canonical
    all_rules = pd.concat([pd.read_csv(s, sep="\t") for s in (SRC_MAIN, SRC_R100)],
                          ignore_index=True)
    all_rules = all_rules.merge(df_map, on="resource", how="left")
    vc_rules = all_rules["resource_meta"].replace("", pd.NA).dropna().value_counts()
    print(f"\nRule-count by canonical resource (top 40):")
    print(vc_rules.head(40).to_string())
    print(f"\nTotal rules covered by top 39: "
          f"{int(vc_rules[vc_rules.index.isin(CANONICAL_39)].sum())} "
          f"/ {int(vc_rules.sum())}")

    (CACHE_DIR / "_run_log.json").write_text(json.dumps({
        "model": MODEL,
        "prompt": PROMPT_FILE.name,
        "n_resources": len(resources),
        "mapped": len(mapping),
        "n_canonical_hits": int(len(canonical_hits)),
        "n_new_canonicals": int(len(new_hits)),
        "ok_batches": ok,
        "errored_batches": bad,
        "input_tokens": tin,
        "output_tokens": tout,
        "cost_usd": round(cost, 4),
        "elapsed_sec": round(elapsed, 1),
    }, indent=2))
    print(f"\nMap: {OUT_MAP.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
