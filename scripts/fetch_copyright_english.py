"""
Fetch public-domain English translations for the Perseus works whose
English editions were flagged 'not migrated' in canonical-greekLit
(src under .../copyright/).

Sources: Wikisource (Kenyon 1921, Adams 1849) and Project Gutenberg
(Athenian Society 1912, Dakyns 1897). All translators died before 1955
and the editions are pre-1928 → PD in the US.

Output mirrors the existing extracted layout:
  data/full_text_copyrights_added/tlgXXXX/tlgYYY/tlgXXXX.tlgYYY.perseus-engN.txt

Aristotle, On Virtues and Vices (tlg0086.tlg045) is skipped: the only
English translations readily available online are Rackham 1935 (Loeb,
still in US copyright) and Solomon 1915 (Oxford vol IX, not digitised
in a clean PD source we could locate). See README in the output dir.
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "full_text_copyrights_added"
CACHE_DIR = ROOT / "data" / "_fetch_cache"
OUT_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

UA = "Mozilla/5.0 HumanRightsResearch (cdedampierre@bunka.ai)"
HEADERS = {"User-Agent": UA}


def fetch(url: str, cache_name: str) -> str:
    cache = CACHE_DIR / cache_name
    if cache.exists() and cache.stat().st_size > 5_000:
        return cache.read_text(encoding="utf-8")
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=60)
            if r.status_code == 200 and len(r.text) > 5_000:
                cache.write_text(r.text, encoding="utf-8")
                return r.text
        except requests.RequestException:
            pass
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}")


def strip_gutenberg(text: str) -> str:
    s = re.search(
        r"\*\*\*\s*START OF (?:THE |THIS )?PROJECT GUTENBERG[^\n]*\*\*\*", text
    )
    e = re.search(r"\*\*\*\s*END OF (?:THE |THIS )?PROJECT GUTENBERG[^\n]*\*\*\*", text)
    start = s.end() if s else 0
    end = e.start() if e else len(text)
    return text[start:end].strip()


def extract_between_titles(text: str, title: str, next_title: str | None) -> str:
    """
    Gutenberg 'Eleven Comedies' repeats each play title — once in the TOC,
    once at the play's actual start. Take the *second* occurrence and slice
    until the next play's second occurrence (or the following play's
    INTRODUCTION heading).
    """
    occs = [m.start() for m in re.finditer(rf"(?m)^{re.escape(title)}\s*$", text)]
    if len(occs) < 2:
        raise ValueError(f"expected >=2 occurrences of {title!r}, got {len(occs)}")
    start = occs[1]

    if next_title:
        next_occs = [
            m.start() for m in re.finditer(rf"(?m)^{re.escape(next_title)}\s*$", text)
        ]
        next_occs = [o for o in next_occs if o > start]
        if not next_occs:
            raise ValueError(
                f"no occurrence of next title {next_title!r} after {title!r}"
            )
        end = next_occs[0]
    else:
        end = len(text)

    return text[start:end].strip()


def extract_polity_athenians(text: str) -> str:
    """Dakyns vol has Athens part first, then Sparta. Take Athens only."""
    athens_marker = "THE POLITY OF THE ATHENIANS"
    sparta_marker = "THE POLITY OF THE LACEDAEMONIANS"
    occs = [
        m.start() for m in re.finditer(rf"(?m)^{re.escape(athens_marker)}\s*$", text)
    ]
    if len(occs) < 2:
        occs = [m.start() for m in re.finditer(re.escape(athens_marker), text)]
    start = occs[-1] if len(occs) > 1 else occs[0]
    end_match = re.search(rf"(?m)^{re.escape(sparta_marker)}\s*$", text)
    end = end_match.start() if end_match else len(text)
    return text[start:end].strip()


def wikisource_plain(url: str, cache_name: str) -> str:
    html = fetch(url, cache_name)
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
    ]:
        for el in content.select(sel):
            el.decompose()
    text = content.get_text("\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# Aristophanes play order inside each Gutenberg volume, with the title strings
# to split on. We skip Clouds (vol 1) and Birds (vol 2) — not in target list.
VOL1_ORDER = ["THE KNIGHTS", "THE ACHARNIANS", "PEACE", "LYSISTRATA", "THE CLOUDS"]
VOL2_ORDER = [
    "THE WASPS",
    "THE BIRDS",
    "THE FROGS",
    "THE THESMOPHORIAZUSAE",
    "THE ECCLESIAZUSAE",
    "PLUTUS",
]


def next_in(order: list[str], title: str) -> str | None:
    i = order.index(title)
    return order[i + 1] if i + 1 < len(order) else None


# One row per target work
WORKS: list[dict] = [
    # Aristotle — Athenian Constitution (Kenyon 1921, revised)
    {
        "urn": "tlg0086.tlg003.perseus-eng1",
        "tlg_author": "tlg0086",
        "tlg_work": "tlg003",
        "label": "Aristotle, Athenian Constitution (Kenyon 1921)",
        "fetch": lambda: wikisource_plain(
            "https://en.wikisource.org/wiki/Athenian_Constitution",
            "ws_athenian_constitution.html",
        ),
    },
    # Hippocrates — Oath (Adams 1849)
    {
        "urn": "tlg0627.tlg013.perseus-eng3",
        "tlg_author": "tlg0627",
        "tlg_work": "tlg013",
        "label": "Hippocrates, Oath (Adams 1849)",
        "fetch": lambda: wikisource_plain(
            "https://en.wikisource.org/wiki/Oath_of_Hippocrates",
            "ws_oath_hippocrates.html",
        ),
    },
    # Pseudo-Xenophon — Constitution of the Athenians (Dakyns)
    {
        "urn": "tlg0032.tlg015.perseus-eng1",
        "tlg_author": "tlg0032",
        "tlg_work": "tlg015",
        "label": "Pseudo-Xenophon, Constitution of the Athenians (Dakyns 1897)",
        "fetch": lambda: extract_polity_athenians(
            strip_gutenberg(
                fetch("https://www.gutenberg.org/ebooks/1178.txt.utf-8", "pg1178.txt")
            )
        ),
    },
]

# Aristophanes plays — 9 of 11, drawn from vol 1 (pg8688) and vol 2 (pg8689)
ARISTOPHANES = [
    ("tlg001", "Acharnians", 1, "THE ACHARNIANS"),
    ("tlg002", "Knights", 1, "THE KNIGHTS"),
    ("tlg004", "Wasps", 2, "THE WASPS"),
    ("tlg005", "Peace", 1, "PEACE"),
    ("tlg007", "Lysistrata", 1, "LYSISTRATA"),
    ("tlg008", "Thesmophoriazusae", 2, "THE THESMOPHORIAZUSAE"),
    ("tlg009", "Frogs", 2, "THE FROGS"),
    ("tlg010", "Ecclesiazusae", 2, "THE ECCLESIAZUSAE"),
    ("tlg011", "Plutus", 2, "PLUTUS"),
]


def _make_aristophanes_fetcher(vol: int, title: str):
    def _f():
        if vol == 1:
            raw = fetch("https://www.gutenberg.org/ebooks/8688.txt.utf-8", "pg8688.txt")
            order = VOL1_ORDER
        else:
            raw = fetch("https://www.gutenberg.org/ebooks/8689.txt.utf-8", "pg8689.txt")
            order = VOL2_ORDER
        body = strip_gutenberg(raw)
        return extract_between_titles(body, title, next_in(order, title))

    return _f


for tlg_work, pretty, vol, title in ARISTOPHANES:
    WORKS.append(
        {
            "urn": f"tlg0019.{tlg_work}.perseus-eng1",
            "tlg_author": "tlg0019",
            "tlg_work": tlg_work,
            "label": f"Aristophanes, {pretty} (Athenian Society 1912)",
            "fetch": _make_aristophanes_fetcher(vol, title),
        }
    )


# Aristotle, On Virtues and Vices — no clean PD source located.
SKIPPED = [
    {
        "urn": "tlg0086.tlg045.perseus-eng1",
        "label": "Aristotle, On Virtues and Vices",
        "reason": (
            "Only online English translations are Rackham 1935 (Loeb, "
            "still in US copyright until 2031) and Solomon 1915 "
            "(Oxford Works of Aristotle vol IX, not located in a "
            "clean PD digitisation)."
        ),
    },
]


def save(work: dict, text: str) -> Path:
    out = OUT_DIR / work["tlg_author"] / work["tlg_work"] / f"{work['urn']}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    header = (
        f"# {work['label']}\n"
        f"# URN: urn:cts:greekLit:{work['urn']}\n"
        f"# Source: public-domain edition fetched via Wikisource or Project Gutenberg.\n"
        f"# Fetched for research use only — not redistributable under the CC-BY-SA\n"
        f"# licence of canonical-greekLit (these were originally flagged\n"
        f"# 'copyright/' by Perseus and never migrated).\n\n"
    )
    out.write_text(header + text + "\n", encoding="utf-8")
    return out


def main() -> int:
    errors: list[tuple[str, str]] = []

    pbar = tqdm(WORKS, desc="Fetching", unit="work")
    for w in pbar:
        pbar.set_postfix_str(w["urn"])
        try:
            text = w["fetch"]()
            if len(text) < 500:
                raise ValueError(f"suspiciously short output ({len(text)} chars)")
            save(w, text)
        except Exception as exc:
            errors.append((w["urn"], str(exc)))

    # Write a skip note for V&V
    for s in SKIPPED:
        urn = s["urn"]
        author, work_id = urn.split(".")[0], urn.split(".")[1]
        out = OUT_DIR / author / work_id / f"{urn}.SKIPPED.txt"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            f"# {s['label']}\n# URN: urn:cts:greekLit:{urn}\n\n"
            f"SKIPPED — no clean public-domain English source located.\n\n"
            f"Reason: {s['reason']}\n",
            encoding="utf-8",
        )

    print()
    print(f"Output dir: {OUT_DIR}")
    print(f"Fetched:    {len(WORKS) - len(errors)} / {len(WORKS)}")
    print(f"Skipped:    {len(SKIPPED)} (documented)")
    if errors:
        print("Errors:")
        for urn, msg in errors:
            print(f"  {urn}: {msg}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
