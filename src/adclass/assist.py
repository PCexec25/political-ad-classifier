"""Model-assisted labeling with a blind holdout.

Pre-filled suggestions make labeling faster, but a human checking a
suggestion agrees with it more often than they would have labeled the
same way from scratch (anchoring). Left unmeasured, that bias flows into
every score computed against the gold set. So:

- A seeded random subset of ads is BLIND: no suggestion is shown, and the
  human labels from scratch. These ads are the clean benchmark.
- The rest are ASSISTED: the keyword-rule baseline's labels are pre-filled,
  and count as gold only after the human marks the row checked.
- The suggestions are stored in gold.csv (not just the workbook), so the
  override rate and the anchoring gap can be computed afterwards.
"""

from __future__ import annotations

import csv
import random
from pathlib import Path

from .baseline import classify_text
from .library_import import ALL_COLUMNS, read_gold_rows

BLIND, ASSISTED = "blind", "assisted"


def assign_assist(gold_path: str | Path, n_blind: int = 40, seed: int = 2026) -> dict[str, int]:
    """Mark each ad blind or assisted and store suggestions for assisted ads.

    Idempotent: ads that already have a mode keep it, so re-running after
    importing new ads only assigns the new ones (new ads become assisted;
    the blind set is fixed once drawn, so it stays a clean random sample).
    """
    gold_path = Path(gold_path)
    rows = read_gold_rows(gold_path)
    if any(r.get("label_mode") for r in rows):
        blind_ids = {r["ad_id"] for r in rows if r.get("label_mode") == BLIND}
    else:
        ids = sorted(r["ad_id"] for r in rows)
        if n_blind > len(ids):
            raise ValueError(f"n_blind={n_blind} exceeds the {len(ids)} ads in {gold_path}")
        blind_ids = set(random.Random(seed).sample(ids, n_blind))

    for r in rows:
        if r.get("label_mode"):
            continue
        if r["ad_id"] in blind_ids:
            r.update(label_mode=BLIND, suggested_goal="", suggested_issue="", suggestion_reason="")
        else:
            s = classify_text(r["ad_text"])
            r.update(label_mode=ASSISTED, suggested_goal=s.goal, suggested_issue=s.issue, suggestion_reason=s.reason)

    with open(gold_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(ALL_COLUMNS), extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({c: r.get(c, "") for c in ALL_COLUMNS})
    return {
        "ads": len(rows),
        "blind": sum(r["label_mode"] == BLIND for r in rows),
        "assisted": sum(r["label_mode"] == ASSISTED for r in rows),
    }
