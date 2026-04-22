"""
Audit for notebook 11:
  (1) Verify that author_impact_date (floruit) lands in the intended period
      for every author kept in the final filtered corpus.
  (2) Identify which Hellenistic-era authors the user named are absent from
      the Perseus corpus — and when present, show exactly which filter drops
      them.
"""

from pathlib import Path
import pandas as pd
import re

ROOT = Path(__file__).resolve().parent.parent
META = ROOT / "data/processed_data/perseus_works_wikidata.tsv"
FACT = ROOT / "data/llm_results/works_factuality_v18.tsv"

# Canonical floruit year for each author (scholarly consensus, approximate
# midpoint of their active writing years). Source: OCD4 / Cambridge History.
FLORUIT = {
    "Thucydides": -420,
    "Aristophanes": -415,
    "Lysias": -395,
    "Plato": -370,
    "Xenophon": -380,
    "Isocrates": -370,
    "Aristotle": -340,
    "Demosthenes": -345,
    "Aeschines": -340,
    "Dinarchus": -320,
    "Lycurgus": -330,
    "Polybius": -150,
    "Strabo": 5,  # c. 7 CE
    "Plutarch": 90,
    "New Testament": 60,
    "Epictetus": 100,
    "Barnabas": 100,
    "Athenaeus": 200,
    "Lucian of Samosata": 170,
    "Lucian": 170,
    "Pausanias": 160,
    "Hermas": 140,
}

PERIODS = [
    ("Early Classical", -480, -404),
    ("Late Classical", -404, -31),
    ("Early Imperial", -31, 231),
]


def canonical_period(year):
    for label, lo, hi in PERIODS:
        if lo <= year < hi:
            return label
    return "OUTSIDE"


# ---------- Build the final corpus the notebook uses ----------
df = pd.read_csv(META, sep="\t")
df = df[df["selected_english_translation"] == 1].copy()
excl = {"unknown", "pseudo-plutarch"}
df = df[~df["perseus_author"].astype(str).str.strip().str.lower().isin(excl)]
df["year"] = pd.to_numeric(df["author_impact_date"], errors="coerce")
df = df[df["year"].notna()].copy()
df["year"] = df["year"].astype(int)

fact = pd.read_csv(FACT, sep="\t")[["perseus_id", "factuality"]]
df = df.merge(fact, on="perseus_id", how="left")
df = df[df["factuality"] != 1]
df = df[df["is_scientific"].fillna(0) != 1]
df = df[(df["historian"] != 1) | (df["keep_greek_focus"] == 1)]

# ---------- (1) Floruit vs. corpus date ----------
per_author = (
    df.groupby("perseus_author").agg(corpus_year=("year", "first")).reset_index()
)

per_author["canonical_floruit"] = per_author["perseus_author"].map(FLORUIT)
per_author["corpus_period"] = per_author["corpus_year"].apply(canonical_period)
per_author["floruit_period"] = per_author["canonical_floruit"].apply(
    lambda y: canonical_period(y) if pd.notna(y) else "n/a"
)
per_author["agrees"] = per_author.apply(
    lambda r: (
        r["corpus_period"] == r["floruit_period"]
        if r["floruit_period"] != "n/a"
        else None
    ),
    axis=1,
)

print("=" * 78)
print(" (1) FLORUIT AUDIT — does author_impact_date land in the right bin?")
print("=" * 78)
cols = [
    "perseus_author",
    "corpus_year",
    "canonical_floruit",
    "corpus_period",
    "floruit_period",
    "agrees",
]
print(per_author.sort_values("corpus_year")[cols].to_string(index=False))

mismatches = per_author[per_author["agrees"] == False]
print(
    f"\nAuthors whose corpus period disagrees with canonical floruit: {len(mismatches)}"
)
if len(mismatches):
    print(mismatches[cols].to_string(index=False))
missing_ref = per_author[per_author["canonical_floruit"].isna()]
if len(missing_ref):
    print(f"\nAuthors not in FLORUIT reference table: {len(missing_ref)}")
    print(missing_ref["perseus_author"].tolist())

# ---------- (2) Missing Hellenistic authors ----------
print()
print("=" * 78)
print(" (2) MISSING HELLENISTIC AUTHORS — where do they go?")
print("=" * 78)

# Candidates user listed (search pattern → description)
CANDIDATES = [
    ("Callimachus", "poetry"),
    ("Apollonius", "poetry (Argonautica) / maths (of Perga)"),
    ("Theocritus", "pastoral poetry"),
    ("Herodas", "mimes"),
    ("Aratus", "didactic poetry"),
    ("Leonidas", "epigrams"),
    ("Asclepiades", "epigrams"),
    ("Posidippus", "epigrams"),
    ("Epicurus", "philosophy"),
    ("Zeno", "Stoic philosophy"),
    ("Chrysippus", "Stoic philosophy"),
    ("Euclid", "maths"),
    ("Archimedes", "maths / mechanics"),
    ("Eratosthenes", "geography / maths"),
    ("Hipparchus", "astronomy"),
    ("Aristarchus", "astronomy / Alexandrian philology"),
    ("Herophilus", "medicine"),
    ("Erasistratus", "medicine"),
    ("Hieronymus", "historiography"),
    ("Timaeus", "historiography"),
    ("Duris", "historiography"),
    ("Phylarchus", "historiography"),
    ("Agatharchides", "historiography"),
    ("Zenodotus", "philology"),
    ("Septuagint", "Bible translation"),
]

raw = pd.read_csv(META, sep="\t")
raw_fact = raw.merge(fact, on="perseus_id", how="left")

for pattern, note in CANDIDATES:
    mask = (
        raw["perseus_author"]
        .astype(str)
        .str.contains(pattern, case=False, na=False, regex=False)
    )
    hits = raw_fact[mask]
    if hits.empty:
        print(f"[ABSENT ] {pattern:<16s}  ({note})  — not in Perseus corpus at all")
        continue
    # Walk the filter chain for each match
    for _, row in hits.iterrows():
        reasons = []
        if row["selected_english_translation"] != 1:
            reasons.append("no selected English translation")
        if pd.isna(row["author_impact_date"]):
            reasons.append("no author_impact_date")
        if row.get("factuality") == 1:
            reasons.append("mythic/tragic/epic (factuality==1)")
        if row.get("is_scientific") == 1:
            reasons.append("scientific author filter")
        if row.get("historian") == 1 and row.get("keep_greek_focus") != 1:
            reasons.append("historian but not Greek-focused")
        status = "KEPT   " if not reasons else "DROPPED"
        print(
            f'[{status}] {row["perseus_author"]:<25s} | {row.get("perseus_title","")[:45]:<45s}'
            f' | {"; ".join(reasons) if reasons else "in final corpus"}'
        )
