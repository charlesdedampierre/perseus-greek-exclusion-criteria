# Rule polity, time-reference, and date classifier — V2

Annotate each social-exclusion / inclusion rule with four fields:

- `rule_polity`           the specific polity the rule documents
- `rule_time_reference`   exactly one of {contemporary, past, mixed}
- `rule_date`             a year or narrow year-range (negative = BCE)
- `rule_polity_reasoning` one short sentence (<= 250 chars)
- `rule_time_reasoning`   one short sentence, includes the date justification

## Core principle

EVERY rule has a polity and a date. There are NO "timeless", "abstract",
"generic", or "universal" rules: even the most maxim-like philosophical,
medical, or ethical statement was uttered by a specific author embedded in a
specific society at a specific moment, and it documents that society's norms. There are also NO "future" rules. The moment a rule is stated it is
CONTEMPORARY to its author. Eschatological, prophetic, or utopian rules are
dated to when the author states them, not to when they will apply.

## Inputs per rule

`author`, `author_floruit_year`, `author_polity`, `author_description`,
`work_title`, `work_genre`, `rule`, `criteria`, `group`, `resource`,
`verbatim`.

## Task 1 — `rule_polity`

Assign a specific polity label. DEFAULT = the author's own polity
(`author_polity`), because the rule is stated from within it. Deviate only
when the rule is explicitly ABOUT a different society:

- Aristotle citing Solon's laws             → Archaic Athens (Solonic)
- Athenian orator describing Spartan custom → Sparta
- Lucian satirising classical mythology     → Classical Greece / Homeric world
- Roman-era geographer describing 5th-c. Athens → Classical Athens
- A rule embedded in a narrative set in a clearly pre-historical heroic age
  (Homeric gods, Titans) → `"Mythological / legendary setting"`

NEVER use "Generic / abstract / no specific polity". If the rule has no
explicit historical target, the polity is the author's polity. Philosophical
maxims, medical protocols, and ethical universals all belong to the polity in
which the author was writing.

## Task 2 — `rule_time_reference`

Exactly one of:

- **`contemporary`** (DEFAULT)
  The rule is stated by the author for their own society. Includes:
  - philosophical, moral, and ethical maxims
  - medical / scientific guidance (documents the author's contemporary
     medical practice)
  - legal and procedural rules in force in the author's time
  - religious commandments given by a contemporary community
  - eschatological, prophetic, or utopian rules (contemporary to the
     author who states them)
  - rules stated as "universal", "timeless", or "always"

- **`past`**
  The rule DESCRIBES a society that existed clearly before the author's time
  (not just a rule that cites an older source in passing). Examples:
  - Aristotle reporting Solonic property classes
  - Roman-era Lucian or Pausanias reconstructing 5th-c. Athens
  - A Christian writer discussing Mosaic Law as a historical institution
  - Aristotle's *Politics* describing the constitution of archaic Syracuse

- **`mixed`**
  Rare. The rule meaningfully documents both the author's own society AND an
  earlier era in comparable proportion (e.g. Pausanias' *Periegesis*, where
  a single passage weighs contemporary Roman-era Greece against the
  Classical polis it replaced).

There is NO `timeless` and NO `future`.

## Task 3 — `rule_date`

A specific year OR a narrow year-range, in years (negative = BCE, positive =
CE). This is the date the rule DOCUMENTS, not the date the manuscript was
edited.

- CONTEMPORARY rules → the author's floruit year or a tight range around it.
- PAST rules → the date when the described society / law was in force.
- MIXED → two values separated by `|` (author range `|` historical range).

Prefer a specific year when recoverable (a named lawgiver, reform, ruler, or
event); otherwise a narrow range of at most ±25 years. Do not default to a
single century — be as precise as the evidence allows.

## Output format

Return ONLY valid JSON, a list of objects, one per input item:

```json
{
  "i": 0,
  "rule_polity": "Classical Athens",
  "rule_polity_reasoning": "Aristotle writes from 4th-c. Athens; the rule documents Athenian civic norms.",
  "rule_time_reference": "contemporary",
  "rule_date": "-350 to -340",
  "rule_time_reasoning": "Stated by Aristotle at his floruit (~-348); even when framed as a universal, it is a norm of his own polity."
}
```
