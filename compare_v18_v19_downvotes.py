"""
For each downvoted rule in data/annotation/user_comments_sample60_v18.csv,
check whether a similar rule still appears in V19 output for the same work.

Matching heuristic:
- Same file_id.
- Score each V19 candidate by: group-name overlap, resource overlap, verbatim
  overlap. Report the best match.

Output:
- data/annotation/v18_downvotes_vs_v19.tsv     per-rule verdict table
- prints a compact summary.
"""

import json
import re
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
SAMPLE_CSV = HERE / "data/annotation/user_comments_sample60_v18.csv"
V19_DIR = HERE / "data/llm_results/gemini_v19"
OUT_TSV = HERE / "data/annotation/v18_downvotes_vs_v19.tsv"


def tokens(s: str) -> set:
    s = str(s or "").lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return {t for t in s.split() if len(t) > 3}


def load_v19_for(file_id: str) -> list[dict]:
    path = V19_DIR / f"{file_id}.json"
    if not path.exists():
        return []
    d = json.loads(path.read_text())
    return d.get("extracted_rules", []) or []


def verbatim_text(rule: dict) -> str:
    v = rule.get("verbatim") or rule.get("proof") or ""
    if isinstance(v, list):
        return " ".join(str(x) for x in v)
    return str(v)


def similarity(v18_row: dict, v19_rule: dict) -> tuple[float, dict]:
    g18 = tokens(v18_row.get("in_group", ""))
    g19 = tokens(v19_rule.get("group", ""))
    r18 = tokens(v18_row.get("resource", ""))
    r19 = tokens(v19_rule.get("resource", ""))
    vb18 = tokens(v18_row.get("verbatim", ""))
    vb19 = tokens(verbatim_text(v19_rule))

    def jacc(a, b):
        if not a and not b:
            return 0.0
        return len(a & b) / max(1, len(a | b))

    g_sim = jacc(g18, g19)
    r_sim = jacc(r18, r19)
    v_sim = jacc(vb18, vb19)
    score = 0.4 * g_sim + 0.3 * r_sim + 0.3 * v_sim
    return score, {"group_sim": g_sim, "resource_sim": r_sim, "verbatim_sim": v_sim}


def classify_match(score: float, parts: dict) -> str:
    if score >= 0.45:
        return "STILL PRESENT"
    if score >= 0.25:
        return "REFORMULATED"
    if parts["verbatim_sim"] >= 0.25:
        return "SAME PASSAGE, DIFFERENT RULE"
    return "GONE"


def best_match(v18_row: dict, v19_rules: list[dict]) -> dict:
    if not v19_rules:
        return {
            "verdict": "NO V19 RULES",
            "score": 0.0,
            "best_group": "",
            "best_resource": "",
            "best_rule": "",
            "best_verbatim": "",
        }
    best = None
    for r in v19_rules:
        s, parts = similarity(v18_row, r)
        if best is None or s > best[0]:
            best = (s, parts, r)
    score, parts, r = best
    return {
        "verdict": classify_match(score, parts),
        "score": round(score, 3),
        "group_sim": round(parts["group_sim"], 2),
        "resource_sim": round(parts["resource_sim"], 2),
        "verbatim_sim": round(parts["verbatim_sim"], 2),
        "best_group": r.get("group", ""),
        "best_resource": r.get("resource", ""),
        "best_rule": r.get("rule", r.get("rule_name", "")),
        "best_criteria": "|".join(
            r.get("criteria", []) if isinstance(r.get("criteria"), list) else []
        ),
    }


def main():
    df = pd.read_csv(SAMPLE_CSV)
    df = df[df["file_id"].astype(str).str.startswith("tlg")].copy()
    down = df[df["vote"] == "down"].copy()
    print(f"Downvoted rules to check: {len(down)}")

    rows = []
    for _, r in down.iterrows():
        v19 = load_v19_for(r["file_id"])
        match = best_match(r.to_dict(), v19)
        rows.append(
            {
                "file_id": r["file_id"],
                "author": r["author"],
                "work_name": r["work_name"],
                "v18_rule": r["criterion_label"],
                "v18_group": r["in_group"],
                "v18_resource": r["resource"],
                "v18_comment": r.get("comment", ""),
                **match,
            }
        )

    out = pd.DataFrame(rows).sort_values("verdict").reset_index(drop=True)
    OUT_TSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_TSV, sep="\t", index=False)

    print(f"\nWrote {OUT_TSV}")
    print()
    print("Verdict distribution:")
    print(out["verdict"].value_counts().to_string())
    print()
    print("Per-rule breakdown:")
    cols = ["file_id", "v18_rule", "verdict", "score", "best_rule", "v18_comment"]
    print(out[cols].to_string(index=False, max_colwidth=40))


if __name__ == "__main__":
    main()
