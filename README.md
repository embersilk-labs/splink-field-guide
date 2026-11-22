# Splink Field Guide

Alice Johnson and Alise Johnson share a birth date and postcode. Two entries for Priya Shah agree on all four fields. Which records would you merge? In this fictional dataset, Alice and Alise are the same person. The two Priyas are different people, yet their pair earns the highest match score.

This guide walks through **record linkage with Splink 4** in Python. The task is deciding which rows refer to the same person when there is no shared person ID. Run Splink locally with DuckDB on 14 fictional records, inspect the proposed matches, then change one rule at a time to see which mistakes you can fix.

The walkthrough uses **Splink 4.0.17**. Its `Linker` takes the DuckDB backend through the `db_api` argument. In Splink 5, you register the input with the backend first, then pass the registered table to `Linker`. Install the pinned requirements below to run this example. [Splink 5 linker API](https://github.com/moj-analytical-services/splink/blob/v5.0.0/splink/internals/linker.py)

## Run the example

Use **Python 3.12 or 3.13**. Clone or download this repository and open a terminal in the directory containing `match_people.py`. On Linux or macOS, use the command for your installed version (`python3.12` or `python3.13`) to create the environment, then activate it.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

In Windows PowerShell, use `py -3.12` or `py -3.13` to select the interpreter.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the pinned packages and run the example. The data is included, and the example runs without an API key or database account.

```bash
python -m pip install -r requirements.txt
python match_people.py
```

The default run prints this summary.

```text
Records: 14
Candidate pairs: 5 / 91 (surname OR postcode blocking)
Threshold: 0.95
Accepted pairs:
  1-2: 0.999959
  3-4: 0.997392
  5-6: 0.986061
  9-10: 0.999997
True matches: 1-2, 3-4, 5-6
False positives: 9-10
False negatives: 11-12
Missed by blocking: 11-12
Missed by score: none
Wrote results/pairs.csv, clusters.csv, summary.json
```

## Follow a record from input to match

1. **Prepare the columns.** The script loads IDs and postcodes as text so `02139` keeps its leading zero. It trims and lowercases names, preserves missing values, and uses the ISO-formatted birth dates supplied in the data. [Input records](data/people.csv)
2. **Choose which pairs to compare.** This step is called *blocking*. A pair qualifies if its records share an exact surname **or** an exact postcode. That leaves five of the 91 possible pairs. Elena Martin and Elena Martn have different postcodes, so their pair never reaches the scorer.
3. **Score each candidate.** Splink combines the evidence from first name, surname, birth date and postcode. The default run accepts a pair at a score of `0.95` or higher. A difference of one letter counts as evidence of a near match in a name. The two Sam Lee records share a name and postcode. Their different birth dates bring the score below the threshold. [Model and comparison rules](match_people.py)
4. **Check the proposed links.** After scoring, the script reads a separate file that names the fictional person behind each record. This lets you see which links were correct, which joined two different people, and which duplicates the pipeline missed. [Identity labels](data/truth.csv)

| Record IDs | Evidence in the records | Default result |
|---|---|---|
| 1–2 | Alice / Alise Johnson, same birth date and postcode | Correct match |
| 3–4 | Robert / Rob Chen, same birth date and postcode | Correct match |
| 5–6 | Maria Garcia / Garica, same birth date and postcode | Correct match |
| 7–8 | Two people named Sam Lee, same postcode, different birth dates | Correctly kept separate |
| 9–10 | Two people named Priya Shah, identical on all four fields | False match |
| 11–12 | Elena Martin / Martn, same birth date, different postcode | Missed duplicate |
| 13 and 14 | Noah Kim and Eva Lopez each appear once. Eva's postcode is missing. | Each stays in a group of one |

The name comparison counts insertions, deletions and substitutions. Swapping the middle letters in Garcia/Garica takes two edits under this rule, and Robert/Rob also falls outside the one-edit name match. Agreement on other fields carries those pairs.

## Two experiments

**1. Give Elena a chance to match.** Run the same model and threshold, but let every pair reach the scorer.

```bash
python match_people.py --compare-all --output-dir results-all
```

The run now scores all 91 pairs, including 11–12. Elena's pair scores **0.985919**, above the original threshold. The default run lost her during candidate selection. All four intended duplicates are now found, and the Priyas still match incorrectly. Comparing every pair is practical here because the dataset is tiny. With `n` records the number of pairs grows as `n * (n - 1) / 2`.

**2. Raise the threshold.** Go back to the original blocking rules and accept scores of at least `0.99`.

```bash
python match_people.py --threshold 0.99 --output-dir results-strict
```

Maria's pair now appears under `missed_by_score`. Elena's still appears under `missed_by_blocking`. The Priya pair still clears the threshold. To tell the two Priyas apart, you'd need a distinguishing piece of evidence.

## Inspect the generated files

Each run writes three files under `--output-dir`, which defaults to `results/`. Rerunning into the same directory overwrites those three files.

| File | What to look for |
|---|---|
| `pairs.csv` | Every candidate pair, its score rounded to six decimals, and whether it passed. The decision uses the unrounded score. |
| `clusters.csv` | The predicted group for every input record. Accepted links connect the records in a group, so a false link can join two people. Each group is labeled with its smallest numeric record ID. |
| `summary.json` | Correct matches, false positives and false negatives. Compare `missed_by_blocking` with `missed_by_score` across runs. |

## How to interpret a score

The model starts with a hand-set prior match probability of `0.01`. For each field, `m` is the assumed probability of seeing a comparison outcome in a true match, and `u` is the same probability for two different people. Their ratio determines how much that outcome changes the match odds. For example, the model treats an exact birth-date match as much stronger evidence than an exact postcode match. A missing value contributes no evidence for that field.

| Field | Comparison outcomes, in order | m | u |
|---|---|---|---|
| First name | Exact, one edit, other | 0.85, 0.10, 0.05 | 0.02, 0.03, 0.95 |
| Surname | Exact, one edit, other | 0.90, 0.08, 0.02 | 0.01, 0.02, 0.97 |
| Birth date | Exact, other | 0.999, 0.001 | 0.005, 0.995 |
| Postcode | Exact, other | 0.80, 0.20 | 0.02, 0.98 |

These are teaching assumptions. For your own data, estimate the parameters on a representative sample and evaluate the proposed links on separately labeled pairs. Choose fields that contribute distinct evidence. City and postcode, for example, can repeat much of the same information. Check both the cost of merging different people and the cost of missing duplicates when choosing a threshold. [Splink parameter-estimation tutorial](https://moj-analytical-services.github.io/splink4_legacy_docs/demos/tutorials/04_Estimating_model_parameters.html)

## Verify the example

```bash
python -m pip check
python -m unittest discover -s tests -v
```

The eight tests cover the intentional errors, the effects of changing the rules, and details like leading-zero postcodes and keeping singletons. The environment pins Splink 4.0.17, DuckDB 1.4.3, pandas 2.2.3, and NumPy 2.2.6. [Dependency versions](requirements.txt) · [Verification details](VERIFICATION.md)

## Further reading

- [Splink 4 getting started](https://moj-analytical-services.github.io/splink4_legacy_docs/getting_started.html)
- [Customizing Splink comparisons](https://moj-analytical-services.github.io/splink4_legacy_docs/topic_guides/comparisons/customising_comparisons.html)
- [Intellectually Curious episode on Splink](https://www.youtube.com/watch?v=hyq7AHtVLOk)

Made by [Embersilk](https://embersilk.com). [MIT license](LICENSE)
