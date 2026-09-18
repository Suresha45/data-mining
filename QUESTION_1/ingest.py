from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


FILE_RE = re.compile(
    r"^SALES_(?P<store>S\d{2})_(?P<date>\d{8})(?:__R\d+)?\.(?P<ext>csv|parquet)$",
    re.IGNORECASE,
)
FIELD_ALIASES = {
    "bill_no": "bill_no",
    "line_no": "line_no",
    "product_code": "product_code",
    "item_code": "product_code",
    "qty": "qty",
    "quantity": "qty",
    "unit_price": "unit_price",
    "rate": "unit_price",
    "line_type": "line_type",
    "type": "line_type",
    "ts": "ts",
    "txn_time": "ts",
}


def canonical_file_name(path: Path) -> tuple[str, str, str]:
    match = FILE_RE.match(path.name)
    if not match:
        raise ValueError(f"Unexpected sales filename: {path.name}")
    return match.group("store"), match.group("date"), match.group("ext").lower()


def parse_timestamp(value: str) -> str:
    value = value.strip()
    if value.isdigit():
        return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%d-%m-%Y %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).isoformat()
        except ValueError:
            pass
    return value


def read_csv_rows(path: Path, store: str, business_date: str):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        delimiter = ";" if sample.splitlines()[0].count(";") > sample.splitlines()[0].count(",") else ","
        reader = csv.DictReader(handle, delimiter=delimiter)
        for source in reader:
            row = {FIELD_ALIASES[key.strip().lower()]: value for key, value in source.items() if key}
            yield {
                "store_id": store,
                "business_date": datetime.strptime(business_date, "%Y%m%d").date().isoformat(),
                "bill_no": row["bill_no"].strip(),
                "line_no": int(row["line_no"]),
                "product_code": row["product_code"].strip(),
                "qty": float(row["qty"]),
                "unit_price": float(row["unit_price"]),
                "line_type": row["line_type"].strip().upper(),
                "ts": parse_timestamp(row["ts"]),
            }


def read_parquet_rows(path: Path, store: str, business_date: str, duckdb: str):
    temp = path.with_suffix(".csv.tmp")
    query = f"COPY (SELECT * FROM read_parquet('{path.as_posix()}')) TO '{temp.as_posix()}' (HEADER, DELIMITER ',')"
    subprocess.run([duckdb, "-c", query], check=True, capture_output=True, text=True)
    try:
        yield from read_csv_rows(temp, store, business_date)
    finally:
        temp.unlink(missing_ok=True)


def row_checksum(rows: list[dict]) -> str:
    digest = hashlib.sha256()
    for row in sorted(rows, key=lambda item: (item["bill_no"], item["line_no"])):
        digest.update(json.dumps(row, sort_keys=True, separators=(",", ":")).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("sales"))
    parser.add_argument("--landing", type=Path, default=Path("object_store"))
    parser.add_argument("--duckdb", default="duckdb")
    args = parser.parse_args()

    files = sorted((path for path in args.source.iterdir() if path.is_file()), key=lambda path: path.name)
    rows_by_key: dict[tuple[str, int], dict] = {}
    raw_lines = 0
    source_files = 0
    for path in files:
        if not FILE_RE.match(path.name):
            continue
        store, business_date, extension = canonical_file_name(path)
        source_files += 1
        rows = read_csv_rows(path, store, business_date) if extension == "csv" else read_parquet_rows(path, store, business_date, args.duckdb)
        for row in rows:
            raw_lines += 1
            rows_by_key.setdefault((row["bill_no"], row["line_no"]), row)

    rows = list(rows_by_key.values())
    if args.landing.exists():
        shutil.rmtree(args.landing)
    args.landing.mkdir(parents=True)
    canonical_csv = args.landing / "canonical_sales.csv"
    with canonical_csv.open("w", encoding="utf-8", newline="") as handle:
        columns = ["store_id", "business_date", "bill_no", "line_no", "product_code", "qty", "unit_price", "line_type", "ts"]
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in sorted(rows, key=lambda item: (item["business_date"], item["store_id"], item["bill_no"], item["line_no"])):
            writer.writerow(row)

    partition_root = args.landing / "sales"
    partition_rows: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        month = row["business_date"][:7]
        partition_rows.setdefault((month, row["store_id"]), []).append(row)
    partition_columns = [
        "store_id", "business_date", "bill_no", "line_no", "product_code",
        "qty", "unit_price", "line_type", "ts",
    ]
    partition_files = []
    for (month, store_id), partition in sorted(partition_rows.items()):
        directory = partition_root / f"business_month={month}" / f"store_id={store_id}"
        directory.mkdir(parents=True, exist_ok=True)
        output = directory / "sales.csv"
        with output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=partition_columns)
            writer.writeheader()
            writer.writerows(sorted(partition, key=lambda item: (item["business_date"], item["bill_no"], item["line_no"])))
        partition_files.append({"path": output.as_posix(), "rows": len(partition), "bytes": output.stat().st_size})

    metadata = {
        "source_files": source_files,
        "raw_lines": raw_lines,
        "canonical_lines": len(rows),
        "duplicate_lines_removed": raw_lines - len(rows),
        "checksum": row_checksum(rows),
        "partition_layout": "sales/business_month=YYYY-MM/store_id=Snn/sales.csv",
        "partition_count": len(partition_files),
        "partition_bytes": sum(item["bytes"] for item in partition_files),
        "partition_files": partition_files,
        "single_folder_files": source_files,
        "single_folder_bytes": sum(path.stat().st_size for path in files if FILE_RE.match(path.name)),
    }
    (args.landing / "load_manifest.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()