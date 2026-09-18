INSTALL postgres;
LOAD postgres;

-- Change report_start/report_end and business_month in both statements for another period.
EXPLAIN SELECT
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
JOIN postgres_scan('host=postgres port=5432 dbname=annapurna user=annapurna password=annapurna', 'public', 'products') p
  ON p.product_code = f.product_code
 AND CAST(f.business_date AS DATE) >= p.valid_from
 AND CAST(f.business_date AS DATE) < p.valid_to
JOIN postgres_scan('host=postgres port=5432 dbname=annapurna user=annapurna password=annapurna', 'public', 'product_categories') c
  ON c.category_id = p.category_id
JOIN postgres_scan('host=postgres port=5432 dbname=annapurna user=annapurna password=annapurna', 'public', 'price_revisions') pr
  ON pr.product_sk = p.product_sk
 AND CAST(f.business_date AS DATE) >= pr.effective_from
 AND CAST(f.business_date AS DATE) < pr.effective_to
WHERE f.line_type IN ('SALE', 'RETURN', 'DISCOUNT', 'VOID')
GROUP BY 1, 2, 3, 4, 5, 6;

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
JOIN postgres_scan('host=postgres port=5432 dbname=annapurna user=annapurna password=annapurna', 'public', 'products') p
  ON p.product_code = f.product_code
 AND CAST(f.business_date AS DATE) >= p.valid_from
 AND CAST(f.business_date AS DATE) < p.valid_to
JOIN postgres_scan('host=postgres port=5432 dbname=annapurna user=annapurna password=annapurna', 'public', 'product_categories') c
  ON c.category_id = p.category_id
JOIN postgres_scan('host=postgres port=5432 dbname=annapurna user=annapurna password=annapurna', 'public', 'price_revisions') pr
  ON pr.product_sk = p.product_sk
 AND CAST(f.business_date AS DATE) >= pr.effective_from
 AND CAST(f.business_date AS DATE) < pr.effective_to
WHERE f.line_type IN ('SALE', 'RETURN', 'DISCOUNT', 'VOID')
GROUP BY 1, 2, 3, 4, 5, 6;
