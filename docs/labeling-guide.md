# Labeling guide: action necessity (v1)

Thank you for labeling. Your labels become the reference answers for
measuring whether an automatic "necessity gate" blocks actions an AI agent
really needed. Careful, independent judgement matters more than speed.

## What you will see

Each row of the sheet is one **case**:

| Column | Meaning |
|---|---|
| `goal` | What the user asked the agent to do. |
| `current_state` | What the agent knows right now, if anything. |
| `history` | The actions the agent already took, each followed by `->` and the result it got. |
| `proposed_action` | The **next** action the agent wants to take. |
| `label` | **Your answer:** `necessary`, `unnecessary` or `uncertain` (shortcuts: `n`, `u`, `?`). |
| `note` | Optional. One short sentence on why, especially for hard calls. |

Several rows often share the same goal and history with different proposed
actions. Judge each row on its own.

## The question

> If a competent, efficient agent were in this exact situation, would it take
> this next action?

- **`necessary`**: Skipping it would risk the goal or leave the agent without
  information or confirmation it reasonably needs.
- **`unnecessary`**: Skipping it would not hurt the goal. The action repeats
  work, gathers nothing new, goes beyond the goal, or comes after the goal is
  already done.
- **`uncertain`**: Reasonable, careful people could disagree, or the case does
  not give enough information to decide.

`uncertain` is a real answer, not a failure. Use it whenever you would hesitate
to tell an engineer "don't do that". Do **not** use it just to go faster.

## How to judge

Work through these questions in order and stop at the first one that settles
it:

1. **Is the goal already achieved?** Look at the history and its results. If
   so, only reporting back or finishing is necessary. Everything else is
   unnecessary, unless it checks something that is genuinely still unverified.
2. **Has the agent already done this, or something equivalent?** Same tool,
   same target, same arguments, or a trivially reworded search.
   - If **nothing relevant changed** since, it is usually unnecessary.
   - If **something relevant changed** since (a file edited, a record
     deleted, a page submitted), repeating can be necessary.
3. **Did it fail last time?**
   - A failure that will not go away by itself (file not found, invalid key,
     syntax error), retried with nothing changed: unnecessary.
   - A failure that might be temporary (timeout, rate limit, "service
     unavailable"): one retry is usually reasonable. Use uncertain or
     necessary, as you judge.
4. **Does it give the agent something it still needs?** Information not yet
   seen, a prerequisite before changing something, or confirmation that a
   change worked.
5. **Is it proportionate to the goal?** Scanning the whole repository or
   dumping an entire table for a small, specific goal is unnecessary, even if
   it would technically contain the answer.

## Guidance for common patterns

These examples are generic illustrations. None of them appear in the sheet.

| Situation | Typical label |
|---|---|
| Reading a file again with no change in between | unnecessary |
| Reading a file again after editing it, to confirm the edit | necessary (the first confirmation) |
| Confirming the same edit a second time | unnecessary |
| Re-running a passing test suite with no code change | unnecessary |
| Re-running tests after changing code | necessary |
| Re-running tests after changing only documentation | unnecessary |
| Retrying a timed-out request once | uncertain or necessary |
| Retrying the same request after "invalid credentials" | unnecessary |
| Reading the next page of a result that said it was truncated | necessary, if the goal needs the rest |
| Repeating a write that already succeeded (sending a message, creating a record) | unnecessary, and possibly harmful |
| Opening a link or file that an earlier result pointed to | depends: necessary if the goal still needs it, unnecessary if the answer is already known |
| Wide search for a narrow goal | unnecessary |
| Wide search when the goal itself is wide ("everywhere", "all usages") | necessary |
| Finishing or reporting when the goal is done | necessary |

## Things not to judge

- **Safety or correctness.** Do not consider whether the action is safe,
  allowed, or will succeed. Only consider whether it is needed.
- **Your own preferred plan.** If the action is a reasonable step towards the
  goal, do not mark it unnecessary just because you would have done something
  else first.
- **Cost size.** A cheap redundant action is still unnecessary. An expensive
  but needed one is still necessary.

## Independence rules

- Label alone. Do not discuss cases with other annotators until everyone has
  handed in their sheet.
- Do not look at any existing labels in the repository
  (`benchmarks/v1/labels/`), the gate's output, or its source code while
  labeling.
- If a case seems broken (contradictory or unreadable), label it `uncertain`
  and say so in `note`.

## Workflow

1. The coordinator runs `python -m benchmarks.labeling export --out sheet.csv`
   and sends you `sheet.csv`.
2. Open it in a spreadsheet program, fill in `label` (and `note` where
   useful), and save it as CSV.
3. Send it back. The coordinator imports it with
   `python -m benchmarks.labeling import filled.csv --annotator <your-name>`.

Expect roughly 30 to 45 seconds per case. Split the work into sessions of
about an hour, because labeling quality drops when tired.

## For the coordinator

| Step | Command |
|---|---|
| Agreement between all annotators (including the author's own labels, for bias analysis) | `python -m benchmarks.labeling agree --show-disagreements` |
| Build the gold sets | `python -m benchmarks.labeling gold` |

How `gold` treats each case:

- **Unanimous:** the shared label stands.
- **Mixed with `uncertain`:** becomes `uncertain`.
- **`necessary` vs `unnecessary`:** listed as *disputed*. Resolve it by
  discussion and record the outcome in `benchmarks/v1/adjudication.jsonl`
  (`{"id": ..., "label": ..., "note": ...}`).
- **The author's labels never count towards gold.**

Splitting:

- Cases are split by scenario (`context_id`), so variants of one scenario
  never appear in both sets. The default sends 60% of scenarios to the
  **test** set.
- `gold-test.jsonl` is **frozen**. Evaluate on it once per evaluator version,
  never tune on it, and record every run in `benchmarks/RESULTS.md`.
