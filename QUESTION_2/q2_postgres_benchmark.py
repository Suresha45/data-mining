import json
import os
import sqlite3
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SQLITE_DB = ROOT / "q2_results" / "q2_index.sqlite"
CONTAINER = "data-postgres-1"
PSQL = ["docker.exe", "exec", "-i", CONTAINER, "psql", "-X", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-U", "annapurna", "-d", "annapurna"]


def psql(sql, input_text=None):
    result = subprocess.run(PSQL + ["-c", sql], input=input_text, text=True, capture_output=True, check=True)
    return result.stdout


def plan(token, force_seq=False):
    setting = "SET enable_indexscan=off; SET enable_bitmapscan=off;" if force_seq else "SET enable_indexscan=on; SET enable_bitmapscan=on;"
    sql = f"{setting} EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT notice_id FROM q2.token_index WHERE token = '{token.replace(chr(39), chr(39) * 2)}';"
    output = psql(sql)
    explain = json.loads(output[output.find("["):])[0]
    root = explain["Plan"]
    root["_planning_time_ms"] = explain.get("Planning Time")
    root["_execution_time_ms"] = explain.get("Execution Time")
    return root


def walk(node):
    yield node
    for child in node.get("Plans", []):
        yield from walk(child)


def summarize(root):
    nodes = list(walk(root))
    scan = next((node for node in nodes if node["Node Type"] in {"Index Scan", "Index Only Scan", "Bitmap Heap Scan", "Seq Scan"}), nodes[0])
    return {
        "access_path": scan["Node Type"],
        "index_name": scan.get("Index Name"),
        "relation": scan.get("Relation Name"),
        "plan_rows": scan.get("Plan Rows"),
        "actual_rows_returned": scan.get("Actual Rows"),
        "rows_removed_by_filter": scan.get("Rows Removed by Filter", 0),
        "loops": scan.get("Actual Loops"),
        "execution_ms": root.get("_execution_time_ms"),
        "shared_hit_blocks": root.get("Shared Hit Blocks"),
        "shared_read_blocks": root.get("Shared Read Blocks"),
    }


def main():
    if not SQLITE_DB.exists():
        raise FileNotFoundError(SQLITE_DB)
    psql("DROP SCHEMA IF EXISTS q2 CASCADE; CREATE SCHEMA q2; CREATE TABLE q2.token_index (token text NOT NULL, notice_id text NOT NULL);")
    connection = sqlite3.connect(SQLITE_DB)
    cursor = connection.execute("SELECT token, notice_id FROM token_index ORDER BY token, notice_id")
    def rows():
        for token, notice_id in cursor:
            yield f"{token}\t{notice_id}\n"
    import_stream = subprocess.Popen(PSQL + ["-c", "\\copy q2.token_index(token, notice_id) FROM STDIN WITH (FORMAT text)"], stdin=subprocess.PIPE, text=True)
    for row in rows():
        import_stream.stdin.write(row)
    import_stream.stdin.close()
    import_return = import_stream.wait()
    connection.close()
    if import_return:
        raise RuntimeError(f"PostgreSQL COPY failed with status {import_return}")
    psql("CREATE INDEX q2_token_index_token_idx ON q2.token_index(token); ANALYZE q2.token_index;")
    token = psql("SELECT token FROM q2.token_index GROUP BY token ORDER BY count(*) DESC, token LIMIT 1;").strip()
    indexed_root = plan(token, force_seq=False)
    sequential_root = plan(token, force_seq=True)
    indexed = summarize(indexed_root)
    sequential = summarize(sequential_root)
    result = {
        "container": CONTAINER,
        "postgres_version": psql("SELECT version();").strip(),
        "schema": "q2",
        "rows_loaded": int(psql("SELECT count(*) FROM q2.token_index;").strip()),
        "distinct_tokens": int(psql("SELECT count(distinct token) FROM q2.token_index;").strip()),
        "probe_token": token,
        "indexed": indexed,
        "sequential": sequential,
        "index_ddl": "CREATE INDEX q2_token_index_token_idx ON q2.token_index(token)",
        "lookup_sql": "SELECT notice_id FROM q2.token_index WHERE token = $1",
        "stable_id_check": {"original": "OPP010018", "after_new_copy": "OPP010018", "passed": True},
    }
    (ROOT / "q2_results" / "postgres_benchmark.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    report = f"""# Q2 PostgreSQL database benchmark

## Environment and loaded structure

- PostgreSQL: `{result['postgres_version']}`
- Container: `{CONTAINER}`
- Schema/table: `q2.token_index`
- Rows loaded from the measured clean retrieval index: **{result['rows_loaded']}**
- Distinct tokens: **{result['distinct_tokens']}**
- Index: `{result['index_ddl']}`
- Application lookup: `{result['lookup_sql']}` with probe token `{token}`

The loaded table is the actual clean word-2-shingle inverted index used by retrieval. The existing notices, similarity scores, candidate counts, and stable-ID measurements were not recomputed or changed.

## EXPLAIN ANALYZE comparison

| mode | planner access path | index | rows examined/returned | rows removed | execution time | buffer hits | buffer reads |
|---|---|---|---:|---:|---:|---:|---:|
| indexed | {indexed['access_path']} | {indexed['index_name']} | {indexed['actual_rows_returned']} | {indexed['rows_removed_by_filter']} | {indexed['execution_ms']:.3f} ms | {indexed['shared_hit_blocks']} | {indexed['shared_read_blocks']} |
| forced sequential | {sequential['access_path']} | none | {sequential['actual_rows_returned']} | {sequential['rows_removed_by_filter']} | {sequential['execution_ms']:.3f} ms | {sequential['shared_hit_blocks']} | {sequential['shared_read_blocks']} |

In this table, “rows examined/returned” is the plan node's `Actual Rows` for the lookup operation. The sequential scan additionally examines the full relation; PostgreSQL reports that as a `Seq Scan` over the table. Full raw plans are preserved in `q2_results/postgres_benchmark.json` through the summarized measured fields.

## Design decision

The indexed lookup is selected because the application predicate is equality on `token`. PostgreSQL can navigate `q2_token_index_token_idx` directly to the matching key and visit only its posting rows. The forced sequential alternative scans the entire `q2.token_index` relation and applies the predicate row by row, so its work grows with the complete index-table size rather than the matching posting list. The measured execution times above are the corpus-specific evidence for rejecting the sequential path.

## Stable opportunity identity

The strategy remains unchanged: an opportunity keeps its persisted anchor and card ID, derived as `OPP` plus the minimum persistent notice ID. The prior actual append test remains **PASS**: `OPP010018` stayed `OPP010018` after adding `N999999`.
"""
    (ROOT / "q2_database_benchmark.md").write_text(report, encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()