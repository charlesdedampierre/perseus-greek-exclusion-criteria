# Resource-type classifier — V1 (8 big meta-categories)

You receive a batch of RESOURCE strings (rights, protections, accesses,
exemptions, or eligibilities already consolidated at the canonical
level — e.g. `Right to own land`, `Eligibility for public office`,
`Protection from corporal punishment`). Your job is to assign each
string to **one or more** of the 8 big meta-categories below.

The 8 meta-categories are ordered along a materiality axis, from most
material (bodily / physical) to most symbolic (reputational, sacred).
They are not mutually exclusive — a resource often belongs to several.

## The 8 meta-categories

| # | Category | What it captures |
|---:|---|---|
| 1 | **Bodily Autonomy** | Protection from enslavement, corporal punishment, execution, torture, forced labor; bodily integrity; freedom of movement. |
| 2 | **Legal Standing** | Recognition before the law; ability to sue, testify, be tried, contract, own, inherit, adopt, bequeath; protection from arbitrary legal action. |
| 3 | **Household Authority** | Control over one's household, dependents, dowry, marriage, adoption, domestic affairs. |
| 4 | **Material Wealth** | Ownership of property, land, money, movable goods; earnings; tax / financing exemptions that preserve wealth. |
| 5 | **Education** | Access to formal instruction, literacy, rhetorical / philosophical / professional training, gymnasium, transmitted knowledge. |
| 6 | **Political Power** | Participation in governance — office-holding, voting, deliberation, speaking in the assembly, military command, public remuneration. |
| 7 | **Honor** | Public esteem, reputation, social prestige — public honors, seating precedence, freedom from libel, right to a public burial. |
| 8 | **Religious Standing** | Access to rites, priesthoods, sacred privileges, covenantal inheritance. |

## Rules for mapping

1. **Assign the smallest set of categories that genuinely covers the
   resource.** Most canonical resources fit one category cleanly;
   some legitimately straddle two (e.g. `Right to own land` →
   `Material Wealth; Legal Standing`; `Right to a dowry` →
   `Material Wealth; Household Authority`). Do not pad: if one
   category is clearly the core meaning, use only one.
2. **Prefer the more specific axis when only one applies.** A
   `Right to retain property` is primarily `Material Wealth`, even
   though possession is a legal concept. Reserve `Legal Standing` for
   resources whose defining feature is *the legal channel itself*
   (trial, prosecution, testimony, contractual capacity, formal
   recognition, inheritance as a legal mechanism).
3. **`Household Authority` covers kin-level authority, not the state.**
   Dowry, marriage, adoption, authority over dependents. It does not
   cover civic / public life.
4. **`Political Power` covers civic governance — not just any public
   role.** Priesthoods are Religious Standing; public honors are
   Honor; military service as a civic duty/exemption can be Political
   Power when it concerns eligibility or command, Bodily Autonomy
   when it concerns bodily risk.
5. **`Honor` is about public esteem itself**, not about any
   publicly-visible right. Seating precedence, the right to a public
   funeral, protection from slander belong here. Holding office is
   *Political Power*, not Honor, even though office is honorific.
6. **`Religious Standing` is the narrowest category.** Only resources
   whose defining content is sacred access / participation / covenantal
   status.
7. **Refuse to classify only when you truly cannot map.** If none of
   the 8 categories fits — or the string is so abstract that assigning
   any one would be arbitrary — return the single token
   `UNCLASSIFIABLE`. Do not invent new categories.

## Input

A JSON list of objects, each with `i` (index) and `value` (the
canonical resource string to classify).

## Output

Return ONLY valid JSON — a list of objects, one per input, in input
order. Each object must include `i` and `resource_type`.

- `resource_type` is a **list of strings**, each string being one of
  the 8 category names spelled exactly as in the table above
  (`Bodily Autonomy`, `Legal Standing`, `Household Authority`,
  `Material Wealth`, `Education`, `Political Power`, `Honor`,
  `Religious Standing`).
- If unclassifiable, return `["UNCLASSIFIABLE"]`.

Example:

```json
[
  {"i": 0, "resource_type": ["Material Wealth", "Legal Standing"]},
  {"i": 1, "resource_type": ["Political Power"]},
  {"i": 2, "resource_type": ["Bodily Autonomy"]},
  {"i": 3, "resource_type": ["UNCLASSIFIABLE"]}
]
```
