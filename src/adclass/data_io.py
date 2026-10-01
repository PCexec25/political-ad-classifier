"""Reading the gold set and reading/writing prediction files."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from .schema import Ad, GoldLabel, Prediction

GOLD_COLUMNS = ("ad_id", "page_name", "ad_text", "source_url", "gold_goal", "gold_issue", "notes")


def load_gold(path: str | Path) -> tuple[list[Ad], dict[str, GoldLabel]]:
    """Load and validate the hand-labeled CSV.

    Fails loudly on duplicate IDs, empty text, missing columns, or unknown
    labels, because a quietly bad gold set makes every metric meaningless.
    Rows with blank gold labels are loaded as ads but left out of the gold
    dict, so you can classify ads you haven't finished labeling.
    """
    ads: list[Ad] = []
    gold: dict[str, GoldLabel] = {}
    seen: set[str] = set()
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = set(GOLD_COLUMNS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: missing columns {sorted(missing)}")
        for line_no, row in enumerate(reader, start=2):
            ad_id = (row["ad_id"] or "").strip()
            text = (row["ad_text"] or "").strip()
            if not ad_id:
                raise ValueError(f"{path}:{line_no}: empty ad_id")
            if ad_id in seen:
                raise ValueError(f"{path}:{line_no}: duplicate ad_id {ad_id!r}")
            if not text:
                raise ValueError(f"{path}:{line_no}: empty ad_text for {ad_id!r}")
            seen.add(ad_id)
            ads.append(Ad(ad_id=ad_id, text=text, page_name=row["page_name"].strip(), source_url=row["source_url"].strip()))
            goal, issue = row["gold_goal"].strip(), row["gold_issue"].strip()
            if goal or issue:
                try:
                    gold[ad_id] = GoldLabel(ad_id=ad_id, goal=goal, issue=issue)
                except ValueError as exc:
                    raise ValueError(f"{path}:{line_no}: {exc}") from exc
    return ads, gold


def write_prediction(path: str | Path, prediction: Prediction) -> None:
    """Append one prediction as a JSON line. Appending makes long runs resumable."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(prediction)) + "\n")


def load_predictions(path: str | Path) -> dict[str, Prediction]:
    """Load a predictions JSONL file. If an ad appears twice, the last line wins."""
    path = Path(path)
    if not path.exists():
        return {}
    out: dict[str, Prediction] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                record = json.loads(line)
                out[record["ad_id"]] = Prediction(**record)
    return out
