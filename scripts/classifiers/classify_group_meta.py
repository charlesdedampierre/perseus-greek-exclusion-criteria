"""Map every distinct `group` surface string to one of 27 canonical groups.

Uses prompt_group_meta_V3.md, which anchors on an explicit canonical
list consolidated from the top-50 raw groups. The model may introduce
a new canonical ONLY when the item sits at the same conceptual level
as the existing ones but does not fit any.

Reads:
  - data/processed_data/rules_all_scored_with_polity_time.tsv
  - data/processed_data/rules_random100_with_polity_time.tsv

Writes:
  - data/processed_data/group_meta_category_v3.tsv       group → group_meta
  - data/processed_data/rules_all_with_group_meta.tsv    662 rules + group_meta
  - data/processed_data/rules_random100_with_group_meta.tsv  946 rules + group_meta
  - data/llm_results/group_meta_v3/_batch_NNNN.json      per-batch cache
  - data/llm_results/group_meta_v3/_run_log.json
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
PROMPT_FILE = ROOT / "scripts/classifiers/prompt/prompt_group_meta_V3.md"
SRC_MAIN = ROOT / "data/processed_data/rules_all_scored_with_polity_time.tsv"
SRC_R100 = ROOT / "data/processed_data/rules_random100_with_polity_time.tsv"
CACHE_DIR = ROOT / "data/llm_results/group_meta_v3"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

OUT_MAP = ROOT / "data/processed_data/group_meta_category_v3.tsv"
OUT_MAIN = ROOT / "data/processed_data/rules_all_with_group_meta.tsv"
OUT_R100 = ROOT / "data/processed_data/rules_random100_with_group_meta.tsv"

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
        "Map each of the following group strings to one canonical group "
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


def collect_groups() -> list[str]:
    seen = set()
    for src in (SRC_MAIN, SRC_R100):
        df = pd.read_csv(src, sep="\t")
        for v in df["group"].dropna().astype(str):
            s = v.strip()
            if s:
                seen.add(s)
    return sorted(seen)


def main() -> None:
    groups = collect_groups()
    print(f"Distinct groups to classify: {len(groups)}")
    print(f"Model:   {MODEL}")
    print(f"Prompt:  {PROMPT_FILE.name}")
    print(f"Cache:   {CACHE_DIR.relative_to(ROOT)}\n")

    items = [{"i": i, "value": g} for i, g in enumerate(groups)]
    batches = [items[i : i + BATCH_SIZE] for i in range(0, len(items), BATCH_SIZE)]
    batches_local = [[{"i": j, "value": it["value"]}
                      for j, it in enumerate(b)] for b in batches]

    print(f"Dispatching {len(batches)} batches...\n")
    start = time.time()
    outputs: list[dict] = []
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as ex:
        futures = {ex.submit(run_batch, i, b): i
                   for i, b in enumerate(batches_local)}
        for fut in tqdm(as_completed(futures), total=len(futures), desc="group_meta"):
            outputs.append(fut.result())
    elapsed = time.time() - start

    mapping: dict[str, str] = {}      # joined "A;B"
    mapping_list: dict[str, list[str]] = {}
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
            gm = entry.get("group_meta") or entry.get("meta_category")
            if idx is None or gm is None:
                continue
            try:
                idx = int(idx)
            except (TypeError, ValueError):
                continue
            if idx < 0 or idx >= len(items_b):
                continue
            if isinstance(gm, str):
                labels = [gm.strip()]
            elif isinstance(gm, list):
                labels = [str(x).strip() for x in gm if str(x).strip()]
            else:
                continue
            labels = [l for l in labels if l]
            if not labels:
                continue
            mapping_list[items_b[idx]["value"]] = labels
            mapping[items_b[idx]["value"]] = ";".join(labels)

    cost = tin / 1e6 * PRICE_IN + tout / 1e6 * PRICE_OUT

    df_map = pd.DataFrame(
        [(g, mapping.get(g, "")) for g in groups],
        columns=["group", "group_meta"],
    )
    df_map.to_csv(OUT_MAP, sep="\t", index=False)

    for src, out in [(SRC_MAIN, OUT_MAIN), (SRC_R100, OUT_R100)]:
        df = pd.read_csv(src, sep="\t")
        df = df.merge(df_map, on="group", how="left")
        df.to_csv(out, sep="\t", index=False)

    CANONICAL_KNOWN = {
        "Citizens", "Slaves", "The wealthy", "Women", "Foreigners", "The poor",
        "Minors", "Men", "Magistrates", "Priests", "Nobles", "Philosophers",
        "The educated", "Kings", "Poets", "Heirs", "Artisans", "Christians",
        "Soldiers", "Greeks", "Jews", "Exiles", "Wives", "Spartans", "Syrians",
        "The multitude", "Orphans",
        "Elders", "Sick", "Sailors", "Other",
    }

    # Flatten multi-label cells for hit counting.
    flat_labels: list[str] = []
    for labels in mapping_list.values():
        flat_labels.extend(labels)
    vc = pd.Series(flat_labels).value_counts()
    canonical_hits = vc[vc.index.isin(CANONICAL_KNOWN)]
    new_hits = vc[~vc.index.isin(CANONICAL_KNOWN)]

    print(f"\n{'=' * 60}")
    print(f"Done in {elapsed / 60:.1f} min  ({elapsed:.0f}s)")
    print(f"OK batches: {ok}  |  Errored: {bad}")
    print(f"Groups mapped: {len(mapping)} / {len(groups)}")
    print(f"Input tokens:  {tin:>12,}")
    print(f"Output tokens: {tout:>12,}")
    print(f"Cost (USD):    ${cost:>12.4f}")

    print(f"\nCanonical hits (of 27 canonicals) — how many distinct groups map to each:")
    print(canonical_hits.to_string())

    print(f"\nNew canonicals introduced ({len(new_hits)}):")
    if len(new_hits):
        print(new_hits.to_string())
    else:
        print("  (none — every group fitted an existing canonical)")

    # Also report by rule count (one rule counts once per canonical in its cell).
    all_rules = pd.concat([pd.read_csv(s, sep="\t") for s in (SRC_MAIN, SRC_R100)],
                          ignore_index=True)
    all_rules = all_rules.merge(df_map, on="group", how="left")
    exploded = (all_rules["group_meta"].fillna("")
                .str.split(";").explode().str.strip())
    vc_rules = exploded[exploded != ""].value_counts()
    print(f"\nRule-count by canonical group (one rule × each of its labels, top 30):")
    print(vc_rules.head(30).to_string())

    n_multi = sum(1 for v in mapping_list.values() if len(v) > 1)
    print(f"\nMulti-label groups: {n_multi} / {len(mapping_list)} "
          f"({100*n_multi/max(1,len(mapping_list)):.0f}%)")

    (CACHE_DIR / "_run_log.json").write_text(json.dumps({
        "model": MODEL,
        "prompt": PROMPT_FILE.name,
        "n_groups": len(groups),
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
