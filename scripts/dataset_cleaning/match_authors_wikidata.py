"""
Match Perseus authors with Wikidata entries from humans_clean.sqlite3
Extract cliopatria polity, impact date, wikidata ID, wikipedia URL, occupation
Uses multiprocessing for speed.
"""

import sqlite3
import pandas as pd
from multiprocessing import Pool, cpu_count
from tqdm import tqdm

# Paths
PERSEUS_METADATA = "perseus_metadata.tsv"
DB_PATH = "/Users/charlesdedampierre/Desktop/Rsearch Folder/cultura_database/data/humans_clean.sqlite3"
OUTPUT_TSV = "perseus_authors_wikidata.tsv"

# Author name mappings for better matching
AUTHOR_MAPPINGS = {
    "Apollonius Rhodius": "Apollonius of Rhodes",
    "Appian of Alexandria": "Appian",
    "Aratus Solensis": "Aratus",
    "Aretaeus of Cappadocia": "Aretaeus of Cappadocia",
    "Basil, Saint, Bishop of Caesarea": "Basil of Caesarea",
    "Bion of Phlossa": "Bion of Smyrna",
    "Cassius Dio Cocceianus": "Cassius Dio",
    "Clement of Rome": "Pope Clement I",
    "Claudius Ptolemy": "Ptolemy",
    "Dio Chrysostom": "Dio Chrysostom",
    "Diogenes Laertius": "Diogenes Laërtius",
    "Eusebius of Caesarea": "Eusebius of Caesarea",
    "Flavius Josephus": "Josephus",
    "Harpocration, Valerius": "Valerius Harpocration",
    "Ignatius of Antioch": "Ignatius of Antioch",
    "Joannes Zonaras": "John Zonaras",
    "John of Damascus": "John of Damascus",
    "Julian the Emperor": "Julian",
    "Lucian of Samosata": "Lucian of Samosata",
    "Lucian of Samosota": "Lucian of Samosata",
    "Marcus Aurelius": "Marcus Aurelius",
    "Nonnus of Panopolis": "Nonnus",
    "Oppian of Apamea": "Oppian",
    "Philostratus Minor": "Philostratus the Younger",
    "Philostratus Sophista": "Philostratus the Athenian",
    "Philostratus the Athenian": "Philostratus the Athenian",
    "Pseudo-Lucian": "Lucian of Samosata",
    "Pseudo-Plutarch": "Plutarch",
    "Quintus Smyrnaeus": "Quintus Smyrnaeus",
    "Xenophon of Ephesus": "Xenophon of Ephesus",
}

# Authors to skip (not individual persons)
SKIP_AUTHORS = {"Anonymous", "New Testament", "Old Testament"}

# Ancient author occupation keywords (must have at least one)
ANCIENT_OCCUPATIONS = [
    "philosopher",
    "historian",
    "poet",
    "playwright",
    "orator",
    "mathematician",
    "physician",
    "geographer",
    "astronomer",
    "tragedian",
    "comedian",
    "rhetorician",
    "biographer",
    "theologian",
    "bishop",
    "writer",
    "sophist",
    "lyric poet",
    "epic poet",
    "dramatist",
    "satirist",
    "grammarian",
    "encyclopedist",
    "natural philosopher",
    "political philosopher",
]

# Keywords that indicate ancient Greek/Roman context
ANCIENT_CONTEXT = [
    "ancient greek",
    "greek philosopher",
    "greek historian",
    "greek poet",
    "roman",
    "athenian",
    "spartan",
    "bc",
    "bce",
    "1st century",
    "2nd century",
    "3rd century",
    "4th century",
    "5th century",
    "hellenistic",
    "classical",
    "stoic",
    "epicurean",
    "peripatetic",
    "neoplatonist",
    "platonic",
    "church father",
]


def score_match(name, description, occupations, birthdate, search_name):
    """Score how well a match fits an ancient Greek author."""
    score = 0
    text = f"{description or ''} {occupations or ''}".lower()
    name_lower = name.lower()
    search_lower = search_name.lower()

    # Exact name match is huge
    if name_lower == search_lower:
        score += 100

    # Check for ancient context in description
    for ctx in ANCIENT_CONTEXT:
        if ctx in text:
            score += 20

    # Check for relevant occupation
    for occ in ANCIENT_OCCUPATIONS:
        if occ in text:
            score += 10

    # Check birthdate is ancient (before 600 CE)
    if birthdate:
        try:
            year = None
            if birthdate.startswith("-"):
                parts = birthdate.split("-")
                if len(parts) >= 2 and parts[1]:
                    year = -int(parts[1])
            elif birthdate[0].isdigit():
                year = int(birthdate.split("-")[0])

            if year is not None:
                if year < -500:  # Very ancient
                    score += 50
                elif year < 0:  # BC
                    score += 40
                elif year < 200:  # Early CE
                    score += 30
                elif year < 600:  # Late antiquity
                    score += 20
                else:  # Medieval or later - probably wrong
                    score -= 50
        except:
            pass

    # Penalize if description suggests wrong period
    if "byzantine" in text and "ancient" not in text:
        score -= 20
    if "medieval" in text:
        score -= 30
    if "modern" in text:
        score -= 50

    return score


def process_author(author):
    """Process a single author - runs in separate process."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    search_name = AUTHOR_MAPPINGS.get(author, author)

    # Search in individuals table - exact match first
    cursor.execute(
        """
        SELECT i.wikidata_id, i.name_en, i.description_en, i.occupations_en,
               i.birthdate, i.deathdate
        FROM individuals i
        WHERE LOWER(i.name_en) = LOWER(?)
    """,
        (search_name,),
    )
    matches = cursor.fetchall()

    # If no exact match, try LIKE
    if not matches:
        cursor.execute(
            """
            SELECT i.wikidata_id, i.name_en, i.description_en, i.occupations_en,
                   i.birthdate, i.deathdate
            FROM individuals i
            WHERE LOWER(i.name_en) LIKE LOWER(?)
            LIMIT 100
        """,
            (f"%{search_name}%",),
        )
        matches = cursor.fetchall()

    result = None

    if matches:
        # Score all matches and pick the best
        scored_matches = []
        for match in matches:
            wikidata_id, name, desc, occupations, birthdate, deathdate = match
            score = score_match(name, desc, occupations, birthdate, search_name)
            if score > 0:  # Only consider positive scores
                scored_matches.append((score, match))

        if scored_matches:
            # Sort by score descending
            scored_matches.sort(key=lambda x: x[0], reverse=True)
            best_score, best = scored_matches[0]

            wikidata_id, name, desc, occupations, birthdate, deathdate = best

            # Get cliopatria polity
            cursor.execute(
                """
                SELECT polity_name, polity_id, impact_date
                FROM individuals_cliopatria
                WHERE wikidata_id = ?
            """,
                (wikidata_id,),
            )
            polity_result = cursor.fetchone()
            polity_name = polity_result[0] if polity_result else None
            polity_id = polity_result[1] if polity_result else None
            impact_date_clio = polity_result[2] if polity_result else None

            # Get impact date from individuals_impact_date
            cursor.execute(
                """
                SELECT impact_date, precision_name
                FROM individuals_impact_date
                WHERE wikidata_id = ?
            """,
                (wikidata_id,),
            )
            impact_result = cursor.fetchone()
            impact_date = impact_result[0] if impact_result else impact_date_clio
            impact_precision = impact_result[1] if impact_result else None

            # Get Wikipedia URL
            cursor.execute(
                """
                SELECT url
                FROM sitelinks
                WHERE wikidata_id = ? AND site = 'enwiki'
            """,
                (wikidata_id,),
            )
            wiki_result = cursor.fetchone()
            wikipedia_url = wiki_result[0] if wiki_result else None

            result = {
                "perseus_author": author,
                "wikidata_id": wikidata_id,
                "wikidata_name": name,
                "description": desc,
                "occupations": occupations,
                "cliopatria_polity": polity_name,
                "cliopatria_polity_id": polity_id,
                "birthdate": birthdate,
                "deathdate": deathdate,
                "impact_date": impact_date,
                "impact_date_precision": impact_precision,
                "wikipedia_url": wikipedia_url,
                "match_score": best_score,
            }

    conn.close()
    return (author, result)


def main():
    # Load Perseus metadata
    df = pd.read_csv(PERSEUS_METADATA, sep="\t")
    authors = df["author"].dropna().unique()
    authors = [a for a in authors if a not in SKIP_AUTHORS]

    print(f"Searching for {len(authors)} authors using {cpu_count()} CPUs...")

    # Use multiprocessing
    with Pool(processes=cpu_count()) as pool:
        results_list = list(
            tqdm(
                pool.imap(process_author, authors),
                total=len(authors),
                desc="Matching authors",
            )
        )

    # Separate found and not found
    results = []
    not_found = []

    for author, result in results_list:
        if result:
            results.append(result)
        else:
            not_found.append(author)

    # Save results
    results_df = pd.DataFrame(results)
    results_df.to_csv(OUTPUT_TSV, sep="\t", index=False)

    print(f"\nFound {len(results)} authors")
    print(f"Not found: {len(not_found)}")
    if not_found:
        print("Missing authors:")
        for a in not_found:
            print(f"  - {a}")

    print(f"\nSaved to {OUTPUT_TSV}")


if __name__ == "__main__":
    main()
