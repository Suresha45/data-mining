# Annapurna Store data warehouse

The reproducible commands are in `run_all.ps1`. The source master export is `masters.sql`; the requested singular `master.sql` is not present in this dataset.

## (a)-(f)

(a) Docker Compose provisions PostgreSQL, MinIO, and DuckDB. PostgreSQL initializes from `masters.sql`; MinIO stores the object-store volume; DuckDB runs the analytical SQL.

(b) The raw folder is immutable. `ingest.py` normalizes all dialect aliases, takes business date from the filename, deduplicates by `(bill_no,line_no)`, and writes deterministic store-month partitions under `object_store/sales/business_month=YYYY-MM/store_id=Snn/`.

(c) The star schema is `fact_sales` plus `dim_store`, `dim_category`, `dim_product`, and effective-dated `dim_price_revision`. Product identity uses `(product_code, business_date)` against `valid_from`/`valid_to`; price reporting uses the analogous price interval.

(d) Revenue includes SALE, RETURN, DISCOUNT, and VOID. TAX and TENDER remain auditable but contribute zero. VOID rows are retained and included according to the source billing rule; the source contains both negative and positive VOID quantities.

(e) Dashboard dimensions are store, category, day-of-week, and month. The federated query scans the relevant CSV partitions and reads products, categories, and effective-dated price revisions directly from PostgreSQL with `postgres_scan`; product and price joins use sale-date validity. `EXPLAIN ANALYZE` profiles this complete federated query in DuckDB.

(f) Reconciliation and the October duplicate investigation are produced by `reconcile.py`; exact observed outputs belong in the run transcript below.
