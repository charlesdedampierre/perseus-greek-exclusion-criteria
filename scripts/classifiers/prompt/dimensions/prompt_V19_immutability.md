# Group Near-Immutability Classifier

You receive an already-extracted rule and score how NEAR-IMMUTABLE the group is on a 1–5 scale. The question is: **how easily can an individual leave the group within the author's society?**

The input is a JSON object with at least: `group`, `rule`, `verbatim`, `reasoning`.

## Scoring guide (1 = mutable / behavioural, 5 = strictly immutable)

- **5 — Strictly immutable.** Biologically or birth-fixed traits that cannot be changed by choice: sex / gender, ethnicity, lineage, family / clan membership, age (at a given moment), skin colour, hereditary disability.

- **4 — Very hard to change; legal / structural birth-status.** Citizenship (requires naturalisation or exile), free vs. enslaved legal status (requires formal manumission), caste, nobility, hereditary priesthood, born-vs-converted religion.

- **3 — Changeable with effort but still a durable social identity.** Occupation / profession acquired through training, religious initiation, marital status, wealth bracket (rich vs. poor, acquired over time), foreign residency (metic), guild membership.

- **2 — Role-bound or episodic.** Status tied to a specific procedure or temporary condition: litigant, defendant, plaintiff, juror for a single trial, patient during an illness, soldier on active duty, office-holder during a term.

- **1 — Behavioural or one-off.** The group is defined by an action, choice, or single event: "men who committed adultery", "people who swore the oath", "the defendant in this case", a single named individual, "the multitude who cheered".

## Rules

- Rate the GROUP as *defined in this rule*, not the group's category in general. A group like "Priests" is usually 4 (hereditary priesthood) but 3 if the text describes an elective priesthood.
- If the group label is ambiguous, use the `rule` / `verbatim` / `reasoning` context to choose.
- Default to the lower score when two levels are both plausible.

## Output format

Return ONLY valid JSON — a list of objects, each with keys `i` (input index), `group_immutability` (int 1–5), `immutability_reasoning` (short string ≤25 words).

Example:

```json
[
  {"i": 0, "group_immutability": 5, "immutability_reasoning": "Women is a sex-defined group; membership is biologically fixed."},
  {"i": 1, "group_immutability": 1, "immutability_reasoning": "Defined by an action (swearing an oath) — membership is episodic."}
]
```
