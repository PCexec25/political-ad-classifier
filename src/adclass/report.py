"""Turn gold labels + predictions into an evaluation report (dict and Markdown)."""

from __future__ import annotations

from typing import Any

from . import metrics
from .schema import GOALS, ISSUES, GoldLabel, Prediction

ERROR_LABEL = "(error)"
FIELDS = {"goal": GOALS, "issue": ISSUES}


def align(gold: dict[str, GoldLabel], preds: dict[str, Prediction], field: str) -> tuple[list[str], list[str], list[str]]:
    """Pair gold and predicted labels over every gold item.

    A gold item with no prediction, or a failed prediction, is scored as
    ERROR_LABEL (always wrong). Dropping failures instead would inflate scores.
    """
    ids = sorted(gold)
    g, p = [], []
    for ad_id in ids:
        g.append(getattr(gold[ad_id], field))
        pred = preds.get(ad_id)
        p.append(getattr(pred, field) if pred is not None and pred.ok else ERROR_LABEL)
    return ids, g, p


def evaluate(gold: dict[str, GoldLabel], preds: dict[str, Prediction]) -> dict[str, Any]:
    if not gold:
        raise ValueError("gold set is empty; label some ads first")
    covered = [a for a in gold if a in preds and preds[a].ok]
    result: dict[str, Any] = {
        "n_gold": len(gold),
        "n_scored_ok": len(covered),
        "n_errors": len(gold) - len(covered),
        "fields": {},
    }
    for field, labels in FIELDS.items():
        _, g, p = align(gold, preds, field)
        all_labels = list(labels) + [ERROR_LABEL]
        result["fields"][field] = {
            "accuracy": metrics.accuracy(g, p),
            "accuracy_ci95": metrics.bootstrap_accuracy_ci(g, p),
            "macro_f1": metrics.macro_f1(g, p, labels),
            "kappa": metrics.cohens_kappa(g, p),
            "per_label": metrics.per_label_scores(g, p, labels),
            "labels": all_labels,
            "confusion": metrics.confusion_matrix(g, p, all_labels),
        }
    tokens_in = sum(preds[a].usage.get("input_tokens", 0) for a in gold if a in preds)
    tokens_out = sum(preds[a].usage.get("output_tokens", 0) for a in gold if a in preds)
    result["tokens"] = {"input": tokens_in, "output": tokens_out}
    return result


def disagreements(gold: dict[str, GoldLabel], preds: dict[str, Prediction]) -> list[dict[str, str]]:
    """Every gold item where the model differs on either field, for manual error analysis."""
    rows = []
    for ad_id in sorted(gold):
        pred = preds.get(ad_id)
        g = gold[ad_id]
        if pred is None or not pred.ok or pred.goal != g.goal or pred.issue != g.issue:
            rows.append(
                {
                    "ad_id": ad_id,
                    "gold": f"{g.goal} / {g.issue}",
                    "model": f"{pred.goal} / {pred.issue}" if pred and pred.ok else ERROR_LABEL,
                    "confidence": pred.confidence if pred and pred.ok else "",
                    "rationale": (pred.rationale if pred and pred.ok else (pred.error if pred else "no prediction")),
                }
            )
    return rows


def compare(gold: dict[str, GoldLabel], preds_a: dict[str, Prediction], preds_b: dict[str, Prediction]) -> dict[str, Any]:
    out = {}
    for field in FIELDS:
        _, g, pa = align(gold, preds_a, field)
        _, _, pb = align(gold, preds_b, field)
        out[field] = {
            "accuracy_a": metrics.accuracy(g, pa),
            "accuracy_b": metrics.accuracy(g, pb),
            "mcnemar": metrics.mcnemar_exact(g, pa, pb),
        }
    return out


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def _md_table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def render_markdown(title: str, result: dict[str, Any], disagree: list[dict[str, str]]) -> str:
    parts = [f"# {title}", ""]
    parts.append(
        f"Gold items: {result['n_gold']} · scored OK: {result['n_scored_ok']} · "
        f"errors (scored as wrong): {result['n_errors']} · "
        f"tokens in/out: {result['tokens']['input']:,} / {result['tokens']['output']:,}"
    )
    for field, r in result["fields"].items():
        lo, hi = r["accuracy_ci95"]
        parts += [
            "",
            f"## {field}",
            "",
            f"Accuracy {_pct(r['accuracy'])} (95% bootstrap CI {_pct(lo)}–{_pct(hi)}) · "
            f"macro-F1 {r['macro_f1']:.3f} · Cohen's kappa {r['kappa']:.3f}",
            "",
            _md_table(
                ["label", "precision", "recall", "F1", "gold n"],
                [[s.label, f"{s.precision:.2f}", f"{s.recall:.2f}", f"{s.f1:.2f}", str(s.support)] for s in r["per_label"]],
            ),
            "",
            "Confusion matrix (rows = gold, columns = model):",
            "",
            _md_table(["gold \\ model"] + r["labels"], [[lab] + [str(c) for c in row] for lab, row in zip(r["labels"], r["confusion"]) if lab != ERROR_LABEL]),
        ]
    parts += ["", f"## Disagreements ({len(disagree)})", ""]
    if disagree:
        parts.append(
            _md_table(
                ["ad_id", "gold", "model", "conf.", "model rationale"],
                [[d["ad_id"], d["gold"], d["model"], d["confidence"], d["rationale"].replace("|", "/")] for d in disagree],
            )
        )
    else:
        parts.append("None.")
    return "\n".join(parts) + "\n"


def render_comparison(name_a: str, name_b: str, cmp: dict[str, Any], n: int) -> str:
    rows = []
    for field, r in cmp.items():
        m = r["mcnemar"]
        rows.append([field, _pct(r["accuracy_a"]), _pct(r["accuracy_b"]), str(m.a_only_correct), str(m.b_only_correct), f"{m.p_value:.3f}"])
    table = _md_table(["field", f"{name_a} acc.", f"{name_b} acc.", f"only {name_a} right", f"only {name_b} right", "McNemar p"], rows)
    return (
        f"# {name_a} vs {name_b}\n\nSame {n} gold ads. McNemar's exact test asks whether the ads the two "
        f"runs disagree on split unevenly enough to rule out chance; with small n, p > 0.05 means "
        f"\"not yet distinguishable\", not \"equal\".\n\n{table}\n"
    )
