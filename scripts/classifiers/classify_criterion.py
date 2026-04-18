"""
Classify each unique GROUP NAME into ZERO OR MORE of our 12 canonical criteria
via Gemini on OpenRouter. A group can have multiple criteria (e.g.
"Adult male citizens" → Gender + Citizenship + Age). Rule-level context
(rule_name + reasoning) is passed to disambiguate polysemous group names.

Outputs:
- data/criterion_mapping.json         cache: {group: [criterion, ...]}
- data/rules_classified_v18.tsv       rule-level table + `criteria` column
                                      (pipe-separated list, empty when none apply)
- data/sample50_v18.tsv               sample with `criteria`
- data-exploration/explorer-app/public/data/sample50_v18.csv
                                      explorer CSV with `criteria`
"""

import json
import os
import pathlib
import random
from collections import Counter, defaultdict

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from tqdm import tqdm

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
GEMINI_DIR = HERE / "data/llm_results/gemini_v18"
META_TSV = HERE / "data/processed_data/perseus_works_wikidata.tsv"
MAP_JSON = HERE / "data/criterion_mapping.json"
RULES_TSV = HERE / "data/rules_classified_v18.tsv"
SAMPLE_TSV = HERE / "data/sample60_v18.tsv"
EXPLORER_CSV = HERE / "data-exploration/explorer-app/public/data/sample60_v18.csv"

CRITERIA = [
    "Gender",
    "Citizenship",
    "Occupation",
    "Age",
    "Lineage",
    "Nobility",
    "Wealth / Properties",
    "Ethnicity",
    "Education",
    "Freedom",
    "Religion",
    "Health",
    "Legal Standing",
]
CRITERIA_SET = set(CRITERIA)

EXCLUDE_AUTHORS = {"unknown", "pseudo-plutarch"}
MAX_CTX_EXAMPLES = 2  # rule contexts passed per group

SYSTEM_PROMPT = """You classify social group names from Ancient Greek literature into a fixed list of exclusion criteria.

A group can have ZERO, ONE, or MANY criteria. Return ALL that apply.

Criteria (with definitions):
- Gender: men vs. women.
- Citizenship: citizens vs. non-citizens (metics, foreigners, exiles treated politically).
- Occupation: defined by profession or role (soldiers, priests, farmers, craftsmen, rulers; slaves only when described as a role, not as legal status).
- Age: children, youths, adults, elders, or any age threshold.
- Lineage: coming from a specific family, clan, or kinship line (legitimate heirs, descendants, orphans, bastards).
- Nobility: high-born / aristocratic vs. common-born; inherited social rank.
- Wealth / Properties: rich vs. poor, property owners, landless, creditors, debtors — anyone defined by material possessions or economic standing.
- Ethnicity: Greek vs. barbarian, or any ethnic / geographic-origin group (Athenians vs. Thebans, Greeks vs. Persians).
- Education: level of education, literacy, or philosophical training.
- Freedom: free persons vs. enslaved persons — the legal-status distinction.
- Religion: members of a religion, initiates, priests-as-religious-status, or religious belief groups.
- Health: groups defined by physical or mental condition — the sick, patients, disabled, blind, deaf, lame, chronically ill.
- Legal Standing: groups defined by legal/procedural role — defendants, plaintiffs, prosecutors, litigants, witnesses, jurors, suppliants, speakers (in court), debtors-in-lawsuits, accused persons.

Multi-criterion examples:
- "Adult male citizens" → ["Gender", "Citizenship", "Age"]
- "Wealthy landowners" → ["Wealth / Properties"]
- "Elderly female slaves" → ["Age", "Gender", "Freedom"]
- "Noble Athenian generals" → ["Nobility", "Ethnicity", "Occupation"]

Guidelines:
1. Return an empty list [] only when no criterion applies (e.g. "The dead", "Mortals", "Humans", "The public", "The multitude").
2. Prefer specificity: if a group is named by a specific kinship line (e.g. "Alcmaeonids"), return ["Lineage"]; if it is a legal role like "Suppliants", return ["Legal Standing"].
3. "Speakers", "Orators", "Rhetors" in a courtroom/political context → Legal Standing (and possibly Occupation).
4. Economic/wealth groups ALWAYS include "Wealth / Properties".
5. Health/disability groups ALWAYS include "Health".
6. "Slaves"/"Freedmen" as legal status → Freedom. Foreigners/metics → Citizenship.
7. Use the provided rule_name and reasoning as context to disambiguate polysemous group names.

Respond ONLY with valid JSON — a list of objects, each with keys `i` (the input index) and `criteria` (list of criterion strings, possibly empty)."""


def norm(v):
    if v is None:
        return ""
    if isinstance(v, list):
        return " | ".join(str(x).strip() for x in v)
    return str(v).strip()


def load_pairs_with_context():
    """Return {group_name: [ {rule_name, reasoning}, ... ]} using up to MAX_CTX_EXAMPLES
    contexts per group, plus Counter(group_name -> rule count) for stats."""
    contexts = defaultdict(list)
    counts = Counter()
    for fp in GEMINI_DIR.glob("tlg*.json"):
        d = json.loads(fp.read_text())
        for r in d.get("extracted_rules", []):
            if not isinstance(r, dict):
                continue
            g = norm(r.get("group"))
            counts[g] += 1
            if len(contexts[g]) < MAX_CTX_EXAMPLES:
                contexts[g].append(
                    {
                        "rule_name": norm(r.get("rule_name"))[:140],
                        "reasoning": norm(r.get("reasoning"))[:400],
                    }
                )
    return contexts, counts


def classify_batch(client, batch):
    """batch: list of {i, group, contexts}. Returns {i: list[str]}."""
    user_msg = (
        "Classify each group below into zero or more criteria using the rule "
        "contexts as hints. Input items:\n"
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
        raise RuntimeError(f"Unexpected response shape: {text[:500]}")

    out = {}
    for item in results:
        i = item.get("i")
        crits = item.get("criteria") or []
        if not isinstance(crits, list):
            crits = [crits]
        cleaned = [c for c in crits if c in CRITERIA_SET]
        out[i] = cleaned
    return out


def classify_all(contexts, batch_size=50):
    load_dotenv(REPO_ROOT / ".env")
    api_key = os.getenv("OPEN_ROUTER_API")
    if not api_key:
        raise RuntimeError("OPEN_ROUTER_API not set in .env")
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

    cache = {}
    if MAP_JSON.exists():
        try:
            raw = json.loads(MAP_JSON.read_text())
            # only accept list-valued entries (new schema)
            cache = {k: v for k, v in raw.items() if isinstance(v, list)}
            print(f"Loaded {len(cache)} cached entries (list-valued)")
        except Exception:
            pass

    to_do = [g for g in contexts if g not in cache]
    print(f"New groups to classify: {len(to_do)} / {len(contexts)}")

    if not to_do:
        return cache

    for start in tqdm(range(0, len(to_do), batch_size), desc="Classifying batches"):
        chunk = to_do[start : start + batch_size]
        batch = [
            {"i": i, "group": g, "contexts": contexts[g]}
            for i, g in enumerate(chunk)
        ]
        try:
            res = classify_batch(client, batch)
        except Exception as e:
            print(f"Batch at {start} failed: {e}. Skipping chunk.")
            continue
        for i, g in enumerate(chunk):
            cache[g] = res.get(i, [])
        MAP_JSON.write_text(json.dumps(cache, ensure_ascii=False, indent=2))

    return cache


LLM_FIELDS = [
    "rule_name",
    "rule_category",
    "group",
    "resource",
    "resource_category",
    "directionality",
    "proof",
    "reasoning",
    "specificity",
    "specificity_reasoning",
    "confidence",
]


def build_rules_table(mapping):
    """Rule-level table: only fields present in the LLM output, plus file_id,
    rule_uid, and the computed `criteria` column.

    Authors excluded are still filtered out so downstream sampling behaves
    consistently with the rest of the project.
    """
    meta = pd.read_csv(META_TSV, sep="\t")
    meta = meta[
        (meta["selected_english_translation"] == 1) & (meta["historian"] == 0)
    ].copy()
    meta = meta[
        ~meta["perseus_author"]
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(EXCLUDE_AUTHORS)
    ]
    keep_fids = set(meta["file_id"])
    # sidecar for sampling stratification + explorer display
    meta_lookup = meta.set_index("file_id").to_dict("index")

    rows = []
    for fp in sorted(GEMINI_DIR.glob("tlg*.json")):
        d = json.loads(fp.read_text())
        fid = d.get("_file_id", fp.stem)
        if fid not in keep_fids:
            continue
        for i, r in enumerate(d.get("extracted_rules", [])):
            if not isinstance(r, dict):
                continue
            g = norm(r.get("group"))
            crits = mapping.get(g) or []
            row = {"rule_uid": f"{fid}#{i}", "file_id": fid}
            for f in LLM_FIELDS:
                v = r.get(f)
                if f == "proof" and isinstance(v, list):
                    v = " | ".join(str(x) for x in v)
                elif f == "group":
                    v = g
                row[f] = v
            row["criteria"] = "|".join(crits)
            rows.append(row)
    df_rules = pd.DataFrame(rows)

    # Attach a small sidecar DataFrame keyed by file_id for sampling only;
    # NOT written to the TSV.
    author_map = {
        fid: {
            "author": m.get("perseus_author"),
            "work_title": m.get("wikidata_work_label") or m.get("perseus_title"),
            "author_impact_date": m.get("author_impact_date"),
        }
        for fid, m in meta_lookup.items()
    }
    return df_rules, author_map


def resample_50(rules, author_map, per_criterion=5):
    """Sample EXACTLY `per_criterion` rules for each primary criterion.

    Total sample size = (number of primary criteria) * per_criterion.
    Each rule is counted toward exactly ONE criterion's quota — the one it is
    selected for — even if its `criteria` field carries several tags.
    Within a criterion, picks prefer authors not yet sampled, so the sample
    spans as many distinct authors as possible.
    """

    def tags(s):
        return [c for c in str(s or "").split("|") if c]

    pool = rules[
        rules["criteria"].apply(
            lambda s: bool(tags(s)) and "Legal Standing" not in tags(s)
        )
    ].copy()
    pool["author"] = pool["file_id"].map(
        lambda f: author_map.get(f, {}).get("author")
    )
    pool = pool[pool["author"].notna()].reset_index(drop=True)

    print(
        f"Sampling pool: {len(pool):,} / {len(rules):,} rules "
        f"(dropped empty-criteria and any rule containing Legal Standing)"
    )

    target_criteria = [c for c in CRITERIA if c != "Legal Standing"]
    picked_uids = set()
    picked = []
    authors_used = set()
    fill = {c: 0 for c in target_criteria}

    pool_shuffled = pool.sample(frac=1, random_state=42).reset_index(drop=True)

    for crit in target_criteria:
        eligible = pool_shuffled[
            pool_shuffled["criteria"].apply(lambda s: crit in tags(s))
            & ~pool_shuffled["rule_uid"].isin(picked_uids)
        ].copy()
        eligible["_new_author"] = eligible["author"].map(
            lambda a: 0 if a not in authors_used else 1
        )
        eligible = eligible.sort_values("_new_author").drop(columns="_new_author")

        for _, row in eligible.iterrows():
            if fill[crit] >= per_criterion:
                break
            picked_uids.add(row["rule_uid"])
            row = row.to_dict()
            row["sampled_for"] = crit  # which quota this rule was picked to fill
            picked.append(row)
            authors_used.add(row["author"])
            fill[crit] += 1

    sample = (
        pd.DataFrame(picked)
        .sort_values(["sampled_for", "author", "file_id"])
        .reset_index(drop=True)
    )
    sample = sample.drop(columns=[c for c in ["author"] if c in sample.columns])

    print(
        f"\nSample size: {len(sample)} rules / {len(authors_used)} unique authors"
    )
    print(f"Per-criterion fill (target = {per_criterion}):")
    for c in target_criteria:
        print(f"  {c!r:<25}  {fill[c]}")

    return sample


def write_explorer_csv(sample, author_map):
    """The explorer UI expects a v7-style schema. We derive display-only
    metadata (work name, author, impact year) from the author_map sidecar so
    the TSV itself stays clean.
    """
    meta_cols = sample["file_id"].map(
        lambda f: author_map.get(f, {"author": "", "work_title": "", "author_impact_date": None})
    )
    out = pd.DataFrame(
        {
            "work_name": meta_cols.map(lambda m: m.get("work_title", "")),
            "author": meta_cols.map(lambda m: m.get("author", "")),
            "impact_year": pd.to_numeric(
                meta_cols.map(lambda m: m.get("author_impact_date")),
                errors="coerce",
            ).astype("Int64"),
            "polity": "",
            "criteria": sample["criteria"],
            "sampled_for": sample["sampled_for"] if "sampled_for" in sample else "",
            "criterion_label": sample["rule_name"],
            "in_group": sample["group"],
            "out_group": "",
            "resource": sample["resource"],
            "resource_std": sample["resource_category"],
            "speaker": sample["directionality"],
            "verbatim": sample["proof"],
            "matched_keywords": sample["rule_category"],
            "extraction_method": "gemini_v18",
            "extraction_cost_usd": "",
            "prompt_tokens": "",
            "completion_tokens": "",
            "rule_uid": sample["rule_uid"],
            "file_id": sample["file_id"],
            "rule_category": sample["rule_category"],
            "reasoning": sample["reasoning"],
            "specificity": sample["specificity"],
            "specificity_reasoning": sample["specificity_reasoning"],
            "confidence": sample["confidence"],
        }
    )
    out.to_csv(EXPLORER_CSV, index=False)


def main():
    contexts, counts = load_pairs_with_context()
    print(
        f"Groups: {len(contexts):,} unique, {sum(counts.values()):,} total rules"
    )

    mapping = classify_all(contexts)
    print(f"\nMapping covers {len(mapping):,} groups")

    # Stats: unique groups per criterion, rules per criterion
    unique_per_crit = Counter()
    for g, crits in mapping.items():
        for c in crits:
            unique_per_crit[c] += 1
        if not crits:
            unique_per_crit["(none)"] += 1
    print("\nDistribution over unique group names (a group can count in multiple criteria):")
    for c, n in sorted(unique_per_crit.items(), key=lambda x: -x[1]):
        print(f"  {c!r:<25}  {n}")

    rules, author_map = build_rules_table(mapping)
    rules.to_csv(RULES_TSV, sep="\t", index=False)
    print(f"\nWrote {len(rules):,} rules ({len(rules.columns)} cols) to {RULES_TSV}")

    # Rule-weighted stats
    rule_unique_crit = Counter()
    multi = Counter()
    for s in rules["criteria"].fillna(""):
        cs = [c for c in s.split("|") if c]
        if not cs:
            rule_unique_crit["(none)"] += 1
        else:
            multi[len(cs)] += 1
            for c in cs:
                rule_unique_crit[c] += 1
    print("\nRule-weighted criterion counts (a rule can count in multiple):")
    for c, n in sorted(rule_unique_crit.items(), key=lambda x: -x[1]):
        print(f"  {c!r:<25}  {n}")
    print("\nRules with N criteria:")
    for n in sorted(multi):
        print(f"  {n} criteria  -> {multi[n]} rules")

    sample = resample_50(rules, author_map)
    sample["valid"] = ""
    sample["comment"] = ""
    sample.to_csv(SAMPLE_TSV, sep="\t", index=False)
    print(f"\nWrote {len(sample)} sampled rules ({len(sample.columns)} cols) to {SAMPLE_TSV}")

    write_explorer_csv(sample, author_map)
    print(f"Wrote explorer CSV to {EXPLORER_CSV}")


if __name__ == "__main__":
    main()
