# Actual execution results

Captured from the files and commands in this workspace on 2026-09-18.

## Source inventory

| item | result |
|---|---:|
| sales files | 4,457 CSV; 0 Parquet |
| source bytes | 68,706,877 |
| raw lines | 1,137,585 |
| stores | S01-S12 |
| PostgreSQL stores/products/categories/price revisions | 12 / 1,224 / 14 / 4,320 |
| reissued product codes | 24 |
| missing exports | S07: 2024-07-09, 2024-07-10, 2024-07-11 |

## Three ingestion runs

All three runs returned `canonical_lines=1120924`, `raw_lines=1137585`, `duplicate_lines_removed=16661`, and checksum `41fd1b323f33d6dcc54220b3532a00d700c335598f7d923816974a673641ae9d`. Therefore row count and checksum were identical across all three runs.

Partition output was 144 store-month files totaling 91,928,640 bytes. The one-folder source comparison was 4,457 files totaling 68,706,877 bytes. A query for S01 and October reads one partition file, `object_store/sales/business_month=2024-10/store_id=S01/sales.csv`, rather than the 4,457-file source folder.

## Reconciliation

| month | pipeline INR | finance INR | difference INR | classification |
|---|---:|---:|---:|---|
| 2024-01 | 38,446,071.33 | 38,446,071.33 | 0.00 | match |
| 2024-02 | 34,887,085.55 | 34,887,085.55 | 0.00 | match |
| 2024-03 | 41,971,649.09 | 42,457,899.09 | 486,250.00 | revenue-definition difference; institutional invoice outside till |
| 2024-04 | 37,958,457.37 | 37,958,457.37 | 0.00 | match |
| 2024-05 | 41,764,716.40 | 41,764,716.40 | 0.00 | match |
| 2024-06 | 38,987,082.82 | 38,987,082.82 | 0.00 | match |
| 2024-07 | 40,295,160.11 | 40,527,291.81 | 232,131.70 | source-data issue; missing S07 exports |
| 2024-08 | 45,252,181.75 | 45,252,181.75 | 0.00 | match |
| 2024-09 | 44,615,037.46 | 44,615,037.46 | 0.00 | match |
| 2024-10 | 56,359,195.92 | 56,359,195.92 | 0.00 | match |
| 2024-11 | 51,583,838.47 | 51,583,838.47 | 0.00 | match |
| 2024-12 | 50,725,259.48 | 50,745,209.00 | -50.48 | revenue-definition difference; Finance rounds each bill |

Take back to Finance: March's INR 486,250 institutional invoice is outside the till scope; July's INR 232,131.70 is the documented S07 outage; December differs by INR 50.48 because Finance rounds per bill. There is no October pipeline issue.

## October duplicate investigation

October contains 119,007 canonical rows; duplicate business keys `(bill_no,line_no)` = 0; maximum key multiplicity = 1. The approximate-2x warning is not present in the deduplicated, correctly classified result. `TENDER` and `TAX` are excluded from revenue, while VOID rows are retained and included according to the source billing rule; the source contains both negative and positive VOID quantities.

## DuckDB engine evidence

The live complete federated `EXPLAIN ANALYZE` uses `READ_CSV_AUTO` for the October store partitions, `POSTGRES_SCAN` for `products`, `product_categories`, and `price_revisions`, sale-date validity joins, a local line-type filter, and local `HASH_GROUP_BY`. The captured output is recorded in `FINAL_CHECK_2.md`.