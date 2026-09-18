$ErrorActionPreference = 'Stop'

python .\ingest.py --source .\sales --landing .\object_store --duckdb duckdb
python .\ingest.py --source .\sales --landing .\object_store --duckdb duckdb
python .\ingest.py --source .\sales --landing .\object_store --duckdb duckdb
Get-Content .\object_store\load_manifest.json

python .\reconcile.py

docker compose up -d postgres minio duckdb
docker compose exec -T postgres psql -U annapurna -d annapurna -c "SELECT 'stores' AS table_name, count(*) FROM stores UNION ALL SELECT 'products', count(*) FROM products UNION ALL SELECT 'price_revisions', count(*) FROM price_revisions;"
docker compose run --rm duckdb -c ".read /workspace/duckdb_federated.sql"
