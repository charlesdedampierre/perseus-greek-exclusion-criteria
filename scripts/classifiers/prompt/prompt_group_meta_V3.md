# Group meta-category classifier — V3 (axis decomposition, multi-label)

You receive GROUP strings from ancient texts. Each string names a
category of persons. Your job: **decompose the string into every
intrinsic attribute it references, and return the canonical label for
each attribute.**

## The axes of categorisation

A person's membership in a group is defined along one or more of these
axes. Each axis has its own small set of canonical labels.

| Axis | Canonicals on this axis |
|---|---|
| **sex** | Men · Women |
| **age** | Minors · Elders |
| **legal status** | Citizens · Foreigners · Slaves · Exiles |
| **kinship role** | Wives · Heirs · Orphans |
| **wealth** | The wealthy · The poor |
| **social rank** | Nobles · The multitude |
| **ethnicity / polity** | Greeks · Spartans · Jews · Syrians · Scythians · *(add new if needed)* |
| **occupation / office** | Magistrates · Priests · Soldiers · Sailors · Poets · Artisans · Philosophers · The educated · Kings |
| **health** | Sick |
| **religion** | Christians · Jews · Priests |

(When a new ethnicity or occupation is clearly named and sits at the
same level of abstraction as the canonicals above, introduce it as a
new canonical — e.g. `Romans`, `Persians`, `Physicians`. Do **not**
invent behavioural or abstract canonicals.)

## The decomposition rule

1. Read the input as a noun phrase.
2. Every **adjective, modifier, or conjunction** typically introduces
   a new axis.
3. For each axis the string references, emit the one canonical that
   best represents it.
4. Never emit two canonicals from the same axis (no Men + Women, no
   Minors + Elders).

### Illustrative examples (not an exhaustive list)

- `Old men` → `[Men, Elders]` (sex + age)
- `Wives` → `[Women, Wives]` (sex + kinship)
- `Daughters of citizens` → `[Citizens, Women]` (status + sex)
- `High-born men` → `[Nobles, Men]` (rank + sex)
- `The infirm poor` → `[The poor, Sick]` (wealth + health)
- `Enslaved women` → `[Slaves, Women]` (status + sex)
- `Elderly fathers` → `[Men, Elders]` (sex + age; "fathers" ≈ Men)
- `Slaves and foreigners` → `[Slaves, Foreigners]` (explicit conjunction)
- `Jewish priests` → `[Jews, Priests]` (ethnicity + occupation)
- `Sicilian Greeks` → `[Greeks]` (regional qualifier is not a separate axis)
- `Mercenaries` → `[Soldiers]` (single-axis)

### Axis-specific guidance

- **Age.** Any age qualifier (old, elderly, aged, X-year-old, young,
  boy, girl, child) triggers the age axis. "Elders" as a Spartan
  council is still an age-based label — emit `Elders` (you may add
  `Magistrates` if the context is clearly an office).
- **Sex.** Gendered nouns (fathers, sons, daughters, wives, matrons,
  maidens) imply a sex canonical even when the surface word isn't
  "Men" or "Women".
- **Behavioural descriptors** ("Men who committed impiety", "Aspiring
  tyrants"): ignore the behaviour; keep only the underlying immutable
  axes (`Men` / `Citizens`).
- **Abstract criteria** that leak through (`Education`,
  `Citizenship`): map to the people-noun of that axis
  (`The educated`, `Citizens`).

## Fallback

If the string is genuinely outside the human taxonomy above (Gods,
The dead, Fictional characters), emit `["Other"]`.

## Input

A JSON list of `{i, value}` objects.

## Output

Return ONLY valid JSON — a list of objects in input order. Each object
has `i` and `group_meta`, where **`group_meta` is a list of 1–3
canonical strings**.

```json
[
  {"i": 0, "group_meta": ["Citizens"]},
  {"i": 1, "group_meta": ["Men", "Elders"]},
  {"i": 2, "group_meta": ["Women", "Slaves"]},
  {"i": 3, "group_meta": ["The poor", "Sick"]},
  {"i": 4, "group_meta": ["Slaves", "Foreigners"]},
  {"i": 5, "group_meta": ["Other"]}
]
```
