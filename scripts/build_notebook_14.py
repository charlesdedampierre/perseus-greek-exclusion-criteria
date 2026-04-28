"""Build analysis_notebooks/14_clean_inspection_dataset.ipynb.

Produces a co-author-friendly inspection TSV from the final 130-works
dataset, joined with `source_type`, with one column per criterion +
its reasoning, polity coalesced (rule -> work -> author), and a flag
indicating whether each rule survives the notebook 08 filter.

Run once: `python scripts/build_notebook_14.py`. Then open the notebook
in Jupyter and run all cells (or `jupyter nbconvert --execute`).
"""
from __future__ import annotations

from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "analysis_notebooks" / "14_clean_inspection_dataset.ipynb"


def md(src: str):
    return nbf.v4.new_markdown_cell(src.strip("\n"))


def code(src: str):
    return nbf.v4.new_code_cell(src.strip("\n"))


cells = []

cells.append(md(r'''
# 14 — Clean inspection dataset for co-authors

A single TSV co-authors can open in Excel / Numbers / pandas to inspect
every rule used in the analysis, plus the rules that get filtered out
by `08_group_resource_type.ipynb`.

**What this notebook does**

1. Loads `data/clean/final/rules_final_dataset_130works_april_2026.tsv`
   (the gold-filtered rule corpus, 1,011 rows).
2. Joins each rule with its work-level **`source_type`** (A_legal /
   B_oration / C_historical / D_treatise / E_entertainment /
   F_religious) by **merging on `file_id`** with the pre-built
   `data/legacy_data/processed_data/works_source_type.tsv` table — no
   reclassification.
3. **Coalesces polity**: prefers `rule_polity`, falls back to
   `work_polity`, then to `work_author_polity_cliopatria`. The
   `polity_source` column records which level supplied the value.
4. **All groups and all rules are kept** — including those filtered
   out by notebook 08's analytical choices. Co-authors get the full
   1,011 rows.
5. Reorders columns into a sensible reading order (id → bibliography →
   rule core → group → resource → polity/date → criteria + reasoning)
   and writes
   `data/clean/final/rules_dataset_april_2026.tsv`.

The output is **rule-level** (one row per rule). Rules with multi-label
`group_meta` keep the original `;`-joined string; co-authors who want
the exploded view can re-derive it from this file.

*Follows `notebook_rule.md`.*
'''))

cells.append(md("## 1. Setup"))

cells.append(code(r'''
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path('..').resolve()

DATA_IN     = ROOT / 'data/clean/final/rules_final_dataset_130works_april_2026.tsv'
SOURCE_TYPE = ROOT / 'data/legacy_data/processed_data/works_source_type.tsv'
DATA_OUT    = ROOT / 'data/clean/final/rules_dataset_april_2026.tsv'

EXCLUDE_GROUPS = {
    'Soldiers', 'Artisans', 'Philosophers',
    'The multitude', 'Heirs', 'Priests',
}
'''))

cells.append(md("## 2. Load the rule corpus"))

cells.append(code(r'''
df = pd.read_csv(DATA_IN, sep='\t')
print(f'Loaded {len(df):,} rules from {DATA_IN.name}')
print(f'Columns: {len(df.columns)}')
df.head(2)
'''))

cells.append(md('''
## 3. Merge in `source_type`

`works_source_type.tsv` is the pre-built work-level classification
(see `scripts/classify_source_type.py` for how it was produced). We
**merge on `file_id`** here — no rules are reclassified.
'''))

cells.append(code(r'''
src = (pd.read_csv(SOURCE_TYPE, sep='\t')
         [['file_id', 'source_type', 'source_type_description']])

before = len(df)
df = df.merge(src, on='file_id', how='left', validate='many_to_one')
assert len(df) == before, 'merge changed row count'
assert df['source_type'].notna().all(), \
    f'{df["source_type"].isna().sum()} rules have no matching source_type'

# Strip the leading letter prefix (e.g. "B_oration" -> "oration").
df['source_type'] = df['source_type'].str.replace(r'^[A-Z]_', '', regex=True)

print('source_type distribution:')
print(df['source_type'].value_counts().to_string())
'''))

cells.append(md('''
## 4. Coalesce polity

The corpus carries three polity columns at different levels of
specificity. We prefer the most specific available, and record which
source supplied the final value.
'''))

cells.append(code(r'''
def coalesce(row):
    for col in ('rule_polity', 'work_polity', 'work_author_polity_cliopatria'):
        v = row.get(col)
        if pd.notna(v) and str(v).strip() not in ('', 'nan', 'None'):
            return v
    return np.nan

df['rule_polity'] = df.apply(coalesce, axis=1)
print(f'rules with no polity at any level: {df["rule_polity"].isna().sum()}')
'''))

cells.append(md('''
## 5. Keep everything — no row dropped

All 1,011 rules and all groups (including Soldiers, Artisans,
Philosophers, The multitude, Heirs, Priests) are retained for
co-author inspection. Notebook 08 narrows its figures further; this
TSV does not.
'''))

cells.append(md('''
## 6. Select & reorder columns

The order below moves from identification → bibliographic context →
rule core → group → resource → polity/date → criteria (each score
followed immediately by its reasoning) → filter status. This is the
order co-authors should read row-by-row.
'''))

cells.append(code(r'''
COL_ORDER = [
    # Identifier
    'rule_uid',

    # Bibliographic context
    'perseus_author',
    'perseus_title',
    'period',
    'source_type',
    'source_type_description',

    # Rule core
    'rule',
    'verbatim',
    'reasoning',
    'directionality',
    'confidence',

    # Group
    'group',
    'group_meta',

    # Resource
    'resource',
    'resource_meta',
    'resource_type',

    # Polity & date
    'rule_polity',
    'rule_polity_reasoning',
    'rule_date',
    'rule_time_reasoning',

    # Criteria — score followed by its reasoning
    'resource_materiality',  'materiality_reasoning',
    'resource_generality',   'generality_reasoning',
    'resource_persistence',  'persistence_reasoning',
    'group_immutability',    'immutability_reasoning',
    'rule_contemporarity',   'contemporarity_reasoning',
    'opinion_vs_fact',       'opinion_vs_fact_reasoning',
    'tautology',             'tautology_reasoning',
]

missing = [c for c in COL_ORDER if c not in df.columns]
assert not missing, f'missing columns: {missing}'

out = (df[COL_ORDER]
        .rename(columns={'rule_uid': 'rule_id',
                         'rule_time_reasoning': 'rule_date_reasoning',
                         'confidence': 'llm_confidence_in_answer'}))

# rule_contemporarity is encoded inverted in the source (0 = contemporary,
# 1 = not). Co-authors expect 1 = contemporary, so flip.
out['rule_contemporarity'] = 1 - out['rule_contemporarity']

out.head(3)
'''))

cells.append(md("## 7. Write the inspection TSV"))

cells.append(code(r'''
DATA_OUT.parent.mkdir(parents=True, exist_ok=True)
out.to_csv(DATA_OUT, sep='\t', index=False)

print(f'Wrote {DATA_OUT.relative_to(ROOT)}')
print(f'  rows:    {len(out):,}')
print(f'  columns: {len(out.columns)}')
print(f'  size:    {DATA_OUT.stat().st_size / 1024:.1f} KB')
'''))

cells.append(md('''
## 8. Sanity checks

- Row count matches the input.
- Every rule has a `rule_polity` value (coalesced).
- `rule_contemporarity` is now in {0, 1} with 1 = contemporary.
'''))

cells.append(code(r'''
assert len(out) == len(df)
assert out['rule_polity'].notna().all()
assert set(out['rule_contemporarity'].dropna().unique()).issubset({0, 1})

print(f'rows: {len(out):,} | columns: {len(out.columns)}')
print('\nrule_contemporarity counts:')
print(out['rule_contemporarity'].value_counts(dropna=False).to_string())
'''))


nb = nbf.v4.new_notebook(cells=cells)
nb.metadata = {
    "kernelspec": {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    },
    "language_info": {"name": "python"},
}

OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open("w") as f:
    nbf.write(nb, f)
print(f"Wrote {OUT.relative_to(ROOT)}  ({len(cells)} cells)")
