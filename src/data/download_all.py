#!/usr/bin/env python3
"""
NYC Transit Recovery Project - Data Download Script
Downloads all required datasets for the analysis.

Usage:
    python download_all.py [--dataset DATASET_NAME]

Datasets:
    - mta_ridership: MTA Subway Hourly Ridership (2020-2024)
    - pluto: NYC PLUTO Property Data (2020-2022)
    - permits: NYC Building Permits
    - complaints: NYC 311 Service Requests (2020+)
    - nta: Neighborhood Tabulation Area boundaries
    - all: Download all datasets (default)

Note: LEHD and ACS data require separate download due to Census API requirements.
"""

import os
import sys
import requests
import argparse
from pathlib import Path
from datetime import datetime
from tqdm import tqdm

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_EXTERNAL = PROJECT_ROOT / "data" / "external"


# =============================================================================
# Dataset URLs and Configurations
# =============================================================================

DATASETS = {
    "mta_ridership": {
        "name": "MTA Subway Hourly Ridership 2020-2024",
        "url": "https://data.ny.gov/api/views/wujg-7c2s/rows.csv?accessType=DOWNLOAD",
        "filename": "mta_subway_hourly_ridership_2020_2024.csv",
        "description": "Hourly ridership by station complex and fare type",
        "size_estimate": "~500MB",
    },
    "pluto_2020": {
        "name": "NYC PLUTO 2020v8",
        "url": "https://data.cityofnewyork.us/api/views/64uk-42ks/rows.csv?accessType=DOWNLOAD",
        "filename": "pluto_2020.csv",
        "description": "Property land use data for NYC tax lots (2020)",
        "size_estimate": "~100MB",
    },
    "permits": {
        "name": "DOB Permit Issuance",
        "url": "https://data.cityofnewyork.us/api/views/ipu4-2q9a/rows.csv?accessType=DOWNLOAD",
        "filename": "dob_permit_issuance.csv",
        "description": "Building permits issued by NYC DOB",
        "size_estimate": "~200MB",
    },
    "complaints_2020_present": {
        "name": "311 Service Requests 2020-Present",
        "url": "https://data.cityofnewyork.us/api/views/erm2-nwe9/rows.csv?accessType=DOWNLOAD",
        "filename": "311_complaints_2020_present.csv",
        "description": "311 service requests from 2020 onwards",
        "size_estimate": "~1GB (large file, be patient)",
    },
    "nta_boundaries": {
        "name": "2020 Neighborhood Tabulation Areas (NTAs)",
        "url": "https://data.cityofnewyork.us/api/geospatial/9nt8-h7nd?method=export&format=GeoJSON",
        "filename": "nta_boundaries_2020.geojson",
        "description": "Geographic boundaries for 195 NYC neighborhoods",
        "size_estimate": "~5MB",
    },
}


# =============================================================================
# Download Functions
# =============================================================================

def download_file(url: str, filepath: Path, description: str = "") -> bool:
    """
    Download a file with progress bar.

    Args:
        url: URL to download from
        filepath: Local path to save file
        description: Description for progress bar

    Returns:
        True if successful, False otherwise
    """
    try:
        print(f"\nDownloading: {description or filepath.name}")
        print(f"URL: {url}")
        print(f"Saving to: {filepath}")

        # Create directory if needed
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Stream download with progress bar
        response = requests.get(url, stream=True)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))

        with open(filepath, 'wb') as f:
            with tqdm(total=total_size, unit='B', unit_scale=True, desc=filepath.name) as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    pbar.update(len(chunk))

        print(f"Successfully downloaded: {filepath.name}")
        return True

    except requests.exceptions.RequestException as e:
        print(f"ERROR downloading {filepath.name}: {e}")
        return False


def download_dataset(dataset_key: str) -> bool:
    """Download a specific dataset by key."""
    if dataset_key not in DATASETS:
        print(f"Unknown dataset: {dataset_key}")
        print(f"Available datasets: {list(DATASETS.keys())}")
        return False

    config = DATASETS[dataset_key]

    # Determine save location
    if "boundaries" in dataset_key or "nta" in dataset_key:
        save_dir = DATA_EXTERNAL
    else:
        save_dir = DATA_RAW

    filepath = save_dir / config["filename"]

    # Check if file already exists
    if filepath.exists():
        print(f"\nFile already exists: {filepath}")
        response = input("Overwrite? [y/N]: ").strip().lower()
        if response != 'y':
            print("Skipping...")
            return True

    print(f"\n{'='*60}")
    print(f"Dataset: {config['name']}")
    print(f"Description: {config['description']}")
    print(f"Estimated size: {config['size_estimate']}")
    print(f"{'='*60}")

    return download_file(config["url"], filepath, config["name"])


def download_all():
    """Download all datasets."""
    print("\n" + "="*60)
    print("NYC TRANSIT RECOVERY PROJECT - DATA DOWNLOAD")
    print("="*60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Raw data directory: {DATA_RAW}")
    print(f"External data directory: {DATA_EXTERNAL}")

    # Create directories
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    DATA_EXTERNAL.mkdir(parents=True, exist_ok=True)

    results = {}
    for key in DATASETS:
        results[key] = download_dataset(key)

    # Summary
    print("\n" + "="*60)
    print("DOWNLOAD SUMMARY")
    print("="*60)
    for key, success in results.items():
        status = "OK" if success else "FAILED"
        print(f"  {DATASETS[key]['name']}: {status}")

    # Instructions for manual downloads
    print("\n" + "="*60)
    print("MANUAL DOWNLOADS REQUIRED")
    print("="*60)
    print("""
The following datasets require manual download or API access:

1. LEHD Employment Data (Census):
   - URL: https://lehd.ces.census.gov/data/
   - Download: LODES WAC (Workplace Area Characteristics) for NY
   - Years: 2020, 2021, 2022, 2023
   - Save to: data/raw/lehd/

2. American Community Survey (Census):
   - URL: https://data.census.gov
   - Search: "ACS 5-Year Estimates" for NYC
   - Tables: B19013 (Median Income), B23025 (Employment Status), etc.
   - Geography: Census Tract level for NYC
   - Save to: data/raw/acs/

3. Station-to-NTA Mapping:
   - You'll need to create a mapping of MTA stations to NTAs
   - Use station coordinates + NTA boundaries for spatial join
""")

    return all(results.values())


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download NYC Transit Recovery datasets")
    parser.add_argument(
        "--dataset", "-d",
        choices=list(DATASETS.keys()) + ["all"],
        default="all",
        help="Specific dataset to download (default: all)"
    )

    args = parser.parse_args()

    if args.dataset == "all":
        success = download_all()
    else:
        success = download_dataset(args.dataset)

    sys.exit(0 if success else 1)
