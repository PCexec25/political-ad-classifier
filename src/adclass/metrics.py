"""Evaluation metrics, written out in plain Python so every number is inspectable.

Covers what a reviewer will ask about a classifier on a small gold set:
per-label precision/recall/F1, macro-F1 (so rare labels count), Cohen's
kappa (agreement beyond chance), a bootstrap interval on accuracy (because
n is small), and an exact McNemar test for "is prompt B really better
than prompt A on the same ads, or is that noise?".
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from math import comb
from typing import Sequence


@dataclass(frozen=True)
class LabelScores:
    label: str
    precision: float
    recall: float
    f1: float
    support: int  # number of gold items with this label


def accuracy(gold: Sequence[str], pred: Sequence[str]) -> float:
    _check(gold, pred)
    if not gold:
        return 0.0
    return sum(g == p for g, p in zip(gold, pred)) / len(gold)


def per_label_scores(gold: Sequence[str], pred: Sequence[str], labels: Sequence[str]) -> list[LabelScores]:
    _check(gold, pred)
    scores = []
    for label in labels:
        tp = sum(g == label and p == label for g, p in zip(gold, pred))
        fp = sum(g != label and p == label for g, p in zip(gold, pred))
        fn = sum(g == label and p != label for g, p in zip(gold, pred))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        scores.append(LabelScores(label, precision, recall, f1, tp + fn))
    return scores


def macro_f1(gold: Sequence[str], pred: Sequence[str], labels: Sequence[str]) -> float:
    """Mean F1 over labels that appear in the gold set (absent labels are skipped, not zeroed)."""
    present = [s for s in per_label_scores(gold, pred, labels) if s.support > 0]
    if not present:
        return 0.0
    return sum(s.f1 for s in present) / len(present)


def confusion_matrix(gold: Sequence[str], pred: Sequence[str], labels: Sequence[str]) -> list[list[int]]:
    """Rows are gold labels, columns are predicted labels, both in `labels` order."""
    _check(gold, pred)
    index = {label: i for i, label in enumerate(labels)}
    matrix = [[0] * len(labels) for _ in labels]
    for g, p in zip(gold, pred):
        matrix[index[g]][index[p]] += 1
    return matrix


def cohens_kappa(gold: Sequence[str], pred: Sequence[str]) -> float:
    _check(gold, pred)
    n = len(gold)
    if n == 0:
        return 0.0
    observed = accuracy(gold, pred)
    labels = set(gold) | set(pred)
    expected = sum((gold.count(label) / n) * (pred.count(label) / n) for label in labels)
    if expected == 1.0:
        return 1.0 if observed == 1.0 else 0.0
    return (observed - expected) / (1 - expected)


def bootstrap_accuracy_ci(
    gold: Sequence[str],
    pred: Sequence[str],
    n_resamples: int = 2000,
    alpha: float = 0.05,
    seed: int = 0,
) -> tuple[float, float]:
    """Percentile bootstrap interval for accuracy. Seeded, so results are reproducible."""
    _check(gold, pred)
    n = len(gold)
    if n == 0:
        return (0.0, 0.0)
    correct = [g == p for g, p in zip(gold, pred)]
    rng = random.Random(seed)
    stats = sorted(sum(rng.choices(correct, k=n)) / n for _ in range(n_resamples))
    lo = stats[int((alpha / 2) * n_resamples)]
    hi = stats[min(n_resamples - 1, int((1 - alpha / 2) * n_resamples))]
    return (lo, hi)


@dataclass(frozen=True)
class McNemarResult:
    a_only_correct: int  # items system A got right and B got wrong
    b_only_correct: int
    p_value: float  # two-sided exact binomial test on the discordant pairs


def mcnemar_exact(gold: Sequence[str], pred_a: Sequence[str], pred_b: Sequence[str]) -> McNemarResult:
    """Paired comparison of two systems on the same items."""
    _check(gold, pred_a)
    _check(gold, pred_b)
    a_only = sum(a == g and b != g for g, a, b in zip(gold, pred_a, pred_b))
    b_only = sum(b == g and a != g for g, a, b in zip(gold, pred_a, pred_b))
    n = a_only + b_only
    if n == 0:
        return McNemarResult(a_only, b_only, 1.0)
    k = min(a_only, b_only)
    tail = sum(comb(n, i) for i in range(k + 1)) / 2**n
    return McNemarResult(a_only, b_only, min(1.0, 2 * tail))


def _check(gold: Sequence[str], pred: Sequence[str]) -> None:
    if len(gold) != len(pred):
        raise ValueError(f"length mismatch: {len(gold)} gold vs {len(pred)} predictions")
