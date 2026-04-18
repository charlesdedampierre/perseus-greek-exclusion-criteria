# Resource Persistence Classifier

You receive an already-extracted rule and score the PERSISTENCE of its resource on a 1–5 scale. The question is: **once an individual in the group gains or loses this resource, how long does that hold in their life?**

The input is a JSON object with at least: `group`, `resource`, `rule`, `verbatim`, `reasoning`.

## Scoring guide (1 = very short-lived, 5 = very persistent)

- **5 — Lifelong / structural.** The resource holds for the person's whole life or across many years: ownership of land, inheritance, freedom vs. enslavement, citizenship status, permanent legal standing, lifelong priesthood, right to bequeath, marital property rights, nobility.

- **4 — Long-term but revocable.** The resource lasts for many years but can change: right to hold office across a career, long-term tax status, marital rights while a marriage lasts, permanent-till-revoked protections, membership in an institution one can leave.

- **3 — Bounded to a life stage or recurring period.** The resource attaches to a phase (childhood, adulthood, old age), or recurs every year / every cycle (annual festival right, right during military service, right while employed in a role).

- **2 — Brief episode or single procedure.** The resource holds only for the duration of a specific procedure or transaction: right to a fair trial in one case, right to speak during one assembly session, protection while a specific ritual is carried out.

- **1 — Momentary / one-off.** The resource is exhausted on a single occasion and has no durable afterlife: right to speak at a specific event, a one-time exemption, access to a single ceremony, a single transient protection bound to one narrow moment.

## Rules

- Rate the RESOURCE's persistence as it applies to members of the group, not the rule or the verbatim.
- If the resource's duration depends on a contingent event (e.g. illness), take the normal case for an individual affected: a patient's right lasts through the illness (2), not beyond.
- Default to the lower score when two levels are both plausible.

## Output format

Return ONLY valid JSON — a list of objects, each with keys `i` (input index), `resource_persistence` (int 1–5), `persistence_reasoning` (short string ≤25 words).

Example:

```json
[
  {"i": 0, "resource_persistence": 5, "persistence_reasoning": "Land ownership persists across the owner's life and can be bequeathed."},
  {"i": 1, "resource_persistence": 1, "persistence_reasoning": "Right to speak at a single meeting is exhausted after that meeting."}
]
```
