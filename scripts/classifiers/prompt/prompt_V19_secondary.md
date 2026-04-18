# Secondary Classifier — Group Specificity & Historical Distance

You receive an already-extracted rule produced by a first pass. Your job is to add two pieces of information that help filter out unreliable extractions.

The input rule is a JSON object with at least: `author`, `impact_year`, `work_title`, `criteria`, `group`, `resource`, `rule`, `verbatim`, `reasoning`.

## 1. GROUP_SPECIFICITY (score 1–5)

Rate how appropriately general the group is — high order of generality without being a tautology.

- **5 — Ideal generality.** Canonical near-immutable societal group covering a wide swath of the population (e.g. by gender, legal status, age, class, occupation, ethnicity, religion).
- **4 — Broad, still usable.** Compound but still societal: two or three generality axes combined (e.g. adult members of X, wealthy members of Y).
- **3 — Borderline.** A specific role, profession, or status within a broader class; still a recognisable social category but narrower.
- **2 — Too narrow.** Named sub-group or highly contextual role tied to a specific institution, moment, or place.
- **1 — Not a group / behavioural.** Defined by an action or a one-off referent (people who did X; the defendant in this case; a single named individual).

Return an **integer 1–5**.

## 2. IS_HISTORICAL (0 / 1)

Does the rule describe an event, law, or social arrangement from an era **well before the author's own lifetime** (roughly: more than ~150 years earlier, OR a mythological / pre-historical / scriptural / legendary past)?

- **1 = HISTORICAL.** The verbatim / reasoning points to a distant past relative to the author: distant ancestors or lawgivers, foundational myths, scriptural figures from earlier scriptures, legendary or heroic settings, pre-historical institutions narrated as bygone.
- **0 = CONTEMPORARY.** The rule describes the author's own time or the generation or two around it, OR a timeless observation the author makes about their own society, OR a legal code / institution still in force in their era.

When ambiguous, prefer **0** (contemporary). Only flag **1** when the text clearly points to a distant past.

Return an **integer 0 or 1**.

## 3. REASONING

One short sentence (≤25 words) explaining both scores.

## Output format

Return ONLY valid JSON — a list of objects, each with keys `i` (the input index), `group_specificity` (int 1–5), `is_historical` (int 0 or 1), and `reasoning` (string).

Example:

```json
[
  {"i": 0, "group_specificity": 5, "is_historical": 0, "reasoning": "Canonical societal group; author describes a contemporary norm."},
  {"i": 1, "group_specificity": 3, "is_historical": 1, "reasoning": "Borderline specific group; the narrative concerns a scriptural or legendary past."}
]
```
