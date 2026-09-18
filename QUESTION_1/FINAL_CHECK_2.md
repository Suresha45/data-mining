# Final Fix Verification

Verified on 2026-09-18 using the existing source files and running Docker services. No source sales data was changed, and reconciliation/idempotency results were not rerun or altered.

## 1. VOID documentation fix

Updated `exam_answers.md` and `RESULTS.md` to state:

> VOID rows are retained and included according to the source billing rule; the source contains both negative and positive VOID quantities.

The implementation still preserves source quantities. Actual unchanged source check:

```text
void_rows,negative_void_rows,positive_void_rows
4892,4660,232
```

No quantities were forced negative. **PASS**

## 2. Federated historical-price fix

`duckdb_federated.sql` now joins PostgreSQL `products`, `product_categories`, and `price_revisions` through `postgres_scan`. It uses:

```sql
JOIN postgres_scan(
  'host=postgres port=5432 dbname=annapurna user=annapurna password=annapurna',
  'public', 'products'
) p
  ON p.product_code = f.product_code
 AND CAST(f.business_date AS DATE) >= p.valid_from
 AND CAST(f.business_date AS DATE) < p.valid_to
JOIN postgres_scan(
  'host=postgres port=5432 dbname=annapurna user=annapurna password=annapurna',
  'public', 'price_revisions'
) pr
  ON pr.product_sk = p.product_sk
 AND CAST(f.business_date AS DATE) >= pr.effective_from
 AND CAST(f.business_date AS DATE) < pr.effective_to
```

The report query exposes `pr.selling_price AS reporting_unit_price`. Revenue remains based on the printed export price, as required by the existing billing/revenue implementation; the historical master price is separately available as the reporting price.

The same effective-date query was executed for March and October with only the reporting period/source partition changed. Actual output for product code `P100621`:

```text
report_month,business_date,product_code,product_sk,product_name,revision_id,selling_price,effective_from,effective_to
2024-03-01,2024-03-03,P100621,1089,Catch Coriander Powder 500g,500314,226.51,2023-12-17,2024-03-07
2024-03-01,2024-03-05,P100621,1089,Catch Coriander Powder 500g,500314,226.51,2023-12-17,2024-03-07
2024-03-01,2024-03-09,P100621,1089,Catch Coriander Powder 500g,500315,229.48,2024-03-08,2024-03-22
2024-03-01,2024-03-12,P100621,1089,Catch Coriander Powder 500g,500315,229.48,2024-03-08,2024-03-22
2024-03-01,2024-03-14,P100621,1089,Catch Coriander Powder 500g,500315,229.48,2024-03-08,2024-03-22
2024-03-01,2024-03-17,P100621,1089,Catch Coriander Powder 500g,500315,229.48,2024-03-08,2024-03-22
2024-03-01,2024-03-19,P100621,1089,Catch Coriander Powder 500g,500315,229.48,2024-03-08,2024-03-22
2024-03-01,2024-03-31,P100621,1089,Catch Coriander Powder 500g,500316,210.70,2024-03-23,9999-12-31
2024-10-01,2024-10-04,P100621,2213,Cadbury Chewing Gum 50g,504287,134.28,2024-05-10,9999-12-31
2024-10-01,2024-10-06,P100621,2213,Cadbury Chewing Gum 50g,504287,134.28,2024-05-10,9999-12-31
```

The actual database therefore selects SK 1089 / Catch Coriander Powder in March, with revisions 500314, 500315, and 500316 as their validity intervals change. October selects SK 2213 / Cadbury Chewing Gum with revision 504287. This also verifies reused product-code handling using `product_code + business_date` validity. No PostgreSQL dimension table is copied into DuckDB. **PASS**

## 3. Complete federated EXPLAIN ANALYZE

The existing `duckdb_federated.sql` now runs `EXPLAIN ANALYZE` on the complete query, including the object-store scan, product identity join, category join, and price-revision join. The actual query contains:

```sql
EXPLAIN ANALYZE SELECT
  f.store_id,
  c.category_name,
  STRFTIME(CAST(f.business_date AS DATE), '%A') AS day_of_week,
  p.product_sk,
  pr.revision_id,
  pr.selling_price AS reporting_unit_price,
  SUM(CASE WHEN f.line_type IN ('SALE', 'RETURN', 'DISCOUNT', 'VOID')
           THEN CAST(f.qty AS DECIMAL(18,3)) * CAST(f.unit_price AS DECIMAL(18,2)) ELSE 0 END) AS revenue_inr
FROM read_csv_auto('/workspace/object_store/sales/business_month=2024-10/store_id=*/sales.csv', header=true) f
JOIN (SELECT DATE '2024-10-01' AS report_start, DATE '2024-11-01' AS report_end) period
  ON CAST(f.business_date AS DATE) >= period.report_start
 AND CAST(f.business_date AS DATE) < period.report_end
JOIN postgres_scan(..., 'public', 'products') p ON ...
JOIN postgres_scan(..., 'public', 'product_categories') c ON ...
JOIN postgres_scan(..., 'public', 'price_revisions') pr ON ...
WHERE f.line_type IN ('SALE', 'RETURN', 'DISCOUNT', 'VOID')
GROUP BY 1, 2, 3, 4, 5, 6;
```

Relevant actual plan markers from the complete query:

```text
HASH_GROUP_BY
  HASH_JOIN
    NESTED_LOOP_JOIN
      FILTER (line_type = 'RETURN' ... SALE ... DISCOUNT ... VOID)
        READ_CSV_AUTO
      POSTGRES_SCAN Table: products
    POSTGRES_SCAN Table: product_categories
  POSTGRES_SCAN Table: price_revisions
```

The complete `EXPLAIN ANALYZE` output reported:

```text
Total Time: 0.168s
READ_CSV_AUTO
Total Files Read: 12
119,007 rows
POSTGRES_SCAN Table: products       1,224 rows
POSTGRES_SCAN Table: product_categories 14 rows
POSTGRES_SCAN Table: price_revisions 4,320 rows
HASH_JOIN / NESTED_LOOP_JOIN
HASH_GROUP_BY
```

This is genuinely federated: sales are read directly from object-store CSV partitions and all three dimensions are read directly from PostgreSQL via `postgres_scan`. There is no `CREATE TABLE`, `COPY`, or dimension extract in this query. **PASS**

## Final status

| fix | status |
|---|---|
| VOID documentation matches actual source | **PASS** |
| Historical price revisions in federated reporting | **PASS** |
| Complete federated `EXPLAIN ANALYZE` | **PASS** |
