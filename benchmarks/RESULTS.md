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
