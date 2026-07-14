#!/usr/bin/env python3
"""
Classical-Athens rights figures — single reproducible generator.

ONE data model (criteria, rights, groups) drives ALL FOUR figures:

  fig1  athens-fig1-table-criteria    rights×criteria table + "criteria ranked
                                       by the rights they gate" Hasse + legend
  fig2  athens-fig2-groups-overall     group names+criteria + the Overall
                                       rights Hasse, laid out in tiers (Graphviz)
  fig3  athens-fig3-five-graphs        five per-right-type group Hasse diagrams
                                       (which groups hold which rights) + legend
  fig4  athens-fig4-criteria-by-type   five per-right-type criteria Hasse
                                       diagrams (criteria ranked by rights gated)

The whole "mathematics" is the rights-inclusion partial order: a group holds a
right iff its criteria contain the right's required criteria; edges are the
covering relations of that order. Node sizes encode magnitude (population for
groups, #rights-gated for criteria) — no printed numbers.

Run:   python3 generate_figures.py
Needs: Graphviz `dot` and `rsvg-convert` on PATH (brew install graphviz librsvg).
Edit the DATA MODEL block below to change criteria / rights / groups / sizes;
every figure updates consistently.
"""

import math
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
INK, GREY, LINE, EDGE = "#111111", "#7d7d7d", "#7d7d7d", "#9a9a9a"
FONT = "Helvetica Neue, Helvetica, Arial, sans-serif"

# ============================================================ DATA MODEL =====
# criteria keys and their display labels (column/label order)
F, NB, CP, M, A, W = "F", "NB", "CP", "M", "A", "W"
CRIT_ORDER = [F, NB, CP, M, A, W]
CRIT_LABEL = {
    F: "Free",
    NB: "Native-born",
    CP: "Two citizen parents",
    M: "Male",
    A: "Adult",
    W: "Wealthy",
}
# two-line splits for long criterion labels (used in the compact fig4 panels)
CRIT_SPLIT = {"Two citizen parents": ["Two citizen", "parents"]}

# 16 rights: (right-type, display name, required criteria)
RIGHTS = [
    ("Political", "Vote in the Ekklesia", {F, NB, CP, M, A}),
    ("Political", "Sit on juries (Heliaia)", {F, NB, CP, M, A}),
    ("Political", "Hold office by lot (archai)", {F, NB, CP, M, A}),
    ("Political", "Speak in the assembly (isegoria)", {F, NB, CP, M, A}),
    ("Legal", "Freedom from torture (basanos)", {F}),
    ("Legal", "Protection from hubris", {F}),
    ("Legal", "Bring a public suit (graphe)", {F, NB, M, A}),
    ("Economic", "Own land & house (enktesis)", {F, NB}),
    ("Economic", "Bank & lend (trapeza)", {F, W}),
    ("Economic", "Trade in the agora", {F}),
    ("Religious", "Legitimate marriage & heirs", {F, NB, CP}),
    ("Religious", "Hold a priesthood", {F, NB, CP}),
    ("Religious", "Initiation in the Mysteries", {F}),
    ("Military", "Serve as cavalry (hippeus)", {F, NB, M, A, W}),
    ("Military", "Serve as hoplite", {F, NB, M, A}),
    ("Military", "Row in the fleet", {F, M, A}),
]
# right-type -> section header shown in the fig1 table (order preserved)
TABLE_SECTIONS = [
    ("Political", "Political"),
    ("Legal", "Legal"),
    ("Economic", "Economic"),
    ("Religious", "Religious & family"),
    ("Military", "Military"),
]
TYPES = ["Political", "Legal", "Economic", "Religious", "Military"]

# 8 social groups: (name, criteria it meets, relative population)
GROUPS = [
    ("Wealthy citizen", {F, NB, CP, M, A, W}, 81),
    ("Poor citizen", {F, NB, CP, M, A}, 237),
    ("Citizen youth", {F, NB, CP, M}, 119),
    ("Citizen woman", {F, NB, CP, A}, 250),
    ("One citizen parent", {F, NB, M, A}, 61),
    ("Wealthy metic", {F, M, A, W}, 166),
    ("Freedman", {F, M, A}, 70),
    ("Slave", set(), 388),
]
GROUP_SPLIT = {
    "Wealthy citizen": ["Wealthy", "citizen"],
    "Poor citizen": ["Poor", "citizen"],
    "Citizen youth": ["Citizen", "youth"],
    "Citizen woman": ["Citizen", "woman"],
    "One citizen parent": ["One citizen", "parent"],
    "Wealthy metic": ["Wealthy", "metic"],
    "Freedman": ["Freedman"],
    "Slave": ["Slave"],
}

GNAMES = [g[0] for g in GROUPS]
GCRIT = {g[0]: g[1] for g in GROUPS}
GPOP = {g[0]: g[2] for g in GROUPS}


# ============================================================ CORE MATHS =====
def rights_of_type(t=None):
    return [i for i, r in enumerate(RIGHTS) if t is None or r[0] == t]


def held(critset, idxs):
    """indices (within idxs) of rights whose requirement ⊆ critset."""
    return frozenset(i for i in idxs if RIGHTS[i][2] <= critset)


def gated(crit, idxs):
    """indices (within idxs) of rights that require this single criterion."""
    return frozenset(i for i in idxs if crit in RIGHTS[i][2])


def covering(items, hmap):
    """covering pairs (upper, lower) of the ⊆-order on hmap[item]."""
    e = []
    for lo in items:
        for hi in items:
            if hmap[lo] < hmap[hi] and not any(
                n not in (lo, hi) and hmap[lo] < hmap[n] < hmap[hi] for n in items
            ):
                e.append((hi, lo))
    return e


def levels_from_top(items, edges):
    """longest-path layer from the maxima (0 = top)."""
    parents = {i: [] for i in items}
    for hi, lo in edges:
        parents[lo].append(hi)
    lvl, changed = {i: 0 for i in items}, True
    while changed:
        changed = False
        for i in items:
            for p in parents[i]:
                if lvl[p] + 1 > lvl[i]:
                    lvl[i] = lvl[p] + 1
                    changed = True
    return lvl


# ============================================================ SVG HELPERS ====
def svg(w, h, body, vx=0, vy=0):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" '
        f'viewBox="{vx} {vy} {w:.0f} {h:.0f}" font-family="{FONT}" fill="{INK}">\n'
        f'<rect x="{vx}" y="{vy}" width="{w:.0f}" height="{h:.0f}" fill="#fff"/>\n'
        f"{body}\n</svg>\n"
    )


def node(cx, cy, r, lines, fs=11.5, stroke=1.5, bold=False):
    out = [
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="#f0f0f0" '
        f'stroke="{INK}" stroke-width="{stroke}"/>'
    ]
    fw = ' font-weight="700"' if bold else ""
    ly = cy + r + 12
    for ln in lines:
        wln = len(ln) * fs * 0.56
        out.append(
            f'<rect x="{cx-wln/2:.1f}" y="{ly-fs+1.5:.1f}" width="{wln:.1f}" '
            f'height="{fs:.0f}" fill="#fff"/>'
        )
        out.append(
            f'<text x="{cx:.1f}" y="{ly:.1f}" font-size="{fs}"{fw} '
            f'text-anchor="middle">{ln}</text>'
        )
        ly += fs + 1
    return "\n".join(out)


def line(p, q, pos, bow=0.0):
    (x1, y1), (x2, y2) = pos[p], pos[q]
    if bow:
        cx, cy = (x1 + x2) / 2 + bow, (y1 + y2) / 2
        return (
            f'<path d="M {x1:.1f} {y1:.1f} Q {cx:.1f} {cy:.1f} {x2:.1f} {y2:.1f}" '
            f'fill="none" stroke="{LINE}" stroke-width="1"/>'
        )
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="{LINE}" stroke-width="1"/>'
    )


# =============================================================== FIGURE 1 =====
def fig1():
    xs = [336 + 52 * i for i in range(6)]  # criterion column centres
    body = [
        '<text x="60" y="142" font-size="10" font-weight="700" fill="'
        + GREY
        + '">RIGHT ↓ / CRITERIA →</text>'
    ]
    for x, c in zip(xs, CRIT_ORDER):
        body.append(
            f'<text x="{x}" y="144" font-size="10" text-anchor="start" '
            f'transform="rotate(-42 {x} 144)">{CRIT_LABEL[c]}</text>'
        )
    body.append('<line x1="60" y1="150" x2="622" y2="150" stroke="' + INK + '"/>')
    hy = 166
    for t, header in TABLE_SECTIONS:
        body.append(
            f'<text x="60" y="{hy}" font-size="10.5" font-weight="700" '
            f'fill="{GREY}">{header.replace("&", "&amp;")}</text>'
        )
        ry = hy + 14
        for i in rights_of_type(t):
            name = RIGHTS[i][1].replace("&", "&amp;")
            body.append(f'<text x="74" y="{ry+4}" font-size="11">{name}</text>')
            for x, c in zip(xs, CRIT_ORDER):
                if c in RIGHTS[i][2]:
                    body.append(f'<circle cx="{x}" cy="{ry}" r="5" fill="{INK}"/>')
                else:
                    body.append(
                        f'<circle cx="{x}" cy="{ry}" r="3.8" fill="#fff" '
                        f'stroke="{INK}" stroke-width="1.2"/>'
                    )
            ry += 18
        hy = ry + 8
    table_bottom = hy

    # criteria ranked by ALL the rights they gate — laid out exactly like the
    # five group graphs: each criterion's set of gated rights is a rights-
    # inclusion order; vertical position = number of rights gated, and an edge
    # joins a criterion to one directly above whose gated rights include all of
    # its own. (Free gates every right → apex; Wealthy gates only two → floor.)
    allr = rights_of_type()
    gmap = {c: gated(c, allr) for c in CRIT_ORDER}
    s, _ = type_panel(
        925,
        200,
        "Criteria ranked by the rights they gate",
        CRIT_ORDER,
        gmap,
        radius=lambda c: 3.8 * math.sqrt(len(gmap[c])),
        split=lambda c: CRIT_SPLIT.get(CRIT_LABEL[c], [CRIT_LABEL[c]]),
        vs=88,
        xs_gap=150,
        hy_off=44,
        bold=True,
    )
    body.append(s)

    # legends
    body.append(f'<circle cx="70" cy="{table_bottom+40}" r="5.5" fill="{INK}"/>')
    body.append(
        f'<text x="83" y="{table_bottom+44}" font-size="12">criterion required for the right</text>'
    )
    body.append(
        f'<circle cx="300" cy="{table_bottom+40}" r="4.5" fill="#fff" stroke="{INK}" stroke-width="1.2"/>'
    )
    body.append(
        f'<text x="312" y="{table_bottom+44}" font-size="12">not required</text>'
    )
    for k, txt in enumerate(
        [
            "Each node is a criterion; size and height both ∝ the number of rights it gates (higher = more).",
            "An edge links a criterion to one above whose gated rights include all of its own —",
            "the same set-inclusion ranking as the group graphs. Free gates every right; Wealthy only two.",
        ]
    ):
        body.append(
            f'<text x="1000" y="{600+k*16}" font-size="11" fill="{GREY}" '
            f'text-anchor="middle">{txt}</text>'
        )
    return svg(1250, 640, "\n".join(body), vx=30, vy=60)


# =============================================================== FIGURE 2 =====
def fig2():
    idxs = rights_of_type()
    hmap = {n: held(GCRIT[n], idxs) for n in GNAMES}
    count = {n: len(hmap[n]) for n in GNAMES}
    edges = covering(GNAMES, hmap)

    # rank each group to its "rights held" tier via invisible anchors, let dot
    # place x and route the long (skip-tier) edges around the nodes.
    ID = {n: f"g{i}" for i, n in enumerate(GNAMES)}
    rid = {v: k for k, v in ID.items()}
    tiers = sorted({count[n] for n in GNAMES}, reverse=True)
    anc = {c: f"a{c}" for c in tiers}
    dot = [
        "digraph G {",
        "rankdir=TB; splines=true;",
        "nodesep=0.34; ranksep=0.5;",
        'node [shape=box, fixedsize=true, width=1.05, height=0.62, label=""];',
    ]
    dot += [f"{anc[c]} [style=invis, width=0.01, height=0.01];" for c in tiers]
    dot.append(" -> ".join(anc[c] for c in tiers) + " [style=invis];")
    for c in tiers:
        dot.append(
            "{rank=same; "
            + anc[c]
            + "; "
            + "; ".join(ID[n] for n in GNAMES if count[n] == c)
            + ";}"
        )
    for hi, lo in edges:
        dot.append(f"{ID[hi]} -> {ID[lo]};")
    dot.append("}")
    plain = subprocess.run(
        ["dot", "-Tplain"],
        input="\n".join(dot),
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    pos, gh, epts = {}, 0.0, []
    for ln in plain.splitlines():
        t = ln.split()
        if t[0] == "graph":
            gh = float(t[3])
        elif t[0] == "node" and t[1] in rid:
            pos[rid[t[1]]] = (float(t[2]), float(t[3]))
        elif t[0] == "edge" and t[1] in rid and t[2] in rid:  # skip anchor chain
            n = int(t[3])
            epts.append([(float(t[4 + 2 * i]), float(t[5 + 2 * i])) for i in range(n)])

    SC, PADX, PADY, GX = 96.0, 24, 30, 390

    def X(x):
        return GX + PADX + x * SC

    def Y(y):
        return PADY + (gh - y) * SC

    xs = [X(px) for px, _ in pos.values()]
    body = []
    for pts in epts:
        d = f"M {X(pts[0][0]):.1f} {Y(pts[0][1]):.1f}"
        i = 1
        while i + 2 < len(pts):
            d += (
                f" C {X(pts[i][0]):.1f} {Y(pts[i][1]):.1f} {X(pts[i+1][0]):.1f} "
                f"{Y(pts[i+1][1]):.1f} {X(pts[i+2][0]):.1f} {Y(pts[i+2][1]):.1f}"
            )
            i += 3
        body.append(f'<path d="{d}" fill="none" stroke="{EDGE}" stroke-width="1.2"/>')
    for n in GNAMES:
        body.append(
            node(
                X(pos[n][0]), Y(pos[n][1]), max(4.0, math.sqrt(GPOP[n])), GROUP_SPLIT[n]
            )
        )

    # left column: group name + the criteria it meets
    gl = [
        f'<text x="40" y="34" font-size="11" font-weight="700" fill="{GREY}">GROUPS</text>'
    ]
    gy = 62
    for name, crit, _ in GROUPS:
        gl.append(
            f'<text x="40" y="{gy}" font-size="12.5" font-weight="700">{name}</text>'
        )
        cstr = " · ".join(CRIT_LABEL[c] for c in CRIT_ORDER if c in crit) or "— (none)"
        gl.append(
            f'<text x="42" y="{gy+15}" font-size="10.5" fill="{GREY}">{cstr}</text>'
        )
        gy += 40
    W = max(xs) + PADX + 60
    return svg(W, max(560, PADY + gh * SC + 40), "\n".join(gl) + "\n" + "\n".join(body))


# ================================================= per-type Hasse renderer ====
def type_panel(
    gx, top, title, items, hmap, radius, split, vs, xs_gap, hy_off=34, bold=False
):
    counts = sorted({len(hmap[n]) for n in items}, reverse=True)
    lvl = {c: i for i, c in enumerate(counts)}
    by = {}
    for n in items:
        by.setdefault(lvl[len(hmap[n])], []).append(n)
    maxk = max(len(v) for v in by.values())
    cx = gx + (maxk - 1) * xs_gap / 2
    pos = {}
    for L, ns in by.items():
        k = len(ns)
        for i, n in enumerate(ns):
            pos[n] = (cx + (i - (k - 1) / 2) * xs_gap, top + L * vs)
    body = [
        f'<text x="{cx:.1f}" y="{top-hy_off:.0f}" font-size="14" font-weight="700" '
        f'text-anchor="middle">{title}</text>'
    ]
    nlvl = {n: lvl[len(hmap[n])] for n in items}
    for hi, lo in covering(items, hmap):
        # a covering edge that skips ≥1 tier and runs vertically through the
        # centre gets bowed aside if a node blocks the straight path.
        bow = 0.0
        if abs(pos[hi][0] - pos[lo][0]) < 1.0 and nlvl[lo] - nlvl[hi] >= 2:
            if any(
                n not in (hi, lo)
                and nlvl[hi] < nlvl[n] < nlvl[lo]
                and abs(pos[n][0] - pos[hi][0]) < radius(n) + 8
                for n in items
            ):
                bow = 30 + 9 * (nlvl[lo] - nlvl[hi])
        body.append(line(hi, lo, pos, bow=bow))
    for n in items:
        body.append(node(*pos[n], radius(n), split(n), fs=10.5, stroke=1.4, bold=bold))
    return "\n".join(body), gx + maxk * xs_gap + 46


# =============================================================== FIGURE 3 =====
def fig3():
    parts, x = [], 40
    for t in TYPES:
        idxs = rights_of_type(t)
        hmap = {n: held(GCRIT[n], idxs) for n in GNAMES}
        s, x = type_panel(
            x,
            96,
            t,
            GNAMES,
            hmap,
            radius=lambda n: max(4.0, 0.58 * math.sqrt(GPOP[n])),
            split=lambda n: GROUP_SPLIT[n],
            vs=92,
            xs_gap=82,
        )
        parts.append(s)
    # legend
    ly = 470
    lx = 70
    leg = [
        f'<line x1="60" y1="{ly-26}" x2="{x-60}" y2="{ly-26}" stroke="#ededed" stroke-width="1"/>',
        f'<circle cx="{lx}" cy="{ly}" r="4" fill="#f0f0f0" stroke="{INK}" stroke-width="1.2"/>',
        f'<circle cx="{lx+26}" cy="{ly}" r="9" fill="#f0f0f0" stroke="{INK}" stroke-width="1.2"/>',
        f'<text x="{lx+44}" y="{ly+4}" font-size="11" fill="{GREY}">node size ∝ share of the '
        "population · vertical position = number of rights the group holds (higher = more rights)</text>",
        f'<text x="{lx+44}" y="{ly+20}" font-size="11" fill="{GREY}">an edge joins a group to one '
        "directly above whose rights include all of its own · each panel restricts to one type of "
        "right — the ranking reshuffles between panels</text>",
    ]
    return svg(x, 500, "\n".join(parts) + "\n" + "\n".join(leg))


# =============================================================== FIGURE 4 =====
def fig4():
    def split(c):
        lbl = CRIT_LABEL[c]
        return CRIT_SPLIT.get(lbl, [lbl])

    parts, x = [], 40
    for t in TYPES:
        idxs = rights_of_type(t)
        gmap = {c: gated(c, idxs) for c in CRIT_ORDER}
        s, x = type_panel(
            x,
            132,
            t,
            CRIT_ORDER,
            gmap,
            radius=lambda c: max(5.0, 7 * math.sqrt(len(gmap[c]))),
            split=split,
            vs=88,
            xs_gap=90,
            bold=True,
        )
        parts.append(s)
    cx = x / 2
    head = (
        f'<text x="{cx:.0f}" y="54" font-size="16" font-weight="700" '
        'text-anchor="middle">Criteria ranked by the rights they gate — within each type of right</text>'
    )
    leg = [
        f'<line x1="60" y1="454" x2="{x-60:.0f}" y2="454" stroke="#ededed" stroke-width="1"/>',
        f'<text x="{cx:.0f}" y="474" font-size="11" fill="{GREY}" text-anchor="middle">'
        "Each panel restricts to one type of right; within it the criteria are ranked by how many rights of that type they gate — "
        "node size and height both ∝ that count (higher = more).</text>",
        f'<text x="{cx:.0f}" y="490" font-size="11" fill="{GREY}" text-anchor="middle">'
        "An edge links a criterion to one above whose gated rights include all of its own. Free tops every type; the rest reshuffle — "
        "Wealthy gates only banking &amp; cavalry, birth-criteria dominate the religious sphere.</text>",
    ]
    return svg(x, 510, head + "\n" + "\n".join(parts) + "\n" + "\n".join(leg))


# =================================================================== MAIN =====
def render(name, markup):
    sp = os.path.join(HERE, name + ".svg")
    with open(sp, "w") as fh:
        fh.write(markup)
    subprocess.run(
        ["rsvg-convert", "-z", "2", sp, "-o", os.path.join(HERE, name + ".png")],
        check=True,
    )
    print("wrote", name + ".svg / .png")


if __name__ == "__main__":
    render("athens-fig1-table-criteria", fig1())
    render("athens-fig2-groups-overall", fig2())
    render("athens-fig3-five-graphs", fig3())
    render("athens-fig4-criteria-by-type", fig4())
