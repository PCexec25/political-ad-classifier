"""Command-line entry point: `adclass classify | evaluate | compare`."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import report
from .classifier import DEFAULT_MODEL, Classifier
from .data_io import load_gold, load_predictions, write_prediction


def _cmd_classify(args: argparse.Namespace) -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set. Put it in your environment (see .env.example); never commit it.", file=sys.stderr)
        return 2
    import anthropic  # imported here so tests and `evaluate` don't need the SDK

    ads, _ = load_gold(args.gold)
    if args.limit:
        ads = ads[: args.limit]
    out = Path(args.out)
    done = {a for a, p in load_predictions(out).items() if p.ok}
    todo = [ad for ad in ads if ad.ad_id not in done]
    print(f"{len(ads)} ads, {len(done)} already done, {len(todo)} to classify -> {out}")

    clf = Classifier(anthropic.Anthropic(), prompt_version=args.prompt, model=args.model)
    failures = 0
    for i, ad in enumerate(todo, start=1):
        pred = clf.classify(ad)
        write_prediction(out, pred)
        failures += not pred.ok
        status = f"{pred.goal}/{pred.issue}" if pred.ok else f"ERROR {pred.error}"
        print(f"[{i}/{len(todo)}] {ad.ad_id}: {status}")
    print(f"Done. {failures} failures.")
    return 0 if failures == 0 else 1


def _cmd_evaluate(args: argparse.Namespace) -> int:
    if not Path(args.preds).exists():
        print(f"No predictions file at {args.preds}. Run `adclass classify` first.", file=sys.stderr)
        return 2
    _, gold = load_gold(args.gold)
    preds = load_predictions(args.preds)
    result = report.evaluate(gold, preds)
    md = report.render_markdown(f"Evaluation: {Path(args.preds).stem}", result, report.disagreements(gold, preds))
    _emit(md, args.report)
    return 0


def _cmd_compare(args: argparse.Namespace) -> int:
    _, gold = load_gold(args.gold)
    a, b = load_predictions(args.preds_a), load_predictions(args.preds_b)
    md = report.render_comparison(Path(args.preds_a).stem, Path(args.preds_b).stem, report.compare(gold, a, b), len(gold))
    _emit(md, args.report)
    return 0


def _emit(md: str, path: str | None) -> None:
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(md, encoding="utf-8")
        print(f"Wrote {path}")
    else:
        print(md)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="adclass", description="Classify political ad text with an LLM and evaluate it against hand labels.")
    sub = parser.add_subparsers(dest="command", required=True)

    c = sub.add_parser("classify", help="run the classifier over the ads in a gold CSV")
    c.add_argument("--gold", default="data/gold.csv")
    c.add_argument("--prompt", default="v2", help="prompt version in adclass/prompts/ (default v2)")
    c.add_argument("--model", default=DEFAULT_MODEL)
    c.add_argument("--out", required=True, help="predictions JSONL (appended; reruns skip finished ads)")
    c.add_argument("--limit", type=int, default=0, help="only the first N ads (for a cheap smoke test)")
    c.set_defaults(func=_cmd_classify)

    e = sub.add_parser("evaluate", help="score one predictions file against the gold labels")
    e.add_argument("--gold", default="data/gold.csv")
    e.add_argument("--preds", required=True)
    e.add_argument("--report", help="write Markdown here instead of printing")
    e.set_defaults(func=_cmd_evaluate)

    m = sub.add_parser("compare", help="paired comparison of two prediction files")
    m.add_argument("--gold", default="data/gold.csv")
    m.add_argument("--preds-a", required=True)
    m.add_argument("--preds-b", required=True)
    m.add_argument("--report")
    m.set_defaults(func=_cmd_compare)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
