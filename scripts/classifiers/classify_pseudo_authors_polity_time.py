"""
One-off extension of the historians polity/time classifier to cover
Pseudo-Lucian (tlg0061) and Pseudo-Plutarch (tlg0094). These authors
have ``historian = 0`` in the corpus, so the main classifier
(``classify_work_polity_time.py``) excludes them, but for the purposes
of the historians-coverage notebook we want their works annotated with
the same polity/time schema.

Reuses the prompt, model, and batch logic from the main classifier.
Writes to the shared cache file ``works_polity_time_mapping_v2.json``.
"""

import datetime as dt
import json
import os
import pathlib
import sys
import time

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from tqdm import tqdm

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
from classify_work_polity_time import (  # noqa: E402
    MODEL,
    PRICE_IN,
    PRICE_OUT,
    SYSTEM_PROMPT,
    build_item,
    classify_batch,
    update_gemini_log,
)

WORKS_TSV = REPO_ROOT / "data" / "clean" / "perseus" / "perseus_works_wikidata.tsv"
AUTHORS_TSV = REPO_ROOT / "data" / "clean" / "perseus" / "perseus_authors_cleaned.tsv"
MAP_JSON = REPO_ROOT / "data" / "clean" / "classifications" / "works_polity_time_mapping_v2.json"

PSEUDO_AUTHOR_CODES = {"tlg0061", "tlg0094"}


def main():
    load_dotenv(REPO_ROOT / ".env")
    api_key = os.getenv("OPEN_ROUTER_API")
    if not api_key:
        raise RuntimeError(f"OPEN_ROUTER_API not set in .env at {REPO_ROOT / '.env'}")
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

    works = pd.read_csv(WORKS_TSV, sep="\t", dtype=str, keep_default_na=False)
    scope = works[
        works["author_code"].isin(PSEUDO_AUTHOR_CODES)
        & (works["selected_english_translation"] == "1")
    ].copy()
    print(f"Pseudo-author works in scope: {len(scope)}")
    print(
        scope[["file_id", "perseus_author", "perseus_title"]].to_string(index=False)
    )

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
        cache = json.loads(MAP_JSON.read_text())
        print(f"Loaded {len(cache):,} cached classifications")

    todo = scope[~scope["file_id"].isin(cache)].reset_index(drop=True)
    print(f"Works to classify: {len(todo)} / {len(scope)}")

    if not len(todo):
        print("Nothing to do.")
        return

    items = []
    for i, row in todo.iterrows():
        d = row.to_dict()
        d["_i"] = i
        items.append(build_item(d))
    idx_to_fid = dict(zip(todo.index.tolist(), todo["file_id"].tolist()))

    start = time.time()
    total_in = 0
    total_out = 0
    total_upstream = 0.0

    # 7 works fit comfortably in one batch; keep tqdm for consistency.
    for _ in tqdm([0], desc="Classifying Pseudo-* works"):
        res, in_tok, out_tok, up_cost = classify_batch(client, items)
        total_in += in_tok
        total_out += out_tok
        total_upstream += up_cost
        for i, v in res.items():
            fid = idx_to_fid.get(i)
            if fid is not None:
                cache[fid] = v

    MAP_JSON.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
    wall_min = (time.time() - start) / 60.0
    print(f"Saved {len(cache):,} classifications to {MAP_JSON}")
    print(f"Wall-clock: {wall_min:.2f} min")

    est_cost = total_in * PRICE_IN + total_out * PRICE_OUT
    cost = total_upstream if total_upstream > 0 else est_cost
    print(
        f"\nTokens this run: input={total_in:,} output={total_out:,}\n"
        f"Run cost: ${cost:.4f} "
        f"(upstream={total_upstream:.4f}, estimated={est_cost:.4f})"
    )

    if total_in or total_out:
        update_gemini_log(
            script_name="scripts/classifiers/classify_pseudo_authors_polity_time.py",
            purpose=(
                f"Work-level polity/time on {len(todo)} Pseudo-Lucian + "
                f"Pseudo-Plutarch works; {wall_min:.1f} min wall-clock"
            ),
            in_tok=total_in,
            out_tok=total_out,
            cost=cost,
        )
        print("Logged to gemini_api.md")

    # Quick glance at what we classified.
    print("\nNew entries:")
    for fid in todo["file_id"]:
        entry = cache.get(fid, {})
        print(
            f"  {fid}  →  polities={entry.get('mentioned_polities_in_work', '')!r}  "
            f"time={entry.get('mentioned_time_start_in_work')}→"
            f"{entry.get('mentioned_time_end_in_work')}"
        )


if __name__ == "__main__":
    main()
