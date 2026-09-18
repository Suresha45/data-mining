# Q2 retrieval experiments

The selected retrieval is a bounded-frequency inverted index over clean word 2-shingles. A token is indexed only when document frequency is at most 0.5% of the 12,000-notice corpus: `60 / 12000 = 0.005`. It avoids all-pairs comparison.

## MinHash estimator

The requirement is absolute error <= 0.05 with approximate 95% confidence. The conservative bound `m >= ln(2/delta)/(2 epsilon^2)` gives `m >= 738`, so **1024** is selected; 128 and 512 are measured comparators.

| signatures | mean absolute error | p95 absolute error | largest observed failure |
|---:|---:|---:|---|
| 128 | 0.034594 | 0.086812 | N001314/N003288 |
| 512 | 0.019541 | 0.049172 | N003720/N006775 |
| 1024 | 0.016094 | 0.040017 | N000078/N006886 |

## Candidate retrieval

| mode | indexed buckets | candidate pairs | mean/notice | p50 | p95 | p99 | max | labelled survival | SAME survival | seconds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| raw | 38307 | 1436916 | 119.74 | 119 | 188 | 216 | 284 | 0.3267 | 1.0000 | 4.419 |
| clean | 11509 | 1482078 | 123.51 | 123 | 194 | 228 | 295 | 0.3267 | 1.0000 | 10.001 |

The survival plot is `q2_results/plots/similarity_survival.svg`; the selected score threshold is marked.

Measured phase timings from the raw result JSON (seconds): load/profile 0.266, label scoring 3.005, raw retrieval 4.424, clean retrieval 10.005, indexing/database 18.594, candidate scoring 44.343, clustering 0.043, total 121.735.
