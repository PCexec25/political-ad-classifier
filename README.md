# Political Ad Classifier

Classifies the text of US political ads by **goal** (persuasion, mobilization, fundraising, other) and **primary issue** (8 categories) using Claude, and measures how well it does against a hand-labeled gold set.

The point of the project is the evaluation, not the classifier. Getting an LLM to emit a label takes ten lines of code. Knowing whether the label is right, where it fails, and whether a prompt change actually helped is the harder problem, and it's the one this repo is built around.

**Status:** prototype, October 2026. Built by Peter Clark using an agentic development workflow (Claude as coding agent). I designed the taxonomy and codebook, hand-labeled the gold set, and reviewed and tested every module.

## What it does

```
gold.csv (hand-labeled ads)
   │
   ├─ adclass classify ──► runs/<prompt>-<model>.jsonl   one validated prediction per ad
   │
   ├─ adclass evaluate ──► reports/<run>.md              accuracy + CI, per-label P/R/F1,
   │                                                     kappa, confusion matrix, every disagreement
   └─ adclass compare  ──► reports/<a>-vs-<b>.md         paired McNemar test between two runs
```

## Quickstart

```bash
git clone https://github.com/PCexec25/political-ad-classifier
cd political-ad-classifier
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q                                    # 31 tests, no API key needed

export ANTHROPIC_API_KEY=...                 # see .env.example; never commit it
adclass classify --prompt v2 --out runs/v2-haiku.jsonl --limit 5   # cheap smoke test
adclass classify --prompt v2 --out runs/v2-haiku.jsonl             # full run (resumes if interrupted)
adclass evaluate --preds runs/v2-haiku.jsonl --report reports/v2-haiku.md
```

Comparing the bare prompt with the codebook prompt:

```bash
adclass classify --prompt v1 --out runs/v1-haiku.jsonl
adclass compare --preds-a runs/v1-haiku.jsonl --preds-b runs/v2-haiku.jsonl --report reports/v1-vs-v2.md
```

Comparing models on the same prompt:

```bash
adclass classify --prompt v2 --model claude-sonnet-5-5 --out runs/v2-sonnet.jsonl
adclass compare --preds-a runs/v2-haiku.jsonl --preds-b runs/v2-sonnet.jsonl
```

## The gold set

`data/gold.csv` has the columns `ad_id, page_name, ad_text, source_url, gold_goal, gold_issue, notes`. Ad text was copied by hand from the public [Meta Ad Library](https://www.facebook.com/ads/library/) website (no API access, scraping, or third-party tools) and labeled according to [CODEBOOK.md](CODEBOOK.md). The repo works with any source of ad text in this CSV format. Rows with blank gold labels are still classified, so you can run the model on ads you haven't finished labeling.

## Design decisions

- **Structured output by forced tool call.** The model must answer through a JSON schema whose enums are generated from `schema.py`. Nothing is parsed out of free text.
- **Validate anyway.** An off-taxonomy or empty answer becomes a recorded error, not a silent wrong label. Errors and missing predictions are **scored as wrong**, because dropping them would inflate the numbers.
- **Prompts are versioned files.** `prompts/v1.txt` is a bare instruction and `prompts/v2.txt` encodes the codebook with explicit tie-break rules. Every prediction records the prompt version and model that produced it.
- **Temperature 0 and resumable runs.** Predictions append to JSONL and reruns skip finished ads, so an interrupted run costs nothing to restart.
- **Statistics sized for a small gold set.** With about 100 items, a 3-point accuracy gain is often noise. Reports give a bootstrap 95% interval on accuracy, and `compare` uses McNemar's exact test on the ads the two runs disagree on, rather than eyeballing two accuracies.
- **Macro-F1 alongside accuracy.** If most ads are persuasion, a model can score high accuracy while failing on mobilization. Macro-F1 weights every label equally.
- **Testable without a network.** The API client is injected, and tests use a fake client to cover retries, malformed output, and missing tool calls.

## Security notes

- The API key is read only from the environment. `.env` is git-ignored, and the CLI refuses to run without a key rather than prompting for one.
- Ad copy is untrusted input. It is fenced in `<ad>` tags and declared to be data, and the tool schema constrains what the model can return, which limits what an injected instruction could do.
- No personal data is collected. Inputs are public ad text only.

## Results

*To be filled in from `reports/` after the first full run. No numbers are reported here until they come from a real run on the real gold set.*

## Limitations

- **One labeler.** Gold labels reflect one person applying the codebook. CODEBOOK.md describes a self-consistency check, but a second independent labeler would be the real test.
- **Text only.** Most political ads are image or video. Text-only classification misses the creative itself.
- **Small, hand-picked sample.** The gold set is not a random sample of the Ad Library, so the scores describe performance on this set, not on the population of ads.

## Roadmap

1. Grow the gold set from additional public sources that need no account or identity verification, such as published academic ad-text datasets released for research use.
2. Profile Google political-ad spend and targeting by advertiser from the public BigQuery dataset (`bigquery-public-data.google_political_ads`). That dataset has no ad text, so it complements this classifier rather than feeding it.
3. Calibration analysis: does the model's self-reported confidence actually predict when it's right?
