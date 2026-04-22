# Work polity, time-reference, and date-range classifier — V2 (historians)

Revision of V1 after inspection on a 20-item sample. V2 tightens two
things:

1. **`mentioned_polities_in_work` is a LIST** — historiographic works
   routinely span multiple polities (Polybius: Rome + Carthage +
   Macedon + Seleucid; Plutarch's *Parallel Lives*: an Athenian + a
   Roman; Appian's *Roman History* series: Rome + every campaign
   enemy). Return ALL the distinct polities the work meaningfully
   documents, not a single "best" one.
2. **Dates become a RANGE** — `mentioned_time_start_in_work` and
   `mentioned_time_end_in_work`. The start is the earliest event
   narrated; the end is the latest event narrated. For single-point
   subjects (a life, a single battle, a single reform year), start ==
   end.

Adapted from the rule-level prompt V3. The unit of annotation is the
whole WORK, not its rules. The fields capture what the work DOCUMENTS,
not properties of the work itself.

Inputs: author, author floruit year, author polity, work title, genre /
form_of_creative_work, and the model's own knowledge of the canonical
historiographic corpus. No passage-level text is provided.

## Six fields per work

- `mentioned_polities_in_work`    LIST of polities the work documents
- `mentioned_polity_reasoning`    one short sentence (<= 300 chars)
- `mentioned_time_reference`      exactly one of {contemporary, past, mixed}
- `mentioned_time_start_in_work`  earliest year narrated (integer; BCE = negative)
- `mentioned_time_end_in_work`    latest year narrated (integer; BCE = negative)
- `mentioned_time_reasoning`      one short sentence, including the date
                                   range justification (<= 300 chars)

## Core principle — the SUBJECT the work documents

For a historian, the relevant polity / time is what the WORK NARRATES,
not where the author sat and not when the work was published. Thucydides
wrote from Athens but his work documents the Peloponnesian conflict;
Plutarch wrote under Rome but his Lives document Archaic Athens, Sparta,
late-Republican Rome, and Hellenistic kingdoms.

`mentioned_time_reference` still asks whether the events narrated fall
within the author's lifetime (`contemporary`), before it (`past`), or
both in comparable proportion (`mixed`).

## Task 1 — `mentioned_polities_in_work` (LIST)

Return all polities / political settings the work MEANINGFULLY documents
as a list of specific labels. Rules:

- **Always a list**, even for single-polity works. `["Classical Athens"]`
  is fine for *Life of Pericles*; `["Rome"]` alone is fine for *Roman
  Questions*.
- **Enumerate genuinely distinct polities**, not sub-eras of the same
  polity. Do NOT list "Roman Republic" AND "Late Roman Republic" — pick
  the more specific one ("Late Roman Republic").
- **Parallel Lives**: list BOTH polities (e.g. *Comparison of Theseus
  and Romulus* → `["Mythological Athens", "Early Roman Kingdom"]`).
- **Campaign narratives**: list aggressor + theatres only if the work
  gives substantive coverage to both. Xenophon's *Anabasis* is about
  Greek mercenaries crossing Persia — `["Achaemenid Persia", "Classical
  Greek mercenary polis-world"]`.
- Never use "Generic", "Universal", or "Greco-Roman world" as a single
  catch-all if you can name the specific theatres.

Reference labels by work:

- Thucydides, Peloponnesian War → `["Classical Athens", "Classical
  Sparta and Peloponnesian League"]`
- Herodotus, Histories → `["Achaemenid Empire", "Classical Greek
  poleis", "Lydia", "Pharaonic Egypt"]`
- Xenophon, Anabasis → `["Achaemenid Persia", "Classical Greek
  mercenary polis-world"]`
- Xenophon, Hellenica → `["Classical Athens", "Classical Sparta",
  "Classical Thebes", "Classical Greek poleis more broadly"]`
- Xenophon, Cyropaedia → `["Achaemenid Empire (Cyrus the Great)"]`
- Plutarch, Life of Solon → `["Archaic Athens (Solonic)"]`
- Plutarch, Life of Caesar → `["Late Roman Republic"]`
- Plutarch, *Comparison of Theseus and Romulus* → `["Mythological
  Athens", "Early Roman Kingdom"]`
- Plutarch, *Life of Alexander* → `["Macedonian Empire", "Achaemenid
  Empire"]`
- Plutarch, Roman Questions → `["Rome (antiquarian)"]`
- Josephus, Antiquities → `["Ancient Israel / Second Temple Judaism"]`
- Josephus, Jewish War → `["Judea", "Roman Empire (Flavian)"]`
- Polybius, Histories → `["Rome", "Carthage", "Macedonian kingdom",
  "Seleucid Empire", "Achaean League"]`
- Appian, Civil Wars → `["Late Roman Republic"]`
- Appian, Punic Wars → `["Rome", "Carthage"]`
- Appian, Mithridatic Wars → `["Rome", "Pontic kingdom (Mithridates
  VI)"]`
- Diogenes Laertius, Lives → `["Greek philosophical tradition
  (pan-Hellenic)"]`
- Strabo, Geography → `["Roman Empire", "Hellenistic Mediterranean",
  "named provinces Strabo actually surveys in the selected books"]`

## Task 2 — `mentioned_time_reference`

Exactly one of:

- **`contemporary`** — the work documents events within, or directly
  adjacent to, the author's own lifetime:
  - Thucydides, Peloponnesian War
  - Xenophon, Anabasis / Hellenica
  - Josephus, Jewish War / Against Apion / Life
  - Plutarch, Life of Galba / Otho
  - Strabo, Geography (describes Strabo's own early-Principate world)

- **`past`** (DEFAULT for most biographies and antiquarian histories) —
  the work reconstructs an earlier society the author did not live in:
  - Herodotus, Histories
  - Plutarch, Life of Solon / Lycurgus / Theseus / Romulus / Caesar /
    Cicero / Pompey / Cato etc.
  - Josephus, Antiquities
  - Appian, Civil Wars / Punic Wars / Mithridatic Wars etc.
  - Diogenes Laertius, Lives

- **`mixed`** — the work meaningfully covers BOTH the author's own era
  AND a clearly earlier era in comparable proportion:
  - Polybius, Histories (starts -264, continues into his adulthood)
  - Plutarch, *Of Banishment* and similar moral essays that draw on both
    Archaic and contemporary exempla in comparable depth
  - Strabo on specific books that are as much historical as geographical

## Task 3 — date RANGE (two integer fields)

`mentioned_time_start_in_work` = earliest year of events narrated.
`mentioned_time_end_in_work`   = latest year of events narrated.

Rules:

- Both are integers. BCE = negative. CE = positive.
- For a **single life or single event**, start == end is acceptable but
  prefer natural span. For a Plutarch Life, use `[birth, death]` of the
  subject. For a single battle, use the battle year for both.
- For a **running narrative**, use the opening anchor for start and the
  closing anchor for end.
- For a **compilation or antiquarian miscellany**, use the earliest and
  latest exemplum the work draws on.
- The string `"mythological"` is NOT allowed any more. For deep legendary
  content pick a traditional anchor (e.g. Trojan War ~-1200, traditional
  founding of Rome -753) — integers only.

Reference ranges:

- Thucydides, Peloponnesian War              → `[-431, -411]`
- Herodotus, Histories                       → `[-560, -479]`
- Xenophon, Anabasis                         → `[-401, -399]`
- Xenophon, Hellenica                        → `[-411, -362]`
- Xenophon, Cyropaedia                       → `[-559, -530]`
- Plutarch, Solon                            → `[-638, -558]`  (Solon's lifetime)
- Plutarch, Theseus                          → `[-1300, -1200]`
- Plutarch, Romulus                          → `[-771, -717]`  (traditional)
- Plutarch, Lycurgus                         → `[-900, -800]`  (traditional Lycurgan horizon)
- Plutarch, Pericles                         → `[-495, -429]`
- Plutarch, Alexander                        → `[-356, -323]`
- Plutarch, Caesar                           → `[-100, -44]`
- Plutarch, Cato the Younger                 → `[-95, -46]`
- Plutarch, Brutus                           → `[-85, -42]`
- Plutarch, Galba                            → `[68, 69]`
- Plutarch, Isis and Osiris                  → `[-2500, 100]`  (spans Pharaonic antiquity
                                                               to Plutarch's own day)
- Plutarch, Roman Questions                  → `[-753, 100]`   (founding to Plutarch)
- Josephus, Antiquities                      → `[-2000, 66]`
- Josephus, Jewish War                       → `[66, 74]`
- Josephus, Against Apion                    → `[-2000, 95]`
- Josephus, Life                             → `[37, 100]`
- Polybius, Histories                        → `[-264, -146]`
- Appian, Civil Wars                         → `[-133, -35]`
- Appian, Punic Wars                         → `[-264, -146]`
- Appian, Mithridatic Wars                   → `[-89, -63]`
- Diogenes Laertius, Lives                   → `[-600, 300]`
- Strabo, Geography                          → `[-200, 23]`   (some historical depth but
                                                              the ethnographic present is
                                                              Augustan-Tiberian)

## Output format

Return ONLY valid JSON — a list of objects, one per input item (or an
object wrapping the list under `"results"`):

```json
{
  "i": 0,
  "mentioned_polities_in_work": ["Classical Athens", "Classical Sparta and Peloponnesian League"],
  "mentioned_polity_reasoning": "Thucydides narrates the 27-year war between the Athenian and Peloponnesian alliances.",
  "mentioned_time_reference": "contemporary",
  "mentioned_time_start_in_work": -431,
  "mentioned_time_end_in_work": -411,
  "mentioned_time_reasoning": "Opens at the war's outbreak (-431) and ends mid-narrative at -411 where Thucydides stops; Thucydides served in the war."
}
```

## Worked examples

1. **Thucydides, *The Peloponnesian War***
   → contemporary · `["Classical Athens", "Classical Sparta and Peloponnesian League"]`
   · [-431, -411]

2. **Herodotus, *The Histories***
   → past · `["Achaemenid Empire", "Classical Greek poleis", "Lydia", "Pharaonic Egypt"]`
   · [-560, -479]

3. **Xenophon, *Anabasis***
   → contemporary · `["Achaemenid Persia", "Classical Greek mercenary polis-world"]`
   · [-401, -399]

4. **Xenophon, *Hellenica***
   → contemporary · `["Classical Athens", "Classical Sparta", "Classical Thebes",
   "Classical Greek poleis more broadly"]` · [-411, -362]

5. **Xenophon, *Cyropaedia***
   → past · `["Achaemenid Empire (Cyrus the Great)"]` · [-559, -530]

6. **Plutarch, *Life of Solon***
   → past · `["Archaic Athens (Solonic)"]` · [-638, -558]

7. **Plutarch, *Life of Caesar***
   → past · `["Late Roman Republic"]` · [-100, -44]

8. **Plutarch, *Comparison of Theseus and Romulus***
   → past · `["Mythological Athens", "Early Roman Kingdom"]` · [-1300, -717]

9. **Plutarch, *Life of Alexander***
   → past · `["Macedonian Empire", "Achaemenid Empire"]` · [-356, -323]

10. **Plutarch, *Life of Galba***
    → contemporary · `["Roman Empire (Year of the Four Emperors)"]` · [68, 69]

11. **Plutarch, *Isis and Osiris***
    → mixed · `["Pharaonic Egypt (religious-mythic)", "Roman Empire (Plutarch's own
    Hellenistic-religious reception)"]` · [-2500, 100]

12. **Josephus, *Antiquities of the Jews***
    → past · `["Ancient Israel / Second Temple Judaism"]` · [-2000, 66]

13. **Josephus, *The Wars of the Jews***
    → contemporary · `["Judea", "Roman Empire (Flavian)"]` · [66, 74]

14. **Polybius, *The Histories***
    → mixed · `["Rome", "Carthage", "Macedonian kingdom", "Seleucid Empire",
    "Achaean League"]` · [-264, -146]

15. **Appian, *The Civil Wars***
    → past · `["Late Roman Republic"]` · [-133, -35]

16. **Appian, *The Punic Wars***
    → past · `["Rome", "Carthage"]` · [-264, -146]

17. **Diogenes Laertius, *Lives of Eminent Philosophers***
    → past · `["Greek philosophical tradition (pan-Hellenic)"]` · [-600, 300]

18. **Strabo, *Geography***
    → contemporary · `["Roman Empire", "Hellenistic Mediterranean"]` · [-200, 23]
