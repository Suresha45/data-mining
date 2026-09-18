# Final Verification

Verification performed against the existing workspace files and the already-running Docker services on 2026-09-18. No pipeline rebuild, deletion, or architecture change was performed. The source of truth for billing behavior is `billing_notes.md`.

## A. Billing notes verification

The notes define the revenue treatment exactly as follows, and the implementation's `CASE` expression in `warehouse.sql` matches it:

| line type | billing-notes rule | implementation result |
|---|---|---|
| `SALE` | counts as revenue; positive quantity | included |
| `RETURN` | counts as revenue and subtracts | included; source negative quantity subtracts |
| `DISCOUNT` | counts as revenue and subtracts | included; source negative unit price subtracts |
| `VOID` | counts as revenue and cancels | included |
| `TAX` | does not count as revenue | zero |
| `TENDER` | does not count as revenue | zero |

Actual canonical-file check:

```sql
SELECT line_type, COUNT(*) AS rows,
       SUM(CASE WHEN line_type IN ('SALE','RETURN','DISCOUNT','VOID')
                THEN qty * unit_price ELSE 0 END) AS revenue_contribution
FROM read_csv_auto('/workspace/object_store/canonical_sales.csv', header=true)
GROUP BY line_type ORDER BY line_type;
```

Observed output:

```text
DISCOUNT  22603   -5294511.420000002
RETURN    16161   -11779518.41
SALE      745860   543249622.2100018
TAX       165704  0.0
TENDER    165704  0.0
VOID      4892    -3309856.630000001
```

`TAX` and `TENDER` therefore contribute zero in the implemented revenue expression, as required by the notes. The notes also explicitly warn that summing every line would count `TENDER` and GST, so excluding both is supported by the source notes, not inferred from general accounting practice.

### VOID claim check

The statement in `exam_answers.md` and `RESULTS.md` that “VOID is retained with negated quantity” is only partly supported.

Actual check:

```sql
SELECT
  SUM(CASE WHEN qty < 0 THEN 1 ELSE 0 END) AS negative_qty_rows,
  SUM(CASE WHEN qty = 0 THEN 1 ELSE 0 END) AS zero_qty_rows,
  SUM(CASE WHEN qty > 0 THEN 1 ELSE 0 END) AS positive_qty_rows,
  MIN(qty) AS min_qty, MAX(qty) AS max_qty
FROM read_csv_auto('/workspace/object_store/canonical_sales.csv', header=true)
WHERE line_type = 'VOID';
```

Observed output: `4660` negative, `0` zero, `232` positive, minimum `-7.0`, maximum `4.0`. Examples of positive source rows include `S01/20240101/00009`, line 18, product code `DISC`, quantity `1.0`, and item rows with positive quantities.

The ingestion code retains source `qty`; it does not enforce or derive a negative quantity for `VOID`. Therefore the precise supported claim is: **VOID rows are retained and included in revenue, but the actual source contains 232 positive-quantity VOID rows.** This is a data/claim mismatch and is not silently corrected here.

**Billing status: NEEDS-FIX for the broad VOID claim; PASS for the TAX/TENDER and line-type revenue CASE.**

## B. Historical price verification

The effective-date logic in `warehouse.sql` is:

```sql
LEFT JOIN dim_price_revision pr ON pr.product_sk = p.product_sk
  AND f.business_date >= pr.effective_from
  AND f.business_date < pr.effective_to
```

Product identity is also date-effective:

```sql
JOIN dim_product p ON p.product_code = f.product_code
  AND f.business_date >= p.valid_from
  AND f.business_date < p.valid_to
```

The same query shape was run for March and October against actual object-store sales and PostgreSQL using `postgres_scan`. Only `params.report_month` and the corresponding source partition changed:

```sql
WITH params(report_month) AS (VALUES (DATE '2024-03-01')),
sales AS (
  SELECT CAST(business_date AS DATE) AS business_date, product_code
  FROM read_csv_auto('/workspace/object_store/sales/business_month=2024-03/store_id=S01/sales.csv', header=true)
),
products AS (
  SELECT * FROM postgres_scan(
    'host=postgres port=5432 dbname=annapurna user=annapurna password=annapurna',
    'public', 'products'
  )
),
prices AS (
  SELECT * FROM postgres_scan(
    'host=postgres port=5432 dbname=annapurna user=annapurna password=annapurna',
    'public', 'price_revisions'
  )
)
SELECT p.report_month, s.business_date, s.product_code,
       pr.product_sk, pr.product_name, px.revision_id,
       px.selling_price, px.effective_from, px.effective_to
FROM params p
JOIN sales s ON DATE_TRUNC('month', s.business_date) = p.report_month
JOIN products pr ON pr.product_code = s.product_code
  AND s.business_date >= pr.valid_from AND s.business_date < pr.valid_to
JOIN prices px ON px.product_sk = pr.product_sk
  AND s.business_date >= px.effective_from AND s.business_date < px.effective_to
WHERE s.product_code = 'P100621'
ORDER BY s.business_date
LIMIT 5;
```

For October, the only parameter/source changes were `DATE '2024-10-01'` and `business_month=2024-10`.

Actual March output:

```text
2024-03-01,2024-03-03,P100621,1089,Catch Coriander Powder 500g,500314,226.51,2023-12-17,2024-03-07
2024-03-01,2024-03-05,P100621,1089,Catch Coriander Powder 500g,500314,226.51,2023-12-17,2024-03-07
2024-03-01,2024-03-09,P100621,1089,Catch Coriander Powder 500g,500315,229.48,2024-03-08,2024-03-22
2024-03-01,2024-03-12,P100621,1089,Catch Coriander Powder 500g,500315,229.48,2024-03-08,2024-03-22
2024-03-01,2024-03-14,P100621,1089,Catch Coriander Powder 500g,500315,229.48,2024-03-08,2024-03-22
```

Actual October output:

```text
2024-10-01,2024-10-04,P100621,2213,Cadbury Chewing Gum 50g,504287,134.28,2024-05-10,9999-12-31
2024-10-01,2024-10-06,P100621,2213,Cadbury Chewing Gum 50g,504287,134.28,2024-05-10,9999-12-31
2024-10-01,2024-10-12,P100621,2213,Cadbury Chewing Gum 50g,504287,134.28,2024-05-10,9999-12-31
2024-10-01,2024-10-19,P100621,2213,Cadbury Chewing Gum 50g,504287,134.28,2024-05-10,9999-12-31
2024-10-01,2024-10-26,P100621,2213,Cadbury Chewing Gum 50g,504287,134.28,2024-05-10,9999-12-31
```

This proves per-sale-date price selection: March changes from revision 500314 to 500315 within March, while October uses revision 504287. It also proves reused-code handling: `P100621` is product SK 1089, `Catch Coriander Powder 500g`, before June 2024, and product SK 2213, `Cadbury Chewing Gum 50g`, from June 2024. The categories differ (`C06` versus `C13`). A product-code-only join would return both identities and duplicate/misclassify facts.

Important limitation: `warehouse.sql` has the correct price view, but the existing `duckdb_federated.sql` query joins `products` and `product_categories` only and aggregates the printed `unit_price`; it does not join `price_revisions`. Thus the historical-price claim is verified for `warehouse.sql` and the explicit verification query above, but **not verified for the current federated dashboard SQL**.

**Historical price status: NEEDS-FIX for the complete federated reporting path; PASS for the effective-date SQL in `warehouse.sql` and the demonstrated query.**

## C. Federated EXPLAIN verification

The existing federated `EXPLAIN` was run without creating dimension copies. Its relevant physical operators were:

```text
HASH_GROUP_BY
  PROJECTION
    HASH_JOIN
      FILTER
        READ_CSV_AUTO
      POSTGRES_SCAN  Table: products
    POSTGRES_SCAN    Table: product_categories
```

The object-store side is `READ_CSV_AUTO` over:

```text
/workspace/object_store/sales/business_month=2024-10/store_id=S01/sales.csv
```

The PostgreSQL side is read directly by `postgres_scan` from the live `products` and `product_categories` tables. The temporal product join condition appears in the plan as `product_code = product_code`, `business_date >= valid_from`, and `business_date < valid_to`. The line-type filter is a local DuckDB `FILTER`, and the category/day/store aggregation is a local DuckDB `HASH_GROUP_BY`.

There is no `CREATE TABLE`, `COPY`, or dimension extract in this federated SQL. PostgreSQL dimensions are not first copied into DuckDB; the query is genuinely federated.

The existing file has two different statements: the first is federated `EXPLAIN`; the second is `EXPLAIN ANALYZE` over the object-store CSV glob only. Therefore a full `EXPLAIN ANALYZE` of the joined federated query is **NOT VERIFIED** by the existing script. The plan itself proves federation; it does not prove that PostgreSQL join timing was profiled in the captured `EXPLAIN ANALYZE`.

**Federated status: NEEDS-FIX for the claim that the captured `EXPLAIN ANALYZE` profiles the complete federated join; PASS for genuine direct CSV/PostgreSQL federation and plan operator identification.**

## D. Timing explanation

The existing all-partitions `EXPLAIN ANALYZE` output reported, in separate places:

```text
Total Files Read: 144
1,120,924 rows
TABLE_SCAN ... 4.32s
HASH_GROUP_BY ... 0.03s
Total Time: 0.597s
```

The earlier run reported 4.23 seconds for the same scan and 0.710 seconds total. These are not validly compared as two additive wall-clock measurements. The operator time shown for the `TABLE_SCAN` is the scan operator's profiled execution time and can be accumulated across parallel worker threads; `Total Time` is the query's end-to-end elapsed wall time for that execution. The totals also vary between runs because of filesystem cache, container state, and runtime scheduling. The correct conclusion is that DuckDB scanned 144 files and 1,120,924 rows in the profiled execution, while the end-to-end query elapsed time was 0.597 seconds in the latest run; 4.32 seconds is not an additional 4.32 seconds to add to 0.597.

## E. Unsupported or incorrect claims

1. “VOID is retained with negated quantity” is too broad. The pipeline retains VOID source rows, but actual data has 232 positive-quantity VOID rows. The implementation does not enforce negation.
2. The statement that historical reporting prices are implemented is supported by `warehouse.sql`, but not by the current federated query, which uses printed `unit_price` and does not join `price_revisions`.
3. The statement that `EXPLAIN ANALYZE` evidence covers the federated query is too broad. The captured `EXPLAIN` covers the federation; the captured `EXPLAIN ANALYZE` profiles the object-store-only aggregate.

## F. Final status

| check | status | reason |
|---|---|---|
| Billing rules | **NEEDS-FIX** | TAX/TENDER and revenue inclusion match; actual VOID sign data contradicts the broad negated-quantity claim. |
| Historical prices | **NEEDS-FIX** | Effective dating and reissued identity work in `warehouse.sql`/verification query; federated dashboard SQL omits price revisions. |
| DuckDB federation / EXPLAIN ANALYZE | **NEEDS-FIX** | Federation and plan are genuine; full federated `EXPLAIN ANALYZE` was not captured, and timing claims must distinguish operator time from wall time. |