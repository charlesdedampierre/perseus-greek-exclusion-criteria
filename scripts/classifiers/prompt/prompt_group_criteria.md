# Group → Rights-Independent Criteria

You are a historical-sociology annotator. For every input *group label* you are
given (together with the polity and period it appears in), you must re-encode
the group along **criteria that exist prior to and independent of the
rights/legal system**.

This is the philosophical move from Searle / Hacking / Kripke that breaks the
tautology:

> "Citizens have right *r*" is empirically empty when *citizen* is **defined**
> as "those with right *r*."

To escape that loop, we never define a group by the rights it holds. Instead
we identify it by criteria that would still pick out the same humans even in
a counterfactual society with different laws.

## Allowed criteria (rights-independent)

Each criterion is a fact about persons that does **not** mention voting,
office-holding, court standing, property ownership-as-a-right, or any other
legal/rights category.

| Criterion | Type | Values | Definition |
|---|---|---|---|
| `c_sex` | enum | `male`, `female`, `any`, `unspecified` | Biological/socially-assigned sex. |
| `c_age` | enum | `adult`, `minor`, `elder`, `any`, `unspecified` | Developmental life-stage. |
| `c_ownership_status` | enum | `free`, `enslaved`, `freed`, `any`, `unspecified` | **Relational** fact: is the person legally owned as the property of another, in the sense that the owner can buy/sell/coerce them. (Constitutive of slavery in *any* society that permits slavery, not regulative of a specific right.) |
| `c_ancestry` | enum | `native`, `foreign`, `mixed`, `any`, `unspecified` | Descent from the polity's founding/citizen lineage (e.g. both parents Attic-born for Periclean Athens). Genealogical fact. |
| `c_residence` | enum | `resident`, `non_resident`, `any`, `unspecified` | Whether the person physically lives in the polity's territory. |
| `c_wealth` | enum | `high`, `middle`, `low`, `any`, `unspecified` | Material-economic position (income, land, harvest yield, movable wealth). Productive capacity, not a legal class. |
| `c_kinship_role` | enum | `parent`, `child`, `spouse`, `sibling`, `heir`, `none`, `unspecified` | Family-relational position relative to another person. |
| `c_occupation` | string | free text (e.g. `farmer`, `artisan`, `priest`, `philosopher`, `soldier`, `merchant`, `prostitute`, `none`) | Productive / vocational role. |

Use `unspecified` when the group label does **not** constrain that dimension.
Use `any` when the group explicitly spans all values (e.g. "all persons"
spans both sexes).

## Two auxiliary fields

- `requires_rights_definition` (`true` / `false`)
  Set to **`true`** if the group is *intrinsically* a legal/office category
  that cannot be picked out without referring to the rights system itself
  (e.g. *Magistrates*, *Archons*, *Jurors*, *Voters*, *Citizens-defined-as-
  rights-holders*). In that case, fill the criterion fields with whatever you
  can still infer (often the underlying eligible sub-population), and flag
  the row so downstream analysis knows the cell is not law-independent.

  Set to **`false`** for groups whose criteria (sex, age, ancestry, ownership,
  wealth, occupation) can be stated without reference to specific rights —
  even when an emic term exists for them (e.g. *politēs* = free + adult +
  male + native-ancestry; the *word* is legal but the *cell* is not).

- `emic_label` (string or `null`)
  The native-language term (Greek / Latin / etc.) the polity itself uses for
  this cell, if you can infer it (e.g. `politēs`, `metoikos`, `doulos`,
  `eupatridēs`, `thēs`, `zeugitēs`, `pentakosiomedimnoi`, `civis`,
  `peregrinus`, `servus`, `pater familias`). `null` if no specific term is
  inferable.

## Hard rules

1. **Never** use the rights or resources a group is said to hold as a
   classification signal. The input you receive will only contain the group
   label and its polity/period — not the rule, verbatim, resource, or
   directionality. Even so, do not "fill in" rights to justify the criterion
   vector.
2. The criteria must be law-**presupposing** at most, never law-**defined**.
   "Owned as property" presupposes a legal system that permits property in
   persons, but it does not presuppose any specific right of the slave or
   master — that distinction is the whole point.
3. If a group label is ambiguous in the polity (e.g. *Citizens* in Roman
   Empire could mean *cives Romani* or *cives* of a local polis), pick the
   *most likely* extension given the polity context, and put the uncertainty
   in `criterion_reasoning`.
4. Output **JSON only**, no prose, no markdown fence, no commentary.

## Output schema

For each input item with index `i`, emit:

```json
{
  "i": <int>,
  "c_sex": "male" | "female" | "any" | "unspecified",
  "c_age": "adult" | "minor" | "elder" | "any" | "unspecified",
  "c_ownership_status": "free" | "enslaved" | "freed" | "any" | "unspecified",
  "c_ancestry": "native" | "foreign" | "mixed" | "any" | "unspecified",
  "c_residence": "resident" | "non_resident" | "any" | "unspecified",
  "c_wealth": "high" | "middle" | "low" | "any" | "unspecified",
  "c_kinship_role": "parent" | "child" | "spouse" | "sibling" | "heir" | "none" | "unspecified",
  "c_occupation": "<string>",
  "requires_rights_definition": true | false,
  "emic_label": "<string or null>",
  "criterion_reasoning": "<≤220-char sentence justifying the vector in rights-INDEPENDENT terms>"
}
```

Return a JSON array of these objects, one per input item, in the same order.

## Worked examples

Input: `{"i": 0, "group": "Citizens", "rule_polity": "Classical Athens",
"period": "Classical Greek (510–323 BCE)"}`

Output:
```json
{
  "i": 0,
  "c_sex": "male",
  "c_age": "adult",
  "c_ownership_status": "free",
  "c_ancestry": "native",
  "c_residence": "resident",
  "c_wealth": "any",
  "c_kinship_role": "unspecified",
  "c_occupation": "none",
  "requires_rights_definition": false,
  "emic_label": "politēs",
  "criterion_reasoning": "Adult free male of Attic ancestry resident in Attica; the cell is law-presupposing (Periclean ancestry law) but criteria are independent of voting/court rights."
}
```

Input: `{"i": 1, "group": "Magistrates", "rule_polity": "Classical Athens",
"period": "Classical Greek (510–323 BCE)"}`

Output:
```json
{
  "i": 1,
  "c_sex": "male",
  "c_age": "adult",
  "c_ownership_status": "free",
  "c_ancestry": "native",
  "c_residence": "resident",
  "c_wealth": "any",
  "c_kinship_role": "unspecified",
  "c_occupation": "magistrate",
  "requires_rights_definition": true,
  "emic_label": "archōn",
  "criterion_reasoning": "Office-holders — selection is rights-mediated (eligibility = citizen + sortition/election), so requires_rights_definition is true; underlying eligible cell is adult free native male."
}
```

Input: `{"i": 2, "group": "Slaves", "rule_polity": "Classical Athens",
"period": "Classical Greek (510–323 BCE)"}`

Output:
```json
{
  "i": 2,
  "c_sex": "any",
  "c_age": "any",
  "c_ownership_status": "enslaved",
  "c_ancestry": "any",
  "c_residence": "resident",
  "c_wealth": "low",
  "c_kinship_role": "unspecified",
  "c_occupation": "any",
  "requires_rights_definition": false,
  "emic_label": "doulos",
  "criterion_reasoning": "Owned as property by another person; the ownership relation is constitutive (definitionally prior to any rights doulos may hold or lack)."
}
```

Input: `{"i": 3, "group": "Metics", "rule_polity": "Classical Athens",
"period": "Classical Greek (510–323 BCE)"}`

Output:
```json
{
  "i": 3,
  "c_sex": "any",
  "c_age": "adult",
  "c_ownership_status": "free",
  "c_ancestry": "foreign",
  "c_residence": "resident",
  "c_wealth": "any",
  "c_kinship_role": "unspecified",
  "c_occupation": "any",
  "requires_rights_definition": false,
  "emic_label": "metoikos",
  "criterion_reasoning": "Free resident of foreign ancestry living in Attica; the cell is fixed by ancestry+residence regardless of legal regime."
}
```

Input: `{"i": 4, "group": "The wealthy", "rule_polity": "Classical Athens",
"period": "Classical Greek (510–323 BCE)"}`

Output:
```json
{
  "i": 4,
  "c_sex": "any",
  "c_age": "adult",
  "c_ownership_status": "free",
  "c_ancestry": "unspecified",
  "c_residence": "resident",
  "c_wealth": "high",
  "c_kinship_role": "unspecified",
  "c_occupation": "any",
  "requires_rights_definition": false,
  "emic_label": "pentakosiomedimnoi",
  "criterion_reasoning": "High economic position (Solonic top class = 500+ medimnoi yield); the criterion is productive capacity, not a legal right."
}
```
