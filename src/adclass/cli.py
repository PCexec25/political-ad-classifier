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


def _cmd_import_library(args: argparse.Namespace) -> int:
    from .library_import import import_into_gold

    raw = Path(args.raw).read_text(encoding="utf-8")
    result = import_into_gold(raw, args.gold, search_term=args.search, max_per_page=args.max_per_page, limit=args.limit)
    print(f"Added {len(result.added)} ads to {args.gold}; skipped {len(result.skipped)}.")
    over_limit = [i for i, reason in result.skipped if reason.startswith("batch limit")]
    for library_id, reason in result.skipped:
        if not reason.startswith("batch limit"):
            print(f"  skipped {library_id}: {reason}")
    if over_limit:
        print(f"  not reached ({len(over_limit)} ads past --limit {args.limit}); rerun with a higher --limit to add them")
    return 0


def _cmd_drop_ad(args: argparse.Namespace) -> int:
    from .library_import import drop_ad

    entry = drop_ad(args.gold, args.id, args.reason)
    print(f"Dropped {entry['ad_id']} ({entry['page_name']}): {entry['reason']}")
    return 0


def _cmd_import_labels(args: argparse.Namespace) -> int:
    from .labels_xlsx import import_labels

    stats = import_labels(args.xlsx, args.gold)
    print(f"{args.gold}: {stats['labeled']} of {stats['ads']} ads labeled; all labels valid.")
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

    i = sub.add_parser("import-library", help="append ads from text copied off the Meta Ad Library website")
    i.add_argument("--raw", required=True, help="text file of a pasted Ad Library results page")
    i.add_argument("--search", required=True, help="the search term used, recorded for each row")
    i.add_argument("--gold", default="data/gold.csv")
    i.add_argument("--max-per-page", type=int, default=4)
    i.add_argument("--limit", type=int, default=0, help="add at most N ads from this paste (0 = all)")
    i.set_defaults(func=_cmd_import_library)

    d = sub.add_parser("drop-ad", help="remove an ad from the gold file, logging the reason in dropped.csv")
    d.add_argument("--id", required=True)
    d.add_argument("--reason", required=True)
    d.add_argument("--gold", default="data/gold.csv")
    d.set_defaults(func=_cmd_drop_ad)

    x = sub.add_parser("import-labels", help="copy labels from the labeling workbook into the gold CSV")
    x.add_argument("--xlsx", required=True)
    x.add_argument("--gold", default="data/gold.csv")
    x.set_defaults(func=_cmd_import_labels)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
