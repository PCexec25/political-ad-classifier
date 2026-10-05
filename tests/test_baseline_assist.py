"""Keyword baseline rule order, and the blind-holdout assignment."""

import csv
from pathlib import Path

from adclass.assist import assign_assist
from adclass.baseline import classify_text
from adclass.cli import main
from adclass.library_import import import_into_gold

RAW = (Path(__file__).parent / "fixtures" / "library_paste.txt").read_text(encoding="utf-8")


def test_rule1_money_beats_voting_info():
    r = classify_text("Early voting starts Oct 19. Chip in $5 before midnight!")
    assert r.goal == "fundraising" and "rule 1" in r.reason


def test_rule2_practical_voting_info_is_mobilization():
    assert classify_text("Find your polling place and make a plan to vote.").goal == "mobilization"
    assert classify_text("Sign the petition to protect public lands.").goal == "mobilization"


def test_rule3_named_candidate_with_date_is_persuasion():
    r = classify_text("Vote Joe Strada on November 3rd, fighting to make Florida more affordable.")
    assert r.goal == "persuasion"
    assert r.issue == "economy"


def test_product_offer_is_other_even_with_political_words():
    assert classify_text("The real story of the election. Stream it now on our app.").goal == "other"


def test_issue_majority_and_tie_priority():
    assert classify_text("The border is open. Illegal immigration is up. Prices too.").issue == "immigration"
    tie = classify_text("Abortion and taxes.")
    assert tie.issue == "abortion" and "tie" in tie.reason and tie.confidence == "low"


def test_no_topic_is_other_and_every_reason_cites_keywords():
    r = classify_text("Please chip in today.")
    assert r.issue == "other" and '"chip in"' in r.reason


def test_blind_set_is_seeded_and_stable(tmp_path):
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    for g in (a, b):
        import_into_gold(RAW, g, search_term="x")
        assign_assist(g, n_blind=1, seed=7)
    pick = lambda g: [r["ad_id"] for r in csv.DictReader(open(g, encoding="utf-8")) if r["label_mode"] == "blind"]
    assert pick(a) == pick(b) and len(pick(a)) == 1
    assign_assist(a, n_blind=2, seed=99)  # re-running never redraws an existing assignment
    assert pick(a) == pick(b)
    rows = list(csv.DictReader(open(a, encoding="utf-8")))
    assert all((r["suggested_goal"] == "") == (r["label_mode"] == "blind") for r in rows)


def test_baseline_predictions_feed_evaluate(tmp_path):
    fixture = Path(__file__).parent / "fixtures" / "synthetic_gold.csv"
    out = tmp_path / "base.jsonl"
    assert main(["baseline", "--gold", str(fixture), "--out", str(out)]) == 0
    rep = tmp_path / "r.md"
    assert main(["evaluate", "--gold", str(fixture), "--preds", str(out), "--report", str(rep)]) == 0
    assert "## goal" in rep.read_text()
