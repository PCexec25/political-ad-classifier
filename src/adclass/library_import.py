"""Convert text copied from the Meta Ad Library website into gold-set rows.

Workflow: run a search on facebook.com/ads/library, select the results
page, copy, paste into a .txt file, then run

    adclass import-library --raw chip_in.txt --search "chip in"

Each ad card in the pasted text looks like:

    Library ID: 712330514526004
    Started running on May 12, 2025
    ...metadata...
    Page Name
    Page Name
    Sponsored • Paid for by Committee Name
    <body text, possibly several paragraphs>
    0:00 / 0:27              <- video timer, or
    SECURE.ACTBLUE.COM       <- link domain, or
    NOT AFFILIATED WITH META <- disclaimer, or
    ​                   <- zero-width separator before the next card

The body is everything between the "Sponsored" line and the first of
those terminators. The link headline and button text after the domain are
deliberately excluded: the codebook labels the body copy only.

Cleaning rules, all logged so nothing disappears silently:
- ads with no body text (video- or image-only) are skipped;
- exact and near-duplicate bodies (word-set Jaccard >= 0.75) are skipped,
  across this batch and the existing gold file;
- at most `max_per_page` ads per page across the whole gold file.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from .data_io import GOLD_COLUMNS

EXTRA_COLUMNS = ("search_term", "paid_for", "started_running")
ALL_COLUMNS = GOLD_COLUMNS + EXTRA_COLUMNS

_LIBRARY_ID = re.compile(r"^Library ID:\s*(\d+)\s*$")
_STARTED = re.compile(r"^Started running on (.+)$")
_SPONSORED = re.compile(r"^Sponsored\s*•\s*Paid for by\s+(.+)$")
_VIDEO_TIMER = re.compile(r"^\d{1,2}:\d{2}\s*/\s*\d{1,2}:\d{2}$")
_DOMAIN = re.compile(r"^[A-Z0-9-]+(\.[A-Z0-9-]+)+$")
_ZERO_WIDTH = "​"
NEAR_DUP_THRESHOLD = 0.75


@dataclass
class ParsedAd:
    library_id: str
    page_name: str
    paid_for: str
    started_running: str
    text: str


@dataclass
class ImportResult:
    added: list[ParsedAd] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (library_id, reason)


def normalize_text(text: str) -> str:
    """NFKC folds 'bold' Unicode letters (𝐓𝐡𝐢𝐬) to plain ASCII; also trims each line."""
    text = unicodedata.normalize("NFKC", text).replace(_ZERO_WIDTH, "")
    lines = [line.rstrip() for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _is_terminator(line: str) -> bool:
    s = line.strip()
    return (
        s == _ZERO_WIDTH
        or bool(_VIDEO_TIMER.match(s))
        or bool(_DOMAIN.match(s))
        or s == "NOT AFFILIATED WITH META"
        or s.startswith("Impressions:")
        # "Active" opens the next card. Pasting through some apps strips the
        # zero-width separator, so this is the fallback end-of-body marker.
        or s == "Active"
    )


def parse_library_text(raw: str) -> list[ParsedAd]:
    lines = raw.splitlines()
    starts = [i for i, line in enumerate(lines) if _LIBRARY_ID.match(line.strip())]
    ads = []
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        block = lines[start:end]
        library_id = _LIBRARY_ID.match(block[0].strip()).group(1)
        started = next((m.group(1).strip() for line in block if (m := _STARTED.match(line.strip()))), "")
        sponsored_at = next((i for i, line in enumerate(block) if _SPONSORED.match(line.strip())), None)
        if sponsored_at is None:
            ads.append(ParsedAd(library_id, "", "", started, ""))
            continue
        paid_for = _SPONSORED.match(block[sponsored_at].strip()).group(1).strip()
        page_name = block[sponsored_at - 1].strip() if sponsored_at > 0 else ""
        body = []
        for line in block[sponsored_at + 1 :]:
            if _is_terminator(line):
                break
            body.append(line)
        ads.append(ParsedAd(library_id, page_name, paid_for, started, normalize_text("\n".join(body))))
    return ads


def _word_set(text: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z0-9$']+", text.lower()))


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    return len(a & b) / len(a | b) if a | b else 1.0


def read_gold_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def import_into_gold(raw: str, gold_path: str | Path, search_term: str, max_per_page: int = 4) -> ImportResult:
    """Parse, clean, and append new ads to the gold CSV. Existing rows and labels are untouched."""
    gold_path = Path(gold_path)
    existing = read_gold_rows(gold_path)
    seen_ids = {r["ad_id"] for r in existing}
    seen_texts = [_word_set(r["ad_text"]) for r in existing]
    page_counts: dict[str, int] = {}
    for r in existing:
        page_counts[r["page_name"]] = page_counts.get(r["page_name"], 0) + 1

    result = ImportResult()
    for ad in parse_library_text(raw):
        if ad.library_id in seen_ids:
            result.skipped.append((ad.library_id, "already in gold file"))
            continue
        if not ad.text:
            result.skipped.append((ad.library_id, f"no body text ({ad.page_name or 'unknown page'})"))
            continue
        words = _word_set(ad.text)
        if any(_jaccard(words, other) >= NEAR_DUP_THRESHOLD for other in seen_texts):
            result.skipped.append((ad.library_id, f"duplicate text ({ad.page_name})"))
            continue
        if page_counts.get(ad.page_name, 0) >= max_per_page:
            result.skipped.append((ad.library_id, f"page cap of {max_per_page} reached ({ad.page_name})"))
            continue
        seen_ids.add(ad.library_id)
        seen_texts.append(words)
        page_counts[ad.page_name] = page_counts.get(ad.page_name, 0) + 1
        result.added.append(ad)

    new_rows = [
        {
            "ad_id": ad.library_id,
            "page_name": ad.page_name,
            "ad_text": ad.text,
            "source_url": f"https://www.facebook.com/ads/library/?id={ad.library_id}",
            "gold_goal": "",
            "gold_issue": "",
            "notes": "",
            "search_term": search_term,
            "paid_for": ad.paid_for,
            "started_running": ad.started_running,
        }
        for ad in result.added
    ]
    gold_path.parent.mkdir(parents=True, exist_ok=True)
    with open(gold_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(ALL_COLUMNS), extrasaction="ignore")
        writer.writeheader()
        for row in existing + new_rows:
            writer.writerow({col: row.get(col, "") for col in ALL_COLUMNS})
    return result
