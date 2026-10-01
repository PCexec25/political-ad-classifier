"""Metric tests use small hand-checkable cases; each expected value is worked out in a comment."""

import pytest

from adclass import metrics


def test_accuracy_basic():
    assert metrics.accuracy(["a", "b", "a", "b"], ["a", "b", "b", "b"]) == 0.75


def test_length_mismatch_raises():
    with pytest.raises(ValueError):
        metrics.accuracy(["a"], ["a", "b"])


def test_per_label_scores_hand_computed():
    gold = ["a", "a", "a", "b", "b"]
    pred = ["a", "a", "b", "b", "a"]
    # label a: tp=2, fp=1 (last item), fn=1 -> P=2/3, R=2/3, F1=2/3
    # label b: tp=1, fp=1, fn=1 -> P=1/2, R=1/2, F1=1/2
    a, b = metrics.per_label_scores(gold, pred, ["a", "b"])
    assert (a.precision, a.recall, a.support) == pytest.approx((2 / 3, 2 / 3, 3))
    assert a.f1 == pytest.approx(2 / 3)
    assert b.f1 == pytest.approx(0.5)
    assert b.support == 2


def test_macro_f1_skips_labels_absent_from_gold():
    # "c" never appears in gold; it must not drag the mean toward zero.
    gold, pred = ["a", "b"], ["a", "b"]
    assert metrics.macro_f1(gold, pred, ["a", "b", "c"]) == 1.0


def test_label_never_predicted_has_zero_precision_not_crash():
    (s,) = metrics.per_label_scores(["a", "a"], ["b", "b"], ["a"])
    assert s.precision == 0.0 and s.recall == 0.0 and s.f1 == 0.0


def test_confusion_matrix_rows_are_gold():
    m = metrics.confusion_matrix(["a", "a", "b"], ["a", "b", "b"], ["a", "b"])
    assert m == [[1, 1], [0, 1]]


def test_kappa_perfect_and_chance():
    assert metrics.cohens_kappa(["a", "b", "a", "b"], ["a", "b", "a", "b"]) == 1.0
    # observed 0.5; each side is 50/50 so expected 0.5 -> kappa 0
    assert metrics.cohens_kappa(["a", "a", "b", "b"], ["a", "b", "a", "b"]) == pytest.approx(0.0)


def test_kappa_single_label_everywhere():
    assert metrics.cohens_kappa(["a", "a"], ["a", "a"]) == 1.0


def test_bootstrap_ci_is_reproducible_and_brackets_point_estimate():
    gold = ["a"] * 20
    pred = ["a"] * 15 + ["b"] * 5
    ci1 = metrics.bootstrap_accuracy_ci(gold, pred, seed=1)
    ci2 = metrics.bootstrap_accuracy_ci(gold, pred, seed=1)
    assert ci1 == ci2
    lo, hi = ci1
    assert lo <= 0.75 <= hi
    assert 0.0 <= lo < hi <= 1.0


def test_mcnemar_hand_computed():
    gold = ["a"] * 6
    sys_a = ["a", "a", "a", "a", "a", "b"]  # right on items 0-4
    sys_b = ["b", "b", "b", "b", "a", "a"]  # right on items 4-5
    r = metrics.mcnemar_exact(gold, sys_a, sys_b)
    # discordant: A-only right on 0,1,2,3 (4); B-only right on 5 (1); n=5, k=1
    # P(X<=1 | Bin(5, .5)) = (1 + 5)/32 = 6/32; two-sided -> 12/32 = 0.375
    assert (r.a_only_correct, r.b_only_correct) == (4, 1)
    assert r.p_value == pytest.approx(0.375)


def test_mcnemar_identical_systems():
    r = metrics.mcnemar_exact(["a", "b"], ["a", "a"], ["a", "a"])
    assert r.p_value == 1.0
