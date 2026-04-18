"""
Work-level factuality classifier: for each of the 391 clean non-historian
works, assign a single factuality score 1-5 based on the work's genre,
author, and title.

Scale (same as rule-level classify_factuality.py):
  5  Original legal text / codified statute
  4  Legal oration invoking a contemporary law
  3  Contemporary documentation / treatise / observation
  2  Indirect contemporary inference
  1  Mythic / speculative (tragedy, epic, myth, utopian)

Outputs:
- data/factuality_works_mapping.json    cache: {perseus_id: {...}}
- data/works_factuality_v18.tsv         391 works + factuality, reason
"""

import json
import os
import pathlib
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from tqdm import tqdm

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
META_TSV = HERE / "data/processed_data/perseus_works_wikidata.tsv"
MAP_JSON = HERE / "data/factuality_works_mapping.json"
OUT_TSV = HERE / "data/works_factuality_v18.tsv"

EXCLUDE_AUTHORS = {"unknown", "pseudo-plutarch"}
MAX_WORKERS = 20
BATCH_SIZE = 25

SYSTEM_PROMPT = """You score each classical Greek literary work on a 1-5 factuality scale based on the type of evidence it provides about social rules of its author's era.

Scale:
- 5  ORIGINAL LEGAL TEXT. Codified law, statute, decree, or constitutional clause (Draco's Homicide Law, Solon's laws, Athenian decrees).
- 4  LEGAL ORATION. Forensic / political speeches that invoke specific contemporary laws or legal procedures (Demosthenes, Aeschines, Lysias, Isaeus, Isocrates, Antiphon, Hyperides, Andocides, Dinarchus, Lycurgus).
- 3  CONTEMPORARY DOCUMENTATION. Treatises, philosophical dialogues, medical texts, comedies satirising living Athenians, travelogues of the contemporary world, New Testament / apostolic-father texts about the early church (Aristotle, Plato, Aristophanes, Hippocrates, Pausanias, Epictetus, Galen, Aretaeus, Hermas, Clement of Rome, Barnabas, New Testament).
- 2  INDIRECT CONTEMPORARY INFERENCE. Letters, personal essays, or prose pieces where contemporary norms are mentioned in passing (rare; reserve for borderline cases).
- 1  MYTHIC / SPECULATIVE. Tragedy, epic, mythographic compilation, hymns to gods, fable collections, victory odes invoking myth, or fully utopian/speculative treatises (Homer, Hesiod, Aeschylus, Sophocles, Euripides, Pindar, Apollodorus' *Library*, Lucian's mythological dialogues).

Guidance:
- Anchor on the author, impact_year, title, genre, form_of_creative_work.
- Forensic orators → 4.
- Philosophical/medical/travel/documentary prose → 3.
- Tragedies, epics, mythological dialogues, Odes → 1.
- Epigrams, satyr plays, and mixed literary prose → 1 if mythic content dominates, 3 if contemporary satire.
- Lucian's *non-mythological* satires → 3; his Olympian dialogues (Prometheus, dialogues of the gods) → 1.

Respond ONLY with valid JSON: a list of objects, each {"i": <int>, "factuality": 1|2|3|4|5, "reason": "<1-sentence>"}."""


def build_item(row):
    return {
        "i": row["_i"],
        "author": row["perseus_author"],
        "impact_year": (
            int(row["author_impact_date"])
            if pd.notna(row["author_impact_date"])
            else None
        ),
        "work_title": row["wikidata_work_label"] or row["perseus_title"],
        "genre": row.get("genre") or "",
        "form_of_creative_work": row.get("form_of_creative_work") or "",
        "instance_of": row.get("instance_of") or "",
    }


def classify_batch(client, batch):
    user_msg = (
        "Score each work on the 1-5 factuality scale:\n"
        + json.dumps(batch, ensure_ascii=False)
    )
    resp = client.chat.completions.create(
        model="google/gemini-2.5-flash",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    text = resp.choices[0].message.content.strip()
    parsed = json.loads(text)
    if isinstance(parsed, list):
        results = parsed
    elif isinstance(parsed, dict):
        results = (
            parsed.get("results")
            or parsed.get("classifications")
            or parsed.get("items")
            or next((v for v in parsed.values() if isinstance(v, list)), None)
        )
    else:
        results = None
    if not isinstance(results, list):
        raise RuntimeError(f"Unexpected response: {text[:400]}")
    out = {}
    for it in results:
        try:
            i = int(it.get("i"))
            f = int(it.get("factuality"))
        except (TypeError, ValueError):
            continue
        if 1 <= f <= 5:
            out[i] = {"factuality": f, "reason": (it.get("reason") or "").strip()}
    return out


def main():
    load_dotenv(REPO_ROOT / ".env")
    api_key = os.getenv("OPEN_ROUTER_API")
    if not api_key:
        raise RuntimeError("OPEN_ROUTER_API not set in .env")
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

    df = pd.read_csv(META_TSV, sep="\t")
    df = df[
        (df["selected_english_translation"] == 1) & (df["historian"] == 0)
    ].copy()
    df = df[
        ~df["perseus_author"].astype(str).str.strip().str.lower().isin(EXCLUDE_AUTHORS)
    ]
    df["author_impact_date"] = pd.to_numeric(df["author_impact_date"], errors="coerce")
    df = df[df["author_impact_date"].notna()].reset_index(drop=True)
    print(f"Clean works: {len(df):,}")

    cache = {}
    if MAP_JSON.exists():
        try:
            cache = json.loads(MAP_JSON.read_text())
            print(f"Loaded {len(cache):,} cached entries")
        except Exception:
            pass

    todo = df[~df["perseus_id"].isin(cache)].reset_index(drop=True)
    print(f"Works to classify: {len(todo):,} / {len(df):,}")

    if len(todo) > 0:
        items = []
        for i, row in todo.iterrows():
            row = row.to_dict()
            row["_i"] = i
            items.append(build_item(row))
        batches = [items[s : s + BATCH_SIZE] for s in range(0, len(items), BATCH_SIZE)]
        idx_to_pid = dict(zip(todo.index.tolist(), todo["perseus_id"].tolist()))

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {pool.submit(classify_batch, client, b): b for b in batches}
            for fut in tqdm(
                as_completed(futures), total=len(batches), desc="Classifying"
            ):
                try:
                    res = fut.result()
                except Exception as e:
                    print(f"Batch failed: {e}")
                    continue
                for i, v in res.items():
                    pid = idx_to_pid.get(i)
                    if pid is not None:
                        cache[pid] = v

        MAP_JSON.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
        print(f"\nSaved {len(cache):,} classifications to {MAP_JSON}")

    df["factuality"] = (
        df["perseus_id"]
        .map(lambda pid: cache.get(pid, {}).get("factuality"))
        .astype("Int64")
    )
    df["factuality_reason"] = df["perseus_id"].map(
        lambda pid: cache.get(pid, {}).get("reason", "")
    )

    out_cols = [
        "perseus_id", "perseus_author", "author_impact_date",
        "wikidata_work_label", "perseus_title",
        "genre", "form_of_creative_work", "instance_of",
        "factuality", "factuality_reason",
    ]
    df[out_cols].to_csv(OUT_TSV, sep="\t", index=False)
    print(f"\nWrote {len(df):,} works to {OUT_TSV}")

    print("\nWork-level factuality distribution:")
    for k in range(1, 6):
        n = int((df["factuality"] == k).sum())
        print(f"  {k}  {n:>4,}  ({n/len(df)*100:.1f}%)")
    miss = int(df["factuality"].isna().sum())
    if miss:
        print(f"  unclassified: {miss}")


if __name__ == "__main__":
    main()
