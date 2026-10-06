# Political Ad Classifier

[![tests](https://github.com/PCexec25/political-ad-classifier/actions/workflows/tests.yml/badge.svg)](https://github.com/PCexec25/political-ad-classifier/actions/workflows/tests.yml)

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
pytest -q                                    # 55 tests, no API key needed

export ANTHROPIC_API_KEY=...                 # see .env.example; never commit it
adclass classify --prompt v2 --out runs/v2-haiku.jsonl --limit 5   # cheap smoke test
adclass classify --prompt v2 --out runs/v2-haiku.jsonl             # full run (resumes if interrupted)
adclass evaluate --preds runs/v2-haiku.jsonl --report reports/v2-haiku.md
adclass evaluate --preds runs/v2-haiku.jsonl --subset blind   # headline number: unassisted ads only
```

Comparing against the keyword baseline:

```bash
adclass baseline --out runs/baseline.jsonl
adclass compare --preds-a runs/baseline.jsonl --preds-b runs/v2-haiku.jsonl --subset blind
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

`data/gold.csv` has the columns `ad_id, page_name, ad_text, source_url, gold_goal, gold_issue, notes`. Ad text was copied by hand from the public [Meta Ad Library](https://www.facebook.com/ads/library/) website (no API access, scraping, or third-party tools) and labeled according to [CODEBOOK.md](CODEBOOK.md). The repo works with any source of ad text in this CSV format. To add a batch, run a search on the Ad Library website, copy the results page into a text file, and run:

```bash
adclass import-library --raw data/raw_chip_in.txt --search "chip in"
adclass import-library --raw data/raw_abortion.txt --search "abortion" --limit 15   # keep the 15 highest-reach ads
```

The importer keeps only the ad body (not the link headline or button), folds decorative Unicode such as 𝐛𝐨𝐥𝐝 letters to plain text, and skips ads with no body text, exact and near-duplicate copies (word overlap of 75% or more, which catches the same ad retargeted to another state), and anything beyond 4 ads per page. It logs every skip. Existing rows and labels are never modified. One known limitation: the body is cut off at the link domain, so when an ad has no link, its headline lines stay in the body text. Extra columns (`search_term`, `paid_for`, `started_running`) record where each ad came from. The model never sees them.

Near-duplicates that the automatic rule misses, such as the same appeal with one extra paragraph, are removed by hand with a logged reason:

```bash
adclass drop-ad --id 1709809976696459 --reason "Same billboard appeal as 1285247517012202 plus one paragraph"
```

The row moves to `data/dropped.csv` with its reason, and the importer will not re-add it.

### Labeling protocol: model-assisted, with a blind holdout

Labeling 143 ads from scratch is slow, so most ads are pre-labeled by the keyword-rule baseline (`src/adclass/baseline.py`) and the human checks them. Pre-labeling has a known cost: people checking a suggestion agree with it more often than they would have labeled the same way unaided (anchoring). The protocol is built to contain and measure that.

- **The pre-labeler is not an LLM.** Pre-labeling with the same kind of model being evaluated would make the evaluation circular. The rule model is transparent, and every suggestion lists the keywords that produced it.
- **A blind holdout.** `adclass assist` draws 40 ads at random (seed 2026) that get no suggestion and are labeled from scratch. The LLM's headline numbers are reported on these ads (`--subset blind`).
- **Suggestions count only when confirmed.** In the workbook a pre-filled label becomes gold only after the row is marked `checked = yes`; unchecked rows import as unlabeled.
- **Anchoring is measured, not assumed away.** The suggestions are stored in `gold.csv`. The import reports how often the human overrode them, and the baseline's agreement on blind vs. assisted ads estimates how much the suggestions inflated agreement.

```bash
adclass assist                                          # once: draw the blind set, store suggestions
python scripts/build_labeling_xlsx.py                   # writes gold_labeling.xlsx
adclass import-labels --xlsx gold_labeling.xlsx         # after labeling
```

Only the label and notes columns are read from the workbook; ad text always comes from `gold.csv`. The import is all-or-nothing: an off-codebook value or a half-labeled row (goal without issue) leaves `gold.csv` untouched and names the row.

Rows with blank gold labels are still classified, so you can run the model on ads you haven't finished labeling.

### What happened when the protocol ran

- **Blind ads (40)** were labeled from scratch. Error analysis on them surfaced codebook gaps that were resolved by amending the codebook, not by quietly relabeling. Four rules were added or rewritten: implied money asks; a broader `candidate_character`; vague ads; and petitions, which are labeled by the rest of the ad rather than counted as mobilization.
- **Assisted ads (103)** were all confirmed, with 1 issue label changed and no goal labels changed. On them, the keyword baseline scores 100% on goal and 99% on issue, against 72.5% and 80% on the blind ads. That gap is the anchoring effect the protocol was designed to measure: the assisted labels are effectively the baseline's own output.
- **Consequence:** model evaluation uses the 40 blind ads. The assisted labels are kept and disclosed, but they are not used to score any model, because scoring a model against them would mostly measure agreement with keyword rules. The keyword baseline was frozen as `rules-v1` before the codebook amendments, so it predates rules 4 and 5.

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

All figures are on the 40 blind ads; 95% bootstrap intervals are in parentheses.

| System | Goal accuracy | Goal macro-F1 | Issue accuracy | Issue macro-F1 |
|---|---|---|---|---|
| Keyword baseline (`rules-v1`) | 72.5% (57.5–85.0) | 0.56 | 80.0% (67.5–92.5) | 0.78 |
| Claude, prompt v1 | *pending* | | | |
| Claude, prompt v2 (codebook) | *pending* | | | |

With n = 40, intervals span roughly ±15 points. Differences between systems are tested with McNemar's exact test (`adclass compare --subset blind`), not by comparing point estimates.

## Limitations

- **Baseline word lists saw the data.** The keyword rules were written with the gold ads in view, so the baseline's score is optimistic; it is a floor to beat, not a fair competitor.
- **One labeler.** Gold labels reflect one person applying the codebook. CODEBOOK.md describes a self-consistency check, but a second independent labeler would be the real test.
- **Text only.** Most political ads are image or video. Text-only classification misses the creative itself.
- **Small, hand-picked sample.** The gold set is not a random sample of the Ad Library, so the scores describe performance on this set, not on the population of ads.

## Roadmap

1. Grow the gold set from additional public sources that need no account or identity verification, such as published academic ad-text datasets released for research use.
2. Profile Google political-ad spend and targeting by advertiser from the public BigQuery dataset (`bigquery-public-data.google_political_ads`). That dataset has no ad text, so it complements this classifier rather than feeding it.
3. Calibration analysis: does the model's self-reported confidence actually predict when it's right?
