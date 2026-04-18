# Rule Extraction Prompt

## 1. Context

Societies in the past have created legal and customary rules to allow or to suppress access to resources (wealth, political power, bodily integrity) for different near-immutable groups in society (citizens, nobles, rich people, women, slaves, foreigners, etc.).

You are analyzing a wide range of texts from the past (legal texts, written works, etc.) and extracting rules from those texts. For each rule, specify:

- (a) the concerned group,
- (b) the material resource at stake,
- (c) whether the group is gaining or losing this resource,
- (d) the exact text verbatim from which you extract the rule.

Your output will be a structured inventory of rules comparable across civilizations, revealing which axes of stratification a given society activates (gender, freedom status, citizenship, age, wealth, lineage) and how intensely.

---

## 2. What you must extract

Every extracted rule is a tuple of seven variables: **GROUP**, **GROUP_CATEGORY**, **RESOURCE**, **RESOURCE_CATEGORY**, **DIRECTIONALITY**, **SPECIFICITY**, **PROOF**, **REASONING**, **CONFIDENCE**, and **RULE NAME**, **RULE_CATEGORY**. The rules below define what counts as valid for each.

### 2.1 GROUP

**Near-immutability.** A group must be defined by a near-immutable trait: sex, age, origin, freedom status, inherited wealth level, lineage, or occupation. Never by an action or behavior. Behavioral categories ("men who prostituted themselves") are not accepted.

**High order of generality.** The group must be at a rather general level, not overly narrow.

### 2.2 RESOURCE

**Concrete.** Resources must be concrete legal rights or material entitlements — things a person can be materially harmed by losing, and that a society grants or withholds.

**Positive framing.** A resource is always defined positively, as something a group has or lacks access to. Never as a vulnerability or a negative event:

- "Protection from corporal punishment" *(not* "Vulnerability to corporal punishment"*)*
- "Right to retain property" *(not* "Property confiscation"*)*

**Examples of resources to look for:**

- **Political power** — voting, speaking in assembly, holding office, candidacy
- **Legal standing** — bringing suit, self-defense in court, testifying, acting without a guardian
- **Property and inheritance** — land ownership, inheritance, retention of goods
- **Freedom** — of movement, from enslavement, from imprisonment
- **Body integrity** — protection from torture, corporal punishment, execution without trial
- **Marriage and family** — right to marry, custody, legitimacy of offspring
- **Citizenship** — the status itself and its attached rights
- **Economic privileges** — tax exemptions, access to public resources

**Invalid resources:**

- **Abstractions:** honor, glory, recognition, prestige, social status, divine favor, spiritual unity
- **Traits and capacities:** wisdom, virtue, rational self-governance, physical strength, ability to fight
- **Vague goods:** "access to fine things," "the good life"
- **Divine rights or divine favor:** "right to invoke divine vengeance," "divine protection," "god-given authority." If a right comes from the gods and has no concrete civic mechanism enforcing it, it is NOT a valid resource.
- **Purely religious rules,** unless they carry concrete civic or legal consequences (e.g., temple exclusion that also blocks assembly attendance)
- **Medical or biological facts:** susceptibility to disease, physical vulnerability due to age or sex, or natural consequences of bodily states are NOT societal rules. Only extract if the text describes a legal or customary rule about access to medical care.
- **Job-specific characteristics:** the fact that a profession earns money or has specific working conditions is NOT an exclusion rule — it is simply how the job works. Only extract if the text shows a group being systematically granted or denied access to an occupation or its rewards.

### 2.3 DIRECTIONALITY

State whether the group is gaining (`MORE`) or losing (`LESS`) the resource.

- Follow the direction the text actually describes. If women are barred from X, code *Women, LESS*. Do not invert to *Men, MORE*.
- Do not confuse the violation with the rule. A rule being enforced counts as evidence the rule exists. A conviction for enslaving a free non-citizen proves the society protected non-citizens from enslavement → code as *Non-citizens, MORE, Protection from enslavement*.

### 2.4 SPECIFICITY

Add a metric from 1 to 10 that indicates the specificity of the rule. The specificity concerns the number of people concernet by this rule (with 10 very speficif and 1 almost everyone, or a very small number of people).

This for instance, is very specific

Rule
Restricted palace access
Category
Social stratification
Group
Rural laborers [Occupation]
Direction
LESS
Resource
Freedom of movement to central political sites [Freedom]
Reasoning: Hector rebukes the herdsman for appearing at a military council/command post, explicitly stating that a person of his status belongs at the palace or throne for mundane reports, implying that the herdsman's presence in a high-level military space is a breach of local social and spatial order.
[§14] Hector: Often the rustic mind is afflicted with dullness; so you have probably come to this ill-suited place to tell your master, in armor, about the sheep! Do you not know my palace or my father’s throne, where you should carry your tale when you have prospered with your flocks?

This is medium-specific

Rule
Prosecutorial oath requirement
Category
Legal procedure
Group
Defendants [Legal status]
Direction
MORE
Resource
Protection from unsworn accusations [Legal standing]
Reasoning: The text refers to the 'traditional oath' (the diomosia) required in Athenian murder trials, which acts as a procedural protection for the defendant by forcing the accuser to swear to the truth of the charge under religious sanction.
[§96] Acquit me, then, today and at the trial for murder, the prosecution shall take the traditional oath before accusing me: you shall decide my case by the laws of the land.

This is not specific and encompasses a wide part of society

Rule
Slave admissibility under torture
Category
Legal standing
Group
Slaves [Slaves]
Direction
LESS
Resource
Right to testify without torture [Legal standing]
Reasoning: In Athenian law, a slave's evidence was only admissible in court if it was obtained via 'basanos' (judicial torture). The text treats this as the standard procedure for extracting information from slaves.
[§31] The slave was doubtless promised his freedom: it was certainly to the prosecution alone that he could look for release from his sufferings. Probably both of these considerations induced him to make the false charges against me which he did; he hoped to gain his freedom, and his one immediate wish was to end the torture.

### 2.5 PROOF

Extract the verbatim quote(s) from which the rule is drawn.

- The verbatim must be an **exact** quote from the text.
- The verbatim must be **explicit**: a reader should understand the rule from the verbatim alone.
- A verbatim cannot be cut off mid-sentence.
- You may include as many verbatims as needed.

### 2.6 REASONING

reasoning: Add a short sentence explaining your decision to extract the rule.

specificity_reasoning: add a short sentence that justifies your choice of the level of speficitty (see 2.4 SPECIFICITY)

### 2.7 CONFIDENCE

A score from 1 to 10 reflecting how certain you are of the extraction.

### 2.8 RULE NAME

A short label (maximum four words) describing the rule.

### CATEGORIES

**GROUP_CATEGORY** — the structural axis of stratification. Pick from this list whenever possible:

| Group_category | Examples of groups |
|---|---|
| Gender | Women, Men, Maidens, Widows |
| Freedom status | Slaves, Freed persons, Bondsmen |
| Citizenship | Citizens, Foreigners, Metics, Exiles, Resident aliens |
| Lineage | Nobles, Royal heirs, Legitimate sons, Bastards, Commoners |
| Age | Children, Minors, Youths, Elders, Adults |
| Wealth | The poor, The wealthy, Property owners, Landless |
| Occupation | Soldiers, Priests, Farmers, Artisans, Athletes |
| Origin | Greeks, Barbarians, Messenians, Jews |
| Health | Disabled, Sick, Able-bodied |

If a group belongs to multiple categories (e.g., "Female slaves"), use an array: `["Gender", "Freedom status"]`.

**RESOURCE_CATEGORY** — the type of material right at stake. Pick from this list whenever possible:

| Resource_category | Examples of resources |
|---|---|
| Political power | Right to vote, speak in assembly, hold office, command armies |
| Legal standing | Right to testify, bring suit, self-defense in court, act without guardian |
| Body integrity | Protection from torture, execution, corporal punishment |
| Freedom | Freedom of movement, from enslavement, from imprisonment |
| Property and inheritance | Right to own land, inherit, retain goods, receive dowry |
| Economic privileges | Tax exemptions, access to public resources, wages, rations |
| Marriage and family | Right to marry, choose spouse, custody, legitimacy of offspring |
| Citizenship | The legal status itself and all attached rights |
| Military | Right or obligation to serve, bear arms, receive spoils |
| Religious access | Right to participate in rituals, hold priesthood, enter sacred spaces |

**RULE_CATEGORY** — describes the TYPE OF RULE by combining what happens (the resource) with how it changes (the direction). Use 3-5 words. Think of it as: "What does this society DO to this group?"

| Rule_category example | Built from |
|---|---|
| Denial of housing security | Slaves + LESS + Right to shelter |
| Exclusion from political speech | Women + LESS + Right to speak in assembly |
| Access to judicial protection | Citizens + MORE + Right to trial |
| Access to political succession | Nobles + MORE + Right to inherit throne |
| Restriction of personal freedom | Slaves + LESS + Freedom of movement |
| Grant of economic privilege | Wealthy citizens + MORE + Tax exemptions |
| Age-based political exclusion | Children + LESS + Right to hold office |
| Military service reward | Soldiers + MORE + Right to land allocation |
| Denial of property rights | Women + LESS + Right to own property |
| Marriage restriction by origin | Foreigners + LESS + Right to marry citizens |
| Obligation of public duty | Wealthy citizens + MORE + Duty to fund festivals |
| Exclusion from inheritance | Illegitimate sons + LESS + Right to inherit |
| Protection from bodily harm | Citizens + MORE + Protection from torture |

The rule_category should be descriptive enough that reading it alone tells you: who is affected, in what direction, and what type of resource is at stake.

## 3. Scope constraints

These define what passages are eligible at all.

**Author's own society and time.** Do not extract from descriptions of mythological pasts (the age of heroes) or ideal/speculative societies (Plato's Republic) — unless the author is explicitly comparing such a case to current real practice, in which case extract only the real-practice part.

**Human focused.** Only mention humans and power over other humans. Do not mention gods, divine beings, or supernatural entities as either groups or sources of rights.

**No tautologies.** A rule must be informative. It must tell us something non-obvious about who gets what. The following are tautologies and must NOT be extracted:

- "Non-citizens have less citizenship" (restates the definition)
- "Slaves have less freedom" (restates what slavery means)
- "Kings have more political power" (restates what kingship means)
Instead, extract the SPECIFIC right: "Non-citizens cannot own land," "Slaves cannot testify in court," "Kings can confiscate property without trial."

**No opinions or controversial claims.** Only extract rules that ACTUALLY EXIST as enforced societal norms. If the author is expressing a personal philosophical opinion (especially a controversial one even for their own time), do not extract it as a societal rule.

**No natural consequences.** Do not extract biological or natural facts as societal rules. "Old people are physically weaker" is a fact of nature, not a rule. "Old people are exempt from military service" IS a rule.

**Double-check directionality.** Before finalizing, re-read your extraction and ask: "Does my MORE/LESS assignment match what the text actually says?" A common error is coding a loss as MORE. If a group loses wealth by performing a duty, that is LESS wealth, not MORE.

---

## 4. Step-by-step extraction process

Follow these steps **in order** for every text you analyze. Do not skip steps. Do not extract rules until you have completed steps 1–5.

### Step 1 — Read the passage and check scope eligibility

Before considering any extraction, ask:

1. **Is the author describing their own society and time?** If the passage describes mythological pasts or ideal/speculative societies, discard it — unless the author is explicitly contrasting it with current real practice, in which case keep only the real-practice part.
2. **Is this a general rule or a one-off event?** If the passage describes a single individual's unique circumstances with no implication for a broader category, discard it.

If the passage fails any of these checks, stop and move to the next passage.

### Step 2 — Identify the candidate group

Ask: **who is being treated differently in this passage?**

1. Name the group in the most general, near-immutable terms possible (Women, Slaves, Foreigners, The poor, Minors, etc.).
2. If the text describes a behavior (e.g., "those who commit adultery"), ask what natural category the behavior is a proxy for, and use that category instead.
3. Reject the candidate if the only available group is behavioral, moral-based, overly narrow, or tautological.

If you cannot name a valid group, stop — there is no rule to extract here.

### Step 3 — Identify the resource at stake

Ask: **what concrete right, privilege, or material entitlement is the group gaining or losing?**

1. Name the resource as a positive right ("Right to own land", "Protection from corporal punishment"), never as a vulnerability or negative event.
2. Check the resource against the valid families listed in §2.2.
3. If the only candidate resource is an abstraction (honor, prestige, virtue), a trait (strength, wisdom), or a vague good ("the good life"), stop — there is no rule to extract here.

### Step 4 — Determine directionality

Ask: **does the group have MORE or LESS of this resource?**

1. State the group as it is mentioned in the text. If it is *Women, LESS*, do not interpret it as *Men, MORE*.
2. If the passage shows a rule being enforced (e.g., a conviction for violating it), code the rule, not the violation. A conviction for enslaving a free non-citizen → *Non-citizens, MORE, Protection from enslavement*.
3. If you cannot tell whether the group gains or loses, the rule is too ambiguous — stop.

### Step 5 — Verify the verbatim supports the rule

Locate the exact quote(s) that prove the rule. Then test:

1. **Is it explicit?** Reading the verbatim alone, with no outside context, would another reader arrive at the same rule?
2. **Is it complete?** The quote must not be cut off mid-sentence and must include enough surrounding context (typically 2–3 sentences) for the rule to be unambiguous.
3. **Is it direct?** The connection from the verbatim to the rule must require no chain of assumptions. If you need two or more inferential leaps, stop.

If any check fails, do not extract.

### Step 6 — Score your confidence

On a scale of 1 to 10, rate how certain you are the extracted rule reflects an actual societal rule in the author's time and place:

| Score | Meaning |
|---|---|
| **9–10** | Explicit legal language, multiple corroborating verbatims, or a rule enforced in the narrative with consequences. |
| **7–8** | Clearly stated rule with one strong verbatim, no ambiguity about scope or direction. |
| **5–6** | Implicit but well-supported by narrative context; some interpretive work required. |
| **3–4** | Plausible but the verbatim leaves room for alternative readings. Consider whether to extract at all. |
| **1–2** | Not sure at all. |

### Step 7 — Name the rule

Give the rule a short label of at most four words that captures its substance (e.g., "Slave dismissal season end", "Non-citizen marriage prohibition", "Female exclusion from courts"). The name should be specific enough to distinguish it from other rules in the same text.

### Step 8 — Move to the next passage

Repeat steps 1–7 for the next candidate passage in the text.

---

## 5. Output format

Return **only valid JSON**. No markdown, no code fences, no preamble.

```json
{
  "extracted_rules": [
    {
      "rule_name": "Slave dismissal at season end",
      "rule_category": "Labor control",
      "group": "Slaves",
      "group_category": "Slaves",
      "resource": "Protection from arbitrary dismissal",
      "resource_category": "Employment security",
      "directionality": "LESS",
      "proof": [
        "And so soon as you have safely stored all your stuff indoors, I bid you put your bondman out of doors and seek out a servant-girl with no children;—for a servant with a child to nurse is troublesome."
      ],
      "reasoning": "Hesiod gives this as standard farming advice to any landholder, not as a one-off case. It treats the male slave as a resource to be retained or dismissed at the master's seasonal convenience, demonstrating that slaves in archaic Greek rural society had no protection against being turned out of the household.",
      "specificity":3,
      "specificity_reasoning": "I chose 3 because this applies to manuy individuals in the society",
      "confidence": 8
    },
    {
      "rule_name": "Female servant childbearing restriction",
      "rule_category": "Family rights",
      "group": "Female slaves",
      "group_category": "Female slaves",
      "resource": "Right to keep and raise own children while in service",
      "resource_category": "Family integrity",
      "directionality": "LESS",
      "proof": [
        "I bid you put your bondman out of doors and seek out a servant-girl with no children;—for a servant with a child to nurse is troublesome."
      ],
      "reasoning": "The instruction to deliberately seek a childless female servant, justified by the master's convenience, shows that an enslaved woman's motherhood was treated as a defect making her unhirable. This implies female slaves had no recognized right to combine labor with raising their own children.",
      "specificity":2,
      "specificity_reasoning": "I chose 2 because this applies to manuy individuals in the society",
      "confidence": 7
    }
  ]
}

```
