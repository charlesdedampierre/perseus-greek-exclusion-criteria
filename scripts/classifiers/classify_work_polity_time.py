"""
Work-level polity, time-reference, and date classifier (V1, historians only).

Annotates each work where ``historian = 1`` and
``selected_english_translation = 1`` in
``data/processed_data/perseus_works_wikidata.tsv``. The prompt lives at
``prompt/prompt_work_polity_time_V1.md`` and the unit of annotation is
the WORK (title + author metadata), not the rule.

Five fields per work:

- ``mentioned_polity_in_work``     polity the work documents
- ``mentioned_polity_reasoning``   one short sentence (<=250 chars)
- ``mentioned_time_reference``     one of {contemporary, past, mixed}
- ``mentioned_time_in_work``       single integer year (negative = BCE)
                                    or the string "mythological"
- ``mentioned_time_reasoning``     one short sentence (<=300 chars)

OpenRouter + Gemini 3 Flash, batched via a thread pool. Cached to
``data/llm_results/works_polity_time_mapping_v1.json`` keyed by
``file_id`` so re-runs only classify new works. Writes the
exploration table to ``data/processed_data/works_polity_time_dataset.tsv``.
Usage logged to ``gemini_api.md`` at the repo root (total cost + per-run
row).
"""

import json
import os
import pathlib
import datetime as dt
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from tqdm import tqdm

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
WORKS_TSV = REPO_ROOT / "data" / "processed_data" / "perseus_works_wikidata.tsv"
AUTHORS_TSV = REPO_ROOT / "data" / "processed_data" / "perseus_authors_cleaned.tsv"
MAP_JSON = REPO_ROOT / "data" / "llm_results" / "works_polity_time_mapping_v2.json"
OUT_TSV = REPO_ROOT / "data" / "processed_data" / "works_polity_time_dataset.tsv"
PROMPT_MD = HERE / "prompt" / "prompt_work_polity_time.md"
GEMINI_LOG = REPO_ROOT / "gemini_api.md"

MODEL = "google/gemini-3-flash-preview"
MAX_WORKERS = 8
BATCH_SIZE = 8
PRICE_IN = 0.30 / 1_000_000
PRICE_OUT = 2.50 / 1_000_000

VALID_TIME = {"contemporary", "past", "mixed"}

SYSTEM_PROMPT = PROMPT_MD.read_text() + (
    "\n\nReturn ONLY valid JSON — a list of objects, one per input item "
    "(or an object wrapping the list under \"results\"). Each object MUST "
    "include the integer index \"i\" from the input, plus the fields "
    "\"mentioned_polities_in_work\" (a JSON array of one or more polity "
    "strings), \"mentioned_polity_reasoning\", \"mentioned_time_reference\" "
    "(one of \"contemporary\", \"past\", \"mixed\"), "
    "\"mentioned_time_start_in_work\" (integer year; BCE = negative), "
    "\"mentioned_time_end_in_work\" (integer year; BCE = negative, >= start), "
    "and \"mentioned_time_reasoning\"."
)


def _s(v, limit=None):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    if not s or s.lower() == "nan":
        return None
    if limit:
        s = s[:limit]
    return s


def build_item(row):
    floruit = row.get("author_impact_date")
    try:
        floruit = int(float(floruit)) if floruit not in (None, "", "nan") else None
    except (TypeError, ValueError):
        floruit = None
    return {
        "i": row["_i"],
        "author": _s(row.get("perseus_author")),
        "author_floruit_year": floruit,
        "author_polity": _s(row.get("cliopatria_polity")),
        "author_description": _s(row.get("description"), 250),
        "work_title": _s(row.get("perseus_title"))
            or _s(row.get("wikidata_work_label")),
        "work_genre": _s(row.get("genre"))
            or _s(row.get("form_of_creative_work"))
            or _s(row.get("instance_of")),
    }


def _loose_json(text):
    """Tolerate unquoted keys / single quotes / trailing commas."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    import re
    repaired = text
    repaired = re.sub(
        r"([\{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:",
        r'\1"\2":',
        repaired,
    )
    repaired = re.sub(r"'([^'\n]*)'", r'"\1"', repaired)
    repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)
    return json.loads(repaired)


def _extract_objects(text):
    """Last-resort: scan for brace-balanced objects and parse each."""
    out = []
    depth = 0
    start = None
    in_str = False
    esc = False
    for i, ch in enumerate(text):
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                chunk = text[start : i + 1]
                try:
                    obj = _loose_json(chunk)
                    if isinstance(obj, dict):
                        out.append(obj)
                except Exception:
                    pass
                start = None
    return out


def parse_results(text):
    try:
        parsed = _loose_json(text)
    except Exception:
        parsed = None
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        for key in ("results", "classifications", "items", "works"):
            if isinstance(parsed.get(key), list):
                return parsed[key]
        for v in parsed.values():
            if isinstance(v, list):
                return v
    # Fallback: pull out every top-level {...} object we can find.
    objs = _extract_objects(text)
    if objs:
        return objs
    raise RuntimeError(f"Unexpected response shape: {text[:400]}")


def classify_batch(client, batch):
    user_msg = (
        "Classify the following works (return one object per input item):\n"
        + json.dumps(batch, ensure_ascii=False)
    )
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    text = resp.choices[0].message.content.strip()
    results = parse_results(text)

    usage = getattr(resp, "usage", None)
    in_tok = getattr(usage, "prompt_tokens", 0) or 0
    out_tok = getattr(usage, "completion_tokens", 0) or 0
    upstream_cost = 0.0
    if usage is not None:
        raw = getattr(usage, "cost", None)
        if raw is None and isinstance(usage, dict):
            raw = usage.get("cost")
        if raw:
            try:
                upstream_cost = float(raw)
            except (TypeError, ValueError):
                upstream_cost = 0.0

    def _year(v):
        if v is None or v == "":
            return ""
        try:
            return str(int(float(v)))
        except (TypeError, ValueError):
            return str(v)[:40]

    def _polities(v):
        if v is None:
            return ""
        if isinstance(v, list):
            items = [str(x).strip() for x in v if str(x).strip()]
        elif isinstance(v, str):
            items = [s.strip() for s in v.split(";") if s.strip()]
        else:
            items = [str(v).strip()]
        return "; ".join(items)[:400]

    out = {}
    for it in results:
        try:
            i = int(it["i"])
        except (KeyError, TypeError, ValueError):
            continue
        tref = str(it.get("mentioned_time_reference", "")).strip().lower()
        if tref not in VALID_TIME:
            tref = "past"
        out[i] = {
            "mentioned_polities_in_work": _polities(
                it.get("mentioned_polities_in_work")
                or it.get("mentioned_polity_in_work")
            ),
            "mentioned_polity_reasoning": _s(it.get("mentioned_polity_reasoning"), 300) or "",
            "mentioned_time_reference": tref,
            "mentioned_time_start_in_work": _year(it.get("mentioned_time_start_in_work")),
            "mentioned_time_end_in_work": _year(it.get("mentioned_time_end_in_work")),
            "mentioned_time_reasoning": _s(it.get("mentioned_time_reasoning"), 300) or "",
        }
    return out, in_tok, out_tok, upstream_cost


def update_gemini_log(script_name, purpose, in_tok, out_tok, cost):
    """Append a row to gemini_api.md and refresh the running total."""
    if not GEMINI_LOG.exists():
        return
    text = GEMINI_LOG.read_text()

    # Parse current total
    import re
    m = re.search(r"\*\*\$([0-9.]+) USD\*\*", text)
    prev = float(m.group(1)) if m else 0.0
    new_total = prev + cost
    text = re.sub(
        r"\*\*\$[0-9.]+ USD\*\*",
        f"**${new_total:.4f} USD**",
        text,
        count=1,
    )

    # Append run row. Drop the placeholder if it's still there.
    today = dt.date.today().isoformat()
    run_no_match = re.findall(r"\| (\d+) \| \d{4}-\d{2}-\d{2}", text)
    next_no = (max(int(n) for n in run_no_match) + 1) if run_no_match else 1
    new_row = (
        f"| {next_no} | {today} | `{script_name}` | {purpose} | "
        f"Gemini 3 Flash | {in_tok:,} | {out_tok:,} | ${cost:.4f} |"
    )
    if "_(no runs yet)_" in text:
        text = text.replace(
            "| _(no runs yet)_ | | | | | | | |",
            new_row,
        )
    else:
        # append just before "## Notes"
        text = text.replace("## Notes", new_row + "\n\n## Notes", 1)

    GEMINI_LOG.write_text(text)


def main():
    load_dotenv(REPO_ROOT / ".env")
    api_key = os.getenv("OPEN_ROUTER_API")
    if not api_key:
        raise RuntimeError(
            f"OPEN_ROUTER_API not set in .env at {REPO_ROOT / '.env'}"
        )
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

    works = pd.read_csv(WORKS_TSV, sep="\t", dtype=str, keep_default_na=False)
    scope = works[
        (works["historian"] == "1")
        & (works["selected_english_translation"] == "1")
    ].copy()
    print(
        f"Historian works with selected English translation: "
        f"{len(scope)} / {scope['perseus_author'].nunique()} authors"
    )

    # Merge author metadata (polity, description, impact date precision)
    authors = pd.read_csv(AUTHORS_TSV, sep="\t", dtype=str, keep_default_na=False)[
        [
            "perseus_author",
            "cliopatria_polity",
            "description",
            "occupations",
            "birthdate",
            "deathdate",
            "impact_date_precision",
        ]
    ].drop_duplicates("perseus_author")
    scope = scope.merge(authors, on="perseus_author", how="left")

    cache = {}
    if MAP_JSON.exists():
        try:
            cache = json.loads(MAP_JSON.read_text())
            print(f"Loaded {len(cache):,} cached classifications")
        except Exception:
            cache = {}

    todo = scope[~scope["file_id"].isin(cache)].reset_index(drop=True)
    print(f"Works to classify: {len(todo):,} / {len(scope):,}")

    total_in = 0
    total_out = 0
    total_upstream = 0.0

    if len(todo):
        items = []
        for i, row in todo.iterrows():
            d = row.to_dict()
            d["_i"] = i
            items.append(build_item(d))
        batches = [items[s : s + BATCH_SIZE] for s in range(0, len(items), BATCH_SIZE)]
        idx_to_fid = dict(zip(todo.index.tolist(), todo["file_id"].tolist()))

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {pool.submit(classify_batch, client, b): b for b in batches}
            for fut in tqdm(
                as_completed(futures), total=len(batches), desc="Classifying works"
            ):
                try:
                    res, in_tok, out_tok, up_cost = fut.result()
                except Exception as e:
                    print(f"Batch failed: {e}")
                    continue
                total_in += in_tok
                total_out += out_tok
                total_upstream += up_cost
                for i, v in res.items():
                    fid = idx_to_fid.get(i)
                    if fid is not None:
                        cache[fid] = v

        MAP_JSON.parent.mkdir(parents=True, exist_ok=True)
        MAP_JSON.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
        print(f"Saved {len(cache):,} classifications to {MAP_JSON}")

    def pick(fid, key):
        entry = cache.get(fid)
        return entry.get(key) if isinstance(entry, dict) else None

    for col in (
        "mentioned_polities_in_work",
        "mentioned_polity_reasoning",
        "mentioned_time_reference",
        "mentioned_time_start_in_work",
        "mentioned_time_end_in_work",
        "mentioned_time_reasoning",
    ):
        scope[col] = scope["file_id"].map(lambda u, c=col: pick(u, c))

    preferred = [
        "file_id",
        "perseus_id",
        "perseus_author",
        "perseus_title",
        "wikidata_work_id",
        "wikidata_work_label",
        "author_wikidata_id",
        "author_impact_date",
        "cliopatria_polity",
        "genre",
        "form_of_creative_work",
        "instance_of",
        "mentioned_polities_in_work",
        "mentioned_polity_reasoning",
        "mentioned_time_reference",
        "mentioned_time_start_in_work",
        "mentioned_time_end_in_work",
        "mentioned_time_reasoning",
        "main_language",
        "editors",
        "pub_date",
        "n_words",
        "n_characters",
        "n_pages",
        "file_path",
    ]
    ordered = [c for c in preferred if c in scope.columns]
    extras = [c for c in scope.columns if c not in ordered]
    out = scope[ordered + extras]

    OUT_TSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_TSV, sep="\t", index=False)
    print(
        f"Wrote {len(out):,} rows x {len(out.columns)} cols to {OUT_TSV}"
    )

    n_missing = int(out["mentioned_polities_in_work"].isna().sum()) + int(
        (out["mentioned_polities_in_work"] == "").sum()
    )
    print(f"\nSummary:  classified={len(out) - n_missing:,}  missing={n_missing:,}")
    print("\nTime-reference distribution:")
    print(out["mentioned_time_reference"].value_counts(dropna=False).to_string())
    # Explode the polity list for a flat top-N.
    flat = (
        out["mentioned_polities_in_work"].fillna("").str.split(r";\s*").explode()
    )
    flat = flat[flat != ""]
    print("\nTop 15 polities (exploded across list):")
    print(flat.value_counts().head(15).to_string())
    print("\nTop 15 start years:")
    print(out["mentioned_time_start_in_work"].value_counts(dropna=False).head(15).to_string())
    print("\nTop 15 end years:")
    print(out["mentioned_time_end_in_work"].value_counts(dropna=False).head(15).to_string())

    # Cost + log
    est_cost = total_in * PRICE_IN + total_out * PRICE_OUT
    # Prefer OpenRouter's reported upstream cost when available.
    cost = total_upstream if total_upstream > 0 else est_cost
    print(
        f"\nTokens used this run: input={total_in:,} output={total_out:,}"
    )
    print(
        f"Run cost: ${cost:.4f} (Gemini 3 Flash; "
        f"upstream={total_upstream:.4f}, estimated={est_cost:.4f})"
    )
    if total_in or total_out:
        update_gemini_log(
            script_name="scripts/classifiers/classify_work_polity_time.py",
            purpose=f"Work-level polity/time/date annotation on {len(todo)} historian works",
            in_tok=total_in,
            out_tok=total_out,
            cost=cost,
        )
        print(f"Logged to {GEMINI_LOG}")


if __name__ == "__main__":
    main()
