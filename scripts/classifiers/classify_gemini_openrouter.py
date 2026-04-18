"""
Classify Perseus sample texts with Gemini 2.5 Pro via OpenRouter API using prompt V13.

- Chunks texts into max 15 pages (~3,750 words) per API call
- Merges chunk results into one output per work
- 32,000 max output tokens
- Saves one JSON per work in: greek-pilot/perseus/data/llm_results/gemini_v13/
"""

import os
import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm
from openai import OpenAI  # OpenRouter uses OpenAI-compatible API

# === Config ===
REPO = Path(__file__).resolve().parents[2]
SAMPLE_TSV = REPO / "greek-pilot/perseus/data/perseus_works_wikidata_sample.tsv"
PROMPT_FILE = REPO / "greek-pilot/perseus/prompt/prompt_V18.md"
CLEAN_DIR = REPO / "greek-pilot/perseus/canonical-greekLit/data_clean"
OUT_DIR = REPO / "greek-pilot/perseus/data/llm_results/gemini_v18"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL = "google/gemini-3-flash-preview"
MAX_OUTPUT_TOKENS = 32000
MAX_PARALLEL = 20

# Chunking: max 15 pages per chunk (~3,750 words, ~5,000 tokens, ~20,000 chars)
MAX_PAGES_PER_CHUNK = 15
CHARS_PER_PAGE = 1000  # ~250 words * ~4 chars/word

# Pricing (OpenRouter, per 1M tokens) — Gemini 3 Flash Preview
PRICE_IN = 0.50
PRICE_OUT = 3.00

# === Setup ===
load_dotenv(REPO / ".env")
api_key = os.getenv("OPEN_ROUTER_API")
if not api_key:
    raise RuntimeError("OPEN_ROUTER_API not found in .env")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key,
)

with open(PROMPT_FILE) as f:
    SYSTEM_PROMPT = f.read()


def number_paragraphs(content: str) -> str:
    """Add paragraph numbers [§1], [§2], etc. to each paragraph."""
    paragraphs = content.split("\n\n")
    numbered = []
    for i, p in enumerate(paragraphs, 1):
        p = p.strip()
        if p:
            numbered.append(f"[§{i}] {p}")
    return "\n\n".join(numbered)


def chunk_text(content: str) -> list[str]:
    """Number paragraphs, then split into chunks of max ~15 pages."""
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
    """Make one API call via OpenRouter. Returns dict with parsed JSON + usage."""
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

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=MAX_OUTPUT_TOKENS,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    )

    raw = response.choices[0].message.content.strip()
    # Strip markdown fences if model added them
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"_raw_response": raw, "_parse_error": True, "exclusion_criteria": []}

    input_tokens = getattr(response.usage, "prompt_tokens", 0) or 0
    output_tokens = getattr(response.usage, "completion_tokens", 0) or 0

    return {
        "parsed": parsed,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def merge_chunk_results(chunk_results: list[dict]) -> dict:
    """Merge multiple chunk outputs into one, deduplicating criteria."""
    all_criteria, seen = [], set()
    for cr in chunk_results:
        parsed = cr["parsed"]
        # V14 uses "extracted_rules", earlier versions use "exclusion_criteria"
        rules = parsed.get("extracted_rules", parsed.get("exclusion_criteria", []))
        for entry in rules:
            if not isinstance(entry, dict):
                continue
            group = str(entry.get("group", entry.get("who", ""))).strip().lower()
            resource = str(entry.get("resource", "")).strip().lower()
            rule_name = str(entry.get("rule_name", "")).strip().lower()
            key = (group, resource, rule_name)
            if key not in seen:
                seen.add(key)
                all_criteria.append(entry)

    return {
        "extracted_rules": all_criteria,
    }


def classify_one(row: dict) -> dict:
    """Classify one work (chunking at 15 pages), return summary dict."""
    file_id = row["file_id"]
    out_path = OUT_DIR / f"{file_id}.json"

    # Skip if already done
    if out_path.exists():
        with open(out_path) as f:
            existing = json.load(f)
        return {
            "file_id": file_id,
            "status": "cached",
            "input_tokens": existing.get("_input_tokens", 0),
            "output_tokens": existing.get("_output_tokens", 0),
        }

    # Load the cleaned text
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


def main():
    df = pd.read_csv(SAMPLE_TSV, sep="\t")
    df = df[df["perseus_author"] != "Athenaeus"]  # Too long, skip
    rows = df.to_dict("records")

    print(f"Loaded {len(rows)} works from {SAMPLE_TSV.name}")
    print(f"Model: {MODEL} (via OpenRouter)")
    print(f"Chunking: max {MAX_PAGES_PER_CHUNK} pages per chunk")
    print(f"Output dir: {OUT_DIR}")
    print(f"Parallel workers: {MAX_PARALLEL}")
    print()

    results = []
    start = time.time()

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as executor:
        futures = {executor.submit(classify_one, r): r for r in rows}
        for fut in tqdm(as_completed(futures), total=len(futures), desc="Gemini"):
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
        print(f"\nErrors:")
        for e in errors[:10]:
            print(f"  {e['file_id']}: {e.get('error', e['status'])[:100]}")

    log_path = OUT_DIR / "_run_log.json"
    with open(log_path, "w") as f:
        json.dump(
            {
                "model": MODEL,
                "prompt": PROMPT_FILE.name,
                "sample": SAMPLE_TSV.name,
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
    print(f"\nRun log: {log_path}")


if __name__ == "__main__":
    main()
