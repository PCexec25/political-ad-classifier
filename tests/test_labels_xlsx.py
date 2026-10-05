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
    assert import_labels(xlsx, gold) == {"ads": 3, "labeled": 1}
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
