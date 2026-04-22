# Rules of Exclusion in Ancient Greek Literature

[![License: MIT](https://img.shields.io/badge/License-MIT-informational.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![DOI](https://img.shields.io/badge/DOI-pending-lightgrey.svg)](#)

LLM extraction and annotation of social-exclusion rules from the Perseus Digital Library corpus of ancient Greek literature.

## Layout

```
data/
  full-text-data/    Raw plain-text extraction (gitignored for size)
  clean/             Processed, analysis-ready tables
  annotation/        Manual annotation batches
scripts/
  dataset_cleaning/  Perseus XML → metadata tables
  sample_building/   Annotation sample builders
  classifiers/       LLM classifiers (Gemini via OpenRouter)
analysis_notebooks/  Jupyter notebooks (01 – 12)
```

Main output: `data/clean/final/rules_final_dataset_130works_april_2026.tsv`.
