import os
import argparse
import zipfile
import io
from influxdb import InfluxDBClient
import pandas as pd
from datetime import datetime, timedelta, timezone


parser = argparse.ArgumentParser(description="Export InfluxDB measurements to individual CSVs in a ZIP archive")
parser.add_argument("--last-n-days", type=int, default=None, help="Query data from the last N days (overrides date range)")
parser.add_argument("--start-date", type=str, default=None, help="Start date in YYYY-MM-DD")
parser.add_argument("--end-date", type=str, default=None, help="End date in YYYY-MM-DD (defaults to today)")
args = parser.parse_args()


if args.last_n_days is not None:
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=args.last_n_days)
    time_label = f"Last{args.last_n_days}Days"
else:
    today = datetime.now(timezone.utc).date()
    start_date_str = args.start_date or str(today - timedelta(days=30))
    end_date_str = args.end_date or str(today)

    try:
        start_time = datetime.strptime(start_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end_time = datetime.strptime(end_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as e:
        raise ValueError(f"Invalid date format: {e}")

    if start_time > end_time:
        raise ValueError("Start date must be before end date.")

    time_label = f"{start_time.date()}_to_{end_time.date()}"

time_clause = f"time >= '{start_time.isoformat()}' AND time <= '{end_time.isoformat()}'"
timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
zip_filename = f"/tmp/GarminStats_Export_{timestamp_str}_{time_label}.zip"


INFLUXDB_HOST = os.getenv("INFLUXDB_HOST", "your.influxdb.hostname")
INFLUXDB_PORT = int(os.getenv("INFLUXDB_PORT", 8086))
INFLUXDB_USERNAME = os.getenv("INFLUXDB_USERNAME", "influxdb_username")
INFLUXDB_PASSWORD = os.getenv("INFLUXDB_PASSWORD", "influxdb_access_password")
INFLUXDB_DATABASE = os.getenv("INFLUXDB_DATABASE", "GarminStats")
INFLUXDB_ENDPOINT_IS_HTTP = False if os.getenv("INFLUXDB_ENDPOINT_IS_HTTP") in ['False','false','FALSE','f','F','no','No','NO','0'] else True # optional


if INFLUXDB_ENDPOINT_IS_HTTP:
    influxdbclient = InfluxDBClient(
        host=INFLUXDB_HOST,
        port=INFLUXDB_PORT,
        username=INFLUXDB_USERNAME,
        password=INFLUXDB_PASSWORD
    )
else:
    influxdbclient = InfluxDBClient(
        host=INFLUXDB_HOST,
        port=INFLUXDB_PORT,
        username=INFLUXDB_USERNAME,
        password=INFLUXDB_PASSWORD,
        ssl=True,
        verify_ssl=True
    )

influxdbclient.switch_database(INFLUXDB_DATABASE)

# --- Measurement exclusion list ---
excluded_measurements = {"%", "DemoPoint", "DeviceSync"}

# --- Fetch all measurements ---
measurements_query = "SHOW MEASUREMENTS"
measurements_result = influxdbclient.query(measurements_query)
measurements = [m["name"] for m in measurements_result.get_points()]

print(f"Found {len(measurements)} measurements. Skipping: {excluded_measurements}")

files_written = 0

with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
    for measurement in measurements:
        if measurement in excluded_measurements:
            print(f" !! Skipping: {measurement}")
            continue

        print(f" >> Querying: {measurement}")
        query = f'SELECT * FROM "{measurement}" WHERE {time_clause}'

        try:
            result = influxdbclient.query(query)
            points = list(result.get_points())

            if not points:
                print(" -- ⚠️ No data within given period.")
                continue

            df = pd.DataFrame(points)
            df.insert(0, "measurement", measurement)

            # Write to an in-memory CSV and add to ZIP
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_bytes = csv_buffer.getvalue().encode("utf-8")
            zipf.writestr(f"{measurement}.csv", csv_bytes)
            files_written += 1

        except Exception as e:
            print(f"  ❌ Query failed for {measurement}: {e}")

if files_written:
    print(f"\n✅ Exported {files_written} measurement CSVs into {zip_filename}. ")
else:
    print("⚠️ No data collected or exported.")
