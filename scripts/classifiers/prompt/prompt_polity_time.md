# Rule polity, time-reference

## Four fields per rule

- `rule_polity`            specific polity label
- `rule_polity_reasoning`  one short sentence (<= 250 chars)
- `rule_date`              ONE integer year (e.g. -348, 150)
- `rule_time_reasoning`    one short sentence, including the date
                            justification

## Core principle

Every rule has a polity and a single representative date. The rule-level
polity and date describe the **society and moment the rule actually
governs**, which may differ from the author's own floruit.

**The rule-level polity/time must be at least as specific as — and must
fall inside — any work-level constraints when those constraints are
provided.** The work-level annotation acts as a *background constraint*
giving the span and polity the work documents; the rule-level annotation
then refines that to the specific polity and the specific moment the
verbatim points at.

- A rule stated by an author about their own lived society is contemporary
  to the author and dated to the author's floruit.
- A rule an author describes as a feature of an earlier polity is
  past-referring and dated **within that earlier polity's time**.
- Default to the author's floruit **only when** there is no work-level
  constraint that says otherwise AND the verbatim gives no earlier
  anchor.

## Work-level priors (strong constraints)

For historian / biographical / antiquarian works, the input may include
these work-level fields:

- `work_polity`                    polity (or polities) the work documents
- `work_polity_reasoning`          one-line justification
- `work_time_reference`            `contemporary` or `past`
- `work_time_start`, `work_time_end`  year bounds the work spans
- `work_time_reasoning`            justification for the span
- `work_author_polity_cliopatria`  author's own polity per Cliopatria

**Treat these as constraints on the rule-level annotation:**

1. **Rule polity must be within `work_polity`** (equal to it, or a
   more specific sub-polity of it). Never assign a polity outside the
   work's scope unless the verbatim explicitly names one.
2. **If `work_time_reference == "past"`, the rule is past-referring.**
   `rule_date` MUST fall inside `[work_time_start, work_time_end]`.
   Never date a past-work rule to the author's floruit — that is the
   single most common failure mode and is explicitly forbidden when the
   work's time_reference is `past`.
3. **The rule's date should be more precise than the work's span.**
   Pick the specific year the verbatim anchors (a reform, a named ruler,
   an archonship, a battle, a festival). If the verbatim gives no finer
   anchor, take the midpoint of the work's `[start, end]` window — not
   the author's floruit, not either endpoint.
4. **If `work_time_reference == "contemporary"`** (the work is about the
   author's own society), default `rule_date` to the author's floruit
   and `rule_polity` to one of the `work_polity` values.
5. When work-level fields are absent (philosophy, oratory, satire, etc.):
   default to the author's floruit and polity as before.

**Worked example — the anti-pattern to avoid.**

- Work: Plutarch's *Instituta Laconica*.
- `work_polity = Classical Sparta`, `work_time_reference = past`,
  `work_time_start = -800`, `work_time_end = -200`.
- Candidate rule: "Foreign travel prohibition"; verbatim describes
  Spartan xenelasia as a long-standing institution without naming a
  specific year.
- **WRONG**: `rule_date = 100` (Plutarch's floruit). The rule is about
  a Spartan practice in a `past` work with a specific span — it cannot
  be dated to the author's lifetime.
- **RIGHT**: `rule_date = -500` (midpoint of the work's classical-Sparta
  span, and a canonical classical moment for the institution).
  `rule_polity = Sparta` (inside the work_polity).

## Verbatim override

The verbatim always wins over work-level priors. If the verbatim
unambiguously names a polity or a year that sits outside the work's
`[start, end]` window or outside its `polity` list, follow the verbatim
and record the deviation briefly in the reasoning.

## Task 1 — `rule_polity`

Pick the most specific polity the verbatim supports, constrained by
`work_polity` when present. Examples:

- Aristotle citing Solon's laws               → Archaic Athens (Solonic)
- Athenian orator describing Spartan custom   → Sparta
- Lucian satirising classical mythology       → Classical Greece / Homeric world
- Roman-era geographer describing 5th-c. Athens → Classical Athens
- Homeric / heroic-age narrative              → "Mythological / legendary setting"

## Task 3 — `rule_date` — SINGLE INTEGER YEAR

A single integer. Negative = BCE, positive = CE. **Never a range, never
two numbers separated by `|` or `to`.**

Precedence for picking the year:

1. A year or dateable event named explicitly in the verbatim.
2. A dateable regime / reform / archonship the verbatim points at
   (Draco -621, Solon -594, Cleisthenes -508, Thirty Tyrants -404, etc.).
3. Midpoint of `[work_time_start, work_time_end]` when the work is
   `past` and the verbatim gives no finer anchor.
4. Author's floruit — only if none of the above apply.

## Output format

Return ONLY valid JSON — a list of objects, one per input item (or an
object wrapping the list under `"results"`):

```json
{
  "i": 0,
  "rule_polity": "Classical Athens",
  "rule_polity_reasoning": "Aristotle writes from 4th-c. Athens; the rule documents Athenian civic norms.",
  "rule_date": -348,
  "rule_time_reasoning": "Stated by Aristotle at his floruit (-348); even framed as a universal it is a norm of his own polity."
}
```
