# Benchmark v1: independently labelled cases

v0 (`benchmarks/dataset.jsonl` and `holdout.jsonl`) was written *and*
labelled by the gate's author. v1 removes that bias from the reference
labels: the author writes the cases, and **independent annotators** decide the
answers.

## Contents

| File | What it is | Who may look |
|---|---|---|
| `cases.jsonl` | 300 cases: 60 scenarios (10 per category) × 5 candidate next actions. No labels. | Everyone |
| `pilot.txt` | 6 scenarios (30 cases), one per category, all from the dev split | Coordinator |
| `labels/author.jsonl` | The case writer's own labels and reasons | **Not annotators** (bias analysis only) |
| `labels/<annotator>.jsonl` | One file per independent annotator, created by `import` | Coordinator, after labeling ends |
| `adjudication.jsonl` | Agreed outcomes for disputed cases (created when needed) | Coordinator |
| `gold-dev.jsonl` / `gold-test.jsonl` | Gold sets built by `gold`, in the benchmark runner's format | See the protocol |

Categories: coding, research, browser, database, filesystem, tool calling.

**Why 5 candidates per scenario?** Each scenario's history is shared, and its
candidates mix needed steps, repeats, scope creep and judgement calls. This
mirrors the real decision: among the things the agent *could* do next, which
are worth doing?

## Labeling tools

There are two ways to label, and both produce the same `labels/<annotator>.jsonl`.

**1. Web page (recommended).** Build it with `python -m benchmarks.labeler.build`.
- **What annotators see:** one question per screen, designed so that people with no technical background (including older readers) can take part.
  - Each scenario and candidate is shown in plain Chinese (`plain_zh.jsonl`), and the technical original is one tap away.
  - The text describes what an action does and never hints at the answer; tests guard this.
  - Three large answers (有必要 / 没必要 / 说不准), plus "看不懂" (*don't understand*). "看不懂" is stored as `skip`: it counts as answered but never as a vote.
  - Annotators are asked whether they write code (recorded in `labels/annotators.json`), so expert and lay labels can be analysed separately.
  - The page never contains anyone's labels.
- **Answer code:** at the end the page shows a short code with a checksum. The annotator photographs or screenshots it, and the coordinator runs `python -m benchmarks.labeling import-code "<code>" --annotator NAME`.
- **As a claude.ai artifact** (`dist/labeler.html`):
  - Each annotator's answers save automatically to a private database document that only the owner can read. Annotators must be invited by email with edit access.
  - The coordinator exports those documents to JSON and runs `python -m benchmarks.labeling import-web <files>`.
  - Anyone who cannot save to the database gets a CSV export button instead.
- **As a static page** (`dist/index.html`): answers stay in the annotator's browser and are exported as CSV.
  - A copy is published automatically to GitHub Pages: **https://suffiss.github.io/action-necessity-model/**. It needs no account.
  - The `labeling page` workflow rebuilds the page after the test suite passes, whenever cases or the page change on `main`.

**2. CSV sheet.** `export` writes a spreadsheet; annotators fill in the `label` column and the coordinator runs `import`.

## Protocol

| # | Step | Command / output |
|---|---|---|
| 1 | **Pilot.** Two annotators label the 30 pilot cases, following [docs/labeling-guide.md](../../docs/labeling-guide.md). | `python -m benchmarks.labeling export --contexts benchmarks/v1/pilot.txt --out pilot.csv` |
| 2 | **Review the pilot.** Import both sheets, check agreement, and discuss disagreements. Revise the guide if the disagreements reveal an unclear rule rather than a genuinely ambiguous case. | `agree --show-disagreements` |
| 3 | **Full labeling.** The same (or new) annotators label all 300 cases independently. | `export --out sheet.csv`, then `import filled.csv --annotator NAME` |
| 4 | **Agreement.** Report pairwise Cohen's kappa. Below 0.4 ("fair" or worse), the task definition itself needs work before any gate results mean much. | `agree` |
| 5 | **Adjudication.** Resolve cases where annotators split `necessary` vs `unnecessary` by discussion. Record outcomes in `adjudication.jsonl`. | |
| 6 | **Gold.** Build the gold sets. Scenarios are split 40% dev / 60% test by a fixed hash of `context_id`, so no scenario straddles the split. | `gold` |
| 7 | **Freeze test.** `gold-test.jsonl` is evaluated **once per evaluator version**. Never tune on it. Every run is appended to `benchmarks/RESULTS.md`. | `python -m benchmarks.runner benchmarks/v1/gold-test.jsonl` |

The pilot scenarios were chosen from the dev split on purpose. Discussing them
in step 2 makes them non-independent, which is acceptable for dev and not for
test.

## Synthetic annotations

Simulated annotators (for example LLM-generated personas) are **not** people.
They are only useful for:

- stress-testing the tooling;
- prototyping analysis code;
- forming hypotheses before real labeling.

They must never become gold, and the importers refuse them: documents
flagged `"synthetic": true` and annotator names starting with `syn` are
rejected.

A 90,000-label synthetic set (300 personas × 300 cases) supplied for this
project shows why. It was generated with the author's labels as its prior,
and its majority label equals the author's label on 300/300 cases, so treating
it as annotators would simply turn the author's labels into gold.

Its one durable contribution: a stress test showing that the original gold
rule did not scale. That rule disputed any necessary-vs-unnecessary split, so
with 5 voters 45% of cases were disputed and with 300 voters all of them were.
The supermajority rule above replaced it. On the same data, disputes fall as
voters are added: 54 with 2 voters, 23 with 5, 4 with 10.

## Measuring author bias

`agree` includes `author` alongside the annotators.

- **Author-vs-annotator agreement clearly below annotator-vs-annotator
  agreement** means the author's (and so the gate's) idea of "necessary"
  differs from other people's. That is a key finding.
- **Systematic patterns in the gap** (for example, the author marks more
  actions `unnecessary`) point to which gate rules are likely too aggressive.

## How much can v1 show?

The primary safety metric is the false unnecessary rate on truly necessary
actions. With zero observed false blocks among *n* necessary cases, the exact
one-sided 95% upper bound is `1 − 0.05^(1/n)`:

| Necessary cases in test | 95% upper bound |
|---|---|
| 41 (the author's count for this test split) | 7.0% |
| 60 | 4.9% |
| 100 | 3.0% |
| 150 | 2.0% |

Even with perfect results, v1 cannot demonstrate the "< 3% false blocking"
target. That needs at least about 100 necessary cases in the frozen test set,
roughly twice v1's size. v1's job is to establish whether people agree on the
task at all, how far the author's judgement drifts from theirs, and a first
unbiased estimate. Growing the test set comes after the pilot has validated
the guide.

## Label distribution (author's labels; for planning only)

| Label | Cases |
|---|---|
| necessary | 75 |
| unnecessary | 159 |
| uncertain | 66 |

These are the author's labels, so they are not a result. Gold labels may
differ substantially.
