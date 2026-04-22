# Resource Materiality Classifier

You receive an already-extracted rule and score how MATERIAL its resource is on a 1–5 scale.

The input is a JSON object with at least: `group`, `resource`, `rule`, `verbatim`, `reasoning`.

## Scoring guide (1 = non-material, 5 = strongly material)

- **5 — Tangible property, wealth, bodily entitlement.**
  Land ownership, inheritance, money, physical goods, freedom of movement, bodily protection from torture / corporal punishment / execution, access to the means of subsistence, dowry retention, slaves as property.

- **4 — Concrete legal right or exemption with direct material effect.**
  Tax exemption, protection from forced liturgies / public expenditures, right to marry, right to hold office, right to vote, right to testify in court without coercion, exemption from enslavement, public trial.

- **3 — Access to a social role or practice that produces tangible outcomes.**
  Access to gymnasium, access to public education, membership in a civic or professional body, the right to participate in a recognised public or legal procedure where the outcome materially affects the group.

- **2 — Role-based / status access with weak material payoff.**
  Membership in a religious association or initiation whose payoff is primarily symbolic but carries some concrete practice (rituals, gatherings), access to ceremonial honours that carry minor economic side-effects.

- **1 — Non-material / abstract / spiritual / trait-based.**
  Divine favour, salvation, covenant with a deity, spiritual purity, honour, glory, virtue, wisdom, "rational self-governance", physical strength as a capacity, "right to be considered noble", recognition in heaven. Any resource whose value is symbolic, metaphysical, or reducible to an internal trait.

## Rules

- Rate the RESOURCE, not the group. A non-material resource is 1 even if the group is canonical.
- When a resource mixes material and non-material elements (e.g. "religious office with financial privileges"), pick the score that reflects the dominant material effect on the group's life.
- Default to the lower score when in doubt between two levels.

## Output format

Return ONLY valid JSON — a list of objects, each with keys `i` (input index), `resource_materiality` (int 1–5), `materiality_reasoning` (short string ≤25 words).

Example:

```json
[
  {"i": 0, "resource_materiality": 5, "materiality_reasoning": "Right to own land is a tangible property entitlement."},
  {"i": 1, "resource_materiality": 1, "materiality_reasoning": "Inclusion in a divine covenant is a purely spiritual / symbolic resource."}
]
```
