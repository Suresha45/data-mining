# Q2 measured results

This is the concise run summary; detailed evidence is in the five section reports and `q2_results/raw_results.json`.

- Method: clean word-2-shingle inverted index, frequency cap 60 notices/token, exact weighted title/body score.
- Corpus: 12,000 notices, 260 portals, 56,516,522 workspace source bytes.
- Labels: 279 SAME, 621 DIFFERENT.
- Cost ratio: false merge 10, missed duplicate 1.
- Candidate work: 1,482,078 clean pairs; mean 123.51 per notice; p50 123, p95 194, p99 228, max 295.
- Candidate recall: 0.3267 overall and 1.0000 on labelled SAME pairs.
- Before/after retrieval: raw 4.424s and 1,436,916 candidates; clean 10.005s and 1,482,078 candidates.
- End-to-end run: 121.735s, under the 1,200-second target.
- Stable-ID append test: PASS (`OPP010018` remained `OPP010018`).
- Plot: `q2_results/plots/similarity_survival.svg`.

The clean mitigation preserved all labelled SAME candidates but did not reduce candidate work versus raw at this cap; that result is retained rather than presented as an optimization success. PostgreSQL B(d) is measured in [q2_database_benchmark.md](q2_database_benchmark.md): indexed `Index Scan` 0.038 ms versus forced sequential `Seq Scan` 3.146 ms on the loaded 95,467-row retrieval index. Candidate scoring and clustering timings are present in the raw JSON; per-portal retrieval time is NOT MEASURED.