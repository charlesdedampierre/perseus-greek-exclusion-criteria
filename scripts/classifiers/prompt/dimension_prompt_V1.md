# Rule Dimensions Classifier

## Purpose

You receive an already-extracted rule (one tuple of *criteria → group → resource → directionality → rule*, with its verbatim and reasoning). Your job is to **score it along seven conceptual dimensions** so the downstream pipeline can fine-tune the corpus to the range of phenomena that count as a *right rule* in the sense of the framework.

This is a **post-extraction "conceptual fine-tuning" classifier**: the previous prompt is permissive it captures any candidate rule. This pass scores each candidate so that thresholding on a labelled training set (e.g. *keep where group_immutability ≥ 4 AND resource_materiality ≥ 3 AND tautology = 0*) lets us calibrate which rules genuinely instantiate a stable, structural rule about lifelong access of a well-defined group to a material resource.

A *valid* rule, in the framework, must reflect a **durable structural feature** of the society under examination, not an idiosyncratic or contingent arrangement: it must apply to a sufficiently stable group (high group immutability), allocate a resource of sufficient consequence (high materiality, generality, persistence), be reported as a fact rather than a wish (high factuality), and not collapse into the group's own definition (zero tautology).

## Input

A JSON object with at least these keys, as emitted by the V20 core prompt:

```
criteria, group, resource, rule, directionality, verbatim, reasoning, contemporary, factuality
```

Plus, when available: `author`, `impact_year`, `work_title`.

## What you must score

Seven dimensions. **All seven are independent** — score each on its own merits, do not let one dimension drive another.

| Dimension | Scale | What it measures |
|---|---|---|
| `resource_materiality` | 1–5 | How concretely material the resource is. |
| `resource_generality` | 1–5 | How broad / structural the resource is, vs. hyper-specific. |
| `resource_persistence` | 1–5 | How long, in a member's life, the resource holds once gained or lost. |
| `group_immutability` | 1–5 | How easily an individual can leave the group. |
| `rule_contemporarity` | 0 /1 | How close the rule is to the author's own lived society. |
| `opinion_vs_fact` | 1–5 | How factual (vs. opinionated / rhetorical) the proof verbatim is. |
| `tautology` | 0 / 1 | Whether the rule restates the group's own definition. |

---

## 1. `resource_materiality` (1–5)

How tangibly **material** is the resource? Material resources improve the level of human development by adding freedom of choice; immaterial resources (honour, divine favour, virtue) do not.

- **5 — Tangible property, wealth, bodily entitlement.** Land ownership, inheritance, money, physical goods, freedom of movement, bodily protection from torture / corporal punishment / execution, dowry retention, slaves as property, access to means of subsistence.
- **4 — Concrete legal right or exemption with direct material effect.** Tax exemption, right to marry, right to hold office, right to vote, right to testify in court without coercion, exemption from enslavement, right to a public trial.
- **3 — Access to a social role or practice that produces tangible outcomes.** Access to gymnasium, access to public education, membership in a civic or professional body, participation in a recognised public/legal procedure with material consequences.
- **2 — Role-based / status access with weak material payoff.** Membership in a religious association whose payoff is mostly symbolic, ceremonial honours with minor economic side-effects.
- **1 — Non-material / abstract / spiritual / trait-based.** Divine favour, salvation, covenant with a deity, spiritual purity, honour, glory, virtue, wisdom, "rational self-governance", reputation in heaven.

Score the **resource**, not the group. When a resource mixes material and non-material elements, take the dominant material effect on the group's life. Default to the lower score in doubt.

## 2. `resource_generality` (1–5)

Does the resource cover a **broad class of life outcomes**, or a narrow / hyper-specific one?

- **5 — Very general.** A foundational societal axis: wealth, property, political power, freedom of movement, bodily integrity, legal personhood, access to education, right to inherit, right to marry, right to vote.
- **4 — Broad category.** Major recognisable right or exemption that still spans many situations: tax exemption, freedom from enslavement, access to public office, right to hold land, access to civic festivals.
- **3 — Specific but recurring.** Right to a public trial, right to retain dowry, protection from corporal punishment, right to attend the assembly of a given city.
- **2 — Narrowly scoped.** Tied to a particular institution, setting, or procedure: access to the gymnasium of Cynosarges, participation in a specific festival, exemption from a named tax.
- **1 — Hyper-specific.** Tied to a single circumstance, condition, or niche scenario: protection from a named disease, access to a one-off ritual, a single procedural technicality in one type of trial.

Score the **resource itself**, not the group or the rule. If the phrasing names a particular disease, procedure, ritual, institution, or one-off circumstance, score 1–2. If it names a foundational societal axis, score 5. Default to lower in doubt.

## 3. `resource_persistence` (1–5)

Once a member of the group **gains or loses** this resource, how long does that hold in their life?

- **5 — Lifelong / structural.** Land ownership, inheritance, freedom vs. enslavement, citizenship, permanent legal standing, lifelong priesthood, marital property rights, nobility.
- **4 — Long-term but revocable.** Right to hold office across a career, long-term tax status, marital rights while a marriage lasts, permanent-till-revoked protections, membership in an institution one can leave.
- **3 — Bounded to a life stage or recurring period.** Resource attached to a phase (childhood, adulthood, old age) or recurring annually / per cycle (annual festival right, right while in military service).
- **2 — Brief episode or single procedure.** Right to a fair trial in one case, right to speak during one assembly session, protection during a single ritual.
- **1 — Momentary / one-off.** A single occasion with no durable afterlife: a one-time exemption, a single transient protection.

Take the normal case for an affected individual. If duration depends on a contingent event (illness), use the typical duration of that event (illness ≈ 2). Default to lower in doubt.

## 4. `group_immutability` (1–5)

How easily can an individual **leave the group** within the author's society? A valid rule must apply to a sufficiently stable group; behavioural or one-off groupings are not valid.

- **5 — Strictly immutable.** Biologically or birth-fixed: sex / gender, ethnicity, lineage, family / clan, age (at a given moment), skin colour, hereditary disability.
- **4 — Very hard to change; legal / structural birth-status.** Citizenship (requires naturalisation or exile), free vs. enslaved (requires manumission), caste, nobility, hereditary priesthood, born-vs-converted religion.
- **3 — Changeable with effort but durable social identity.** Occupation acquired through training, religious initiation, marital status, wealth bracket, foreign residency (metic), guild membership.
- **2 — Role-bound or episodic.** Litigant, defendant, juror for a single trial, patient during an illness, soldier on active duty, office-holder during a term.
- **1 — Behavioural or one-off.** Defined by an action or single event: "men who committed adultery", "people who swore the oath", "the multitude who cheered", a single named individual.

Rate the group **as defined in this rule**. "Priests" is normally 4 but 3 if the text describes an elective priesthood. Default to lower in doubt.

## 5. `rule_contemporarity` (1–5)

How close is the rule to the **author's own lived society**? A valid rule must reflect a durable structural feature of the society under examination, not a mythological or legendary past.

- 0 — Author's lived present.** A norm, statute, or practice currently in force in the author's own polity at the time of writing.
- 1 in the past

## 6. `opinion_vs_fact` (1–5)

Is the proof verbatim a **fact** the author reports, or an **opinion** the author advocates?

- **5 — Pure attested fact.** The verbatim names a verifiable institution, statute, or behaviour as if simply observed: "metics paid the metoikion", "women had no vote in the Ekklesia".
- **4 — Reported fact with mild interpretation.** Factual description with some authorial framing: "the Athenians, as is well known, excluded foreigners from the gymnasium of Cynosarges".
- **3 — Mixed.** A claim that mostly describes a real arrangement but is woven into argumentation, where the rule could be either reported or asserted.
- **2 — Mostly opinion / argument.** The author argues that a rule is in force or should be in force, with thin factual grounding: "it would be just that women not inherit, as our ancestors knew".
- **1 — Pure opinion / rhetorical claim / wish.** The verbatim is an exhortation, ideal proposal, or rhetorical assertion with no claim to reflect actual practice ("citizens *should* be men of property", as a normative proposal in a treatise on the ideal state).

Score the **verbatim**, not the rule's plausibility. A rule may be real even when its verbatim is opinionated, and vice versa. Default to **3** in doubt.

## 7. `tautology` (0 / 1)

Flag whether the rule **restates the group's own definition**, so it is information-free.

- **1 — Tautological.** Restating the group already gives the resource: "Slaves have less freedom" (slavery *is* unfreedom); "Non-citizens have less citizenship"; "Poor people lack money"; "Sick people have less health"; "Children are not adults"; "Illegitimate children lack legitimacy". Be strict with the tautology.
- **0 — Not tautological.** A legal or material right that is **not** part of the group's definition, even if culturally expected. "Women cannot own land in Attica" is *not* tautological — being female does not entail being landless in every society. "Slaves have less protection from corporal punishment" is *not* tautological — protection from torture is not what *slave* means.

The directionality matters: if the group is *Poor* and the resource is *money*, LESS = tautological, MORE = non-tautological (paradoxical). Output `1` only when the rule genuinely restates the definition; default to `0` in doubt.

---

## Decision rules across dimensions

- **Score each dimension independently.** Do not let high tautology drag down materiality or vice versa — they capture different things.
- **Use the verbatim and reasoning, not outside knowledge,** to anchor your scoring.
- **Default to the lower / safer score** on the 1–5 dimensions when two adjacent levels are both plausible. For tautology, default to `0`.
- **Per-dimension reasoning must be ≤25 words** and must cite the specific element (resource phrasing, group label, verbatim cue) that drove the score.

## Output format

Return **only valid JSON** — a list of objects, one per input rule, in input order. Each object must include the input index `i`, all seven scores, and a one-line reasoning per dimension.

```json
[
  {
    "i": 0,
    "resource_materiality": 5,
    "materiality_reasoning": "Right to own land in Attica is a tangible property entitlement.",
    "resource_generality": 5,
    "generality_reasoning": "Land ownership is a foundational societal axis.",
    "resource_persistence": 5,
    "persistence_reasoning": "Land ownership persists across the owner's life and can be bequeathed.",
    "group_immutability": 4,
    "immutability_reasoning": "Metic status is legal birth-status — changeable only by naturalisation.",
    "rule_contemporarity": 0,
    "contemporarity_reasoning": "Demosthenes describes a contemporary Athenian statute in force at the time of the speech.",
    "opinion_vs_fact": 5,
    "opinion_vs_fact_reasoning": "Verbatim cites the law as plain fact, no rhetorical framing.",
    "tautology": 0,
    "tautology_reasoning": "Land ownership is not part of the definition of being a metic."
  },
  {
    "i": 1,
    "resource_materiality": 1,
    "materiality_reasoning": "Divine favour is a purely spiritual / symbolic resource.",
    "resource_generality": 4,
    "generality_reasoning": "Frames a broad category of religious standing across many situations.",
    "resource_persistence": 5,
    "persistence_reasoning": "Inclusion in a covenant is treated as lifelong.",
    "group_immutability": 4,
    "immutability_reasoning": "Born-vs-converted religion is structural birth-status.",
    "rule_contemporarity": 1,
    "contemporarity_reasoning": "The verbatim narrates a scriptural foundational covenant, well before the author's lifetime.",
    "opinion_vs_fact": 2,
    "opinion_vs_fact_reasoning": "Verbatim is exhortative, asserting how members ought to relate to the covenant.",
    "tautology": 0,
    "tautology_reasoning": "Covenant inclusion is not part of the definition of the religious group."
  }
]
```
