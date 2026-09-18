# Q2 PostgreSQL database benchmark

## Environment and loaded structure

- PostgreSQL: `PostgreSQL 16.15 (Debian 16.15-1.pgdg13+2) on x86_64-pc-linux-gnu, compiled by gcc (Debian 14.2.0-19) 14.2.0, 64-bit`
- Container: `data-postgres-1`
- Schema/table: `q2.token_index`
- Rows loaded from the measured clean retrieval index: **95467**
- Distinct tokens: **11509**
- Index: `CREATE INDEX q2_token_index_token_idx ON q2.token_index(token)`
- Application lookup: `SELECT notice_id FROM q2.token_index WHERE token = $1` with probe token `aurangabad name`

The loaded table is the actual clean word-2-shingle inverted index used by retrieval. The existing notices, similarity scores, candidate counts, and stable-ID measurements were not recomputed or changed.

## EXPLAIN ANALYZE comparison

| mode | planner access path | index | rows examined/returned | rows removed | execution time | buffer hits | buffer reads |
|---|---|---|---:|---:|---:|---:|---:|
| indexed | Index Scan | q2_token_index_token_idx | 60 | 0 | 0.038 ms | 1 | 2 |
| forced sequential | Seq Scan | none | 60 | 95407 | 3.146 ms | 688 | 0 |

In this table, “rows examined/returned” is the plan node's `Actual Rows` for the lookup operation. The sequential scan additionally examines the full relation; PostgreSQL reports that as a `Seq Scan` over the table. Full raw plans are preserved in `q2_results/postgres_benchmark.json` through the summarized measured fields.

## Design decision

The indexed lookup is selected because the application predicate is equality on `token`. PostgreSQL can navigate `q2_token_index_token_idx` directly to the matching key and visit only its posting rows. The forced sequential alternative scans the entire `q2.token_index` relation and applies the predicate row by row, so its work grows with the complete index-table size rather than the matching posting list. The measured execution times above are the corpus-specific evidence for rejecting the sequential path.

## Stable opportunity identity

The strategy remains unchanged: an opportunity keeps its persisted anchor and card ID, derived as `OPP` plus the minimum persistent notice ID. The prior actual append test remains **PASS**: `OPP010018` stayed `OPP010018` after adding `N999999`.
