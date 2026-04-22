# Resource meta-category classifier — V3 (anchored, 39 canonicals)

You receive a batch of RESOURCE strings (rights, protections, accesses,
exemptions, or eligibilities extracted from ancient texts). Your job is
to map each string to **one** canonical resource — preferably one from
the fixed list below, and only occasionally a new canonical.

## The 39 canonical resources

Every canonical is named with one of the patterns **Right to X**,
**Protection from Y**, **Access to Z**, **Exemption from W**, or
**Eligibility for V**. Picture what is concretely at stake when you
read it.

### Top-level canonicals (from the top-20 consolidation)

| # | Canonical | Typical surface strings it absorbs |
|---:|---|---|
| 1 | **Eligibility for public office** | Eligibility for the archonship / Council / kingship / priesthood / magistracy / jury service / highest offices; Right to hold office; Right to share office in the government; Right to participate in office |
| 2 | **Protection from corporal punishment** | Protection from corporal torture; Protection from torture during legal proceedings |
| 3 | **Right to retain property** | Right to retain dowry upon divorce |
| 4 | **Right to inherit property** | Right to inherit property directly |
| 5 | **Political power** | Right to self-governance; Right to share in government; Political decision-making power; Right to deliberative authority; Right to participate in government |
| 6 | **Protection from capital punishment** | Protection from arbitrary execution; Protection from summary execution; Protection from unlawful killing; Protection from execution; Right to life |
| 7 | **Right to retain own earnings** | Right to retain one's own earnings; Right to retain earnings; Right to retain personal earnings; Right to retain earnings from labor |
| 8 | **Protection from enslavement** | Right to personal freedom; Right to personal liberty; Protection from being sold |
| 9 | **Right to address the assembly** | Right to speak in the Assembly |
| 10 | **Right to own land** | Right to own land in Attica |
| 11 | **Right to vote in the Ekklesia** | Right to vote in the assembly; Right to the franchise; Right to vote in the Assembly |
| 12 | **Exemption from compulsory public financing** | Exemption from public service costs; Exemption from public service financing |
| 13 | **Access to the gymnasium** | Access to the gymnasium and physical training |
| 14 | **Protection from legal prosecution** | — |
| 15 | **Right to valid professional opinion** | — |
| 16 | **Right to reside in the city** | Right of residence in Attica |

### Additional canonicals (from the top-50–100 consolidation)

| # | Canonical | Typical surface strings it absorbs |
|---:|---|---|
| 17 | **Right to citizenship** | Eligibility for citizenship; Right to retain citizenship; Right to exercise citizenship; Full civic rights; Right to civic rights |
| 18 | **Right to free speech** | Right of free speech; Freedom of speech; Parrhesia |
| 19 | **Access to religious rites** | Right to attend the Thesmophoria; Access to sacred mysteries; Right of entry to the temple; Access to religious festivals |
| 20 | **Access to public honors** | Eligibility for public honors; Priority in seating precedence; Right to professional recognition |
| 21 | **Right to burial** | Right to a public funeral |
| 22 | **Right to a dowry** | Right to a marriage dowry |
| 23 | **Right to adopt** | Right to adopt a son |
| 24 | **Right to freedom of movement** | Freedom of movement; Right to leave the country; Right to travel |
| 25 | **Right to bodily autonomy** | — |
| 26 | **Right to bear arms** | Right to possess arms |
| 27 | **Exemption from taxes** | Exemption from all taxes; Tax exemption |
| 28 | **Exemption from manual labor** | Exemption from agricultural labor; Exemption from menial work |
| 29 | **Right to a legal trial** | Protection from state-sanctioned wrongdoing; Right to due process |
| 30 | **Protection from arbitrary banishment** | Protection from exile |
| 31 | **Protection from public libel** | Protection from slander |
| 32 | **Exemption from legal audit** | — |
| 33 | **Right to own property** | (broader than *Right to own land*) |
| 34 | **Right to dispose of property** | Right to bequeath; Right to alienate property |
| 35 | **Right to speak first in assembly** | Priority in public speaking |
| 36 | **Right to remuneration for office** | Pay for public office; State stipend for officials |
| 37 | **Right to drink wine** | — |
| 38 | **Right to professional judgement** | Authority to judge technical accuracy |
| 39 | **Right to inherit divine covenant** | Covenantal inheritance (religious context) |

## Rules for mapping

1. **Prefer a canonical.** For almost every input string, one of the 39
   canonicals is a good-enough fit. Return that canonical verbatim
   (exact spelling and casing as shown above).
2. **"Same kind of thing" is the test.** If the surface string names
   the same concrete right / protection / access / exemption /
   eligibility at the same level of generality as an existing
   canonical, map it. Minor wording differences (articles, apostrophes,
   institutional specifics) are ignored: `Right to own land in Attica`
   → `Right to own land`; `Eligibility for the archonship at Athens`
   → `Eligibility for public office`; `Right to retain one's own
   earnings` → `Right to retain own earnings`.
3. **Pick the MOST specific canonical** that still applies. If a string
   could fit both `Right to own land` (specific) and `Right to own
   property` (general), choose `Right to own land`. If only the
   general one applies, choose the general one.
4. **Directionality is part of the resource label, not the canonical
   pick.** The rule-level `directionality` (MORE/LESS) is separate.
   Always phrase the canonical positively (as the right or protection
   *itself*), never as the negative ("vulnerability to X"). E.g.
   `Protection from torture` is the canonical, not `Torture` or
   `Vulnerability to torture`.
5. **New canonical — only when genuinely needed.** Introduce a new
   canonical ONLY when the input:
   (a) names a concrete right / protection / access / exemption /
       eligibility, AND
   (b) does not fit any of the 39 canonicals even loosely, AND
   (c) you can name it in one of the allowed patterns above.
   Name it the same way — `Right to X` / `Protection from Y` /
   `Access to Z` / `Exemption from W` / `Eligibility for V`.
   Avoid creating singletons when one of the 39 would absorb the item
   at a small quality cost.
6. **Reject invalid items** by mapping them to the closest canonical
   anyway. Never refuse an item. If a string names a pure trait
   ("Physical strength"), a tautology ("Slaves' slavery"), or something
   that is not actually a resource, pick the nearest canonical and
   flag nothing — this classifier does not validate rules, only
   catalogues their resources.

## Input

A JSON list of objects, each with `i` (index) and `value` (the
resource string to classify).

## Output

Return ONLY valid JSON — a list of objects, one per input, in input
order. Each object must include `i` and `resource_meta`.

```json
[
  {"i": 0, "resource_meta": "Eligibility for public office"},
  {"i": 1, "resource_meta": "Right to own land"},
  {"i": 2, "resource_meta": "Right to freedom of movement"}
]
```
