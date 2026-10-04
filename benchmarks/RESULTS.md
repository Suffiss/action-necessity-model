# Benchmark results log

Each entry is a real run of `python -m benchmarks.runner` on `benchmarks/dataset.jsonl`.
Entries are appended, never edited, so regressions and overfitting stay visible.

## Run 1: baseline evaluator (before any benchmark-driven change)

Labels were fixed before this run. This is the only run where the dataset
was fully unseen by the evaluator's author when the rules were written.

```text
Cases: 30
Accuracy: 0.77

label        precision  recall    f1  support
necessary         0.82    0.75  0.78       12
unnecessary       0.92    0.79  0.85       14
uncertain         0.43    0.75  0.55        4

False unnecessary rate:            0.0%
Unnecessary action detection rate: 78.6%
Potential action reduction rate:   40.0%
Uncertain rate:                    23.3%

Confusion matrix (rows = expected, columns = predicted):
               necessary unnecessary   uncertain
necessary              9           0           3
unnecessary            2          11           1
uncertain              0           1           3

Accuracy by category:
  browser        3/5
  coding         3/5
  database       5/5
  filesystem     5/5
  research       3/5
  tool_calling   4/5

Misclassified (7):
  coding-04        expected=unnecessary  predicted=necessary    VERIFICATION_REQUIRED
  coding-05        expected=necessary    predicted=uncertain    LOW_GOAL_RELEVANCE
  research-02      expected=necessary    predicted=uncertain    LOW_GOAL_RELEVANCE
  research-03      expected=unnecessary  predicted=necessary    DIRECT_GOAL_DEPENDENCY
  browser-03       expected=necessary    predicted=uncertain    INSUFFICIENT_CONTEXT
  browser-05       expected=uncertain    predicted=unnecessary  DUPLICATE_ACTION
  tool-04          expected=unnecessary  predicted=uncertain    DUPLICATE_ACTION
```

### Failure analysis

| Case | Expected → predicted | Root cause | Generalizable? |
|---|---|---|---|
| coding-04 | unnecessary → necessary | `LICENSE` has no extension, so its edit was treated as a code change that tests should verify | Yes: extension-less doc filenames |
| coding-05 | necessary → uncertain | Continuing a truncated read with new line ranges produced no supporting signal | Yes: pagination / continuation |
| research-02 | necessary → uncertain | Following a URL returned by the previous search shares no words with the goal | Yes: follow-up on a lead from history |
| browser-03 | necessary → uncertain | Relevance was computed against the whole two-part goal (0.25), not the part the action serves | Yes: per-clause relevance |
| tool-04 | unnecessary → uncertain | All duplicate writes get half the duplicate penalty, even when the arguments carry the full payload | Yes: penalty depends on payload visibility |
| research-03 | unnecessary → necessary | A reworded search after the answer was already found; needs answer detection | Not with current lexical tools |
| browser-05 | uncertain → unnecessary | Duplicate check while the state says deploy status is unknown; label itself is debatable | No clean rule; left as is |

**Weakest failure mode:** necessary actions left uncertain (3 of 12, necessary
recall 0.75), all caused by relevance being purely lexical against the goal.
No necessary action was blocked (false unnecessary rate 0%), but the gate
cleared too little.

## Run 2: after Phase 9 fixes (in-sample)

Changes, each a separate commit with unit tests on new scenarios:

1. Extension-less doc files (`LICENSE`, `AUTHORS`, …) count as documentation.
2. Goal relevance uses the best-matching goal clause.
3. Paging through explicitly truncated output is a new-information signal.
4. Acting on a file/URL surfaced by an earlier result is a new-information signal.
5. Duplicate writes get the full penalty when their arguments carry the payload.

**Caveat:** these fixes were motivated by Run 1's failures on the same 30
cases, so this run is in-sample and optimistic. See Run 3 for held-out numbers.

```text
Cases: 30
Accuracy: 0.90

label        precision  recall    f1  support
necessary         0.92    1.00  0.96       12
unnecessary       0.92    0.86  0.89       14
uncertain         0.75    0.75  0.75        4

False unnecessary rate:            0.0%
Unnecessary action detection rate: 85.7%
Potential action reduction rate:   43.3%
Uncertain rate:                    13.3%

Confusion matrix (rows = expected, columns = predicted):
               necessary unnecessary   uncertain
necessary             12           0           0
unnecessary            1          12           1
uncertain              0           1           3

Accuracy by category:
  browser        4/5
  coding         4/5
  database       5/5
  filesystem     5/5
  research       4/5
  tool_calling   5/5

Misclassified (3):
  coding-04        expected=unnecessary  predicted=uncertain    LOW_GOAL_RELEVANCE
  research-03      expected=unnecessary  predicted=necessary    DIRECT_GOAL_DEPENDENCY
  browser-05       expected=uncertain    predicted=unnecessary  DUPLICATE_ACTION
```

Remaining misses are deliberately not patched:

- **coding-04:** the LICENSE-edit test run now comes out uncertain instead of necessary. That is safer, but still not the `unnecessary` the label expects.
- **research-03:** detecting that an answer is already in hand would require semantic answer extraction.
- **browser-05:** the label itself is debatable.

## Run 3: held-out set (12 cases, run once, no tuning)

`benchmarks/holdout.jsonl` was written and committed before this run.

```text
Cases: 12
Accuracy: 0.83

label        precision  recall    f1  support
necessary         0.71    1.00  0.83        5
unnecessary       1.00    1.00  1.00        4
uncertain         1.00    0.33  0.50        3

False unnecessary rate:            0.0%
Unnecessary action detection rate: 100.0%
Potential action reduction rate:   33.3%
Uncertain rate:                    8.3%

Confusion matrix (rows = expected, columns = predicted):
               necessary unnecessary   uncertain
necessary              5           0           0
unnecessary            0           4           0
uncertain              2           0           1

Accuracy by category:
  browser        1/2
  coding         2/2
  database       2/2
  filesystem     2/2
  research       1/2
  tool_calling   2/2

Misclassified (2):
  holdout-research-01 expected=uncertain    predicted=necessary    NEW_INFORMATION_REQUIRED
  holdout-browser-01 expected=uncertain    predicted=necessary    STATE_CHANGED
```

Both held-out misses are uncertain → necessary: the gate let optional work
through rather than blocking anything. `holdout-research-01` shows a real cost
of the lead-following rule (Run 2, change 4). It cleared a primary-source check
even though the answer was already in hand.

### Summary so far

| Set | Cases | Accuracy | False unnecessary | Unnecessary detected | Potential reduction |
|---|---|---|---|---|---|
| Run 1: dev, baseline | 30 | 0.77 | 0.0% | 78.6% | 40.0% |
| Run 2: dev, after fixes (in-sample) | 30 | 0.90 | 0.0% | 85.7% | 43.3% |
| Run 3: held-out | 12 | 0.83 | 0.0% | 100.0% | 33.3% |

These sets are small. A single case moves held-out accuracy by about 8 points,
so these numbers are indicative, not conclusive.
