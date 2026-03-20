#!/usr/bin/env python3
"""
Download MTA Subway Hourly Ridership using Socrata API with date filtering.

This downloads only the data needed for the project (July 2020 - December 2023)
instead of the full 15GB dataset.
"""

import requests
import pandas as pd
from pathlib import Path
from datetime import datetime
import time

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_RAW = PROJECT_ROOT / 'data' / 'raw'

# Socrata API endpoint
BASE_URL = "https://data.ny.gov/resource/wujg-7c2s.csv"

# Date range for project
START_DATE = "2020-07-01"
END_DATE = "2023-12-31"

# Socrata limits
BATCH_SIZE = 50000  # Max allowed by Socrata


def download_mta_data():
    """Download MTA ridership data with date filtering."""

    print("=" * 60)
    print("MTA SUBWAY RIDERSHIP - FILTERED DOWNLOAD")
    print("=" * 60)
    print(f"Date range: {START_DATE} to {END_DATE}")
    print(f"Batch size: {BATCH_SIZE:,} rows per request")
    print()

    output_file = DATA_RAW / 'mta_subway_hourly_ridership.csv'

    # Build query with date filter
    where_clause = f"transit_timestamp >= '{START_DATE}T00:00:00' AND transit_timestamp <= '{END_DATE}T23:59:59'"

    all_data = []
    offset = 0
    total_rows = 0

    print("Downloading data in batches...")

    while True:
        # Build URL with pagination
        url = f"{BASE_URL}?$where={where_clause}&$limit={BATCH_SIZE}&$offset={offset}&$order=transit_timestamp"

        try:
            response = requests.get(url, timeout=120)
            response.raise_for_status()

            # Parse CSV response
            from io import StringIO
            batch_df = pd.read_csv(StringIO(response.text))

            rows_received = len(batch_df)

            if rows_received == 0:
                print(f"\nDownload complete!")
                break

            all_data.append(batch_df)
            total_rows += rows_received
            offset += BATCH_SIZE

            # Progress update
            print(f"  Downloaded: {total_rows:,} rows (batch {len(all_data)})", end='\r')

            # Small delay to be nice to the API
            time.sleep(0.5)

            # If we got fewer rows than batch size, we're done
            if rows_received < BATCH_SIZE:
                print(f"\nDownload complete!")
                break

        except requests.exceptions.RequestException as e:
            print(f"\nError at offset {offset}: {e}")
            print("Retrying in 5 seconds...")
            time.sleep(5)
            continue

    if not all_data:
        print("No data downloaded!")
        return None

    # Combine all batches
    print(f"\nCombining {len(all_data)} batches...")
    df = pd.concat(all_data, ignore_index=True)

    print(f"Total rows: {len(df):,}")
    print(f"Date range in data: {df['transit_timestamp'].min()} to {df['transit_timestamp'].max()}")
    print(f"Unique stations: {df['station_complex'].nunique()}")

    # Save to CSV
    print(f"\nSaving to {output_file}...")
    df.to_csv(output_file, index=False)

    file_size_mb = output_file.stat().st_size / (1024 * 1024)
    print(f"File size: {file_size_mb:.1f} MB")

    return df


def download_aggregated_daily():
    """
    Alternative: Download pre-aggregated daily data.
    Much smaller and sufficient for most analyses.
    """
    print("=" * 60)
    print("MTA RIDERSHIP - DAILY AGGREGATION")
    print("=" * 60)

    # Use SoQL to aggregate on the server
    # This groups by date and station, summing ridership
    url = (
        f"{BASE_URL}?"
        f"$select=date_trunc_ymd(transit_timestamp) as date,station_complex_id,station_complex,latitude,longitude,sum(ridership) as daily_ridership"
        f"&$where=transit_timestamp >= '{START_DATE}T00:00:00' AND transit_timestamp <= '{END_DATE}T23:59:59'"
        f"&$group=date_trunc_ymd(transit_timestamp),station_complex_id,station_complex,latitude,longitude"
        f"&$order=date,station_complex_id"
        f"&$limit=5000000"
    )

    print("Downloading daily aggregated data...")
    print("(This aggregates hourly to daily on the server - much faster)")

    try:
        response = requests.get(url, timeout=300)
        response.raise_for_status()

        from io import StringIO
        df = pd.read_csv(StringIO(response.text))

        print(f"Downloaded {len(df):,} rows")

        output_file = DATA_RAW / 'mta_subway_daily_ridership.csv'
        df.to_csv(output_file, index=False)

        file_size_mb = output_file.stat().st_size / (1024 * 1024)
        print(f"Saved to {output_file} ({file_size_mb:.1f} MB)")

        return df

    except Exception as e:
        print(f"Error: {e}")
        return None


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Download MTA ridership data')
    parser.add_argument('--daily', action='store_true',
                        help='Download daily aggregated data (smaller, faster)')
    parser.add_argument('--hourly', action='store_true',
                        help='Download full hourly data (larger, complete)')
    args = parser.parse_args()

    DATA_RAW.mkdir(parents=True, exist_ok=True)

    if args.daily:
        download_aggregated_daily()
    elif args.hourly:
        download_mta_data()
    else:
        # Default: try daily first (smaller), offer hourly as option
        print("Downloading DAILY aggregated data (recommended for analysis)")
        print("Use --hourly flag for full hourly data if needed\n")
        download_aggregated_daily()
