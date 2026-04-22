# Perseus Greek Literature — Data Pipeline

Full pipeline for extracting social-exclusion criteria from ancient Greek texts
using LLM classification on the Perseus Digital Library corpus.

## Directory layout

```
Human Rights/
├── README.md                         This file
├── data/
│   ├── full_text/                    Plain-text extraction per author
│   ├── processed_data/               Curated metadata + exploration-ready tables
│   │   ├── perseus_metadata.tsv           File-level metadata (1,749 rows)
│   │   ├── perseus_authors.tsv            Author table (auto-generated)
│   │   ├── perseus_authors_cleaned.tsv    Author table (manually curated,
│   │   │                                  adds impact_date, cliopatria_polity,
│   │   │                                  manual_check_* columns)
│   │   ├── perseus_works_wikidata.tsv     Main works table (1,101 rows)
│   │   ├── perseus_works_wikidata_sample.tsv  Earlier analysis sample (89 works)
│   │   ├── final_dataset_for_criteria.tsv Final filtered sample
│   │   │                                  (318 works, 30 authors)
│   │   └── rules_full_dataset.tsv         Rule-level exploration dataset:
│   │                                      each row = one rule joined with
│   │                                      author + work metadata + all
│   │                                      V19 classifier outputs + the new
│   │                                      polity / time-reference annotations
│   ├── llm_results/                  All LLM artifacts
│   │   ├── gemini_v18/                    V18 extraction (85 JSON files)
│   │   ├── gemini_v19/                    V19 extraction (active)
│   │   ├── rules_classified_v18.tsv       Flat rule table (V18)
│   │   ├── rules_classified_v19*.tsv      Flat rule tables (V19, per sub-criterion)
│   │   ├── works_factuality_v18.tsv       Work-level factuality (V18)
│   │   ├── works_mythological_v18.tsv     Work-level mythological tag (V18)
│   │   ├── *_mapping*.json                Cached LLM classifications, keyed by rule_uid
│   │   │                                  (contemporary, factuality, mythological,
│   │   │                                  criterion, fact_opinion, immutability,
│   │   │                                  materiality, secondary, tautology,
│   │   │                                  resource_generality, resource_persistence)
│   │   └── rules_polity_time_mapping.json Cache of the rule-level polity +
│   │                                      time-reference classifier
│   ├── samples/                      V18 / V19 annotation batches (sample60_*)
│   └── annotation/                   Manual annotation backups + user comments
├── prompt/                            Prompt templates
│   ├── prompt_V18.md                      Single-shot V18 extraction prompt
│   ├── prompt_V19.md                      V19 extraction prompt
│   └── prompt_V19_*.md                    V19 sub-criterion prompts
├── scripts/
│   ├── dataset_cleaning/              Metadata construction
│   │   ├── extract_perseus.py             XML → metadata / plain text
│   │   ├── enrich_authors.py              Wikidata + Cliopatria enrichment
│   │   ├── match_authors_wikidata.py      Fuzzy author match
│   │   └── create_final_dataset.py        Build final_dataset_for_criteria.tsv
│   ├── sample_building/               Build annotation samples
│   │   ├── resample_filtered.py           V18 filtered resample (60 rules)
│   │   ├── build_sample_v19.py            V19 sample (initial)
│   │   └── build_sample_v19_batch[2-4].py V19 sample extensions
│   └── classifiers/                   LLM classifiers (OpenRouter + Gemini 2.5 Flash)
│       ├── classify_gemini_openrouter.py  V18 extraction
│       ├── classify_gemini_v19.py         V19 extraction
│       ├── classify_criterion.py          Criterion tagging
│       ├── classify_contemporary.py       Rule-level contemporary (0/1)
│       ├── classify_fact_opinion.py       Rule-level fact vs. opinion
│       ├── classify_factuality_works.py   Work-level factuality score
│       ├── classify_immutability_v19.py   V19 immutability (per-rule)
│       ├── classify_materiality_v19.py    V19 materiality
│       ├── classify_secondary_v19.py      V19 secondary criterion
│       ├── classify_tautology_v19.py      V19 tautology
│       ├── classify_resource_generality_v19.py
│       ├── classify_resource_persistence_v19.py
│       └── classify_work_polity.py        Rule-level polity + time reference
│                                          (corpus-agnostic prompt)
├── analysis_notebooks/                Jupyter notebooks (01–12)
│   ├── 01_distributions.ipynb             Corpus distributions
│   ├── 02_more_vs_less.ipynb              More/less exclusionary works
│   ├── 03_temporal_evolution.ipynb        Temporal evolution of criteria
│   ├── 04_resource_breakdown.ipynb        Resource breakdown
│   ├── 06_authors_works_per_decade.ipynb
│   ├── 07_perseus_works_wikidata_types.ipynb
│   ├── 08_authors_non_historian_5_periods.ipynb
│   ├── 09_criterion_distribution.ipynb
│   ├── 10_factuality_distribution.ipynb
│   ├── 11_authors_non_mythic_5_periods.ipynb
│   └── 12_final_dataset_for_criteria.ipynb
├── exploring interface/               Web explorer (Vite + React)
│   └── explorer-app/
├── run_explorer.py                    Launches the local explorer UI
├── compare_v18_v19_downvotes.py       Ad-hoc comparison script
└── create_criteria_timeline.py        Ad-hoc timeline script
```

## Data flow

```
Raw TEI-XML (Perseus)             2,538 files / 100 authors
        |
        | extract_perseus.py
        v
data/full_text/                   Plain text per author
        |
        v
data/processed_data/
  perseus_metadata.tsv            File-level metadata (1,749 rows)
  perseus_authors.tsv             Author table (auto-generated, 100 authors)
        |
        | enrich_authors.py + match_authors_wikidata.py
        v
  perseus_authors_cleaned.tsv     Manually curated authors (Wikidata,
                                  Cliopatria polity, impact_date, occupations)
        |
        | merge with file-level metadata + Wikidata work lookups
        v
  perseus_works_wikidata.tsv      Main works table (1,101 rows)
        |
        | create_final_dataset.py (filters below)
        v
  final_dataset_for_criteria.tsv  Filtered sample: 318 works / 30 authors
        |
        | + data/llm_results/rules_classified_v19_full.tsv (extracted rules)
        | + classify_work_polity.py   (adds rule-level polity + time reference)
        v
  rules_full_dataset.tsv          Exploration-ready flat table:
                                  one row per rule, with author + work +
                                  V19 classifier outputs + polity/time
```

## Final filtering (→ 318 works, 30 authors)

`final_dataset_for_criteria.tsv` is the active analysis corpus. Filters applied
by `scripts/dataset_cleaning/create_final_dataset.py`:

1. **Author has `match_score > 120`** (reliable Wikidata match)
2. **Author has `cliopatria_polity` and `impact_date`**
3. **File is an English translation** (filename contains `eng`)
4. **Dedup: last translation per `(author, work_code)`**

Net: 318 unique works by 30 authors — orators, philosophers, playwrights,
physicians, early Christian writers, and encyclopedists from the 5th c. BCE
to the 3rd c. CE.

## Wikidata matching

Works were matched to Wikidata entities by fuzzy-searching `instance_properties.db`
(3.8 M entries) using `author name + title`. The match brings in
`instance_of`, `genre`, `form_of_creative_work`; confidence is in `confidence`.

## Author dates

Author dates come from Cliopatria + Wikidata. `impact_date` is the floruit,
used to assign works to historical periods:

| Period                      | Date range        | Example authors                |
|-----------------------------|-------------------|--------------------------------|
| Archaic                     | 750–480 BCE       | Homer, Hesiod, Pindar          |
| Classical Athens            | 465–360 BCE       | Plato, Aristophanes, Isocrates |
| Late Classical              | 354–165 BCE       | Aristotle, Demosthenes         |
| Hellenistic & Early Roman   | 165 BCE–105 CE    | Epictetus, New Testament       |
| High Roman Empire           | 135–205 CE        | Lucian, Galen, Pausanias       |

## Rule-extraction pipeline

Each work is summarised into a set of "rules" (sentences that encode a social
norm of inclusion/exclusion). Two prompt generations are in use:

- **V18** — one-shot extraction (`prompt/prompt_V18.md`). Active results in
  `data/llm_results/gemini_v18/`. 85 works classified on the V18 sample.
- **V19** — decomposed extraction (`prompt/prompt_V19.md` + per-sub-criterion
  prompts). Active results in `data/llm_results/gemini_v19/`. Extraction is
  split across materiality, immutability, resource_generality,
  resource_persistence, secondary, tautology.

Flat tables: `data/rules_classified_v18.tsv` and
`data/rules_classified_v19*.tsv`.

## Rule-level classifiers (`scripts/classifiers/`)

Each classifier loads a `*_mapping*.json` cache keyed by `rule_uid` so re-runs
only process new rules. All use OpenRouter + `google/gemini-2.5-flash` and
load the API key from `.env` (`OPEN_ROUTER_API`).

| Script                                 | Output column(s)                        | Cache file                                 |
|----------------------------------------|-----------------------------------------|--------------------------------------------|
| `classify_criterion.py`                | criterion tags                          | `criterion_mapping.json`                   |
| `classify_contemporary.py`             | `is_contemporary` (0/1)                 | `contemporary_mapping.json`                |
| `classify_fact_opinion.py`             | `verbatim_type`                         | `fact_opinion_mapping.json`                |
| `classify_factuality_works.py`         | work-level `factuality`                 | `factuality_works_mapping.json`            |
| `classify_immutability_v19.py`         | V19 immutability                        | `immutability_mapping_v19.json`            |
| `classify_materiality_v19.py`          | V19 materiality                         | `materiality_mapping_v19.json`             |
| `classify_secondary_v19.py`            | V19 secondary                           | `secondary_mapping_v19.json`               |
| `classify_tautology_v19.py`            | V19 tautology                           | `tautology_mapping_v19.json`               |
| `classify_resource_generality_v19.py`  | V19 resource generality                 | `resource_generality_mapping_v19.json`     |
| `classify_resource_persistence_v19.py` | V19 resource persistence                | `resource_persistence_mapping_v19.json`    |

## Rule polity & time classifier

`scripts/classifiers/classify_work_polity.py` operates at the **rule** level
(not the work level), because a single work can contain some rules about the
author's own society and other rules about an earlier or later era. Each rule
in `rules_classified_v19_full.tsv` whose `file_id` belongs to the 318-work
sample is annotated with:

- **`rule_polity`** — the polity/society the rule itself refers to. Short,
  canonical label (e.g. "Classical Athens", "Roman Empire (Greek East)",
  "Second Temple Judaism", "Mythological / legendary setting",
  "Generic / abstract (no specific polity)"). May differ from the author's own
  polity.
- **`rule_time_reference`** — one of:
  - `contemporary` — within ~100 years of the author's floruit.
  - `past` — clearly earlier era than the author's time.
  - `future` — clearly later era (prophecy, eschatology, utopia).
  - `mixed` — meaningfully invokes multiple eras.
  - `timeless` — a-temporal / abstract content (logic, geometry, pure
      biology).
- **`rule_polity_reasoning`** / **`rule_time_reasoning`** — short LLM
  rationale (≤250 chars each).

The prompt is deliberately **corpus-agnostic**: nothing is hard-coded to the
Greek world, so the same script can be re-used on any corpus that provides
`(author, impact_year, author_polity, rule_text, verbatim)` per rule.

Inputs per rule: `author`, `impact_year`, `cliopatria_polity`, `description`,
`work_title`, `genre` / `form_of_creative_work`, `rule`, `criteria`, `group`,
`resource`, `verbatim`.

Outputs:

- `data/llm_results/rules_polity_time_mapping.json` — cache keyed by `rule_uid`.
- `data/processed_data/rules_full_dataset.tsv` — exploration-ready flat table:
  one row per rule with rule content + the four new polity / time columns +
  all V19 classifier outputs + author metadata (polity, floruit, Wikidata,
  occupations) + work metadata (title, genre, period, language, size).

Run:

```bash
python scripts/classifiers/classify_work_polity.py
```

## Setup

- Place an `OPEN_ROUTER_API=...` line in `.env` at the project root.
- Python deps: `pandas`, `openai`, `python-dotenv`, `tqdm`.
- Classifiers must be launched from the project root.

## Analysis notebooks

All exploratory analysis lives in `analysis_notebooks/`. Start from
`12_final_dataset_for_criteria.ipynb` for the current corpus overview.
