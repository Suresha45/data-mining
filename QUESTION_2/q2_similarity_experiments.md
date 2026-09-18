# Q2 similarity experiments

## Representations compared

1. **Raw**: normalized case/whitespace, title word 2-shingles and body character 5-shingles; reference numbers, dates, money, and portal preambles remain.
2. **Clean**: the same decomposition, but regex replacement removes reference numbers, date renderings, money renderings, and known aggregator boilerplate before tokenization.

Score is `0.35 * Jaccard(title shingles) + 0.65 * Jaccard(body shingles)`. The body has the larger weight because it carries more tender scope; title remains an independent signal. Amounts/dates/references are retained as fields for display and future validation, but are not identity tokens.

| representation | SAME mean | DIFFERENT mean | SAME p50 | DIFFERENT p50 |
|---|---:|---:|---:|---:|
| raw | 0.7357 | 0.2891 | 0.7290 | 0.2885 |
| clean | 0.7595 | 0.3321 | 0.7466 | 0.3357 |

Example SAME `N010018`/`N010020`: raw `0.4944`, clean `0.5254`. Example DIFFERENT `N007876`/`N008565`: raw `0.2535`, clean `0.3032`.

False merge cost is **10** and missed duplicate cost is **1**. Minimizing `10*FP + 1*FN` on the labelled set selected threshold **0.56**, with FP=2 and FN=25.

Adopt clean preprocessing, the explicit score, threshold `0.56`, and no direct reference-number match.
