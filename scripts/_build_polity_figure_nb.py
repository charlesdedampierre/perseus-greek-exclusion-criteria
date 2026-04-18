"""One-shot builder for analysis_notebooks/13_polity_time_figure.ipynb.

Produces a Science-style figure from data/processed_data/rules_full_dataset.tsv:

- Panel A: per-author stacked horizontal bar of rule_time_reference shares,
           ordered by author floruit year; n-rules annotated on the right.
- Panel B: top rule_polity labels, colored by each polity's dominant
           rule_time_reference.

Figure saved to analysis_notebooks/figures/fig1_polity_time.{png,pdf}.
"""

import pathlib
import textwrap

import nbformat as nbf

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
OUT = REPO / "analysis_notebooks" / "13_polity_time_figure.ipynb"

nb = nbf.v4.new_notebook()
nb["cells"] = [
    nbf.v4.new_markdown_cell(
        textwrap.dedent(
            """\
            # Figure 1 — Temporal framing of social-exclusion rules

            Per-rule annotations produced by
            `scripts/classifiers/classify_work_polity.py`:

            - **`rule_time_reference`** ∈ {contemporary, past, future, mixed, timeless}
            - **`rule_polity`** — short canonical polity label

            **Panel A** — author × time-reference, stacked 100 % bars ordered by floruit.
            **Panel B** — top polities, colored by dominant time reference.

            Styled for a two-column magazine figure (≈ 18 cm wide, Arial/Helvetica,
            7–8 pt, 300 dpi PNG + editable-text PDF).
            """
        )
    ),
    nbf.v4.new_code_cell(
        textwrap.dedent(
            """\
            import pathlib
            import matplotlib.pyplot as plt
            import pandas as pd
            from matplotlib import rcParams

            # Science-magazine-friendly defaults
            rcParams["font.family"] = ["Helvetica", "Arial", "sans-serif"]
            rcParams["font.size"] = 7
            rcParams["axes.labelsize"] = 8
            rcParams["axes.titlesize"] = 9
            rcParams["axes.titleweight"] = "bold"
            rcParams["axes.linewidth"] = 0.6
            rcParams["xtick.labelsize"] = 7
            rcParams["ytick.labelsize"] = 7
            rcParams["xtick.major.width"] = 0.6
            rcParams["ytick.major.width"] = 0.6
            rcParams["xtick.major.size"] = 2.5
            rcParams["ytick.major.size"] = 2.5
            rcParams["legend.fontsize"] = 7
            rcParams["legend.frameon"] = False
            rcParams["pdf.fonttype"] = 42    # editable text in PDF
            rcParams["ps.fonttype"] = 42

            REPO = pathlib.Path().resolve().parent
            DATA = REPO / "data" / "processed_data" / "rules_full_dataset.tsv"
            FIGDIR = REPO / "analysis_notebooks" / "figures"
            FIGDIR.mkdir(parents=True, exist_ok=True)

            df = pd.read_csv(DATA, sep="\\t")
            print(
                f"{len(df):,} rules / {df['author'].nunique()} authors / "
                f"{df['file_id'].nunique()} works"
            )
            """
        )
    ),
    nbf.v4.new_code_cell(
        textwrap.dedent(
            """\
            # Order authors by floruit year; compute time-reference proportions.
            author_order = (
                df.groupby("author")
                .agg(floruit=("impact_year", "first"), n=("rule_uid", "count"))
                .reset_index()
                .sort_values("floruit")
                .reset_index(drop=True)
            )
            authors = author_order["author"].tolist()

            _level_order = ["past", "contemporary", "mixed", "future", "timeless"]
            present = set(df["rule_time_reference"].dropna().unique())
            time_levels = [t for t in _level_order if t in present]
            colors = {
                "contemporary": "#2b6cb0",   # steel blue
                "past":         "#c05621",   # burnt orange
                "future":       "#2f855a",   # forest green
                "mixed":        "#805ad5",   # purple
                "timeless":     "#a0aec0",   # neutral gray
            }

            counts = (
                df.groupby(["author", "rule_time_reference"])
                .size()
                .unstack(fill_value=0)
                .reindex(authors)
            )
            for t in time_levels:
                if t not in counts.columns:
                    counts[t] = 0
            counts = counts[time_levels]
            props = counts.div(counts.sum(axis=1), axis=0)
            props
            """
        )
    ),
    nbf.v4.new_code_cell(
        textwrap.dedent(
            """\
            # Panel B data: top polities + dominant time reference per polity.
            TOP_N = 10
            polities = df["rule_polity"].value_counts().head(TOP_N)
            dom = (
                df.groupby("rule_polity")["rule_time_reference"]
                .agg(lambda s: s.value_counts().idxmax())
            )
            polity_colors = [colors[dom.loc[p]] for p in polities.index]

            def _wrap(label, width=34):
                return label if len(label) <= width else label[: width - 1] + "\u2026"

            polity_labels = [_wrap(p) for p in polities.index]
            polities
            """
        )
    ),
    nbf.v4.new_code_cell(
        textwrap.dedent(
            """\
            fig, (axA, axB) = plt.subplots(
                1, 2, figsize=(9.0, 4.8),
                gridspec_kw={"width_ratios": [1.5, 1.0], "wspace": 1.15},
            )

            # --- Panel A: author x time-reference stacked bar --------------------
            y = range(len(authors))
            left = [0.0] * len(authors)
            for t in time_levels:
                vals = props[t].values
                axA.barh(
                    list(y), vals, left=left,
                    color=colors[t], label=t,
                    height=0.78, edgecolor="white", linewidth=0.5,
                )
                left = [l + v for l, v in zip(left, vals)]

            labels = [
                f"{a}  ({int(f):+d})"
                for a, f in zip(authors, author_order["floruit"].astype(int))
            ]
            axA.set_yticks(list(y))
            axA.set_yticklabels(labels)
            axA.invert_yaxis()
            axA.set_xlim(0, 1)
            axA.set_xticks([0, 0.25, 0.5, 0.75, 1])
            axA.set_xticklabels(["0", "0.25", "0.5", "0.75", "1"])
            axA.set_xlabel("Share of rules")
            axA.set_title("A  Per-author temporal framing",
                          loc="left", fontsize=9, pad=8, fontweight="bold")
            axA.spines[["top", "right"]].set_visible(False)
            axA.tick_params(axis="y", length=0)

            # Annotate n on the right of each bar
            for yi, n in enumerate(author_order["n"].values):
                axA.text(
                    1.015, yi, f"n={int(n)}",
                    va="center", ha="left", fontsize=6.5, color="#4a5568",
                )

            # Legend above plot
            axA.legend(
                loc="lower center", bbox_to_anchor=(0.5, -0.18),
                ncol=5, handlelength=1.2, columnspacing=1.6, handletextpad=0.4,
            )

            # --- Panel B: top polities -------------------------------------------
            yB = range(len(polities))
            axB.barh(
                list(yB), polities.values,
                color=polity_colors, edgecolor="white", linewidth=0.5, height=0.78,
            )
            axB.set_yticks(list(yB))
            axB.set_yticklabels(polity_labels)
            axB.invert_yaxis()
            axB.set_xlabel("Number of rules")
            axB.set_title("B  Top polities referenced",
                          loc="left", fontsize=9, pad=8, fontweight="bold")
            axB.spines[["top", "right"]].set_visible(False)
            axB.tick_params(axis="y", length=0)

            # Value annotations
            xmax = polities.max()
            axB.set_xlim(0, xmax * 1.12)
            for yi, v in enumerate(polities.values):
                axB.text(
                    v + xmax * 0.015, yi, f"{int(v)}",
                    va="center", ha="left", fontsize=6.5, color="#4a5568",
                )

            fig.suptitle(
                "Fig. 1. Temporal framing of 1,594 social-exclusion rules "
                "extracted from 19 ancient Greek and early Christian authors.",
                fontsize=9, y=1.03, x=0.02, ha="left", fontweight="bold",
            )

            for ext in ("png", "pdf"):
                fig.savefig(
                    FIGDIR / f"fig1_polity_time.{ext}",
                    dpi=300, bbox_inches="tight",
                )
            print("Saved", FIGDIR / "fig1_polity_time.png")
            plt.show()
            """
        )
    ),
    nbf.v4.new_code_cell(
        textwrap.dedent(
            """\
            # Quick numeric summary to accompany the figure
            print("Time-reference distribution (all rules):")
            print(df["rule_time_reference"].value_counts().to_string())
            print()
            print("Rules per author, with dominant time reference:")
            dom_auth = (
                df.groupby("author")["rule_time_reference"]
                .agg(["count", lambda s: s.value_counts().idxmax()])
                .rename(columns={"<lambda_0>": "dominant"})
                .sort_values("count", ascending=False)
            )
            print(dom_auth.to_string())
            """
        )
    ),
]

# Kernel metadata (prefer the project .venv when it exists, otherwise the system python)
nb["metadata"] = {
    "kernelspec": {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    },
    "language_info": {"name": "python", "version": "3.11"},
}

OUT.write_text(nbf.writes(nb))
print(f"wrote {OUT}")
