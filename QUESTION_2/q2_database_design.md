# Q2 database design

A PostgreSQL deployment would use `notices`, `notice_signatures`, `lsh_buckets`, `candidate_edges`, `opportunities`, and `opportunity_members`. Each retrieval run has a representation/version key; candidate edges and memberships are append-only until a version is promoted.

The measured PostgreSQL implementation loaded the actual clean word-2-shingle retrieval index into `q2.token_index` with 95,467 posting rows and 11,509 distinct tokens. The application lookup is `SELECT notice_id FROM q2.token_index WHERE token = $1`, indexed by `q2_token_index_token_idx`.

The complete measured PostgreSQL setup, SQL, plans, row counts, buffer activity, and timings are in [q2_database_benchmark.md](q2_database_benchmark.md). The selected indexed plan was `Index Scan`, returning 60 rows in **0.038 ms**. The forced alternative was `Seq Scan`, examining all 95,467 rows, returning 60, in **3.146 ms**. The index is appropriate because equality lookup navigates directly to the posting list; the sequential alternative scans the complete relation.

Stable card ID is `OPP` plus the minimum persistent notice ID in an opportunity, stored as the opportunity anchor. The actual append test used `['N010018', 'N010020']` plus `N999999`: `OPP010018` remained `OPP010018`; passed=True.
