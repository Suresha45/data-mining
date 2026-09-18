# Q2 final answers

## A(a)

Similar means clean weighted Jaccard >= **0.56**:

`0.35 * Jaccard(title word-2-shingles) + 0.65 * Jaccard(body character-5-shingles)`.

Raw retained reference numbers, dates, money strings, and portal boilerplate. Clean replaced those variable/noisy patterns before tokenization. Label measurements were raw SAME mean **0.7357**, DIFFERENT mean **0.2891**; clean SAME mean **0.7595**, DIFFERENT mean **0.3321**. Example SAME `N010018/N010020`: raw **0.4944**, clean **0.5254**. Example DIFFERENT `N007876/N008565`: raw **0.2535**, clean **0.3032**. False merge cost is **10**, missed duplicate cost **1**; threshold optimization gave **2 FP** and **25 FN**.

## A(b)

Use **1024 MinHash components**. For epsilon=$0.05$, delta=$0.05$, the bound requires **738** components. Measured mean/p95 absolute errors were: 128 = **0.034594/0.086812**, 512 = **0.019541/0.049172**, 1024 = **0.016094/0.040017**. The largest listed failures were `N001314/N003288`, `N003720/N006775`, and `N000078/N006886`, respectively.

## A(c)

Use clean word-2-shingle inverted-index retrieval, exact candidate scoring, and a token frequency cap of **60/12,000 = 0.5%**. The survival plot is [similarity_survival.svg](q2_results/plots/similarity_survival.svg).

| mode | candidate pairs | mean | p50/p95/p99/max | labelled survival | SAME survival | time |
|---|---:|---:|---|---:|---:|---:|
| raw | 1,436,916 | 119.743 | 119/188/216/284 | 0.3267 | 1.0000 | 4.424s |
| clean | 1,482,078 | 123.507 | 123/194/228/295 | 0.3267 | 1.0000 | 10.005s |

The 10:1 false-merge/missed-duplicate cost ratio supports threshold **0.56**. Clean preprocessing cost **45,162 additional candidate pairs (+3.14%)** and **5.581s** retrieval time while retaining 100% labelled SAME survival.

## B(d)

The versioned relational design uses notices, signatures/buckets, candidate edges, opportunities, and opportunity members. The actual clean index was loaded into PostgreSQL 16.15 as `q2.token_index`: **95,467 rows**, **11,509 distinct tokens**. `q2_token_index_token_idx` produced an `Index Scan`: **60 rows returned**, **0.038 ms**. The forced `Seq Scan` examined **95,467 rows**, returned **60**, filtered **95,407**, and took **3.146 ms**. See [q2_database_benchmark.md](q2_database_benchmark.md).

The indexed path wins because equality lookup navigates directly to a posting list; sequential access scans the whole relation. Stable ID remains the minimum persistent notice anchor: `OPP010018` stayed `OPP010018` after adding `N999999`.

## B(e)

The mitigation replaces reference-number, date, money, and named aggregator-boilerplate patterns before tokenization, then applies the **0.5%/60-token** cap. Before versus after:

- Runtime: **4.424s -> 10.005s**.
- Candidate pairs: **1,436,916 -> 1,482,078**.
- Candidate distribution mean/p50/p95/p99/max: **119.743/119/188/216/284 -> 123.507/123/194/228/295**.
- Bucket occupancy mean/p50/p95/p99/max: **3.142/1/14/40/60 -> 8.295/4/33/54/60**.
- Overall labelled-pair survival: **0.3267 -> 0.3267**.
- Labelled SAME-pair survival: **1.0000 -> 1.0000**.
- Highest clean portal candidate means: P095 **188.5**, P119 **185.5**, P072 **179.636**, P186 **174.4**, P251 **174.0** candidates/notice.

The hotspot occurs because repeated aggregator preambles create shared shingles and short notices contain little other text, inflating posting-list overlap. Per-portal retrieval time is the only portal-level value not measured.

## Performance

Measured phases in the raw result JSON: load/profile **0.266s**, label scoring **3.005s**, raw retrieval **4.424s**, clean retrieval **10.005s**, indexing/database **18.594s**, candidate scoring **44.343s**, clustering **0.043s**, total **121.735s**. The 1,200-second target is met.