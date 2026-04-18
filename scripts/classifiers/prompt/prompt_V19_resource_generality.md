# Resource Generality Classifier

You receive an already-extracted rule and score how GENERAL the resource is on a 1–5 scale. The question is: **does the resource cover a broad class of life outcomes, or a narrow / hyper-specific one?**

The input is a JSON object with at least: `group`, `resource`, `rule`, `verbatim`, `reasoning`.

## Scoring guide (1 = very specific, 5 = very general)

- **5 — Very general.** Resource is a high-level societal good applicable to a large share of life outcomes: wealth, property, political power, freedom of movement, bodily integrity, legal standing, access to education, right to inherit, right to marry, right to vote.

- **4 — Broad category.** Major recognisable right or exemption that still spans many situations: tax exemption, freedom from enslavement, access to public office, right to hold land, access to civic festivals.

- **3 — Specific but recurring.** A specific but broadly applicable legal/material protection: right to a public trial, right to retain dowry, protection from corporal punishment, right to attend the assembly of a given city.

- **2 — Narrowly scoped.** Resource tied to a particular institution, setting, or procedure: access to the gymnasium of Cynosarges, participation in a specific festival, right to a specific civic award, exemption from a named tax.

- **1 — Hyper-specific.** Resource tied to a single circumstance, condition, or niche scenario: protection from a named disease, right to a specific medical procedure, access to a one-off ritual, a single procedural technicality in one type of trial.

## Rules

- Rate the RESOURCE itself, not the group or the rule.
- A resource is 1–2 when its phrasing names a particular disease, procedure, ritual, institution, or one-off circumstance.
- A resource is 5 when it names a foundational societal axis (wealth, property, political voice, bodily freedom, legal personhood).
- If ambiguous between two adjacent levels, prefer the lower score.

## Output format

Return ONLY valid JSON — a list of objects, each with keys `i` (input index), `resource_generality` (int 1–5), `resource_generality_reasoning` (short string ≤25 words).

Example:

```json
[
  {"i": 0, "resource_generality": 5, "resource_generality_reasoning": "Wealth covers a broad class of life outcomes."},
  {"i": 1, "resource_generality": 1, "resource_generality_reasoning": "Protection from erysipelas of the head is hyper-specific to one disease."}
]
```
