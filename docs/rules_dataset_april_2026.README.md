# `rules_dataset_april_2026.tsv`

## Bibliographic context

| Column | Description |
|---|---|
| `perseus_author` | Author of the work, as in the Perseus catalogue. |
| `perseus_title` | English title of the work. |
| `period` | Historical period bucket the work falls in (e.g. *Classical (500–360 BCE)*). |
| `source_type` | Work-level genre code: `legal_constitutional`, `oration`, `historical`, `contemporary_treatise`, `entertainment`, `religious_scriptural`. |
| `source_type_description` | Plain-English description of the `source_type` bucket. |

## Rule core

| Column | Description |
|---|---|
| `rule` | Short label of the rule (LLM-generated, ≤10 words). |
| `verbatim` | Exact quote(s) from the work that justify the rule. |
| `reasoning` | LLM's free-text justification linking the verbatim to the rule. |
| `directionality` | `MORE` (rule grants access) or `LESS` (rule restricts access); rare other tags exist for unrated rules. |
| `llm_confidence_in_answer` | LLM-reported confidence (1–10) that the rule is correctly extracted. |

## Group (who the rule is about)

| Column | Description |
|---|---|
| `group` | Group as described in the verbatim (e.g. *Athenian women*). |
| `group_meta` | Canonical meta-group(s);, joined with `;` (e.g. *Women;Citizens*). |

## Resource (what is granted/restricted)

| Column | Description |
|---|---|
| `resource` | Resource as described ( e.g. *the right to inherit land*). |
| `resource_meta` | Canonical resource label (e.g. *Inheritance rights*). |
| `resource_type` | High-level category: *Bodily Autonomy, Legal Standing, Household Authority, Material Wealth, Education, Political Power, Honor, Religious Standing*. |

## Polity & date

| Column | Description |
|---|---|
| `rule_polity` | Polity the rule applies to. |
| `rule_polity_reasoning` | LLM's justification for the assigned polity. |
| `rule_date` | Year the rule is in force (CE; negative = BCE). |
| `rule_date_reasoning` | LLM's justification for the assigned date. |

## Criteria scores (each followed by its reasoning)

All seven criteria use the 1–5 (or 0–1 for the binary ones) scoring rubric

| Column | Description |
|---|---|
| `resource_materiality` | 1–5: how *material* the resource is (5 = bodily / physical; 1 = symbolic). |
| `materiality_reasoning` | Justification for the materiality score. |
| `resource_generality` | 1–5: how broadly the resource type applies across life domains. |
| `generality_reasoning` | Justification for the generality score. |
| `resource_persistence` | 1–5: how durably the resource is held / lost (5 = lifelong; 1 = momentary). |
| `persistence_reasoning` | Justification for the persistence score. |
| `group_immutability` | 1–5: how fixed the group attribute is (5 = birth-fixed; 1 = freely chosen). |
| `immutability_reasoning` | Justification for the immutability score. |
| `rule_contemporarity` | 0/1: **1 = the rule is contemporary** to the author, 0 = the author describes a past rule.
| `contemporarity_reasoning` | Justification for the contemporarity flag. |
| `opinion_vs_fact` | 1–5: 5 = stated as plain fact, 1 = stated as opinion. |
| `opinion_vs_fact_reasoning` | Justification. |
| `tautology` | 0/1: 1 = the rule is tautological (group definition trivially implies the resource access); 0 = not tautological. |
| `tautology_reasoning` | Justification. |
