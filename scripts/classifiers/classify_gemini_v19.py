"""
Re-run rule extraction with prompt_V19 on the EXACT SAME works that appear in
`data/annotation/user_comments_sample60_v18.csv`. Saves one JSON per work in
`data/llm_results/gemini_v19/`.

Differences from classify_gemini_openrouter.py:
- Paths fixed for the current repo layout (no `perseus/` subfolder).
- Reads `prompt_V19.md`.
- Only processes file_ids present in the sample60 annotation file.
"""

import os
import json
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm
from openai import OpenAI

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent

META_TSV = HERE / "data/processed_data/perseus_works_wikidata.tsv"
SAMPLE_CSV = HERE / "data/annotation/user_comments_sample60_v18.csv"
PROMPT_FILE = HERE / "prompt/prompt_V19.md"
CLEAN_DIR = HERE / "data/canonical-greekLit/data_clean"
OUT_DIR = HERE / "data/llm_results/gemini_v19"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL = "google/gemini-3-flash-preview"
MAX_OUTPUT_TOKENS = 32000
MAX_PARALLEL = 20

MAX_PAGES_PER_CHUNK = 15
CHARS_PER_PAGE = 1000

PRICE_IN = 0.50
PRICE_OUT = 3.00

load_dotenv(REPO_ROOT / ".env")
API_KEY = os.getenv("OPEN_ROUTER_API")
if not API_KEY:
    raise RuntimeError("OPEN_ROUTER_API not found in .env")

with open(PROMPT_FILE) as f:
    SYSTEM_PROMPT = f.read()

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY)
    return _client


def number_paragraphs(content: str) -> str:
    paragraphs = content.split("\n\n")
    numbered = []
    for i, p in enumerate(paragraphs, 1):
        p = p.strip()
        if p:
            numbered.append(f"[§{i}] {p}")
    return "\n\n".join(numbered)


def chunk_text(content: str) -> list[str]:
    content = number_paragraphs(content)
    max_chars = MAX_PAGES_PER_CHUNK * CHARS_PER_PAGE
    if len(content) <= max_chars:
        return [content]
    paragraphs = content.split("\n\n")
    chunks, current, current_len = [], [], 0
    for p in paragraphs:
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


def call_gemini(row: dict, chunk_content: str, chunk_info: str = "") -> dict:
    user_msg = (
        f"**Work:** {row['perseus_title']}{chunk_info}\n"
        f"**Author:** {row['perseus_author']}\n"
        f"**Period:** {row['author_impact_date']}\n"
        f"**Pages:** {row['n_pages']}\n\n"
        f"---BEGIN TEXT---\n{chunk_content}\n---END TEXT---\n\n"
        f"Analyze the text paragraph by paragraph (each marked with [§N]). "
        f"Extract exclusion criteria. For each verbatim, indicate which paragraph(s) it comes from. "
        f"Return JSON only, no other text, no markdown fences."
    )
    client = _get_client()
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=MAX_OUTPUT_TOKENS,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    )
    raw = (response.choices[0].message.content or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"_raw_response": raw, "_parse_error": True, "extracted_rules": []}
    input_tokens = getattr(response.usage, "prompt_tokens", 0) or 0
    output_tokens = getattr(response.usage, "completion_tokens", 0) or 0
    return {
        "parsed": parsed,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def merge_chunk_results(chunk_results: list[dict]) -> dict:
    all_rules, seen = [], set()
    for cr in chunk_results:
        parsed = cr["parsed"]
        rules = parsed.get("extracted_rules", parsed.get("exclusion_criteria", []))
        for entry in rules:
            if not isinstance(entry, dict):
                continue
            group = str(entry.get("group", "")).strip().lower()
            resource = str(entry.get("resource", "")).strip().lower()
            rule_name = (
                str(entry.get("rule", entry.get("rule_name", ""))).strip().lower()
            )
            key = (group, resource, rule_name)
            if key not in seen:
                seen.add(key)
                all_rules.append(entry)
    return {"extracted_rules": all_rules}


def classify_one(row: dict) -> dict:
    file_id = row["file_id"]
    out_path = OUT_DIR / f"{file_id}.json"

    if out_path.exists():
        with open(out_path) as f:
            existing = json.load(f)
        return {
            "file_id": file_id,
            "status": "cached",
            "input_tokens": existing.get("_input_tokens", 0),
            "output_tokens": existing.get("_output_tokens", 0),
        }

    text_path = CLEAN_DIR / row["file_path"].replace(".xml", ".txt")
    if not text_path.exists():
        return {"file_id": file_id, "status": "missing_text", "error": str(text_path)}

    with open(text_path) as f:
        content = f.read()

    try:
        chunks = chunk_text(content)
        n_chunks = len(chunks)
        chunk_results = []
        for i, chunk in enumerate(chunks, 1):
            chunk_info = f" (chunk {i}/{n_chunks})" if n_chunks > 1 else ""
            result = call_gemini(row, chunk, chunk_info)
            chunk_results.append(result)
        if n_chunks == 1:
            final = chunk_results[0]["parsed"]
        else:
            final = merge_chunk_results(chunk_results)
            final["_n_chunks"] = n_chunks

        total_in = sum(cr["input_tokens"] for cr in chunk_results)
        total_out = sum(cr["output_tokens"] for cr in chunk_results)

        final["_file_id"] = file_id
        final["_input_tokens"] = total_in
        final["_output_tokens"] = total_out
        final["_model"] = MODEL

        with open(out_path, "w") as f:
            json.dump(final, f, indent=2, ensure_ascii=False)

        return {
            "file_id": file_id,
            "status": "ok",
            "n_chunks": n_chunks,
            "input_tokens": total_in,
            "output_tokens": total_out,
        }
    except Exception as e:
        return {"file_id": file_id, "status": "error", "error": str(e)}


def load_target_file_ids() -> set[str]:
    df = pd.read_csv(SAMPLE_CSV)
    fids = df["file_id"].dropna().astype(str)
    fids = fids[fids.str.startswith("tlg")]
    return set(fids.unique())


def main():
    target_ids = load_target_file_ids()
    meta = pd.read_csv(META_TSV, sep="\t")
    meta = meta[meta["file_id"].isin(target_ids)].copy()
    rows = meta.to_dict("records")

    print(f"Target file_ids from sample60_v18: {len(target_ids)}")
    print(f"Matched in metadata: {len(rows)}")
    print(f"Model: {MODEL}")
    print(f"Output dir: {OUT_DIR}")
    print()

    results = []
    start = time.time()
    with ProcessPoolExecutor(max_workers=MAX_PARALLEL) as executor:
        futures = {executor.submit(classify_one, r): r for r in rows}
        for fut in tqdm(as_completed(futures), total=len(futures), desc="Gemini V19"):
            results.append(fut.result())
    elapsed = time.time() - start

    ok = [r for r in results if r["status"] in ("ok", "cached")]
    errors = [r for r in results if r["status"] not in ("ok", "cached")]
    total_in = sum(r.get("input_tokens", 0) for r in ok)
    total_out = sum(r.get("output_tokens", 0) for r in ok)
    cost = (total_in / 1e6) * PRICE_IN + (total_out / 1e6) * PRICE_OUT

    print(f"\n{'='*60}")
    print(f"Done in {elapsed/60:.1f} min")
    print(f"OK: {len(ok)}  |  Errors: {len(errors)}")
    print(f"Input tokens:  {total_in:>12,}")
    print(f"Output tokens: {total_out:>12,}")
    print(f"Cost:          ${cost:>12.2f}")

    if errors:
        print("\nErrors:")
        for e in errors[:10]:
            print(f"  {e['file_id']}: {e.get('error', e['status'])[:100]}")

    with open(OUT_DIR / "_run_log.json", "w") as f:
        json.dump(
            {
                "model": MODEL,
                "prompt": PROMPT_FILE.name,
                "source_sample": SAMPLE_CSV.name,
                "n_works": len(rows),
                "ok": len(ok),
                "errors": len(errors),
                "total_input_tokens": total_in,
                "total_output_tokens": total_out,
                "cost_usd": round(cost, 2),
                "elapsed_sec": round(elapsed, 1),
                "results": results,
            },
            f,
            indent=2,
        )
    print(f"\nRun log: {OUT_DIR / '_run_log.json'}")


if __name__ == "__main__":
    main()
