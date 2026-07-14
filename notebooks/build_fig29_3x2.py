"""CHA-64 — Figure 3 group panels as a 3 x 2 grid.

Rebuilds the "social groups ranked by rights held" panel of notebook
29_figure3_rights_criteria_groups.ipynb as a 3 x 2 grid of six Hasse diagrams:

    All rights          | Political rights
    Legal rights        | Economic rights
    Religious & family rights | Military rights

The word "rights" is appended to every panel title. Data model and SVG
rendering helpers are copied verbatim from notebook 29 so the style matches.
"""
import math
import os
import subprocess

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
FINAL = os.path.join(HERE, "..", "data", "clean", "final")
POLITY = "Classical Athens"

INK, GREY, LINE, EDGE = "#111111", "#7d7d7d", "#7d7d7d", "#9a9a9a"
FONT = "Helvetica Neue, Helvetica, Arial, sans-serif"

# --- Data model (verbatim from notebook 29) -------------------------------
CRITERIA = [
    {"axis": "c_ownership_status", "label": "Free",        "positive": "free",     "negative": {"enslaved", "freed"}},
    {"axis": "c_ancestry",         "label": "Native-born", "positive": "native",   "negative": {"foreign"}},
    {"axis": "c_residence",        "label": "Resident",    "positive": "resident", "negative": {"non_resident", "foreign"}},
    {"axis": "c_sex",              "label": "Male",        "positive": "male",     "negative": {"female"}},
    {"axis": "c_age",              "label": "Adult",       "positive": "adult",    "negative": {"minor", "child"}},
    {"axis": "c_wealth",           "label": "Wealthy",     "positive": "high",     "negative": {"low"}},
]
CRIT_ORDER = [c["label"] for c in CRITERIA]

RIGHTS_CATEGORIES = {
    "Political": ["Voting in the assembly", "Speaking in the assembly", "Eligibility for public office",
                  "Eligibility for jury service", "Deliberative authority"],
    "Legal": ["Right to a trial", "Protection from judicial torture",
              "Protection from private assault"],
    "Economic": ["Inheriting property", "Owning and retaining property",
                 "Right to engage in business", "Exemption from taxes"],
    "Religious & family": ["Participation in sacred rites", "Right to a dowry",
                           "Freedom of choice in marriage", "Right to marry a citizen"],
    "Military": ["Possession of arms", "Exemption from military service", "Eligibility for military command"],
}
RIGHT_NAMES = [r for rights in RIGHTS_CATEGORIES.values() for r in rights]
TYPES = list(RIGHTS_CATEGORIES)

GROUPS = {
    "Wealthy citizen man": {"Free", "Native-born", "Resident", "Male", "Adult", "Wealthy"},
    "Poor citizen man":    {"Free", "Native-born", "Resident", "Male", "Adult"},
    "Citizen youth":       {"Free", "Native-born", "Resident", "Male"},
    "Citizen woman":       {"Free", "Native-born", "Resident", "Adult"},
    "Wealthy metic":       {"Free", "Resident", "Male", "Adult", "Wealthy"},
    "Metic":               {"Free", "Resident", "Male", "Adult"},
    "Freedman":            {"Free", "Resident", "Male"},
    "Slave":               {"Resident"},
}
POPULATION = {
    "Wealthy citizen man": 30, "Poor citizen man": 110, "Citizen youth": 60, "Citizen woman": 140,
    "Wealthy metic": 18, "Metic": 55, "Freedman": 25, "Slave": 160,
}
GROUP_SPLIT = {
    "Wealthy citizen man": ["Wealthy", "citizen man"], "Poor citizen man": ["Poor", "citizen man"],
    "Citizen youth": ["Citizen", "youth"], "Citizen woman": ["Citizen", "woman"],
    "Wealthy metic": ["Wealthy", "metic"], "Metic": ["Metic"], "Freedman": ["Freedman"], "Slave": ["Slave"],
}
GNAMES = list(GROUPS)

# --- Build the "which criteria gate each right" table (verbatim logic) -----
matrix = pd.read_csv(os.path.join(FINAL, "group_rights_matrix.tsv"), sep="\t")
matrix = matrix[matrix["rule_polity"] == POLITY].copy()


def holds_right(v):
    return str(v) in {"1", "1.0"}


def denied_right(v):
    return str(v) in {"0", "0.0"}


def most_fundamental_lacking(group_row):
    for crit in CRITERIA:
        if str(group_row[crit["axis"]]) in crit["negative"]:
            return crit["label"]
    return None


gate_rows, n_holders = {}, {}
for right in RIGHT_NAMES:
    holders = matrix[matrix[right].map(holds_right)]
    deniers = matrix[matrix[right].map(denied_right)]
    n_holders[right] = len(holders)
    denial_labels = set(deniers.apply(most_fundamental_lacking, axis=1).dropna())
    gate_rows[right] = {
        crit["label"]: int(
            ((crit["positive"] in set(holders[crit["axis"]].dropna().astype(str)))
             and not (set(holders[crit["axis"]].dropna().astype(str)) & crit["negative"]))
            or crit["label"] in denial_labels)
        for crit in CRITERIA
    }

gate_required = pd.DataFrame(gate_rows).T.reindex(RIGHT_NAMES)[CRIT_ORDER]
assert (pd.Series(n_holders) > 0).all(), "every right must have an attested holder"

required_criteria = {
    right: {c for c in CRIT_ORDER if gate_required.loc[right, c] == 1}
    for right in RIGHT_NAMES
}
RIGHTS = [(cat, name, required_criteria[name])
          for cat, names in RIGHTS_CATEGORIES.items() for name in names]

# --- Rendering helpers (verbatim from notebook 29) -------------------------
def rights_of_type(t=None):
    return [i for i, r in enumerate(RIGHTS) if t is None or r[0] == t]


def held(critset, idxs):
    return frozenset(i for i in idxs if RIGHTS[i][2] <= critset)


def covering(items, hmap):
    edges = []
    for lo in items:
        for hi in items:
            if hmap[lo] < hmap[hi] and not any(
                    n not in (lo, hi) and hmap[lo] < hmap[n] < hmap[hi] for n in items):
                edges.append((hi, lo))
    return edges


def svg(w, h, body, vx=0, vy=0):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" '
            f'viewBox="{vx} {vy} {w:.0f} {h:.0f}" font-family="{FONT}" fill="{INK}">\n'
            f'<rect x="{vx}" y="{vy}" width="{w:.0f}" height="{h:.0f}" fill="#fff"/>\n{body}\n</svg>\n')


def node(cx, cy, r, lines, fs=11.5, stroke=1.5, bold=False, inside=False):
    out = [f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="#f0f0f0" stroke="{INK}" stroke-width="{stroke}"/>']
    fw = ' font-weight="700"' if bold else ""
    line_h = fs + 1
    if inside:
        ly = cy - (len(lines) - 1) * line_h / 2 + 0.34 * fs
        for ln in lines:
            out.append(f'<text x="{cx:.1f}" y="{ly:.1f}" font-size="{fs}"{fw} text-anchor="middle">{ln}</text>')
            ly += line_h
    else:
        ly = cy + r + fs - 1.5
        for ln in lines:
            wln = len(ln) * fs * 0.56
            out.append(f'<rect x="{cx-wln/2:.1f}" y="{ly-fs+1.5:.1f}" width="{wln:.1f}" height="{fs:.0f}" fill="#fff"/>')
            out.append(f'<text x="{cx:.1f}" y="{ly:.1f}" font-size="{fs}"{fw} text-anchor="middle">{ln}</text>')
            ly += line_h
    return "\n".join(out)


def link(p, q, pos):
    (x1, y1), (x2, y2) = pos[p], pos[q]
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{LINE}" stroke-width="1"/>'


def png(markup, zoom=2):
    return subprocess.run(["rsvg-convert", "-z", str(zoom)], input=markup.encode(), capture_output=True).stdout


def type_panel(gx, top, title, items, hmap, radius, split, vs, xs_gap, hy_off=34, bold=False,
               label_fs=12.5, title_fs=14, label_inside=False):
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
    body = [f'<text x="{cx:.1f}" y="{top-hy_off:.0f}" font-size="{title_fs}" font-weight="700" '
            f'text-anchor="middle">{title.replace("&", "&amp;")}</text>']
    for hi, lo in covering(items, hmap):
        body.append(link(hi, lo, pos))
    for n in items:
        body.append(node(*pos[n], radius(n), split(n), fs=label_fs, stroke=1.4, bold=bold,
                         inside=label_inside))

    # True bounding box: nodes (circle + label lines below), plus the title.
    x0 = x1 = cx
    y0 = top - hy_off - title_fs           # title baseline sits above the top tier
    y1 = top
    title_half = len(title) * title_fs * 0.56 / 2
    x0, x1 = min(x0, cx - title_half), max(x1, cx + title_half)
    for n in items:
        px, py = pos[n]
        r = radius(n)
        lines = split(n)
        lbl_half = max((len(ln) for ln in lines), default=0) * label_fs * 0.56 / 2
        x0 = min(x0, px - r, px - lbl_half)
        x1 = max(x1, px + r, px + lbl_half)
        y1 = max(y1, py + r + len(lines) * (label_fs + 1))
    return "\n".join(body), (x0, y0, x1, y1)


# --- New 3 x 2 grid layout -------------------------------------------------
# Panels: "all rights" first, then the five categories, each with "rights" in
# the title. Titles read: All rights / Political rights / Legal rights /
# Economic rights / Religious & family rights / Military rights.
PANELS = [(None, "All rights")] + [(t, f"{t} rights") for t in TYPES]


def fig_group_panels_3x2(node_scale=1.4, text_scale=1.9, vs=150, xs_gap=250,
                         top=140, cols=3, gutter=70, row_gap=170, margin=40):
    """Six group Hasse panels arranged on a `cols`-wide grid (3 columns x 2 rows by default).

    `gutter` is the horizontal space between columns; `row_gap` is the vertical
    space between rows (kept larger so the two rows breathe and the lower titles
    clear the labels of the row above).

    Each panel is rendered in its own coordinates, its true bounding box is
    measured, then it is translated into a grid cell sized to the widest panel
    per column and the tallest per row. Node size is proportional to population
    share, exactly as the original panel.
    """
    # Precompute each panel's lattice shape (number of tiers, widest tier) so we
    # can give every sub-figure roughly the same drawn width and height. Rather
    # than scaling whole panels (which would change node/font sizes unevenly), we
    # stretch each panel's vertical and horizontal *spacing* to a shared node
    # span. Node radii and font sizes stay identical across all six panels.
    shapes = []
    for t, title in PANELS:
        idxs = rights_of_type(t)
        hmap = {n: held(GROUPS[n], idxs) for n in GNAMES}
        tiers = {}
        for n in GNAMES:
            tiers.setdefault(len(hmap[n]), []).append(n)
        levels = len(tiers)
        maxk = max(len(v) for v in tiers.values())
        shapes.append((title, hmap, levels, maxk))

    span_y = vs * (max(s[2] for s in shapes) - 1)      # tallest panel's tier span
    span_x = xs_gap * (max(s[3] for s in shapes) - 1)  # widest panel's node span

    def build_panel(title, hmap, levels, maxk):
        vs_i = span_y / (levels - 1) if levels > 1 else vs
        xs_i = span_x / (maxk - 1) if maxk > 1 else xs_gap
        return type_panel(0, top, title, GNAMES, hmap,
                          radius=lambda n: node_scale * max(9.0, 1.35 * math.sqrt(POPULATION[n])),
                          split=lambda n: GROUP_SPLIT[n], vs=vs_i, xs_gap=xs_i,
                          hy_off=52, label_fs=20.4 * text_scale, title_fs=20 * text_scale,
                          label_inside=False)

    panels = [build_panel(*s) for s in shapes]
    rows = math.ceil(len(panels) / cols)

    pw = [x1 - x0 for _, (x0, _, x1, _) in panels]
    ph = [y1 - y0 for _, (_, y0, _, y1) in panels]

    # Uniform grid cell = the largest panel's box; every panel is centred inside
    # an identically sized cell. Because the node spans were equalised above, the
    # panels themselves are now close to the same width and height.
    cell_w, cell_h = max(pw), max(ph)
    col_x = [margin + c * (cell_w + gutter) for c in range(cols)]
    row_y = [margin + r * (cell_h + row_gap) for r in range(rows)]

    parts = []
    for i, (body, (x0, y0, x1, y1)) in enumerate(panels):
        col, rowi = i % cols, i // cols
        dx = col_x[col] + (cell_w - pw[i]) / 2 - x0
        dy = row_y[rowi] + (cell_h - ph[i]) / 2 - y0
        parts.append(f'<g transform="translate({dx:.1f} {dy:.1f})">\n{body}\n</g>')

    W = 2 * margin + cols * cell_w + (cols - 1) * gutter
    H = 2 * margin + rows * cell_h + (rows - 1) * row_gap
    return svg(W, H, "\n".join(parts))


if __name__ == "__main__":
    markup = fig_group_panels_3x2()
    with open(os.path.join(HERE, "fig29_group_panels_3x2.svg"), "w") as f:
        f.write(markup)
    with open(os.path.join(HERE, "fig29_group_panels_3x2.png"), "wb") as f:
        f.write(png(markup, zoom=2))
    print("wrote fig29_group_panels_3x2.svg / .png")
