"""
Fetch the latest available public-domain English translations (from Wikisource)
for canonical ancient Greek authors that are NOT shipped with an English file
in Perseus' canonical-greekLit.

Rules:
  * One translation per work — the latest translator that is US-PD (pre-1930).
  * Source: Wikisource only (follows fetch_copyright_english.py precedent).
  * Parallel fetching via multiprocessing.Pool(cpu_count()).
  * Euclid is deliberately excluded (user request).

Output:
  data/full_text_english_translations_not_in_perseus/tlgXXXX/tlgYYY/
      tlgXXXX.tlgYYY.perseus-eng1.txt
"""

from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass
from multiprocessing import Pool, cpu_count
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "full_text_english_translations_not_in_perseus"
CACHE_DIR = ROOT / "data" / "_fetch_cache"
OUT_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

UA = "Mozilla/5.0 HumanRightsResearch (cdedampierre@bunka.ai)"
HEADERS = {"User-Agent": UA}


# -------------------------------------------------------------------- helpers


def http_get(url: str, cache_name: str) -> str:
    cache = CACHE_DIR / cache_name
    if cache.exists() and cache.stat().st_size > 5_000:
        return cache.read_text(encoding="utf-8")
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=60)
            if r.status_code == 200 and len(r.text) > 1_000:
                cache.write_text(r.text, encoding="utf-8")
                return r.text
        except requests.RequestException:
            pass
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}")


def wikisource_plain(url: str, cache_name: str) -> str:
    html = http_get(url, cache_name)
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one("div.mw-parser-output") or soup
    for sel in [
        "div.noprint",
        "table.toc",
        "#toc",
        ".mw-editsection",
        "div.navbox",
        "sup.reference",
        ".references",
        "style",
        "script",
        ".mw-cite-backlink",
        ".thumb",
        "table.header_notes",
        ".header_container",
        ".headertemplate",
        ".sister",
        ".AuxiliaryData",
        ".wst-header",
    ]:
        for el in content.select(sel):
            el.decompose()
    text = content.get_text("\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def wikisource_multi(
    urls: list[str], cache_prefix: str, separator: str = "\n\n"
) -> str:
    """Fetch several sub-pages (e.g. book-by-book) and concat."""
    parts = []
    for i, url in enumerate(urls):
        parts.append(wikisource_plain(url, f"{cache_prefix}_{i:02d}.html"))
    return separator.join(parts)


# ------------------------------------------------- target list (tlg → source)
# TLG author codes follow the canonical Thesaurus Linguae Graecae numbering.
# For each work we record the LATEST US-public-domain English translation
# available on Wikisource, keyed by its Wikisource URL.


@dataclass
class Work:
    tlg_author: str
    tlg_work: str
    label: str  # "Author, Title (Translator YEAR)"
    url: str | list[str]  # Wikisource URL(s)
    cache: str  # cache filename stem


WORKS: list[Work] = [
    # Apollonius Rhodius, Argonautica — Seaton, Loeb 1912
    Work(
        "tlg0001",
        "tlg001",
        "Apollonius Rhodius, Argonautica (Seaton 1912)",
        [
            "https://en.wikisource.org/wiki/Argonautica/Book_1",
            "https://en.wikisource.org/wiki/Argonautica/Book_2",
            "https://en.wikisource.org/wiki/Argonautica/Book_3",
            "https://en.wikisource.org/wiki/Argonautica/Book_4",
        ],
        "apollonius_argonautica",
    ),
    # Theocritus, Idylls — Lang 1880 (prose)
    Work(
        "tlg0005",
        "tlg001",
        "Theocritus, Idylls (Lang 1880)",
        "https://en.wikisource.org/wiki/Theocritus,_Bion_and_Moschus",
        "theocritus_idylls_lang",
    ),
    # Aratus Solensis, Phaenomena — Mair, Loeb 1921
    Work(
        "tlg0653",
        "tlg001",
        "Aratus, Phaenomena (Mair 1921)",
        "https://en.wikisource.org/wiki/Phaenomena_(Aratus)",
        "aratus_phaenomena",
    ),
    # Callimachus — Hymns, Mair Loeb 1921 (one page per hymn)
    Work(
        "tlg0533",
        "tlg015",
        "Callimachus, Hymn to Zeus (Mair 1921)",
        "https://en.wikisource.org/wiki/Hymn_to_Zeus_(Callimachus)",
        "callimachus_zeus",
    ),
    Work(
        "tlg0533",
        "tlg016",
        "Callimachus, Hymn to Apollo (Mair 1921)",
        "https://en.wikisource.org/wiki/Hymn_to_Apollo_(Callimachus)",
        "callimachus_apollo",
    ),
    Work(
        "tlg0533",
        "tlg017",
        "Callimachus, Hymn to Artemis (Mair 1921)",
        "https://en.wikisource.org/wiki/Hymn_to_Artemis_(Callimachus)",
        "callimachus_artemis",
    ),
    Work(
        "tlg0533",
        "tlg018",
        "Callimachus, Hymn to Delos (Mair 1921)",
        "https://en.wikisource.org/wiki/Hymn_to_Delos_(Callimachus)",
        "callimachus_delos",
    ),
    Work(
        "tlg0533",
        "tlg019",
        "Callimachus, Hymn: The Bath of Pallas (Mair 1921)",
        "https://en.wikisource.org/wiki/Hymn_to_the_Bath_of_Pallas_(Callimachus)",
        "callimachus_pallas",
    ),
    Work(
        "tlg0533",
        "tlg020",
        "Callimachus, Hymn to Demeter (Mair 1921)",
        "https://en.wikisource.org/wiki/Hymn_to_Demeter_(Callimachus)",
        "callimachus_demeter",
    ),
    # Marcus Aurelius, Meditations — Long 1862
    Work(
        "tlg0562",
        "tlg001",
        "Marcus Aurelius, Meditations (Long 1862)",
        "https://en.wikisource.org/wiki/The_Thoughts_of_the_Emperor_Marcus_Aurelius_Antoninus",
        "marcus_aurelius_meditations",
    ),
    # Arrian, Anabasis — Chinnock 1884
    Work(
        "tlg0074",
        "tlg001",
        "Arrian, Anabasis of Alexander (Chinnock 1884)",
        "https://en.wikisource.org/wiki/The_Anabasis_of_Alexander",
        "arrian_anabasis",
    ),
    # Arrian, Indica — Chinnock 1884 (same volume)
    Work(
        "tlg0074",
        "tlg002",
        "Arrian, Indica (Chinnock 1884)",
        "https://en.wikisource.org/wiki/The_Anabasis_of_Alexander/Indica",
        "arrian_indica",
    ),
    # Julian, Works — Wright, Loeb 1913–23 (3 vols)
    Work(
        "tlg2003",
        "tlg001",
        "Julian the Emperor, Works vol. 1 (Wright 1913)",
        "https://en.wikisource.org/wiki/The_Works_of_the_Emperor_Julian/Volume_1",
        "julian_vol1",
    ),
    Work(
        "tlg2003",
        "tlg002",
        "Julian the Emperor, Works vol. 2 (Wright 1913)",
        "https://en.wikisource.org/wiki/The_Works_of_the_Emperor_Julian/Volume_2",
        "julian_vol2",
    ),
    Work(
        "tlg2003",
        "tlg003",
        "Julian the Emperor, Works vol. 3 (Wright 1923)",
        "https://en.wikisource.org/wiki/The_Works_of_the_Emperor_Julian/Volume_3",
        "julian_vol3",
    ),
    # Longus, Daphnis and Chloe — Moore 1890
    Work(
        "tlg0561",
        "tlg001",
        "Longus, Daphnis and Chloe (Moore 1890)",
        "https://en.wikisource.org/wiki/Daphnis_and_Chloe",
        "longus_daphnis",
    ),
    # Philostratus, Life of Apollonius — Conybeare, Loeb 1912
    Work(
        "tlg0638",
        "tlg001",
        "Philostratus, Life of Apollonius of Tyana (Conybeare 1912)",
        "https://en.wikisource.org/wiki/The_Life_of_Apollonius_of_Tyana",
        "philostratus_apollonius",
    ),
    # Theophrastus, Characters — Jebb 1870
    Work(
        "tlg0093",
        "tlg011",
        "Theophrastus, Characters (Jebb 1870)",
        "https://en.wikisource.org/wiki/The_Characters_of_Theophrastus",
        "theophrastus_characters",
    ),
    # Longinus, On the Sublime — Roberts 1899 (latest PD)
    Work(
        "tlg0560",
        "tlg001",
        "Longinus, On the Sublime (Roberts 1899)",
        "https://en.wikisource.org/wiki/On_the_Sublime_(Roberts)",
        "longinus_sublime_roberts",
    ),
    # Aeneas Tacticus — Hunter & Handford 1927 (Loeb)
    Work(
        "tlg0084",
        "tlg001",
        "Aeneas Tacticus, On the Defence of Fortified Positions (Hunter 1927)",
        "https://en.wikisource.org/wiki/On_the_Defence_of_Fortified_Positions",
        "aeneas_tacticus",
    ),
    # Asclepiodotus, Tactics — Oldfather Loeb 1923
    Work(
        "tlg0548",
        "tlg001",
        "Asclepiodotus, Tactics (Oldfather 1923)",
        "https://en.wikisource.org/wiki/Tactics_(Asclepiodotus)",
        "asclepiodotus_tactics",
    ),
    # Onasander, Strategikos — Oldfather Loeb 1923
    Work(
        "tlg0594",
        "tlg001",
        "Onasander, The General (Oldfather 1923)",
        "https://en.wikisource.org/wiki/The_General_(Onasander)",
        "onasander_strategikos",
    ),
    # Dionysius of Halicarnassus, Roman Antiquities — Spelman 1758
    Work(
        "tlg0081",
        "tlg001",
        "Dionysius of Halicarnassus, Roman Antiquities (Spelman 1758)",
        "https://en.wikisource.org/wiki/Roman_Antiquities",
        "dionysius_roman_ant",
    ),
    # Procopius, History of the Wars — Dewing Loeb (vols 1–3, 1914–1924 are PD)
    Work(
        "tlg4029",
        "tlg001",
        "Procopius, History of the Wars (Dewing 1914)",
        "https://en.wikisource.org/wiki/History_of_the_Wars",
        "procopius_wars",
    ),
    # Parthenius, Love Romances — Gaselee Loeb 1916
    Work(
        "tlg0655",
        "tlg001",
        "Parthenius, Love Romances (Gaselee 1916)",
        "https://en.wikisource.org/wiki/Love_Romances_(Parthenius)",
        "parthenius_love",
    ),
]


# ------------------------------------------------------- worker + save logic


def fetch_work(work: Work) -> tuple[Work, str | None, str | None]:
    """Worker — returns (work, text, error). text is None on failure."""
    try:
        if isinstance(work.url, list):
            text = wikisource_multi(work.url, work.cache)
        else:
            text = wikisource_plain(work.url, work.cache + ".html")
        if len(text) < 500:
            return (work, None, f"short output ({len(text)} chars)")
        return (work, text, None)
    except Exception as exc:
        return (work, None, str(exc))


def save(work: Work, text: str) -> Path:
    urn = f"{work.tlg_author}.{work.tlg_work}.perseus-eng1"
    out = OUT_DIR / work.tlg_author / work.tlg_work / f"{urn}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    header = (
        f"# {work.label}\n"
        f"# URN: urn:cts:greekLit:{urn}\n"
        f"# Source: English Wikisource, public-domain edition (US PD, pre-1930).\n"
        f"# Fetched for non-redistributive research use.\n\n"
    )
    out.write_text(header + text + "\n", encoding="utf-8")
    return out


def main() -> int:
    n_proc = min(cpu_count(), len(WORKS))
    print(f"Fetching {len(WORKS)} works on {n_proc} processes...")
    results: list[tuple[Work, str | None, str | None]] = []

    with Pool(processes=n_proc) as pool:
        for res in tqdm(
            pool.imap_unordered(fetch_work, WORKS), total=len(WORKS), desc="Wikisource"
        ):
            results.append(res)

    # Save + tally in the parent, serial (cheap)
    ok, fail = 0, []
    for work, text, err in results:
        if text is None:
            fail.append((work.label, err))
        else:
            save(work, text)
            ok += 1

    print()
    print(f"Output: {OUT_DIR}")
    print(f"Fetched: {ok} / {len(WORKS)}")
    if fail:
        print("Failures:")
        for lab, err in fail:
            print(f"  - {lab}: {err}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
