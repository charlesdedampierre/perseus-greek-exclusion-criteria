# Rules of Exclusion in Ancient Greek Literature

[![License: MIT](https://img.shields.io/badge/License-MIT-informational.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![DOI](https://img.shields.io/badge/DOI-pending-lightgrey.svg)](#)

LLM extraction and annotation of social-exclusion rules from the Perseus
Digital Library corpus of ancient Greek literature. The final corpus covers
**328 works by 30 authors** (5th c. BCE – 3rd c. CE), from which **1,017
rules** were extracted and classified.

## Paper

> Preprint, arXiv ID, and DOI will be added here before publication.

## Install

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
echo "OPEN_ROUTER_API=sk-or-..." > .env
```

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

## Citation

```bibtex
@unpublished{dedampierre2026exclusion,
  author = {de Dampierre, Charles},
  title  = {Rules of Exclusion in Ancient Greek Literature},
  year   = {2026},
  note   = {Preprint / DOI forthcoming}
}
```

## Contact

Charles de Dampierre — [cdedampierre@bunka.ai](mailto:cdedampierre@bunka.ai)

## License

MIT — see [`LICENSE`](LICENSE). Source corpus:
[PerseusDL/canonical-greekLit](https://github.com/PerseusDL/canonical-greekLit)
(CC BY-SA).
