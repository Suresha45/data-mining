# Q2 final answers: audited

All numbers below were checked against the current implementation, `q2_results/raw_results.json`, and the section reports. The implemented frequency cap is **60 notices per token**, from `max(10, int(12000 * 0.005))`; therefore it is **0.5%**, not 2%.

## A(a) Define similarity

Two notices are similar when the clean weighted score is at least **0.56**:

`score = 0.35 * Jaccard(title word-2-shingles) + 0.65 * Jaccard(body character-5-shingles)`.

The two measured representation choices were raw and clean. Raw normalized case and whitespace but retained portal preambles, reference numbers, dates, and money strings. Clean replaced reference numbers, dates, money formats, and named aggregator boilerplate before generating shingles. Titles and bodies were scored separately; amounts, dates, and references remain fields for validation/display, not identity tokens.

| representation | SAME mean | DIFFERENT mean | SAME p50 | DIFFERENT p50 |
|---|---:|---:|---:|---:|
| raw | 0.7357 | 0.2891 | 0.7290 | 0.2885 |
| clean | 0.7595 | 0.3321 | 0.7466 | 0.3357 |

Measured examples from `labelled_pairs.csv`:

- SAME `N010018`/`N010020`: raw **0.4944**, clean **0.5254**.
- DIFFERENT `N007876`/`N008565`: raw **0.2535**, clean **0.3032**.

False merge cost is **10** and missed duplicate cost is **1**. Minimizing `10*FP + 1*FN` selected threshold **0.56**, with **2 FP** and **25 FN** on the 900 labelled pairs. The adopted choice is clean preprocessing with the explicit weighted score and threshold.

## A(b) Reduced representation and estimation error

The selected reduced representation is **1024 MinHash components** over clean word-2-shingle sets. The requirement was absolute error at most $0.05$ with $0.05$ approximate failure probability. The bound

`m >= ln(2 / delta) / (2 * epsilon^2)`

requires **738** components, so 1024 was selected rather than a conventional arbitrary size.

Measured labelled-pair estimator errors:

| signatures | mean absolute error | p95 absolute error | largest observed failure |
|---:|---:|---:|---|
| 128 | 0.034594 | 0.086812 | `N001314/N003288` |
| 512 | 0.019541 | 0.049172 | `N003720/N006775` |
| 1024 | 0.016094 | 0.040017 | `N000078/N006886` |

The 128-component estimator exceeds the p95 target; 1024 has measured p95 absolute error **0.040017**.

## A(c) Sublinear retrieval and risk pricing

Candidate retrieval uses a clean word-2-shingle inverted index. A token is indexed only if it occurs in at most **60 of 12,000 notices = 0.5%**. Candidates are then scored exactly. This avoids all-pairs comparison. The measured survival curve is [similarity_survival.svg](q2_results/plots/similarity_survival.svg).

| mode | indexed buckets | candidate pairs | mean | p50 | p95 | p99 | max | labelled-pair survival | SAME survival | retrieval time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| raw | 38,307 | 1,436,916 | 119.743 | 119 | 188 | 216 | 284 | 0.3267 | 1.0000 | 4.424s |
| clean | 11,509 | 1,482,078 | 123.507 | 123 | 194 | 228 | 295 | 0.3267 | 1.0000 | 10.005s |

The operating point is the clean representation, cap 60, and score threshold 0.56. The asymmetric cost ratio is **10:1** against false merges, so the threshold favors avoiding false merges even though it leaves 25 labelled-pair misses. The clean mitigation increased candidate work by **45,162 pairs** (**3.14%**) and retrieval time by **5.581s**, while preserving **100% SAME-pair candidate survival**.

## B(d) Database design and access method

The relational design uses versioned `notices`, `notice_signatures`, `lsh_buckets`, `candidate_edges`, `opportunities`, and `opportunity_members`. The actual clean retrieval index was loaded into PostgreSQL 16.15, schema `q2`, table `q2.token_index`: **95,467 posting rows** and **11,509 distinct tokens**.

Application lookup: `SELECT notice_id FROM q2.token_index WHERE token = $1`.

| mode | access path | index | rows examined/returned | rows filtered | EXPLAIN ANALYZE execution time |
|---|---|---|---:|---:|---:|
| selected | Index Scan | `q2_token_index_token_idx` | 60 returned from posting list | 0 | **0.038 ms** |
| rejected, forced | Seq Scan | none | 95,467 examined; 60 returned | 95,407 | **3.146 ms** |

The index wins physically because equality lookup navigates directly to the token posting list. The sequential alternative scans the complete 95,467-row relation and filters row by row. Full evidence is in [q2_database_benchmark.md](q2_database_benchmark.md) and [postgres_benchmark.json](q2_results/postgres_benchmark.json).

Stable identity is unchanged: the persisted opportunity anchor is the minimum persistent notice ID, producing `OPP` plus that anchor. The actual append test passed: `OPP010018` remained `OPP010018` after adding `N999999`.

## B(e) Skew and mitigation

The measured before/after retrieval distributions were:

| metric | raw before | clean after |
|---|---:|---:|
| retrieval time | 4.424s | 10.005s |
| candidate pairs | 1,436,916 | 1,482,078 |
| mean candidates/notice | 119.743 | 123.507 |
| p50 | 119 | 123 |
| p95 | 188 | 194 |
| p99 | 216 | 228 |
| max | 284 | 295 |
| overall labelled-pair survival | 0.3267 | 0.3267 |
| labelled SAME-pair survival | 1.0000 | 1.0000 |

Bucket occupancy changed as follows:

- Raw: n=38,307, p50=1, p90=8, p95=14, p99=40, max=60, mean=3.142.
- Clean: n=11,509, p50=4, p90=20, p95=33, p99=54, max=60, mean=8.295.

The highest clean portal-level candidate means in the raw result are P095 **188.5**, P119 **185.5**, P072 **179.636**, P186 **174.4**, and P251 **174.0** candidates/notice. Per-portal retrieval time is not measured, but portal-level candidate distributions are measured.

The mitigation is exact and measured: replace reference-number, date, money, and named aggregator-boilerplate text before tokenization, then apply the same cap-60 frequency filter. The mechanical hotspot occurs because repeated aggregator preambles make the same word shingles appear across many notices; short notices contain little non-boilerplate text, so their candidate sets are dominated by shared postings. The measured cost of this mitigation on this corpus is **+45,162 candidate pairs (+3.14%)** and **+5.581s retrieval time**, with no loss in labelled SAME-pair candidate recall.

## Performance and audit status

The raw measured phase timings are: load/profile **0.266s**, label scoring **3.005s**, raw retrieval **4.424s**, clean retrieval **10.005s**, indexing/database **18.594s**, candidate scoring **44.343s**, clustering **0.043s**, and total end-to-end **121.735s**. This is below the 1,200-second nightly target. The only remaining absent measurement is **per-portal retrieval time**; portal-level candidate counts, phase timings, PostgreSQL timings, and stable-ID evidence are present.