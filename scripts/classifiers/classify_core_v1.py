"""Run core_prompt_V1.md against the 10-work sample.

Parallelism is at the **chunk** level, not the work level — every (work, chunk)
pair is a separate task submitted to a single `ThreadPoolExecutor`. A previous
work-level version left 9/10 workers idle while one worker processed Aristotle
*Politics* (41 chunks) serially; the chunk-level version keeps every worker
busy for the whole run.

Reads:
  - data/processed_data/final_dataset_for_criteria_sample.tsv
  - scripts/classifiers/prompt/core_prompt_V1.md
  - data/full_text/{file_path}.txt   (or data/full_text_copyrights_added/...)

Writes:
  - data/llm_results/core_v1/{file_id}.json    one merged result per work
  - data/llm_results/core_v1/_run_log.json     aggregate token + cost log

Model is the project default declared in MODEL.md
(`google/gemini-3-flash-preview`, $0.50 in / $3.00 out per 1M tokens).
"""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from tqdm import tqdm

# === Paths ===
ROOT = Path(__file__).resolve().parents[2]


def _resolve(env_key: str, default: Path) -> Path:
    """Read env var; if set as a relative path, resolve it against ROOT."""
    val = os.getenv(env_key)
    if val is None:
        return default
    p = Path(val)
    return p if p.is_absolute() else (ROOT / p)


# Override via env vars: SAMPLE_TSV=path OUT_DIR=path python classify_core_v1.py
SAMPLE_TSV = _resolve("SAMPLE_TSV",
                      ROOT / "data/processed_data/final_dataset_for_criteria_sample.tsv")
PROMPT_FILE = ROOT / "scripts/classifiers/prompt/core_prompt_V1.md"
TEXT_ROOT = ROOT / "data/full_text"
COPYRIGHT_ROOT = ROOT / "data"  # for paths starting with full_text_copyrights_added/
OUT_DIR = _resolve("OUT_DIR", ROOT / "data/llm_results/core_v1")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# === Model (must match MODEL.md) ===
MODEL = "google/gemini-3-flash-preview"
PRICE_IN = 0.50
PRICE_OUT = 3.00
MAX_OUTPUT_TOKENS = 32_000

# === Runtime ===
MAX_PAGES_PER_CHUNK = 15
CHARS_PER_PAGE = 1000
MAX_PARALLEL = 10

# === Setup ===
load_dotenv(ROOT / ".env")
api_key = os.getenv("OPEN_ROUTER_API")
if not api_key:
    raise RuntimeError("OPEN_ROUTER_API not found in .env")

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
SYSTEM_PROMPT = PROMPT_FILE.read_text()


def resolve_text_path(file_path: str) -> Path:
    if file_path.startswith("full_text_copyrights_added/"):
        return COPYRIGHT_ROOT / file_path
    return TEXT_ROOT / file_path.replace(".xml", ".txt")


def number_paragraphs(content: str) -> str:
    out = []
    for i, p in enumerate(content.split("\n\n"), 1):
        p = p.strip()
        if p:
            out.append(f"[§{i}] {p}")
    return "\n\n".join(out)


def chunk_text(content: str) -> list[str]:
    content = number_paragraphs(content)
    max_chars = MAX_PAGES_PER_CHUNK * CHARS_PER_PAGE
    if len(content) <= max_chars:
        return [content]
    chunks, current, current_len = [], [], 0
    for p in content.split("\n\n"):
        plen = len(p) + 2
        if current and current_len + plen > max_chars:
            chunks.append("\n\n".join(current))
            current, current_len = [p], plen
        else:
            current.append(p)
            current_len += plen
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def call_model(row: dict, chunk: str, chunk_idx: int, n_chunks: int) -> dict:
    chunk_info = f" (chunk {chunk_idx}/{n_chunks})" if n_chunks > 1 else ""
    user_msg = (
        f"**Work:** {row['perseus_title']}{chunk_info}\n"
        f"**Author:** {row['perseus_author']}\n"
        f"**Year:** {row['year']}\n"
        f"**Period:** {row['period']}\n\n"
        f"---BEGIN TEXT---\n{chunk}\n---END TEXT---\n\n"
        "Analyze the text paragraph by paragraph (each marked with [§N]). "
        "Extract every valid rule per the core prompt's step-by-step process. "
        "Return JSON only, no markdown fences, no commentary."
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

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {
            "_raw_response": raw,
            "_parse_error": True,
            "extracted_rules": [],
        }

    return {
        "parsed": parsed,
        "input_tokens": getattr(resp.usage, "prompt_tokens", 0) or 0,
        "output_tokens": getattr(resp.usage, "completion_tokens", 0) or 0,
    }


def merge_chunks(chunk_results: list[dict]) -> dict:
    rules, seen = [], set()
    for cr in chunk_results:
        for entry in cr["parsed"].get("extracted_rules", []) or []:
            if not isinstance(entry, dict):
                continue
            key = (
                str(entry.get("group", "")).strip().lower(),
                str(entry.get("resource", "")).strip().lower(),
                str(entry.get("rule", "")).strip().lower(),
            )
            if key in seen:
                continue
            seen.add(key)
            rules.append(entry)
    return {"extracted_rules": rules}


def build_tasks(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Flatten every (work, chunk) into a single task list.

    Returns:
        tasks   — list of dicts {fid, row, chunk_idx, n_chunks, chunk}
        cached  — list of dicts for works already fully classified on disk
    """
    tasks, cached = [], []
    for row in rows:
        fid = row["file_id"]
        out_path = OUT_DIR / f"{fid}.json"
        if out_path.exists():
            existing = json.loads(out_path.read_text())
            cached.append({
                "file_id": fid,
                "status": "cached",
                "input_tokens": existing.get("_input_tokens", 0),
                "output_tokens": existing.get("_output_tokens", 0),
                "n_rules": len(existing.get("extracted_rules", [])),
            })
            continue

        text_path = resolve_text_path(row["file_path"])
        if not text_path.exists():
            cached.append({"file_id": fid, "status": "missing_text", "error": str(text_path)})
            continue

        chunks = chunk_text(text_path.read_text())
        for i, c in enumerate(chunks, 1):
            tasks.append({
                "file_id": fid,
                "row": row,
                "chunk_idx": i,
                "n_chunks": len(chunks),
                "chunk": c,
            })
    return tasks, cached


def run_chunk(task: dict) -> dict:
    try:
        out = call_model(task["row"], task["chunk"], task["chunk_idx"], task["n_chunks"])
        return {
            "file_id": task["file_id"],
            "chunk_idx": task["chunk_idx"],
            "n_chunks": task["n_chunks"],
            "parsed": out["parsed"],
            "input_tokens": out["input_tokens"],
            "output_tokens": out["output_tokens"],
            "status": "ok",
        }
    except Exception as e:
        return {
            "file_id": task["file_id"],
            "chunk_idx": task["chunk_idx"],
            "n_chunks": task["n_chunks"],
            "status": "error",
            "error": str(e),
        }


def write_work_output(fid: str, row: dict, chunk_results: list[dict]) -> dict:
    chunk_results = sorted(chunk_results, key=lambda x: x["chunk_idx"])
    final = (
        chunk_results[0]["parsed"]
        if len(chunk_results) == 1
        else merge_chunks(chunk_results)
    )
    final["_file_id"] = fid
    final["_perseus_author"] = row["perseus_author"]
    final["_perseus_title"] = row["perseus_title"]
    final["_period"] = row["period"]
    final["_n_chunks"] = len(chunk_results)
    final["_input_tokens"] = sum(r["input_tokens"] for r in chunk_results)
    final["_output_tokens"] = sum(r["output_tokens"] for r in chunk_results)
    final["_model"] = MODEL
    final["_prompt"] = PROMPT_FILE.name
    (OUT_DIR / f"{fid}.json").write_text(
        json.dumps(final, indent=2, ensure_ascii=False)
    )
    return {
        "file_id": fid,
        "status": "ok",
        "n_chunks": len(chunk_results),
        "input_tokens": final["_input_tokens"],
        "output_tokens": final["_output_tokens"],
        "n_rules": len(final.get("extracted_rules", [])),
    }


def estimate_run(rows: list[dict]) -> None:
    sys_tok = len(SYSTEM_PROMPT) / 4
    total_chunks = 0
    total_content_chars = 0
    for r in rows:
        p = resolve_text_path(r["file_path"])
        if not p.exists():
            continue
        n = len(p.read_text())
        total_content_chars += n
        total_chunks += max(1, -(-n // (MAX_PAGES_PER_CHUNK * CHARS_PER_PAGE)))

    in_tok = total_content_chars / 4 + total_chunks * sys_tok
    out_tok = in_tok * 0.20  # calibrated from 2026-04-20 run (actual ≈17%)
    cost = in_tok / 1e6 * PRICE_IN + out_tok / 1e6 * PRICE_OUT
    SEC_PER_CALL = 20  # calibrated — chunk-level parallelism keeps every worker busy
    rounds = -(-total_chunks // MAX_PARALLEL)
    eta_min = rounds * SEC_PER_CALL / 60

    print("--- pre-run estimate ---")
    print(f"  chunks total:          {total_chunks}")
    print(f"  parallel workers:      {MAX_PARALLEL}  (~{rounds} rounds)")
    print(f"  wall-clock (rough):    {eta_min:.1f} min  (~{SEC_PER_CALL}s/call, chunk-level parallel)")
    print(f"  input tokens (est.):   {in_tok:>12,.0f}")
    print(f"  output tokens (est.):  {out_tok:>12,.0f}  (20% of input)")
    print(f"  cost (USD, est.):      ${cost:.4f}")
    print("------------------------\n")


def main() -> None:
    df = pd.read_csv(SAMPLE_TSV, sep="\t")
    rows = df.to_dict("records")
    print(f"Loaded {len(rows)} works from {SAMPLE_TSV.name}")
    print(f"Model:   {MODEL}")
    print(f"Prompt:  {PROMPT_FILE.name}")
    print(f"Out:     {OUT_DIR.relative_to(ROOT)}")
    print(f"Workers: {MAX_PARALLEL}\n")
    estimate_run(rows)

    tasks, cached = build_tasks(rows)
    print(f"Already cached:   {len(cached)}  works (skipping)")
    print(f"To classify now:  {sum({t['file_id'] for t in tasks}.__len__() for _ in [0])} works "
          f"/ {len(tasks)} chunks\n")

    if not tasks:
        print("Nothing to do — all works cached.")
        return

    # Parallel execution at chunk granularity.
    row_by_fid = {t["file_id"]: t["row"] for t in tasks}
    chunks_by_fid: dict[str, list[dict]] = defaultdict(list)
    chunk_errors: list[dict] = []

    start = time.time()
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as ex:
        futures = {ex.submit(run_chunk, t): t for t in tasks}
        for fut in tqdm(as_completed(futures), total=len(futures), desc="chunks"):
            r = fut.result()
            if r["status"] == "ok":
                chunks_by_fid[r["file_id"]].append(r)
            else:
                chunk_errors.append(r)

    # Assemble per-work outputs from completed chunks.
    results = list(cached)
    for fid, chunk_list in chunks_by_fid.items():
        # If any chunk for this fid errored, skip writing the work output.
        errored_fids = {e["file_id"] for e in chunk_errors}
        if fid in errored_fids:
            results.append({"file_id": fid, "status": "error",
                            "error": "one or more chunks failed"})
            continue
        # Sanity: we must have all N chunks before writing.
        expected = chunk_list[0]["n_chunks"]
        if len(chunk_list) != expected:
            results.append({"file_id": fid, "status": "error",
                            "error": f"got {len(chunk_list)}/{expected} chunks"})
            continue
        results.append(write_work_output(fid, row_by_fid[fid], chunk_list))

    elapsed = time.time() - start
    ok = [r for r in results if r["status"] in ("ok", "cached")]
    bad = [r for r in results if r["status"] not in ("ok", "cached")]
    tin = sum(r.get("input_tokens", 0) for r in ok)
    tout = sum(r.get("output_tokens", 0) for r in ok)
    cost = tin / 1e6 * PRICE_IN + tout / 1e6 * PRICE_OUT
    rules_total = sum(r.get("n_rules", 0) for r in ok)

    print(f"\n{'=' * 60}")
    print(f"Done in {elapsed / 60:.1f} min  ({elapsed:.0f}s)")
    print(f"OK: {len(ok)}  |  Errors: {len(bad)}")
    print(f"Chunk errors: {len(chunk_errors)}")
    print(f"Total rules extracted: {rules_total}")
    print(f"Input tokens:  {tin:>12,}")
    print(f"Output tokens: {tout:>12,}")
    print(f"Cost (USD):    ${cost:>12.4f}")
    if bad:
        print("\nWork-level errors:")
        for e in bad[:10]:
            print(f"  {e['file_id']}: {e.get('error', e['status'])[:120]}")
    if chunk_errors:
        print("\nChunk-level errors (first 10):")
        for e in chunk_errors[:10]:
            print(f"  {e['file_id']} chunk {e['chunk_idx']}/{e['n_chunks']}: {e.get('error','')[:120]}")

    (OUT_DIR / "_run_log.json").write_text(json.dumps({
        "model": MODEL,
        "prompt": PROMPT_FILE.name,
        "sample": SAMPLE_TSV.name,
        "parallelism": "chunk-level",
        "max_parallel": MAX_PARALLEL,
        "n_works": len(rows),
        "ok": len(ok),
        "errors": len(bad),
        "chunk_errors": len(chunk_errors),
        "rules_total": rules_total,
        "input_tokens": tin,
        "output_tokens": tout,
        "price_in_per_1M": PRICE_IN,
        "price_out_per_1M": PRICE_OUT,
        "cost_usd": round(cost, 4),
        "elapsed_sec": round(elapsed, 1),
        "results": results,
    }, indent=2))
    print(f"\nRun log: {(OUT_DIR / '_run_log.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
