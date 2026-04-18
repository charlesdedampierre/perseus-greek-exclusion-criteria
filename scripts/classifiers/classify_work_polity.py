"""
Rule-level polity + time-reference classifier.

For each rule in ``rules_classified_v19_full.tsv`` whose ``file_id`` belongs to
the 318-work sample in ``final_dataset_for_criteria.tsv``, annotate:

- ``rule_polity``          the polity / society the RULE refers to. This may
                            differ both from the author's own polity and from
                            other rules in the same work (e.g. a 4th-century
                            orator citing a Solonic law => Archaic Athens, even
                            though the orator himself writes from Classical
                            Athens).
- ``rule_polity_reasoning`` one short sentence (<=250 chars).
- ``rule_time_reference``  exactly one of:
                              "contemporary"  the society referred to by the
                                              rule is within ~100 years of the
                                              author's floruit (before or after).
                              "past"          clearly earlier era than the
                                              author's floruit.
                              "future"        clearly later era (prophecy,
                                              eschatology, political utopia).
                              "mixed"         the rule meaningfully invokes
                                              multiple eras.
                              "timeless"      the rule is a-temporal / abstract
                                              (logic, geometry, general biology)
                                              with no specific polity.
- ``rule_time_reasoning``  one short sentence (<=250 chars).

Design notes
------------
The prompt is intentionally period- and culture-agnostic: nothing in it is
hard-coded to the Greek world, so the same script can be re-used on any corpus
where each rule has (author, impact_year, author_polity, rule_text, work_title,
verbatim). Only the default input paths are project-specific.

OpenRouter + ``google/gemini-2.5-flash``, batched via a thread pool. Cached to
``data/rules_polity_time_mapping.json`` keyed by ``rule_uid`` so re-runs only
classify new rules. Writes an enriched table to
``data/rules_classified_v19_full_polity.tsv``.
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
REPO_ROOT = HERE.parent.parent
RULES_TSV = REPO_ROOT / "data" / "llm_results" / "rules_classified_v19_full.tsv"
FINAL_TSV = REPO_ROOT / "data" / "processed_data" / "final_dataset_for_criteria.tsv"
AUTHORS_TSV = REPO_ROOT / "data" / "processed_data" / "perseus_authors_cleaned.tsv"
MAP_JSON = REPO_ROOT / "data" / "llm_results" / "rules_polity_time_mapping.json"
OUT_TSV = REPO_ROOT / "data" / "processed_data" / "rules_full_dataset.tsv"

MAX_WORKERS = 15
BATCH_SIZE = 15

VALID_TIME = {"contemporary", "past", "future", "mixed", "timeless"}

SYSTEM_PROMPT = """You are a historian-annotator. For each social rule you are
given, decide TWO things about the rule itself — NOT about the work as a whole.
Different rules from the same work can (and often do) refer to different
polities or different time periods.

INPUT FIELDS PER RULE
- author                : the author of the work
- author_floruit_year   : the approximate year the author was active
                          (negative = BCE, positive = CE)
- author_polity         : the polity the author lived in, if known
- author_description    : a short bio
- work_title            : title of the work containing this rule
- work_genre            : genre / form of the work (e.g. oration, treatise,
                          epistle, tragedy, dialogue, medical treatise, ...)
- rule                  : short name of the rule
- criteria              : exclusion/inclusion criterion (e.g. Gender, Age, ...)
- group                 : the group the rule targets
- resource              : the right / resource at stake
- verbatim              : a direct textual excerpt from the work supporting the
                          rule (strongest clue)

TASK 1 — ``rule_polity``
Identify the polity / society the RULE describes, presupposes, or prescribes
for. Use a short, specific, canonical label. Prefer attested historical
polities when they exist (e.g. "Classical Athens", "Roman Empire (Greek
East)", "Achaemenid Persia", "Second Temple Judaism", "Kingdom of France
(Ancien Régime)", "Ming China") and add a qualifier when useful (region,
century). Do not invent fictional labels. Use:
  - "Generic / abstract (no specific polity)" when the rule is a-temporal or
    non-social (logic, geometry, medicine that speaks of biology alone, etc.).
  - "Mythological / legendary setting"         when the rule applies to a
    clearly mythic world (Homeric gods, Titans, Old-Testament patriarchal
    narrative taken as legendary) rather than a real polity.
The rule's polity CAN and OFTEN WILL differ from the author's polity.

TASK 2 — ``rule_time_reference``
Classify the temporal relation between the polity/society the rule is about
and the author's own floruit. Exactly one of:
  - "contemporary" : within ~100 years of author_floruit_year (before or after).
  - "past"         : a clearly earlier era than the author's time.
  - "future"       : a clearly later era (prophecy, eschatology, utopia).
  - "mixed"        : the rule meaningfully invokes multiple eras.
  - "timeless"     : no meaningful temporal anchoring (pure biology, logic,
                     mathematics, ethics stated as universal).

HEURISTICS (corpus-agnostic)
- Anchor on ``author_floruit_year`` and ``author_polity``. A rule that
  prescribes for the author's own society is "contemporary" even if stated
  as a general maxim.
- Rules that quote or cite an older legal code, older historical figure, older
  myth, or older scripture are "past" if the rule is ABOUT that older world.
  If the author cites the old material only to illustrate a present-day rule,
  treat it as "contemporary".
- Letters, sermons, petitions, and political speeches almost always address
  the author's own community => "contemporary" in the author's polity.
- Mythological/epic content set in a clearly pre-historical heroic age =>
  polity "Mythological / legendary setting" and time "past" (relative to a
  historical author) or "timeless" (relative to a mythographer with no clear
  historical vantage).
- Technical treatises (mathematics, anatomy, pure logic) => polity
  "Generic / abstract ..." and time "timeless", UNLESS the rule embeds a
  concrete social detail of the author's own world (then "contemporary").
- Do not use the author's polity as a default answer: re-read the verbatim.
- Prefer precision over vagueness: if the rule names a specific city, dynasty,
  sect, or century, use that.

For EACH input item return an object with:
  "i"                    : the integer index you were given
  "rule_polity"          : short canonical label
  "rule_polity_reasoning": one short sentence (<=250 chars)
  "rule_time_reference"  : one of "contemporary" | "past" | "future" | "mixed" | "timeless"
  "rule_time_reasoning"  : one short sentence (<=250 chars)

Return ONLY valid JSON: a list of such objects (or an object wrapping the list
under "results")."""


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
    floruit = row.get("impact_year")
    if pd.notna(floruit):
        try:
            floruit = int(floruit)
        except (TypeError, ValueError):
            floruit = None
    else:
        floruit = None
    return {
        "i": row["_i"],
        "author": _s(row.get("author")),
        "author_floruit_year": floruit,
        "author_polity": _s(row.get("cliopatria_polity")),
        "author_description": _s(row.get("description"), 250),
        "work_title": _s(row.get("work_title")) or _s(row.get("perseus_title")),
        "work_genre": _s(row.get("genre")) or _s(row.get("form_of_creative_work")),
        "rule": _s(row.get("rule")),
        "criteria": _s(row.get("criteria")),
        "group": _s(row.get("group")),
        "resource": _s(row.get("resource")),
        "verbatim": _s(row.get("verbatim"), 600),
    }


def parse_results(text):
    parsed = json.loads(text)
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        for key in ("results", "classifications", "items", "rules"):
            if isinstance(parsed.get(key), list):
                return parsed[key]
        for v in parsed.values():
            if isinstance(v, list):
                return v
    raise RuntimeError(f"Unexpected response shape: {text[:400]}")


def classify_batch(client, batch):
    user_msg = (
        "Classify the following rules (return one object per input item):\n"
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
    results = parse_results(text)

    out = {}
    for it in results:
        try:
            i = int(it["i"])
        except (KeyError, TypeError, ValueError):
            continue
        tref = str(it.get("rule_time_reference", "")).strip().lower()
        if tref not in VALID_TIME:
            tref = "contemporary"
        out[i] = {
            "rule_polity": _s(it.get("rule_polity"), 200) or "",
            "rule_polity_reasoning": _s(it.get("rule_polity_reasoning"), 300) or "",
            "rule_time_reference": tref,
            "rule_time_reasoning": _s(it.get("rule_time_reasoning"), 300) or "",
        }
    return out


def main():
    load_dotenv(REPO_ROOT / ".env")
    api_key = os.getenv("OPEN_ROUTER_API")
    if not api_key:
        raise RuntimeError(f"OPEN_ROUTER_API not set in .env at {REPO_ROOT / '.env'}")
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

    rules = pd.read_csv(RULES_TSV, sep="\t")
    final = pd.read_csv(FINAL_TSV, sep="\t")
    keep_ids = set(final["file_id"].tolist())
    rules = rules[rules["file_id"].isin(keep_ids)].reset_index(drop=True)
    print(
        f"Rules scoped to the {len(keep_ids)} filtered works: "
        f"{len(rules):,} rules / {rules['file_id'].nunique()} files / "
        f"{rules['author'].nunique()} authors"
    )

    # Attach author metadata (polity / description / occupations / wikidata).
    authors = pd.read_csv(AUTHORS_TSV, sep="\t")[
        [
            "perseus_author",
            "cliopatria_polity",
            "description",
            "occupations",
            "wikidata_id",
            "wikidata_name",
            "birthdate",
            "deathdate",
            "impact_date",
            "impact_date_precision",
        ]
    ].drop_duplicates("perseus_author")
    rules = rules.merge(
        authors, left_on="author", right_on="perseus_author", how="left"
    )

    # Attach per-work metadata from the final 318-work sample so each rule row
    # is self-contained: title / genre / period / language / size.
    work_meta_cols = [
        "file_id",
        "perseus_id",
        "perseus_title",
        "wikidata_work_id",
        "wikidata_work_label",
        "period",
        "genre",
        "form_of_creative_work",
        "instance_of",
        "factuality",
        "main_language",
        "editors",
        "pub_date",
        "n_words",
        "n_characters",
        "n_pages",
    ]
    work_meta_cols = [c for c in work_meta_cols if c in final.columns]
    rules = rules.merge(
        final[work_meta_cols].drop_duplicates("file_id"),
        on="file_id",
        how="left",
        suffixes=("", "_work"),
    )

    cache = {}
    if MAP_JSON.exists():
        try:
            cache = json.loads(MAP_JSON.read_text())
            print(f"Loaded {len(cache):,} cached classifications")
        except Exception:
            cache = {}

    todo = rules[~rules["rule_uid"].isin(cache)].reset_index(drop=True)
    print(f"Rules to classify: {len(todo):,} / {len(rules):,}")

    if len(todo):
        items = []
        for i, row in todo.iterrows():
            d = row.to_dict()
            d["_i"] = i
            items.append(build_item(d))
        batches = [items[s : s + BATCH_SIZE] for s in range(0, len(items), BATCH_SIZE)]
        idx_to_uid = dict(zip(todo.index.tolist(), todo["rule_uid"].tolist()))

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {pool.submit(classify_batch, client, b): b for b in batches}
            for fut in tqdm(
                as_completed(futures), total=len(batches), desc="Classifying rules"
            ):
                try:
                    res = fut.result()
                except Exception as e:
                    print(f"Batch failed: {e}")
                    continue
                for i, v in res.items():
                    uid = idx_to_uid.get(i)
                    if uid is not None:
                        cache[uid] = v

        MAP_JSON.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
        print(f"Saved {len(cache):,} classifications to {MAP_JSON}")

    def pick(uid, key):
        entry = cache.get(uid)
        return entry.get(key) if isinstance(entry, dict) else None

    for col in (
        "rule_polity",
        "rule_polity_reasoning",
        "rule_time_reference",
        "rule_time_reasoning",
    ):
        rules[col] = rules["rule_uid"].map(lambda u, c=col: pick(u, c))

    # Reorder columns for exploration: identity -> rule -> polity/time ->
    # author metadata -> work metadata -> V19 classifier outputs.
    preferred = [
        # identity
        "rule_uid",
        "file_id",
        "perseus_id",
        # rule content
        "criteria",
        "rule",
        "group",
        "resource",
        "directionality",
        "verbatim",
        "reasoning",
        "confidence",
        # new polity + time annotations (the point of this script)
        "rule_polity",
        "rule_polity_reasoning",
        "rule_time_reference",
        "rule_time_reasoning",
        # existing rule-level classifier outputs
        "contemporary",
        "factuality",
        "factuality_work",
        "is_historical",
        "group_specificity",
        "group_immutability",
        "immutability_reasoning",
        "resource_materiality",
        "materiality_reasoning",
        "resource_generality",
        "resource_generality_reasoning",
        "resource_persistence",
        "persistence_reasoning",
        "tautological",
        "tautology_reasoning",
        "secondary_reasoning",
        # author metadata
        "author",
        "wikidata_id",
        "wikidata_name",
        "cliopatria_polity",
        "impact_year",
        "impact_date",
        "impact_date_precision",
        "birthdate",
        "deathdate",
        "occupations",
        "description",
        # work metadata
        "work_title",
        "perseus_title",
        "wikidata_work_id",
        "wikidata_work_label",
        "period",
        "genre",
        "form_of_creative_work",
        "instance_of",
        "main_language",
        "editors",
        "pub_date",
        "n_words",
        "n_characters",
        "n_pages",
    ]
    ordered = [c for c in preferred if c in rules.columns]
    extras = [c for c in rules.columns if c not in ordered and c != "perseus_author"]
    rules = rules[ordered + extras]

    OUT_TSV.parent.mkdir(parents=True, exist_ok=True)
    rules.to_csv(OUT_TSV, sep="\t", index=False)
    print(
        f"Wrote exploration-ready dataset ({len(rules):,} rows x "
        f"{len(rules.columns)} cols) to {OUT_TSV}"
    )

    n_missing = int(rules["rule_polity"].isna().sum())
    print(f"\nSummary:  classified={len(rules) - n_missing:,}  missing={n_missing:,}")

    print("\nTime-reference distribution:")
    print(rules["rule_time_reference"].value_counts(dropna=False).to_string())

    print("\nTop 20 polities:")
    print(rules["rule_polity"].value_counts(dropna=False).head(20).to_string())

    print("\nPer-author time-reference share:")
    print(
        rules.groupby("author")["rule_time_reference"]
        .value_counts(normalize=True)
        .unstack(fill_value=0)
        .round(2)
        .to_string()
    )


if __name__ == "__main__":
    main()
