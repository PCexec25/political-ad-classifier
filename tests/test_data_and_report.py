"""Data loading and end-to-end report tests on a synthetic gold file."""

from pathlib import Path

import pytest

from adclass import report
from adclass.cli import main
from adclass.data_io import load_gold, load_predictions, write_prediction
from adclass.schema import Prediction

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_gold.csv"


def pred(ad_id, goal, issue, error=None):
    return Prediction(ad_id=ad_id, goal=goal, issue=issue, confidence="high", rationale="r", prompt_version="v2", model="m", error=error)


def test_load_gold_skips_unlabeled_rows_but_keeps_ads():
    ads, gold = load_gold(FIXTURE)
    assert len(ads) == 4
    assert set(gold) == {"syn-001", "syn-002", "syn-003"}


def test_duplicate_id_rejected(tmp_path):
    p = tmp_path / "g.csv"
    p.write_text("ad_id,page_name,ad_text,source_url,gold_goal,gold_issue,notes\nx,,t,,other,other,\nx,,t,,other,other,\n")
    with pytest.raises(ValueError, match="duplicate"):
        load_gold(p)


def test_unknown_label_rejected_with_line_number(tmp_path):
    p = tmp_path / "g.csv"
    p.write_text("ad_id,page_name,ad_text,source_url,gold_goal,gold_issue,notes\nx,,t,,persuade,other,\n")
    with pytest.raises(ValueError, match=r"g.csv:2"):
        load_gold(p)


def test_missing_column_rejected(tmp_path):
    p = tmp_path / "g.csv"
    p.write_text("ad_id,ad_text\nx,t\n")
    with pytest.raises(ValueError, match="missing columns"):
        load_gold(p)


def test_predictions_roundtrip_and_last_write_wins(tmp_path):
    out = tmp_path / "runs" / "p.jsonl"
    write_prediction(out, pred("a", "", "", error="boom"))
    write_prediction(out, pred("a", "other", "other"))
    loaded = load_predictions(out)
    assert loaded["a"].ok and loaded["a"].goal == "other"


def test_failed_and_missing_predictions_count_as_wrong():
    _, gold = load_gold(FIXTURE)
    preds = {
        "syn-001": pred("syn-001", "persuasion", "economy"),
        "syn-002": pred("syn-002", "", "", error="timeout"),
        # syn-003 missing entirely
    }
    r = report.evaluate(gold, preds)
    assert r["n_errors"] == 2
    assert r["fields"]["goal"]["accuracy"] == pytest.approx(1 / 3)
    assert len(report.disagreements(gold, preds)) == 2


def test_evaluate_cli_writes_markdown(tmp_path):
    out = tmp_path / "p.jsonl"
    for ad_id, g, i in [("syn-001", "persuasion", "economy"), ("syn-002", "mobilization", "other"), ("syn-003", "persuasion", "healthcare")]:
        write_prediction(out, pred(ad_id, g, i))
    rep = tmp_path / "r.md"
    assert main(["evaluate", "--gold", str(FIXTURE), "--preds", str(out), "--report", str(rep)]) == 0
    text = rep.read_text()
    assert "## goal" in text and "Disagreements (1)" in text and "syn-003" in text


def test_classify_refuses_without_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert main(["classify", "--gold", str(FIXTURE), "--out", str(tmp_path / "p.jsonl")]) == 2


def test_evaluate_refuses_missing_predictions_file(tmp_path):
    assert main(["evaluate", "--gold", str(FIXTURE), "--preds", str(tmp_path / "nope.jsonl")]) == 2
