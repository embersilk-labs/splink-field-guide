# Reproducing the example

Verified on November 22, 2026 with Splink 4.0.17 on Linux ARM64. CPython 3.12.15 and 3.13.5 each passed all eight tests and produced the results below with the same pinned packages. In a fresh virtual environment, run the following from the repository root.

```sh
python -m pip install -r requirements.txt
python -m pip check
python -m unittest discover -s tests -v
python match_people.py
python match_people.py --compare-all --output-dir results-all
python match_people.py --threshold 0.99 --output-dir results-strict
```

Each run wrote a pair table, a cluster table, and a summary. The results below use the known identities in the [fictional fixture](data/truth.csv).

| Run | Pairs scored | Correctly linked pairs | Incorrectly linked | Missed pairs |
| --- | ---: | --- | --- | --- |
| Default, threshold 0.95 | 5 of 91 | 1–2, 3–4, 5–6 | 9–10 | 11–12 excluded by blocking |
| All pairs, threshold 0.95 | 91 of 91 | 1–2, 3–4, 5–6, 11–12 | 9–10 | None |
| Default blocking, threshold 0.99 | 5 of 91 | 1–2, 3–4 | 9–10 | 5–6 below threshold and 11–12 excluded by blocking |
