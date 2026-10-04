# Simulation results log

Real runs of `python -m simulations.runner --steps` on `simulations/trajectories.jsonl`.
Entries are appended, never edited. "Essential" flags were fixed before the first run.

## Run 1: first simulation

```text
Uncertain policy: execute

trajectory                       before  after minimal  saved  saved%  success_possible
coding-readme-typo                    7      5       4      2   28.6%  True
research-eiffel-facts                 5      4       3      1   20.0%  True
file-edit-log-level                   7      5       4      2   28.6%  True
tool-weather-convert                  6      4       3      2   33.3%  True
debug-import-crash                    8      5       5      3   37.5%  True
database-delete-test-accounts         6      4       4      2   33.3%  True

Total actions: 39 -> 27 (saved 12, 30.8%)
Avoidable actions removed: 12/16
Trajectories still successful: 6/6

coding-readme-typo:
  1. [run ] necessary   NEW_INFORMATION_REQUIRED   (essential) Read README.md
  2. [run ] uncertain   SCOPE_TOO_BROAD            (avoidable) Search the entire repository for typos
  3. [SKIP] unnecessary LOW_GOAL_RELEVANCE         (avoidable) Read package.json
  4. [run ] necessary   DIRECT_GOAL_DEPENDENCY     (essential) Fix 'unnecesary' typo in README
  5. [run ] necessary   VERIFICATION_REQUIRED      (essential) Read README.md
  6. [SKIP] unnecessary GOAL_ALREADY_COMPLETED     (avoidable) Run backend tests
  7. [run ] necessary   DIRECT_GOAL_DEPENDENCY     (essential) Report the result to the user
research-eiffel-facts:
  1. [run ] necessary   DIRECT_GOAL_DEPENDENCY     (essential) Search the web for Eiffel Tower completion year
  2. [SKIP] unnecessary DUPLICATE_ACTION           (avoidable) Search the web for eiffel tower completion year
  3. [run ] necessary   DIRECT_GOAL_DEPENDENCY     (essential) Search the web for Eiffel Tower height
  4. [run ] necessary   NEW_INFORMATION_REQUIRED   (avoidable) Read the full Wikipedia article
  5. [run ] uncertain   DIRECT_GOAL_DEPENDENCY     (essential) Report the result to the user
file-edit-log-level:
  1. [run ] necessary   PREREQUISITE_ACTION        (avoidable) List the config directory
  2. [run ] necessary   PREREQUISITE_ACTION        (essential) Read config/app.yaml
  3. [SKIP] unnecessary DUPLICATE_ACTION           (avoidable) Read config/app.yaml
  4. [run ] necessary   DIRECT_GOAL_DEPENDENCY     (essential) Set log_level to debug
  5. [run ] necessary   VERIFICATION_REQUIRED      (essential) Read config/app.yaml
  6. [SKIP] unnecessary REDUNDANT_VERIFICATION     (avoidable) Read config/app.yaml
  7. [run ] necessary   DIRECT_GOAL_DEPENDENCY     (essential) Report the result to the user
tool-weather-convert:
  1. [run ] necessary   DIRECT_GOAL_DEPENDENCY     (avoidable) Get weather for Tokyo
  2. [run ] uncertain   UNCHANGED_RETRY            (essential) Get weather for Tokyo
  3. [SKIP] unnecessary DUPLICATE_ACTION           (avoidable) Get weather for Tokyo
  4. [run ] necessary   NEW_INFORMATION_REQUIRED   (essential) Convert 22 C to Fahrenheit
  5. [SKIP] unnecessary DUPLICATE_ACTION           (avoidable) Convert 22 C to Fahrenheit
  6. [run ] uncertain   DIRECT_GOAL_DEPENDENCY     (essential) Report the result to the user
debug-import-crash:
  1. [run ] necessary   NEW_INFORMATION_REQUIRED   (essential) Read logs/import.log
  2. [SKIP] unnecessary UNCHANGED_RETRY            (avoidable) Read logs/import.log
  3. [run ] necessary   NEW_INFORMATION_REQUIRED   (essential) Read importer/parse.py
  4. [SKIP] unnecessary SCOPE_TOO_BROAD            (avoidable) Search the entire repository for KeyError
  5. [run ] necessary   NEW_INFORMATION_REQUIRED   (essential) Use row.get('customer_id') and skip rows without it
  6. [run ] necessary   VERIFICATION_REQUIRED      (essential) Run the parser tests
  7. [SKIP] unnecessary REDUNDANT_VERIFICATION     (avoidable) Run the parser tests
  8. [run ] uncertain   DIRECT_GOAL_DEPENDENCY     (essential) Report the result to the user
database-delete-test-accounts:
  1. [run ] necessary   PREREQUISITE_ACTION        (essential) Count test accounts
  2. [SKIP] unnecessary DUPLICATE_ACTION           (avoidable) Count test accounts
  3. [run ] necessary   PREREQUISITE_ACTION        (essential) Delete test accounts
  4. [run ] necessary   STATE_CHANGED              (essential) Count test accounts
  5. [SKIP] unnecessary SCOPE_TOO_BROAD            (avoidable) Dump the whole users table
  6. [run ] necessary   DIRECT_GOAL_DEPENDENCY     (essential) Report the result to the user

Uncertain policy: skip

trajectory                       before  after minimal  saved  saved%  success_possible
coding-readme-typo                    7      4       4      3   42.9%  True
research-eiffel-facts                 5      3       3      2   40.0%  False
file-edit-log-level                   7      5       4      2   28.6%  True
tool-weather-convert                  6      2       3      4   66.7%  False
debug-import-crash                    8      4       5      4   50.0%  False
database-delete-test-accounts         6      4       4      2   33.3%  True

Total actions: 39 -> 22 (saved 17, 43.6%)
Avoidable actions removed: 13/16
Trajectories still successful: 3/6
  ! research-eiffel-facts: essential steps skipped [5]
  ! tool-weather-convert: essential steps skipped [2, 6]
  ! debug-import-crash: essential steps skipped [8]

coding-readme-typo:
  1. [run ] necessary   NEW_INFORMATION_REQUIRED   (essential) Read README.md
  2. [SKIP] uncertain   SCOPE_TOO_BROAD            (avoidable) Search the entire repository for typos
  3. [SKIP] unnecessary LOW_GOAL_RELEVANCE         (avoidable) Read package.json
  4. [run ] necessary   DIRECT_GOAL_DEPENDENCY     (essential) Fix 'unnecesary' typo in README
  5. [run ] necessary   VERIFICATION_REQUIRED      (essential) Read README.md
  6. [SKIP] unnecessary GOAL_ALREADY_COMPLETED     (avoidable) Run backend tests
  7. [run ] necessary   DIRECT_GOAL_DEPENDENCY     (essential) Report the result to the user
research-eiffel-facts:
  1. [run ] necessary   DIRECT_GOAL_DEPENDENCY     (essential) Search the web for Eiffel Tower completion year
  2. [SKIP] unnecessary DUPLICATE_ACTION           (avoidable) Search the web for eiffel tower completion year
  3. [run ] necessary   DIRECT_GOAL_DEPENDENCY     (essential) Search the web for Eiffel Tower height
  4. [run ] necessary   NEW_INFORMATION_REQUIRED   (avoidable) Read the full Wikipedia article
  5. [SKIP] uncertain   DIRECT_GOAL_DEPENDENCY     (essential) Report the result to the user
file-edit-log-level:
  1. [run ] necessary   PREREQUISITE_ACTION        (avoidable) List the config directory
  2. [run ] necessary   PREREQUISITE_ACTION        (essential) Read config/app.yaml
  3. [SKIP] unnecessary DUPLICATE_ACTION           (avoidable) Read config/app.yaml
  4. [run ] necessary   DIRECT_GOAL_DEPENDENCY     (essential) Set log_level to debug
  5. [run ] necessary   VERIFICATION_REQUIRED      (essential) Read config/app.yaml
  6. [SKIP] unnecessary REDUNDANT_VERIFICATION     (avoidable) Read config/app.yaml
  7. [run ] necessary   DIRECT_GOAL_DEPENDENCY     (essential) Report the result to the user
tool-weather-convert:
  1. [run ] necessary   DIRECT_GOAL_DEPENDENCY     (avoidable) Get weather for Tokyo
  2. [SKIP] uncertain   UNCHANGED_RETRY            (essential) Get weather for Tokyo
  3. [SKIP] uncertain   UNCHANGED_RETRY            (avoidable) Get weather for Tokyo
  4. [run ] necessary   NEW_INFORMATION_REQUIRED   (essential) Convert 22 C to Fahrenheit
  5. [SKIP] unnecessary DUPLICATE_ACTION           (avoidable) Convert 22 C to Fahrenheit
  6. [SKIP] uncertain   DIRECT_GOAL_DEPENDENCY     (essential) Report the result to the user
debug-import-crash:
  1. [run ] necessary   NEW_INFORMATION_REQUIRED   (essential) Read logs/import.log
  2. [SKIP] unnecessary UNCHANGED_RETRY            (avoidable) Read logs/import.log
  3. [run ] necessary   NEW_INFORMATION_REQUIRED   (essential) Read importer/parse.py
  4. [SKIP] unnecessary SCOPE_TOO_BROAD            (avoidable) Search the entire repository for KeyError
  5. [run ] necessary   NEW_INFORMATION_REQUIRED   (essential) Use row.get('customer_id') and skip rows without it
  6. [run ] necessary   VERIFICATION_REQUIRED      (essential) Run the parser tests
  7. [SKIP] unnecessary REDUNDANT_VERIFICATION     (avoidable) Run the parser tests
  8. [SKIP] uncertain   DIRECT_GOAL_DEPENDENCY     (essential) Report the result to the user
database-delete-test-accounts:
  1. [run ] necessary   PREREQUISITE_ACTION        (essential) Count test accounts
  2. [SKIP] unnecessary DUPLICATE_ACTION           (avoidable) Count test accounts
  3. [run ] necessary   PREREQUISITE_ACTION        (essential) Delete test accounts
  4. [run ] necessary   STATE_CHANGED              (essential) Count test accounts
  5. [SKIP] unnecessary SCOPE_TOO_BROAD            (avoidable) Dump the whole users table
  6. [run ] necessary   DIRECT_GOAL_DEPENDENCY     (essential) Report the result to the user

```

### Observations

- With the recommended policy (uncertain → execute), the gate removed 12 of 16
  avoidable actions and every trajectory kept all of its essential steps.
- Skipping uncertain actions broke 3 of 6 trajectories, mostly by skipping the
  final report step when goal completion could not be inferred. `uncertain`
  must default to execute.
- Three steps had the right decision but the wrong reason code. These are
  fixed in the next commits:
  - The `DELETE` statement was labelled `PREREQUISITE_ACTION`.
  - The code edit was labelled `NEW_INFORMATION_REQUIRED`, from the lead-following rule.
  - Re-reading a log containing a traceback was labelled `UNCHANGED_RETRY`, because
    file content was mistaken for a failed read.
