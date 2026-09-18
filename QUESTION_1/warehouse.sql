INSTALL httpfs;
LOAD httpfs;

CREATE OR REPLACE TABLE dim_store AS SELECT * FROM read_csv_auto('stores.csv', header=true);
CREATE OR REPLACE TABLE dim_category AS SELECT * FROM read_csv_auto('categories.csv', header=true);
CREATE OR REPLACE TABLE dim_product AS SELECT * FROM read_csv_auto('products.csv', header=true);
CREATE OR REPLACE TABLE dim_price_revision AS SELECT * FROM read_csv_auto('price_revisions.csv', header=true);

CREATE OR REPLACE TABLE fact_sales AS
SELECT
  store_id,
  CAST(business_date AS DATE) AS business_date,
  bill_no,
  CAST(line_no AS INTEGER) AS line_no,
  product_code,
  CAST(qty AS DECIMAL(18,3)) AS qty,
  CAST(unit_price AS DECIMAL(18,2)) AS printed_unit_price,
  line_type,
  CAST(ts AS TIMESTAMP) AS event_ts,
  CASE WHEN line_type IN ('SALE', 'RETURN', 'DISCOUNT', 'VOID') THEN qty * unit_price ELSE 0 END AS revenue_inr
FROM read_csv_auto('object_store/canonical_sales.csv', header=true);

CREATE OR REPLACE VIEW v_sales_enriched AS
SELECT
  f.business_date,
  EXTRACT(year FROM f.business_date) AS year,
  EXTRACT(month FROM f.business_date) AS month,
  STRFTIME(f.business_date, '%A') AS day_of_week,
  f.store_id,
  s.store_name,
  p.product_sk,
  p.product_name,
  c.category_id,
  c.category_name,
  f.bill_no,
  f.line_no,
  f.line_type,
  f.qty,
  f.printed_unit_price,
  pr.selling_price AS reporting_unit_price,
  f.revenue_inr
FROM fact_sales f
JOIN dim_store s USING (store_id)
JOIN dim_product p ON p.product_code = f.product_code
  AND f.business_date >= p.valid_from AND f.business_date < p.valid_to
JOIN dim_category c USING (category_id)
LEFT JOIN dim_price_revision pr ON pr.product_sk = p.product_sk
  AND f.business_date >= pr.effective_from AND f.business_date < pr.effective_to;

-- Stable dashboard query: replace only the two date parameters.
-- SELECT store_id, category_name, day_of_week, DATE_TRUNC('month', business_date) AS month,
--        SUM(revenue_inr) AS revenue_inr
-- FROM v_sales_enriched
-- WHERE business_date >= DATE '2024-10-01' AND business_date < DATE '2024-11-01'
-- GROUP BY ALL ORDER BY 1, 2, 3, 4;