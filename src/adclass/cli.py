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


def _subset(gold: dict, gold_path: str, mode: str) -> dict:
    """Restrict gold labels to blind or assisted ads (see assist.py)."""
    if mode == "all":
        return gold
    from .library_import import read_gold_rows

    keep = {r["ad_id"] for r in read_gold_rows(Path(gold_path)) if r.get("label_mode") == mode}
    if not keep:
        raise ValueError(f"no ads with label_mode={mode!r} in {gold_path}; run `adclass assist` first")
    return {k: v for k, v in gold.items() if k in keep}


def _cmd_evaluate(args: argparse.Namespace) -> int:
    if not Path(args.preds).exists():
        print(f"No predictions file at {args.preds}. Run `adclass classify` first.", file=sys.stderr)
        return 2
    _, gold = load_gold(args.gold)
    gold = _subset(gold, args.gold, args.subset)
    preds = load_predictions(args.preds)
    result = report.evaluate(gold, preds)
    title = f"Evaluation: {Path(args.preds).stem}" + ("" if args.subset == "all" else f" ({args.subset} ads only)")
    md = report.render_markdown(title, result, report.disagreements(gold, preds))
    _emit(md, args.report)
    return 0


def _cmd_compare(args: argparse.Namespace) -> int:
    _, gold = load_gold(args.gold)
    gold = _subset(gold, args.gold, args.subset)
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

    s = import_labels(args.xlsx, args.gold)
    print(f"{args.gold}: {s['labeled']} of {s['ads']} ads labeled; all labels valid.")
    print(f"  blind ads labeled: {s['blind_labeled']}")
    print(f"  assisted ads checked: {s['checked_assisted']}")
    if s["checked_assisted"]:
        n = s["checked_assisted"]
        print(f"  you changed the suggested goal on {s['goal_overrides']}/{n} and the issue on {s['issue_overrides']}/{n}")
    if s["unchecked_assisted"]:
        print(f"  {s['unchecked_assisted']} assisted rows had labels but no checked=yes; imported as unlabeled")
    return 0


def _cmd_assist(args: argparse.Namespace) -> int:
    from .assist import assign_assist

    s = assign_assist(args.gold, n_blind=args.blind, seed=args.seed)
    print(f"{args.gold}: {s['blind']} blind, {s['assisted']} assisted (of {s['ads']}).")
    return 0


def _cmd_baseline(args: argparse.Namespace) -> int:
    from .baseline import predict

    ads, _ = load_gold(args.gold)
    out = Path(args.out)
    if out.exists():
        out.unlink()
    for ad in ads:
        write_prediction(out, predict(ad.ad_id, ad.text))
    print(f"Wrote {len(ads)} keyword-baseline predictions to {out}")
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
    e.add_argument("--subset", choices=["all", "blind", "assisted"], default="all", help="score only blind or assisted ads")
    e.set_defaults(func=_cmd_evaluate)

    m = sub.add_parser("compare", help="paired comparison of two prediction files")
    m.add_argument("--gold", default="data/gold.csv")
    m.add_argument("--preds-a", required=True)
    m.add_argument("--preds-b", required=True)
    m.add_argument("--report")
    m.add_argument("--subset", choices=["all", "blind", "assisted"], default="all")
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

    a = sub.add_parser("assist", help="draw the blind holdout and store rule suggestions for the rest")
    a.add_argument("--gold", default="data/gold.csv")
    a.add_argument("--blind", type=int, default=40, help="number of blind (unassisted) ads")
    a.add_argument("--seed", type=int, default=2026)
    a.set_defaults(func=_cmd_assist)

    b = sub.add_parser("baseline", help="run the keyword-rule baseline over the gold ads")
    b.add_argument("--gold", default="data/gold.csv")
    b.add_argument("--out", required=True)
    b.set_defaults(func=_cmd_baseline)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
