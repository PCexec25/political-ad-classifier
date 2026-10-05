"""Ad Library paste parser tests, on a synthetic paste in the website's layout."""

import csv
from pathlib import Path

from adclass.data_io import load_gold
from adclass.library_import import drop_ad, import_into_gold, normalize_text, parse_library_text

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


def test_body_ends_at_next_card_when_separators_are_stripped():
    # Chat apps can drop the zero-width separator and leave blank lines instead.
    raw = (
        "Library ID: 1\nPage\nPage\nSponsored • Paid for by C\nBody line.\n\n\n"
        "Active\nLibrary ID: 2\nPage2\nPage2\nSponsored • Paid for by D\nOther body.\n"
    )
    first, second = parse_library_text(raw)
    assert first.text == "Body line."
    assert second.text == "Other body."


def test_template_variants_count_as_duplicates(tmp_path):
    # Same ad re-targeted to another state: a few words differ (~80% overlap).
    def card(lid, state, date):
        return (
            f"Active\nLibrary ID: {lid}\nP\nP\nSponsored • Paid for by C\n"
            "Are you concerned about the rise of socialism? Millions of Americans are concerned "
            f"that it is destroying the American Dream. Early voting begins on {date}. "
            f"Make a plan to vote to stop it in {state}.\n0:00 / 0:31\n"
        )
    result = import_into_gold(card(1, "Georgia", "October 13th") + card(2, "Arizona", "October 7th"), tmp_path / "g.csv", "x")
    assert [a.library_id for a in result.added] == ["1"]
    assert "duplicate" in dict(result.skipped)["2"]


def test_drop_ad_logs_reason_and_blocks_reimport(tmp_path):
    gold = tmp_path / "gold.csv"
    import_into_gold(RAW, gold, search_term="chip in")
    entry = drop_ad(gold, "444", "same appeal as 111 plus one paragraph")
    assert entry["page_name"] == "Other Page"
    ads, _ = load_gold(gold)
    assert "444" not in [a.ad_id for a in ads]
    with open(tmp_path / "dropped.csv", newline="", encoding="utf-8") as f:
        assert list(csv.DictReader(f))[0]["reason"] == "same appeal as 111 plus one paragraph"
    result = import_into_gold(RAW, gold, search_term="chip in")
    assert "previously dropped" in dict(result.skipped)["444"]


def test_drop_ad_requires_known_id_and_reason(tmp_path):
    import pytest

    gold = tmp_path / "gold.csv"
    import_into_gold(RAW, gold, search_term="chip in")
    with pytest.raises(ValueError, match="not in"):
        drop_ad(gold, "999", "x")
    with pytest.raises(ValueError, match="reason"):
        drop_ad(gold, "111", "  ")


def test_limit_keeps_first_accepted_ads_and_rerun_adds_more(tmp_path):
    gold = tmp_path / "gold.csv"
    result = import_into_gold(RAW, gold, search_term="x", limit=1)
    assert [a.library_id for a in result.added] == ["111"]
    assert "batch limit" in dict(result.skipped)["444"]
    again = import_into_gold(RAW, gold, search_term="x", limit=1)
    assert [a.library_id for a in again.added] == ["444"]
