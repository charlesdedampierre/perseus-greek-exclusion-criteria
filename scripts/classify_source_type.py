"""Classify each work in final_dataset_for_criteria.tsv into one source-type bucket.

Categories (see data/processed_data/source_type_taxonomy.md):
  A_legal_constitutional   Statute / constitutional clause quoted verbatim
  B_oration                Court speech or political oration invoking law/procedure
  C_historical             Work composed by a historian or biographer
  D_contemporary_treatise  Philosophical treatise / political essay
  E_entertainment          Drama, satire, fiction
  F_religious_scriptural   New Testament & apostolic writings
"""

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data/processed_data/final_dataset_for_criteria.tsv"
OUT = ROOT / "data/processed_data/works_source_type.tsv"

CATEGORIES = {
    "A_legal_constitutional": "Original legal text, statute, or constitutional clause quoted verbatim",
    "B_oration": "Court speech or political oration invoking a specific extant law or procedure",
    "C_historical": "Historical text — work by an author writing as historian or biographer",
    "D_contemporary_treatise": "Contemporary philosophical / political treatise implying the rule exists",
    "E_entertainment": "Entertainment text — drama, satire, fiction; mixes commentary with artistic license",
    "F_religious_scriptural": "Religious / scriptural text (NT & apostolic writings)",
}

FORENSIC_AUTHORS = {
    "Lysias",
    "Isaeus",
    "Antiphon",
    "Andocides",
    "Aeschines",
    "Hyperides",
    "Dinarchus",
    "Lycurgus",
    "Demades",
}

ISOCRATES_FORENSIC = {
    "aegineticus",
    "against callimachus",
    "against euthynus",
    "against lochites",
    "concerning the team of horses",
    "trapeziticus",
}

DEMOSTHENES_NON_ORATION = {
    "the funeral speech",
    "the erotic essay",
    "exordia",
    "letters",
}

PLUTARCH_ANECDOTAL_KEYWORDS = (
    "sayings",
    "anecdotes",
    "dinner of the seven wise men",
)

LUCIAN_TREATISE_TITLES = {
    "how to write history",
    "slander, a warning",
    "demosthenes an encomium",
}
LUCIAN_HISTORICAL_BIOGRAPHY = {
    "demonax",
    "alexander the false prophet",
}

XENOPHON_BIOGRAPHY = {"agesilaus"}

NT_AUTHORS = {
    "New Testament",
    "Hermas",
    "Clement of Rome",
    "Polycarp",
    "Ignatius of Antioch",
    "Barnabas",
}


def classify(row: pd.Series) -> str:
    author = str(row.get("perseus_author", "")).strip()
    title = str(row.get("perseus_title", "")).strip().lower()
    genre = str(row.get("genre", "")).lower()
    fcw = str(row.get("form_of_creative_work", "")).lower()
    instance = str(row.get("instance_of", "")).lower()

    if author in NT_AUTHORS:
        return "F_religious_scriptural"

    if "play" in fcw or "comedy" in genre or "dramatic work" in instance:
        return "E_entertainment"
    if author == "Aristophanes":
        return "E_entertainment"

    if "Lucian" in author:
        if any(k in title for k in LUCIAN_TREATISE_TITLES):
            return "D_contemporary_treatise"
        if any(k in title for k in LUCIAN_HISTORICAL_BIOGRAPHY):
            return "C_historical"
        return "E_entertainment"

    if author == "Aristotle":
        if "athenian constitution" in title:
            return "A_legal_constitutional"
        return "D_contemporary_treatise"

    if author == "Plato":
        if title == "apology":
            return "B_oration"
        return "D_contemporary_treatise"

    if author == "Xenophon":
        if title in XENOPHON_BIOGRAPHY:
            return "C_historical"
        return "D_contemporary_treatise"

    if author == "Demosthenes":
        if title in DEMOSTHENES_NON_ORATION:
            return "D_contemporary_treatise"
        return "B_oration"

    if author == "Isocrates":
        if title in ISOCRATES_FORENSIC:
            return "B_oration"
        return "D_contemporary_treatise"

    if author in FORENSIC_AUTHORS:
        return "B_oration"

    if author == "Plutarch":
        if "biography" in genre or "biographical" in genre:
            return "C_historical"
        if any(k in title for k in PLUTARCH_ANECDOTAL_KEYWORDS):
            return "E_entertainment"
        return "D_contemporary_treatise"

    pure_historians = {
        "Thucydides",
        "Polybius",
        "Strabo",
        "Pausanias",
        "Appian of Alexandria",
        "Athenaeus",
        "Diogenes Laertius",
    }
    if author in pure_historians:
        return "C_historical"

    if author == "Epictetus":
        return "D_contemporary_treatise"

    return "D_contemporary_treatise"


def main() -> None:
    df = pd.read_csv(SRC, sep="\t")
    df["source_type"] = df.apply(classify, axis=1)
    df["source_type_description"] = df["source_type"].map(CATEGORIES)

    out_cols = [
        "file_id",
        "perseus_author",
        "perseus_title",
        "period",
        "year",
        "genre",
        "n_words",
        "source_type",
        "source_type_description",
    ]
    df[out_cols].to_csv(OUT, sep="\t", index=False)

    print(f"Wrote {OUT.relative_to(ROOT)}  ({len(df)} rows)\n")
    print("Distribution by source_type:")
    print(df["source_type"].value_counts().to_string())
    print("\nCross-tab by period x source_type:")
    print(pd.crosstab(df["period"], df["source_type"], dropna=False).to_string())


if __name__ == "__main__":
    main()
