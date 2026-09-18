# Q2 skew and mitigation

Before is raw word 2-shingle retrieval. After replaces known aggregator boilerplate and variable reference/date/money strings, with the same 0.5% frequency cap: 60 notices/token over 12,000 notices.

| metric | before | after |
|---|---:|---:|
| retrieval seconds | 4.424 | 10.005 |
| candidate pairs | 1436916 | 1482078 |
| mean candidates/notice | 119.74 | 123.51 |
| p95 candidates | 188 | 194 |
| p99 candidates | 216 | 228 |
| max candidates | 284 | 295 |
| labelled recall | 0.3267 | 0.3267 |
| SAME recall | 1.0000 | 1.0000 |

The mechanical hotspot is common text: repeated aggregator preambles create shared shingles, while short notices contain little else. That inflates posting-list occupancy and candidate work. The raw JSON also contains portal-level candidate distributions. The highest clean portal means were P095=188.5, P119=185.5, P072=179.636, P186=174.4, and P251=174.0 candidates/notice. Per-portal retrieval time is NOT MEASURED.

Bucket occupancy: before `{'n': 38307, 'min': 1, 'p50': 1, 'p90': 8, 'p95': 14, 'p99': 40, 'max': 60, 'mean': 3.1415929203539825}`; after `{'n': 11509, 'min': 1, 'p50': 4, 'p90': 20, 'p95': 33, 'p99': 54, 'max': 60, 'mean': 8.294986532279086}`.
