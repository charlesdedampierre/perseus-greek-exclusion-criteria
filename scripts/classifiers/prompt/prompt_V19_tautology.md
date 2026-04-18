# Tautology Classifier

You receive an already-extracted rule and flag whether it is a TAUTOLOGY. A rule is tautological when the group's definition already implies the resource it lacks or gains — so the rule tells us nothing non-obvious about social stratification.

The input is a JSON object with at least: `group`, `resource`, `rule`, `directionality`, `verbatim`, `reasoning`.

## What counts as tautological

A rule is tautological when *restating the group* would already tell you the outcome. The rule is information-free.

- "Slaves have less freedom" → tautological (slavery **is** unfreedom).
- "Non-citizens have less citizenship" → tautological (restates the definition).
- "Poor people lack money / wealth" → tautological (poverty **is** lack of money).
- "Wealthy people have wealth" → tautological.
- "Children are not adults" → tautological.
- "Illegitimate children lack legitimacy" → tautological.
- "The dead have less life / right to live" → tautological.
- "Sick people have less health" → tautological.
- "Literate people have access to literacy" → tautological.
- "Freedmen have more freedom than slaves" is NOT tautological (it says a freed status grants actual protections — non-obvious).

## What does NOT count as tautological

- A legal or material right that is NOT part of the group's definition, even if "expected" culturally. "Women cannot own land in Attica" is not tautological — women being female does not mean they cannot own land in every society.
- A rule whose resource is concrete and materially distinct from the group's defining trait: "Slaves have less protection from corporal punishment" is NOT tautological (physical protection is not what *slave* means, even if correlated).
- A rule about a specific procedure / exemption / entitlement is NOT tautological even when the group is defined by the related attribute: "The elderly are exempt from military service" is not tautological — being old is not the definition of exemption.

## Rules

- Output `1` ONLY when the rule genuinely restates the group's definition. When in doubt, output `0`.
- The sense of the directionality matters: if the group is *Poor* and the resource is *money*, LESS = tautological, MORE = non-tautological (actually paradoxical).
- Look through the `resource`, `rule`, and `reasoning` to decide.

## Output format

Return ONLY valid JSON — a list of objects, each with keys `i` (input index), `tautological` (int 0 or 1), `tautology_reasoning` (short string ≤25 words).

Example:

```json
[
  {"i": 0, "tautological": 1, "tautology_reasoning": "'Poor people lack wealth' restates poverty as a definition."},
  {"i": 1, "tautological": 0, "tautology_reasoning": "Protection from torture is a distinct legal right, not part of the slave definition."}
]
```
