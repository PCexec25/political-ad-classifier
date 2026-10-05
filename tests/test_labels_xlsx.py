"""Round trip: build a labeling workbook from gold.csv, fill labels, import them back."""

import csv
import shutil
from pathlib import Path

import pytest
from openpyxl import Workbook

from adclass.data_io import load_gold
from adclass.labels_xlsx import import_labels
from adclass.library_import import import_into_gold

RAW = (Path(__file__).parent / "fixtures" / "library_paste.txt").read_text(encoding="utf-8")


def make_gold(tmp_path):
    gold = tmp_path / "gold.csv"
    import_into_gold(RAW, gold, search_term="x")  # ads 111, 444, 555
    return gold


def make_xlsx(tmp_path, rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "Label"
    ws.append(["#", "ad_id", "ad_text", "gold_goal", "gold_issue", "notes", "page_name"])
    for i, r in enumerate(rows, start=1):
        ws.append([i, *r])
    path = tmp_path / "labels.xlsx"
    wb.save(path)
    return path


def test_labels_flow_back_and_text_comes_from_gold(tmp_path):
    gold = make_gold(tmp_path)
    xlsx = make_xlsx(tmp_path, [
        ("111", "EDITED IN EXCEL", "fundraising", "other", "rule 1", "P"),
        ("444", "x", None, None, None, "P"),
        ("555", "x", None, None, None, "P"),
    ])
    stats = import_labels(xlsx, gold)
    assert (stats["ads"], stats["labeled"]) == (3, 1)
    ads, labels = load_gold(gold)
    assert labels["111"].goal == "fundraising"
    assert "EDITED" not in ads[0].text  # ad text is never taken from the workbook
    with open(gold, newline="", encoding="utf-8") as f:
        assert next(csv.DictReader(f))["notes"] == "rule 1"


def test_invalid_or_half_labels_leave_gold_untouched(tmp_path):
    gold = make_gold(tmp_path)
    before = gold.read_text(encoding="utf-8")
    for bad in [("111", "t", "fundraising", None, None, "P"), ("111", "t", "Fundraising", "other", None, "P")]:
        xlsx = make_xlsx(tmp_path, [bad, ("444", "t", None, None, None, "P"), ("555", "t", None, None, None, "P")])
        with pytest.raises(ValueError):
            import_labels(xlsx, gold)
        assert gold.read_text(encoding="utf-8") == before
        assert not gold.with_suffix(".tmp").exists()


def test_missing_ads_rejected(tmp_path):
    gold = make_gold(tmp_path)
    xlsx = make_xlsx(tmp_path, [("111", "t", None, None, None, "P")])
    with pytest.raises(ValueError, match="different ads"):
        import_labels(xlsx, gold)


def test_assisted_rows_count_only_when_checked(tmp_path):
    from adclass.assist import assign_assist

    gold = make_gold(tmp_path)
    assign_assist(gold, n_blind=1, seed=0)
    modes = {r["ad_id"]: r for r in csv.DictReader(open(gold, encoding="utf-8"))}
    blind = next(i for i, r in modes.items() if r["label_mode"] == "blind")
    assisted = [i for i, r in modes.items() if r["label_mode"] == "assisted"]
    sugg = modes[assisted[0]]

    wb = Workbook()
    ws = wb.active
    ws.title = "Label"
    ws.append(["#", "ad_id", "ad_text", "gold_goal", "gold_issue", "checked", "notes"])
    ws.append([1, blind, "t", "other", "other", None, ""])
    # checked, but the human changed the goal
    changed_goal = "other" if sugg["suggested_goal"] != "other" else "persuasion"
    ws.append([2, assisted[0], "t", changed_goal, sugg["suggested_issue"], "yes", ""])
    # pre-filled but never checked: must not become gold
    ws.append([3, assisted[1], "t", modes[assisted[1]]["suggested_goal"], modes[assisted[1]]["suggested_issue"], None, ""])
    path = tmp_path / "assist.xlsx"
    wb.save(path)

    stats = import_labels(path, gold)
    _, labels = load_gold(gold)
    assert set(labels) == {blind, assisted[0]}
    assert stats["blind_labeled"] == 1
    assert stats["checked_assisted"] == 1
    assert stats["goal_overrides"] == 1 and stats["issue_overrides"] == 0
    assert stats["unchecked_assisted"] == 1
