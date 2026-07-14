# Granular right classification — group-independent

You assign each corpus rule to **one granular right** from a controlled vocabulary.
The goal is a level of right that is precise enough that **the same group of people,
in the same place and the same period, is never described as both having and lacking
the same granular right** — unless the sources genuinely contradict each other.

## Why this matters

Coarse rights conflate distinct resources and produce false contradictions. The clearest
example: *"Protection from corporal punishment"* lumps together two genuinely different
things for slaves in Classical Athens —

- protection from **private assault / outrage** (the *hubris* law shielded even slaves
  from being struck or outraged) — slaves partly **had** this, and
- protection from **judicial torture** (*basanos*, the interrogation of slaves under
  torture) — slaves **did not** have this.

One coarse label therefore records both "has" and "lacks." The fix is to classify the
two rules under two different granular rights. Your job is to make exactly these
distinctions.

## The defining principle

> A granular right is defined by the **kind of resource, protection, or action** at
> stake — **never** by who holds it.

Do **not** encode the group into the right. "Eligibility for the archonship" is a right;
"Eligibility for the archonship for wealthy men" is **not** — the wealth restriction
belongs to the *group*, not the right. Two rules about the same office go under the same
granular right even if one grants it and the other denies it to a sub-group; that
residual tension is a fact about the group, not a signal to split the right.

But genuinely different resources **must** be split:

- **Coercion / the body** — separate (a) judicial torture/interrogation, (b) penal
  corporal punishment by the state, (c) protection from private assault / outrage,
  (d) protection from capital punishment / execution, (e) protection from enslavement.
- **Office** — separate distinct offices where the sources name them: archonship,
  generalship/military command, council (boulē) membership, treasurer/financial office,
  jury/judicial service, priesthood, diplomatic office. If the verbatim only says
  "office" generically, use the generic "Eligibility for public office".
- **Political voice** — separate voting in the assembly, speaking/addressing the
  assembly, and proposing legislation.
- **Property** — separate owning/retaining property, inheriting, disposing/alienating,
  and retaining one's own earnings.
- **Standing in court** — separate the right to a trial/legal standing from immunity
  from prosecution and from giving valid testimony.

## Inputs you receive

Per rule:

- `resource` — the original fine-grained resource label assigned at extraction.
- `resource_meta` — the coarse meta-right the rule currently sits under.
- `rule` — one-line summary.
- `verbatim` — the quotation from the source (**the primary evidence**).
- `rule_polity` — the polity.

## Controlled vocabulary

You are given a `taxonomy`: a list of granular rights, each with a `right` label and the
`parent_meta` it refines. **Choose the single best-fitting `right` from this list.**
Only if no entry fits may you propose a new label — set `"is_new": true` and keep the
new label in the same style (a group-independent noun phrase naming the resource).

## Output schema

Return a JSON array, one object per input rule, in input order:

```json
{
  "i": <int>,
  "right": "<granular right label, preferably from the taxonomy>",
  "parent_meta": "<the resource_meta it refines>",
  "is_new": false,
  "reasoning": "<≤180 chars: which words in the verbatim fix the kind of resource>"
}
```

Rules:

1. The `right` must name the **kind of resource**, never the group.
2. Make the coercion/office/property/voice distinctions above whenever the verbatim
   supports them.
3. Prefer an existing taxonomy label over inventing one.
4. Output JSON only — no prose, no markdown fence.
