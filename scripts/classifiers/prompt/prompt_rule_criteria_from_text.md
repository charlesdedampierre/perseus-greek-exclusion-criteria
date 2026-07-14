# Rule → text-grounded criterion vector

You annotate each rule with the criteria that the **verbatim text itself constrains**, not the criteria a historian would fill in from background knowledge.

This is the methodological correction to the previous `prompt_group_criteria.md` pipeline. There, the classifier was given the *group label* (e.g. `Citizens`) plus polity context, and used its background knowledge of Athenian law to fill in `(male, adult, free, native, resident, …)`. The criterion vector was therefore really about the *label*, not about what the source actually said.

Here we invert that. The verbatim is the only evidence. The emic label is just an observation about what the text *calls* the people in scope. The criterion vector is what the **text and the emic words in it** force.

## Inputs you receive

Per rule:

- `verbatim` — short quotation from the source.
- `rule` — one-line summary of what the rule says.
- `group_label` — the rough English label assigned at extraction time (e.g. `Citizens`, `Slaves`, `Women`, `Metics`). **This is not a definition. Treat it as a hint about the emic term, nothing more.**
- `rule_polity` — the polity the rule belongs to (Classical Athens, Roman Empire, …).
- `reasoning` — the extractor's one-line justification.

## Three evidence levels — the central distinction

For each criterion axis, choose **one** of three values:

| Evidence level | Meaning | Example |
|---|---|---|
| `stated` | The verbatim's words directly name the criterion value. The words "free men" name sex=male and ownership=free. "Adult", "wealthy", "Attic", "metic", "resident of Athens" each *state* a criterion. | *"free adult males of Attic descent may sit on juries"* → sex=male **stated**, age=adult **stated**, ownership=free **stated**, ancestry=native **stated**. |
| `implied` | The emic word the verbatim uses *intrinsically* presupposes the criterion value. "Wife" presupposes sex=female and age=adult. "Slave" presupposes ownership=enslaved. "Child" presupposes age=minor. The presupposition is **lexical**, not historical. | *"a wife may not sell her own dowry"* → sex=female **implied** (by *wife*), age=adult **implied** (by *wife*). *"slaves may not testify in court"* → ownership=enslaved **implied** (by *slaves*). |
| `unspecified` | The verbatim and its emic words do not constrain this axis, OR you would need historical/background knowledge of the polity's law to fill it in. **Treat the absence of constraint conservatively — when in doubt, choose `unspecified`.** | *"Athenian citizens may vote in the Ekklesia"* — *citizen* lexically presupposes ownership=free (implied), and *Athenian* presupposes ancestry=native (implied). It does **not** lexically presuppose sex=male or age=adult — *those are historical facts about Athenian law, not lexical facts about the word*. → sex=**unspecified**, age=**unspecified**, ownership=**implied** (free), ancestry=**implied** (native), residence=**implied** (resident, by political participation in Athens). |

### The rule that resolves most edge cases

> If a reader who knew the meaning of the English/emic words in the verbatim but *nothing about the history of this polity* could not infer the criterion value, mark it `unspecified`.

This is the test: does the **lexical meaning** of the words force the value, or does **historical knowledge of the polity** force it? Only the former counts as `stated` / `implied`. The latter is exactly what we are trying to keep out of the criterion vector.

## Output schema

For each input rule with index `i`, emit:

```json
{
  "i": <int>,
  "c_sex":             {"value": "male"|"female"|"any"|"unspecified", "evidence": "stated"|"implied"|"unspecified"},
  "c_age":             {"value": "adult"|"minor"|"elder"|"any"|"unspecified", "evidence": "stated"|"implied"|"unspecified"},
  "c_ownership_status":{"value": "free"|"enslaved"|"freed"|"any"|"unspecified", "evidence": "stated"|"implied"|"unspecified"},
  "c_ancestry":        {"value": "native"|"foreign"|"mixed"|"any"|"unspecified", "evidence": "stated"|"implied"|"unspecified"},
  "c_residence":       {"value": "resident"|"non_resident"|"any"|"unspecified", "evidence": "stated"|"implied"|"unspecified"},
  "c_wealth":          {"value": "high"|"middle"|"low"|"any"|"unspecified", "evidence": "stated"|"implied"|"unspecified"},
  "c_occupation":      {"value": "<string or 'unspecified'>", "evidence": "stated"|"implied"|"unspecified"},
  "emic_label_in_text": "<the categorical noun(s) the verbatim actually uses — e.g. 'citizens', 'free men', 'wives', 'metoikoi', 'douloi', 'pentakosiomedimnoi'>",
  "criterion_reasoning": "<≤220-char sentence pointing to the words in the verbatim that license each non-unspecified axis>"
}
```

Rules:

1. If `evidence == "unspecified"`, the `value` must also be `"unspecified"`.
2. If `evidence == "stated"` or `"implied"`, `value` must be a concrete value (not `"any"` and not `"unspecified"`). Reserve `"any"` only for verbatims that explicitly say the rule applies regardless of an axis (e.g. *"any person, slave or free, who…"* → ownership=any **stated**).
3. The `emic_label_in_text` must be drawn from the verbatim's actual nouns. If the verbatim uses an English translation, take the English categorical noun (`citizens`, `wives`, `slaves`). If it uses a Greek/Latin term, take that.
4. The `criterion_reasoning` must cite specific words from the verbatim. Do not justify with appeals to historical context.
5. Output **JSON only**, no prose, no markdown fence.

Return a JSON array of these objects, one per input rule, in the same order as the input.

## Worked examples

### Example 1 — fully lexical

Input:
```json
{"i": 0, "verbatim": "free adult males of Attic descent may sit on juries", "rule": "Jury eligibility", "group_label": "Citizens", "rule_polity": "Classical Athens", "reasoning": "Solonic / Periclean jury law."}
```

Output:
```json
{
  "i": 0,
  "c_sex": {"value": "male", "evidence": "stated"},
  "c_age": {"value": "adult", "evidence": "stated"},
  "c_ownership_status": {"value": "free", "evidence": "stated"},
  "c_ancestry": {"value": "native", "evidence": "stated"},
  "c_residence": {"value": "unspecified", "evidence": "unspecified"},
  "c_wealth": {"value": "unspecified", "evidence": "unspecified"},
  "c_occupation": {"value": "unspecified", "evidence": "unspecified"},
  "emic_label_in_text": "free adult males of Attic descent",
  "criterion_reasoning": "The verbatim names each of sex='males', age='adult', ownership='free', and ancestry='Attic descent' directly."
}
```

### Example 2 — implied by emic word

Input:
```json
{"i": 1, "verbatim": "a wife may not alienate her dowry without her husband's consent", "rule": "Dowry control", "group_label": "Women", "rule_polity": "Classical Athens", "reasoning": "Aristotle on women's property under guardianship."}
```

Output:
```json
{
  "i": 1,
  "c_sex": {"value": "female", "evidence": "implied"},
  "c_age": {"value": "adult", "evidence": "implied"},
  "c_ownership_status": {"value": "free", "evidence": "implied"},
  "c_ancestry": {"value": "unspecified", "evidence": "unspecified"},
  "c_residence": {"value": "unspecified", "evidence": "unspecified"},
  "c_wealth": {"value": "unspecified", "evidence": "unspecified"},
  "c_occupation": {"value": "unspecified", "evidence": "unspecified"},
  "emic_label_in_text": "wife",
  "criterion_reasoning": "The word 'wife' lexically presupposes female sex, adult age, and (in this register) free status; the verbatim does not name ancestry, residence, or wealth."
}
```

### Example 3 — the case that USED to leak background knowledge

Input:
```json
{"i": 2, "verbatim": "Athenian citizens may vote in the Ekklesia", "rule": "Assembly voting", "group_label": "Citizens", "rule_polity": "Classical Athens", "reasoning": "Pericles on the demos."}
```

Output:
```json
{
  "i": 2,
  "c_sex": {"value": "unspecified", "evidence": "unspecified"},
  "c_age": {"value": "unspecified", "evidence": "unspecified"},
  "c_ownership_status": {"value": "free", "evidence": "implied"},
  "c_ancestry": {"value": "native", "evidence": "implied"},
  "c_residence": {"value": "resident", "evidence": "implied"},
  "c_wealth": {"value": "unspecified", "evidence": "unspecified"},
  "c_occupation": {"value": "unspecified", "evidence": "unspecified"},
  "emic_label_in_text": "Athenian citizens",
  "criterion_reasoning": "'Citizen' lexically presupposes free status; 'Athenian' presupposes native ancestry; voting in the Athenian Ekklesia implies residence. The verbatim does NOT name sex or age — those are historical facts about Athenian law, not lexical facts about the words."
}
```

This is the key example. Under the previous prompt the model would have filled in `sex=male` and `age=adult` from background knowledge. Here we **don't**: a polity *could*, in principle, define citizenship without sex/age constraints, and the verbatim does not rule that out.

### Example 4 — enslaved cell

Input:
```json
{"i": 3, "verbatim": "no slave may give evidence in court except under torture", "rule": "Slave testimony", "group_label": "Slaves", "rule_polity": "Classical Athens", "reasoning": "Lysias / Demosthenes on slave testimony."}
```

Output:
```json
{
  "i": 3,
  "c_sex": {"value": "unspecified", "evidence": "unspecified"},
  "c_age": {"value": "unspecified", "evidence": "unspecified"},
  "c_ownership_status": {"value": "enslaved", "evidence": "implied"},
  "c_ancestry": {"value": "unspecified", "evidence": "unspecified"},
  "c_residence": {"value": "unspecified", "evidence": "unspecified"},
  "c_wealth": {"value": "unspecified", "evidence": "unspecified"},
  "c_occupation": {"value": "unspecified", "evidence": "unspecified"},
  "emic_label_in_text": "slave",
  "criterion_reasoning": "The word 'slave' lexically presupposes ownership='enslaved'; no other axis is constrained by the verbatim."
}
```

### Example 5 — Solonic wealth class

Input:
```json
{"i": 4, "verbatim": "only those who produce five hundred medimnoi may be archons", "rule": "Pentakosiomedimnoi office eligibility", "group_label": "The wealthy", "rule_polity": "Archaic Athens (Solonic)", "reasoning": "Solonic Census class restriction."}
```

Output:
```json
{
  "i": 4,
  "c_sex": {"value": "unspecified", "evidence": "unspecified"},
  "c_age": {"value": "unspecified", "evidence": "unspecified"},
  "c_ownership_status": {"value": "unspecified", "evidence": "unspecified"},
  "c_ancestry": {"value": "unspecified", "evidence": "unspecified"},
  "c_residence": {"value": "unspecified", "evidence": "unspecified"},
  "c_wealth": {"value": "high", "evidence": "stated"},
  "c_occupation": {"value": "unspecified", "evidence": "unspecified"},
  "emic_label_in_text": "those who produce five hundred medimnoi",
  "criterion_reasoning": "The verbatim states a wealth threshold ('five hundred medimnoi' of yield), forcing c_wealth='high' — no other axis is named."
}
```
