"""
Extract metadata and full text from Perseus canonical-greekLit XML files.
"""

import os
import csv
import re
from pathlib import Path
from xml.etree import ElementTree as ET
from tqdm import tqdm

# Paths
REPO_PATH = Path("canonical-greekLit/data")
OUTPUT_DIR = Path("full_text")
METADATA_CSV = Path("perseus_metadata.csv")

# TEI namespace
NS = {"tei": "http://www.tei-c.org/ns/1.0", "": "http://www.tei-c.org/ns/1.0"}


def get_text_content(elem):
    """Extract all text content from an element, including nested elements."""
    if elem is None:
        return ""
    return "".join(elem.itertext()).strip()


def clean_text(text):
    """Clean extracted text."""
    if not text:
        return ""
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_metadata(tree, root):
    """Extract metadata from TEI header."""
    metadata = {}

    # Try with namespace first, then without
    def find(path):
        # Try with tei namespace
        elem = root.find(f".//{{{NS['tei']}}}{path}")
        if elem is None:
            # Try without namespace
            elem = root.find(f".//{path}")
        if elem is None:
            # Try with tei: prefix
            elem = root.find(f".//tei:{path}", NS)
        return elem

    def find_all(path):
        elems = root.findall(f".//{{{NS['tei']}}}{path}")
        if not elems:
            elems = root.findall(f".//{path}")
        if not elems:
            elems = root.findall(f".//tei:{path}", NS)
        return elems

    # Title
    title_elem = find("title")
    metadata["title"] = get_text_content(title_elem) if title_elem is not None else ""

    # Author
    author_elem = find("author")
    metadata["author"] = (
        get_text_content(author_elem) if author_elem is not None else ""
    )

    # Editor(s)
    editors = find_all("editor")
    metadata["editors"] = "; ".join(
        [get_text_content(e) for e in editors if get_text_content(e)]
    )

    # Publisher
    publisher_elem = find("publisher")
    metadata["publisher"] = (
        get_text_content(publisher_elem) if publisher_elem is not None else ""
    )

    # Publication place
    pubplace_elem = find("pubPlace")
    metadata["pub_place"] = (
        get_text_content(pubplace_elem) if pubplace_elem is not None else ""
    )

    # Publication date
    date_elem = find("date")
    metadata["pub_date"] = get_text_content(date_elem) if date_elem is not None else ""

    # Source description - try to get original publication info
    bibl_elem = find("bibl")
    metadata["source_bibl"] = (
        get_text_content(bibl_elem) if bibl_elem is not None else ""
    )

    # Language
    lang_elems = find_all("language")
    languages = []
    for lang in lang_elems:
        ident = lang.get("ident", "")
        if ident:
            languages.append(ident)
    metadata["languages"] = "; ".join(languages)

    # Extent
    extent_elem = find("extent")
    metadata["extent"] = (
        get_text_content(extent_elem) if extent_elem is not None else ""
    )

    # Funder
    funder_elem = find("funder")
    metadata["funder"] = (
        get_text_content(funder_elem) if funder_elem is not None else ""
    )

    # Principal investigator
    principal_elem = find("principal")
    metadata["principal"] = (
        get_text_content(principal_elem) if principal_elem is not None else ""
    )

    return metadata


def extract_body_text(root):
    """Extract the main text content from TEI body."""
    # Try different paths to find body text
    body = None

    # Try with namespace
    body = root.find(f".//{{{NS['tei']}}}body")
    if body is None:
        body = root.find(".//body")
    if body is None:
        body = root.find(".//tei:body", NS)

    if body is None:
        # Try to get text from root
        return get_text_content(root)

    return get_text_content(body)


def process_xml_file(xml_path):
    """Process a single XML file and extract metadata and text."""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Extract metadata
        metadata = extract_metadata(tree, root)

        # Extract text
        text = extract_body_text(root)

        # Get file info
        rel_path = xml_path.relative_to(REPO_PATH)
        parts = rel_path.parts

        metadata["file_path"] = str(rel_path)
        metadata["author_code"] = parts[0] if len(parts) > 0 else ""
        metadata["work_code"] = parts[1] if len(parts) > 1 else ""
        metadata["filename"] = xml_path.name
        metadata["text_length"] = len(text)
        metadata["word_count"] = len(text.split()) if text else 0

        return metadata, text

    except ET.ParseError as e:
        print(f"XML parse error in {xml_path}: {e}")
        return None, None
    except Exception as e:
        print(f"Error processing {xml_path}: {e}")
        return None, None


def main():
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Find all XML files (excluding __cts__.xml metadata files)
    xml_files = [
        f for f in REPO_PATH.rglob("*.xml") if not f.name.startswith("__cts__")
    ]

    print(f"Found {len(xml_files)} XML files to process")

    all_metadata = []

    for xml_path in tqdm(xml_files, desc="Extracting"):
        metadata, text = process_xml_file(xml_path)

        if metadata is None:
            continue

        all_metadata.append(metadata)

        # Save text to file
        if text:
            # Create subdirectory structure
            text_subdir = OUTPUT_DIR / metadata["author_code"] / metadata["work_code"]
            text_subdir.mkdir(parents=True, exist_ok=True)

            # Save text file
            text_filename = xml_path.stem + ".txt"
            text_path = text_subdir / text_filename

            with open(text_path, "w", encoding="utf-8") as f:
                f.write(text)

    # Save metadata CSV
    if all_metadata:
        fieldnames = [
            "author_code",
            "work_code",
            "filename",
            "file_path",
            "title",
            "author",
            "editors",
            "publisher",
            "pub_place",
            "pub_date",
            "source_bibl",
            "languages",
            "extent",
            "funder",
            "principal",
            "text_length",
            "word_count",
        ]

        with open(METADATA_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_metadata)

        print(f"\nSaved metadata to {METADATA_CSV}")
        print(f"Saved {len(all_metadata)} text files to {OUTPUT_DIR}/")

        # Summary stats
        total_words = sum(m["word_count"] for m in all_metadata)
        print(f"\nTotal word count: {total_words:,}")
        print(f"Unique authors: {len(set(m['author_code'] for m in all_metadata))}")
        print(
            f"Unique works: {len(set((m['author_code'], m['work_code']) for m in all_metadata))}"
        )


if __name__ == "__main__":
    main()
