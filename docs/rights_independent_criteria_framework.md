# Rights-independent criteria — operationalised

## The problem this avoids

The corpus rules read like `group → resource (MORE | LESS)`. As long as
`group` is an *emic* label (`Citizens`, `Slaves`, `Nobles`), the implied
diagram of rights inequality is **analytic** — true by definition, with
zero empirical content:

> "Citizens have right *r*" is empty when *Citizen* is defined as "those
> with right *r*."

A Hasse diagram built directly on emic labels would look the same for
Classical Athens, medieval France, and Tang China — distinguished only by
which label sits at the top.

## The fix — criterion-prior-to-rights workflow

We re-encode each group along criteria that exist **independently of the
rights system** — facts about bodies, parentage, property-relations, and
economic production:

| Criterion | Values | Why it is rights-independent |
|---|---|---|
| `c_sex` | male / female / any / unspecified | Biological/socially-assigned, definable without reference to any right. |
| `c_age` | adult / minor / elder / any / unspecified | Developmental life-stage. |
| `c_ownership_status` | free / enslaved / freed / any / unspecified | Constitutive relational fact (X is owned by Y as property); presupposes that *some* legal system permits slavery, but not any specific right of slave or master. |
| `c_ancestry` | native / foreign / mixed / any / unspecified | Genealogical fact (e.g. both parents Attic-born). The same person has the same ancestry no matter what the legal regime says. |
| `c_residence` | resident / non_resident / any / unspecified | Spatial fact about physical presence. |
| `c_wealth` | high / middle / low / any / unspecified | Material-economic position (yield, holdings, movable wealth). |
| `c_kinship_role` | parent / child / spouse / sibling / heir / none / unspecified | Family-relational position. |
| `c_occupation` | free string (`farmer`, `artisan`, `priest`, `soldier`, …) | Productive role. |

Plus two metadata fields:

- `requires_rights_definition` — flags groups (`Magistrates`, `Voters`)
  that **only** make sense as legal/office categories and cannot be
  cleanly picked out by the criteria above.
- `emic_label` — the native-language term (`politēs`, `metoikos`,
  `doulos`, …) inferred for the cell. **A label on the cell, not its
  definition.**

The criteria are at most *law-presupposing* (slavery presupposes a system
that recognises property-in-persons), never *law-defined* (no criterion
mentions voting, court access, office-holding, or any specific right).

## Kripkean rigid-designator test

A criterion-cell is the **rigid designator** — it picks out the same
humans across counterfactual legal regimes. The rights it holds is the
**contingent property**. The sentence

> "Athenian citizens had right *r*, but in a counterfactual Athens with
> different laws, the same humans would not have had *r*"

is incoherent under the emic definition and perfectly meaningful under
the criterion definition. We test this empirically by looking up the
same criterion-cell across multiple polities in the corpus.

## Files

### Inputs

- `data/rules_dataset_april_2026.tsv` — 1011 rules.

### Pipeline

| Step | File | Output |
|---|---|---|
| 1. Prompt | `scripts/classifiers/prompt/prompt_group_criteria.md` | — |
| 2. Classifier | `scripts/classifiers/classify_group_criteria.py` | `data/clean/final/group_criterion_vectors.tsv` (491 vectors, 1 per unique `(group, rule_polity)`) |
| 3. Analysis | `scripts/analysis/analyze_rights_independent_criteria.py` | 5 TSVs in `data/clean/final/` |

The classifier sends **only** the group label + polity + period to the
LLM — never the rule, resource, verbatim, or directionality — so rights
cannot leak into the criterion vector.

### Analytical outputs

| File | What it answers |
|---|---|
| `rules_with_criteria.tsv` | Every rule joined with its criterion vector + cell signature. |
| `criterion_cell_rights_profile.tsv` | For each cell, the resources observed on it and their MORE / LESS frequency. **This is ρ(G) — empirical, not stipulated.** |
| `emic_vs_criterion_partition.tsv` | For each emic `group_meta`, how many criterion-cells its rules spread across. Single-cell labels are clean; multi-cell labels mark places where the native vocabulary aggregates etically-distinct cells. |
| `athens_snapshot.tsv` | Classical Athens (incl. sub-regimes) rebuilt non-tautologically: criterion-cells × resources × MORE/LESS counts, with emic labels layered on. |
| `contingent_rights.tsv` | **The Kripkean test.** For each (cell, resource_meta) observed in ≥2 polities: is the directionality stable (always MORE / always LESS) or contingent (flips across polities)? |

## Summary of findings on the April 2026 dataset

- **95 distinct criterion-cells** observed across 1011 rules.
- **Top cell**: `M-A-F-N-R-*` (sex=male, age=adult, ownership=free,
  ancestry=native, residence=resident, wealth=any) carries **267 rules**
  across 14 polities. This is the *politēs / civis* cell — but defined
  in rights-independent terms.
- **41 of 96 emic labels span ≥2 criterion-cells.** The emic word
  `Citizens` alone spreads over **17 distinct cells** in the corpus —
  proof that the native term is not the etic partition.
- **Kripkean test**: of the 82 (cell, resource) pairs observed in ≥2
  polities, **51 are contingent** (directionality flips), 31 stable.
  Example: `M-A-F-N-R-*` × *Political power* is MORE in 7 Greek polities
  but LESS in Salamis (Cyprus) — exactly the kind of contrast that is
  impossible to state under emic definitions.

## How to use

```bash
# Re-classify (cached per batch — rerunning costs $0 for cached cells)
python scripts/classifiers/classify_group_criteria.py

# Rebuild all analytical TSVs
python scripts/analysis/analyze_rights_independent_criteria.py
```

Adding new criteria, expanding the value vocabulary, or changing the
polity grouping rules only requires editing `prompt_group_criteria.md`
(for new criteria) or `CRITERION_AXES` / `cell_signature` in
`analyze_rights_independent_criteria.py` (for the cell signature).
