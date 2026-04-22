# Rule Extraction Prompt

## 1. Context

You are analyzing a wide range of historical texts (legal texts, written works, etc.) and extracting the rules. Your output will be a structured inventory of rules comparable across civilizations.

In all societies, there are criteria that define the boundaries between groups (gender, age, citizenship etc). Each criterion is associated with a specific group that mechanically distinguishes itself from an out-group (men vs women, slaves vs citizens etc). A group is near-immutable, meaning individuals can’t easily leave it. An individual can be part of different groups at the same time, but can’t be part of both an in-group and an out-group. Those criteria will ultimately determine which resources specific groups have access to. Ressources are both material (money, slaves) and immaterial (rights, fame, political power, influence over others, etc.). Overall, having those ressources ultimately improves the level of human development (more freedom of choice in how one conducts one’s life). The relationship between resources and groups is materialized through rules created in a specific society. Those rules can be legal, norms, or conventions. The rules can link the specific groups in a positive way (giving political rights to citizens in Athens) or in a negative way (systematically torturing slaves when questioned as witnesses): this is the directionality of the rule
---

## 2. What you must extract

Every extracted rule is a tuple of 10 variables: **CRITERIA**, **GROUP**, **RESOURCE**, **DIRECTIONALITY**, **RULE**, **CONTEMPORARY**, **FACTUALITY**, **VERBATIM**, **MODEL_REASONING**, **MODEL_CONFIDENCE**

The rules below define what counts as valid for each.

### 2.1 CRITERIA

They define the boundaries between groups. They are fixed: Gender, Citizenship, Occupation, Age, Lineage, Nobility, Wealth / Properties, Ethnicity, Education, Freedom, Religion, Health.
A rule can come from different criteria at the same time

### 2.1 GROUP

Describe the group as you find it in the text.

Specificity: The group must be specific enough to be separated from others and to understand that the rule applies to this specific group and that if that group were different, then the rule would not apply

**Near-immutability.** A group must be defined by a near-immutable criterion, never by an action or behavior. Behavioral categories ("men who prostituted themselves") are not accepted.

### 2.2 RESOURCE

Ressources are both material (money, slaves) and immaterial (rights, fame, political power, influence over others, etc.). Overall, having those ressources ultimately improves the level of human development (more freedom of choice in how one conducts one’s life).
**Positive framing.** A resource is always defined positively, as something a group has or lacks access to. Never as a vulnerability or a negative event:

- "Protection from corporal punishment" *(not* "Vulnerability to corporal punishment"*)*
- "Right to retain property" *(not* "Property confiscation"*)*

**Examples of resources:**

Right to vote in the Ekklesia
Eligibility for the archonship
Protection from torture during legal proceedings
Right to own land in Attica
Right to inherit property directly
Right to retain dowry upon divorce
Exemption from metic tax (metoikion)
freedom from compulsory public financing (trierarchies, choruses)
Right to retain one's own earnings
Access to the gymnasium and physical training

**Invalid resources:**

- **Abstractions:** honor, divine favor
- **Divine rights or divine favor:** "right to invoke divine vengeance," "divine protection,"
- **Traits and capacities:** wisdom, virtue, rational self-governance, physical strength, ability to fight

### 2.3 DIRECTIONALITY

State whether the group is gaining (`MORE`) or losing (`LESS`) the resource.

- Follow the direction the text actually describes. If women are barred from X, code *Women, LESS*. Do not invert to *Men, MORE*.
- Do not confuse the violation with the rule. A rule being enforced counts as evidence the rule exists. A conviction for enslaving a free non-citizen proves the society protected non-citizens from enslavement → code as *Non-citizens, MORE, Protection from enslavement*.

### 2.4 RULE

The relationship between resources and groups is materialized through rules created in a specific society. Here are some examples of rules:
Citizen assembly voting, Noble access to magistracies, Slave testimony under torture (basanos), Metic (metoikoi) exclusion from land, Women's inheritance restriction (epikleros), Dowry protection for wives’ families, Citizen tax exemptions, Liturgy obligation for the wealthy, Slave earnings retained by the master, Female exclusion from the gymnasium, etc
They are generally 3 to 6 words long and can be understood simply by any non-professional reader

### 2.5 VERBATIM

Extract the verbatim quote(s) that prove the rule.

- The verbatim must be an **exact** quote from the text.
- The verbatim must be **self-sufficient**: reading it alone, a reader must be able to identify the teh criteria, group, the resource, the directionality, and the rule, without relying on too much previous knowledge.
- Include additional adjacent sentences — typically 5–7 sentences of surrounding context, toi make sure the reader can understand the context as well.
- Never cut off mid-sentence.
- You may include multiple verbatim.

### 2.6 CONTEMPORARY

Indicates whether the proof text refers to a contemporary event or a historical event (distant past). You can output (1, 0 or None)

### 2.7 FACTUALITY

Indicates whether the proof text is a fact or an opinion.
You can output (1, 0 or None)

### 2.8 REASONING

Add a short sentence explaining your decision to extract the rule and its connection to the verbatim. It must stay grounded in the verbatim itself.
If it is really needed, the reasoning should make it obvious where each piece of information comes from (for instance, by pointing to another part of the text, or to some metadata you are aware of)

### 2.7 CONFIDENCE

A score from 1 to 10 reflecting how certain you are of the extraction.

## 3. Scope constraints

These define what passages are eligible at all.

**No tautologies.** A rule must be informative. It must tell us something non-obvious about who gets what. The following are tautologies and must NOT be extracted:

- "Non-citizens have less citizenship" (restates the definition)
- "Slaves have less freedom" (restates what slavery means)

## 4. Step-by-step extraction process

Follow these steps **in order** for every passage you analyze. Do not skip steps. Do not extract a rule until you have completed steps 1–7.

### Step 1 — Check scope eligibility

Before considering extraction, ask two gating questions:

1. **Is the author describing their own society and time?** Discard passages about mythological pasts or purely ideal/speculative societies. The only exception is when the author explicitly contrasts such a description with current real practice — in that case, keep only the real-practice portion.
2. **Does the passage describe a general rule, not a one-off event?** Discard passages covering a single individual's unique circumstances with no implication for a broader category.

→ **If either check fails, stop and move on.**

### Step 2 — Identify the criterion and the group

Ask: *who is being treated differently in this passage, and on what basis?*

1. Identify the **criterion** that defines the boundary. It must come from the fixed list in §2.1: Gender, Citizenship, Occupation, Age, Lineage, Nobility, Wealth / Properties, Ethnicity, Education, Freedom, Religion, Health.
2. Name the **group** in the most general, near-immutable terms available (Women, Slaves, Foreigners, The poor, Minors, etc.). The group must follow logically from the criterion — e.g., criterion *Freedom* → group *Slaves*; criterion *Citizenship* → group *Metics*.
3. If the text describes a behavior (e.g., "those who commit adultery"), identify the natural category the behavior stands in for, and use that category instead.
4. Reject the candidate if the only available group is behavioral, moral, overly narrow, or tautological.

→ **If no valid criterion-group pair can be named, stop.**

### Step 3 — Identify the resource

Ask: *what concrete right, privilege, or material entitlement is the group gaining or losing?*

1. Frame the resource as a positive right ("Right to own land", "Protection from corporal punishment"), never as a vulnerability or a negative event.
2. Check it against the valid families listed in §2.2.
3. Reject abstractions (honor, prestige, virtue), traits (strength, wisdom), and vague goods ("the good life").

→ **If no valid resource can be named, stop.**

### Step 4 — Determine directionality

Ask: *does the group have MORE or LESS of this resource?*

1. Preserve the direction the text actually states. If the passage establishes *Women, LESS*, do not invert it to *Men, MORE*.
2. When a passage describes a rule being enforced (e.g., a conviction for violating it), code the rule itself, not the violation. A conviction for enslaving a free non-citizen → *Non-citizens, MORE, Protection from enslavement*.

→ **If directionality is genuinely ambiguous, stop.**

### Step 5 — Verify the verbatim

Locate the exact quote(s) that prove the rule, then test them against three criteria:

1. **Explicit** — reading the verbatim alone, with no outside context, another reader would arrive at the same rule.
2. **Complete** — the quote is not cut off mid-sentence and includes enough surrounding context for the rule to be unambiguous.
3. **Direct** — the link from verbatim to rule requires no chain of assumptions. Two or more inferential leaps disqualify the extraction.

→ **If any check fails, do not extract.**

### Step 6 — Code CONTEMPORARY and FACTUALITY

Assign two metadata codes to the verbatim:

1. **CONTEMPORARY** — does the proof text refer to a contemporary event (the author's own time) or a historical event (distant past)?
   - `1` — Contemporary event
   - `0` — Historical event
   - `None` — Cannot be determined
2. **FACTUALITY** — is the proof text a fact or an opinion?
   - `1` — Fact
   - `0` — Opinion
   - `None` — Cannot be determined

### Step 7 — Score your confidence

On a 1–10 scale, rate how certain you are of the tuple you extracted.

### Step 8 — Name the rule

Give the rule a short, descriptive label (typically 3–6 words) that any non-professional reader could understand on its own — e.g., "Slave dismissal at season end", "Metic exclusion from land", "Female exclusion from courts". The name should be specific enough to distinguish the rule from others in the same text.

Then, move on to the next passage.

## 5. Output format

Return **only valid JSON**. No markdown, no code fences, no preamble, no commentary before or after. If no valid rules can be extracted from the text, return `{"extracted_rules": []}`.

```json
{
  "extracted_rules": [
    {“criteria”:[”Freedom”], 
      "rule": "Slave dismissal at season end",
      "group": "Slaves",
      "resource": "Protection from arbitrary dismissal",
      "directionality": "LESS",
      "verbatim": [
        "And so soon as you have safely stored all your stuff indoors, I bid you put your bondman out of doors and seek out a servant-girl with no children;—for a servant with a child to nurse is troublesome."
      ],
      "contemporary": 1,
      "factuality": 1,
      "reasoning": "Hesiod gives this as standard farming advice to any landholder, not as a one-off case. It treats the male slave as a resource to be retained or dismissed at the master's seasonal convenience, demonstrating that slaves in archaic Greek rural society had no protection against being turned out of the household.",
      "confidence": 8
    },
     ]
}
```
