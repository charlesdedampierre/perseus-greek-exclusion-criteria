"""
Create final dataset with:
- Authors with match_score > 120
- Authors with polity AND impact_date
- Only works with English translations (last translation per work)
"""

import pandas as pd

AUTHORS_TSV = "data/perseus_authors_wikidata.tsv"  # Pre-enriched, no LLM data
METADATA_TSV = "data/perseus_metadata.tsv"
OUTPUT_TSV = "data/perseus_final_dataset.tsv"


def parse_year(date_str):
    """Extract year from date string like -0428-01-01 or 0120-01-01"""
    if pd.isna(date_str) or date_str == "":
        return None
    try:
        date_str = str(date_str)
        if date_str.startswith("-"):
            parts = date_str[1:].split("-")
            return -int(parts[0])
        else:
            parts = date_str.split("-")
            return int(parts[0])
    except:
        return None


def main():
    # Load authors
    authors_df = pd.read_csv(AUTHORS_TSV, sep="\t")

    # Filter authors: score > 120, has polity, has impact_date
    valid_authors = authors_df[
        (authors_df["match_score"] > 120)
        & (authors_df["cliopatria_polity"].notna())
        & (authors_df["cliopatria_polity"] != "")
        & (authors_df["impact_date"].notna())
        & (authors_df["impact_date"] != "")
    ].copy()

    print(f"Authors after filtering: {len(valid_authors)} / {len(authors_df)}")

    # Load works metadata
    metadata_df = pd.read_csv(METADATA_TSV, sep="\t")

    # Filter for English translations only (filename contains 'eng')
    english_works = metadata_df[
        metadata_df["filename"].str.contains("eng", case=False, na=False)
    ].copy()

    print(f"English works: {len(english_works)} / {len(metadata_df)}")

    # Keep only the last translation per work (by author + work_code)
    english_works = english_works.sort_values(["author", "work_code", "filename"])
    english_works = english_works.drop_duplicates(
        subset=["author", "work_code"], keep="last"
    )

    print(f"Unique English works (after dedup): {len(english_works)}")

    # Create author name mapping from perseus_author to match metadata
    # The metadata uses 'author' column, authors_df uses 'perseus_author'
    author_names = set(valid_authors["perseus_author"].tolist())

    # Filter works by valid authors
    valid_works = english_works[english_works["author"].isin(author_names)].copy()

    print(f"Works by valid authors: {len(valid_works)}")

    # Merge works with author information
    final_df = valid_works.merge(
        valid_authors[
            [
                "perseus_author",
                "wikidata_id",
                "wikidata_name",
                "description",
                "occupations",
                "cliopatria_polity",
                "cliopatria_polity_id",
                "birthdate",
                "deathdate",
                "impact_date",
                "impact_date_precision",
                "wikipedia_url",
                "match_score",
            ]
        ],
        left_on="author",
        right_on="perseus_author",
        how="inner",
    )

    # Convert impact_date to year
    final_df["impact_year"] = final_df["impact_date"].apply(parse_year)

    # Add works count per author
    works_count = final_df.groupby("wikidata_id").size().to_dict()
    final_df["works_count"] = final_df["wikidata_id"].map(works_count)

    # Reorder columns: start with wikidata_id, name, impact_year, title
    final_columns = [
        # Key identifiers first
        "wikidata_id",
        "wikidata_name",
        "impact_year",
        "title",
        "works_count",
        # Then other author info
        "author",
        "description",
        "occupations",
        "cliopatria_polity",
        "cliopatria_polity_id",
        "birthdate",
        "deathdate",
        "impact_date",
        "impact_date_precision",
        "wikipedia_url",
        "match_score",
        # Work info
        "author_code",
        "work_code",
        "filename",
        "file_path",
        "editors",
        "publisher",
        "pub_place",
        "pub_date",
        "languages",
        "text_length",
        "word_count",
    ]

    # Keep only columns that exist
    final_columns = [c for c in final_columns if c in final_df.columns]
    final_df = final_df[final_columns]

    # Sort by name and title
    final_df = final_df.sort_values(["wikidata_name", "title"])

    # Save
    final_df.to_csv(OUTPUT_TSV, sep="\t", index=False)

    # Summary
    print(f"\n=== Final Dataset ===")
    print(f"Total works: {len(final_df)}")
    print(f"Unique authors: {final_df['author'].nunique()}")
    print(f"Unique works (by title): {final_df['title'].nunique()}")
    print(f"Total word count: {final_df['word_count'].sum():,}")

    print(f"\nAuthors included:")
    author_counts = final_df.groupby("author").size().sort_values(ascending=False)
    for author, count in author_counts.items():
        polity = final_df[final_df["author"] == author]["cliopatria_polity"].iloc[0]
        print(f"  {author}: {count} works ({polity})")

    print(f"\nSaved to {OUTPUT_TSV}")


if __name__ == "__main__":
    main()
