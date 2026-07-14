# Athens rights figures

One self-contained script — `generate_figures.py` — builds all four figures for
the Classical-Athens "rights as partial orders" argument from a **single shared
data model**. Edit the data once; every figure stays consistent.

## The figures

| File | What it shows |
|------|----------------|
| `athens-fig1-table-criteria` | Left: table of which **criteria** each of the 16 **rights** requires (● required / ○ not), by domain. Right: the six criteria ranked by how many rights they gate (node size ∝ that count; a criterion sits above another when it is required by a *superset* of its rights). |
| `athens-fig2-groups-overall` | Left: the 8 social **groups** and the criteria each meets. Right: the **Overall** Hasse diagram — groups laid out in tiers by how many rights they hold (higher = more), node size ∝ population, long edges routed around nodes by Graphviz. |
| `athens-fig3-five-graphs` | The same groups ranked **within each right-type** (Political · Legal · Economic · Religious · Military) — the ordering reshuffles between panels. Node size ∝ population. |
| `athens-fig4-criteria-by-type` | The six **criteria** ranked by the rights they gate, **within each right-type**. Node size ∝ number of rights gated. |

Each is written as both `.svg` (editable vector, drops into Google Docs / LaTeX)
and `.png` (2× hi-res).

## The idea (what the code computes)

Everything is one partial order. Each right `r` demands a set of criteria
`req(r)`. A group holds `r` iff its criteria ⊇ `req(r)`; a criterion "gates" `r`
iff `r` requires it. The Hasse **edges** are the *covering relations* of the
subset order on those held/gated sets — computed in `covering()`, never drawn by
hand. Node **sizes** encode magnitude only (population for groups, #rights for
criteria); there are no printed numbers.

## Run it

```bash
python3 generate_figures.py
```

Dependencies (both on `PATH`):

```bash
brew install graphviz librsvg   # provides `dot` and `rsvg-convert`
```

`dot` is used only for the Overall graph's tiered layout; everything else is
plain Python emitting SVG.

## Editing

The **DATA MODEL** block near the top of `generate_figures.py` is the single
source of truth:

- `CRITERIA` / `CRIT_LABEL` — the personal criteria and their display names.
- `RIGHTS` — `(right-type, name, {required criteria})`, 16 entries.
- `GROUPS` — `(name, {criteria met}, relative population)`, 8 entries.

Add a right, change a requirement, or drop in real population figures, then
re-run — all four figures update together, no manual SVG surgery.

> Historical note: the group terms and restriction rules were fact-checked
> against Wikipedia (Hippeis, Thetes, ephebos, astē, nothos, metic,
> apeleutheros, doulos; Pericles' 451 BCE citizenship law; basanos; enktēsis;
> etc.). The emic Greek terms were later dropped from the figures at the
> author's request — plain group names only.
