"""Ad Library paste parser tests, on a synthetic paste in the website's layout."""

import csv
from pathlib import Path

from adclass.data_io import load_gold
from adclass.library_import import import_into_gold, normalize_text, parse_library_text

RAW = (Path(__file__).parent / "fixtures" / "library_paste.txt").read_text(encoding="utf-8")


def test_parses_every_card_with_metadata():
    ads = parse_library_text(RAW)
    assert [a.library_id for a in ads] == ["111", "222", "333", "444", "555"]
    first = ads[0]
    assert (first.page_name, first.paid_for, first.started_running) == ("Example Page", "Example Committee", "May 12, 2026")


def test_body_stops_at_domain_and_excludes_headline():
    body = parse_library_text(RAW)[0].text
    assert body == "First paragraph of the body.\n\nSecond paragraph. Chip in $5?"
    assert "Headline" not in body


def test_body_stops_at_video_timer_and_folds_bold_unicode():
    assert parse_library_text(RAW)[3].text == "Bold text here, then a timer."


def test_video_only_ad_has_empty_body():
    assert parse_library_text(RAW)[1].text == ""


def test_normalize_collapses_extra_blank_lines():
    assert normalize_text("a\n\n\n\nb  \n") == "a\n\nb"


def test_import_skips_empty_duplicate_and_capped(tmp_path):
    gold = tmp_path / "gold.csv"
    result = import_into_gold(RAW, gold, search_term="chip in", max_per_page=1)
    assert [a.library_id for a in result.added] == ["111", "444"]
    reasons = dict(result.skipped)
    assert "no body text" in reasons["222"]
    assert "duplicate" in reasons["333"]
    assert "page cap" in reasons["555"]
    ads, labels = load_gold(gold)  # output must be a valid gold file
    assert [a.ad_id for a in ads] == ["111", "444"] and labels == {}


def test_reimport_preserves_labels_and_skips_known_ids(tmp_path):
    gold = tmp_path / "gold.csv"
    import_into_gold(RAW, gold, search_term="chip in")
    with open(gold, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fields = list(rows[0])
    rows[0].update(gold_goal="fundraising", gold_issue="other")
    with open(gold, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    result = import_into_gold(RAW, gold, search_term="chip in")
    assert result.added == []
    _, labels = load_gold(gold)
    assert labels["111"].goal == "fundraising"
