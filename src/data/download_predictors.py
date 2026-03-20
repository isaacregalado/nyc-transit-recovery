#!/usr/bin/env python3
"""
Download predictor datasets for regression analysis.
"""

import requests
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from pathlib import Path
from io import StringIO
import time

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_RAW = PROJECT_ROOT / 'data' / 'raw'
DATA_PROCESSED = PROJECT_ROOT / 'data' / 'processed'


def download_pluto_sample():
    """Download PLUTO data and aggregate to NTA using spatial join."""
    print("\n" + "="*60)
    print("Downloading PLUTO Land Use Data")
    print("="*60)

    # Download with coordinates for spatial join
    print("  Downloading PLUTO records with coordinates...")

    all_data = []
    offset = 0
    batch_size = 50000

    while True:
        url = f"https://data.cityofnewyork.us/resource/64uk-42ks.json?$select=latitude,longitude,unitsres,unitstotal,comarea,resarea,officearea,retailarea,lotarea,yearbuilt,bldgclass,landuse&$where=latitude IS NOT NULL&$limit={batch_size}&$offset={offset}"

        try:
            r = requests.get(url, timeout=120)
            r.raise_for_status()
            batch = r.json()

            if not batch:
                break

            all_data.extend(batch)
            print(f"    Downloaded {len(all_data):,} records...", end='\r')
            offset += batch_size

            if len(batch) < batch_size:
                break

            time.sleep(0.5)

        except Exception as e:
            print(f"\n  Error at offset {offset}: {e}")
            break

    print(f"\n  Total records: {len(all_data):,}")

    if not all_data:
        return None

    df = pd.DataFrame(all_data)

    # Convert numeric columns
    numeric_cols = ['latitude', 'longitude', 'unitsres', 'unitstotal', 'comarea',
                   'resarea', 'officearea', 'retailarea', 'lotarea', 'yearbuilt']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Drop rows without coordinates
    df = df.dropna(subset=['latitude', 'longitude'])
    print(f"  Records with valid coordinates: {len(df):,}")

    # Create GeoDataFrame
    print("  Creating spatial points...")
    geometry = [Point(xy) for xy in zip(df['longitude'], df['latitude'])]
    gdf_pluto = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")

    # Load NTA boundaries
    print("  Loading NTA boundaries...")
    nta_path = PROJECT_ROOT / 'data' / 'external' / 'nta_boundaries_2020.geojson'
    if not nta_path.exists():
        nta_path = DATA_PROCESSED / 'nta_analysis_ready.geojson'

    gdf_nta = gpd.read_file(nta_path)

    # Ensure same CRS
    if gdf_nta.crs != gdf_pluto.crs:
        gdf_nta = gdf_nta.to_crs(gdf_pluto.crs)

    # Standardize NTA code column name
    if 'nta2020' in gdf_nta.columns:
        gdf_nta = gdf_nta.rename(columns={'nta2020': 'nta_code'})
    elif 'NTACode' in gdf_nta.columns:
        gdf_nta = gdf_nta.rename(columns={'NTACode': 'nta_code'})

    # Spatial join - assign each property to its NTA
    print("  Performing spatial join (this may take a moment)...")
    gdf_joined = gpd.sjoin(gdf_pluto, gdf_nta[['nta_code', 'geometry']], how='left', predicate='within')

    # Drop properties that didn't match any NTA
    gdf_joined = gdf_joined.dropna(subset=['nta_code'])
    print(f"  Properties matched to NTAs: {len(gdf_joined):,}")

    # Aggregate to NTA level
    print("  Aggregating by NTA...")
    agg = gdf_joined.groupby('nta_code').agg({
        'unitsres': 'sum',
        'unitstotal': 'sum',
        'comarea': 'sum',
        'resarea': 'sum',
        'officearea': 'sum',
        'retailarea': 'sum',
        'lotarea': 'sum',
        'yearbuilt': 'mean',
        'bldgclass': 'count'
    }).reset_index()

    agg = agg.rename(columns={
        'bldgclass': 'property_count',
        'unitsres': 'total_res_units',
        'unitstotal': 'total_units',
        'comarea': 'total_com_area',
        'resarea': 'total_res_area',
        'officearea': 'total_office_area',
        'retailarea': 'total_retail_area',
        'lotarea': 'total_lot_area',
        'yearbuilt': 'avg_year_built'
    })

    # Calculate derived metrics
    agg['pct_commercial'] = agg['total_com_area'] / (agg['total_com_area'] + agg['total_res_area'] + 1)
    agg['pct_residential'] = agg['total_res_area'] / (agg['total_com_area'] + agg['total_res_area'] + 1)
    agg['commercial_density'] = agg['total_com_area'] / (agg['total_lot_area'] + 1)
    agg['residential_density'] = agg['total_res_area'] / (agg['total_lot_area'] + 1)
    agg['office_share'] = agg['total_office_area'] / (agg['total_com_area'] + 1)
    agg['retail_share'] = agg['total_retail_area'] / (agg['total_com_area'] + 1)
    agg['avg_building_age'] = 2023 - agg['avg_year_built']

    output_path = DATA_RAW / 'pluto_nta_aggregated.csv'
    agg.to_csv(output_path, index=False)
    print(f"  Saved: {output_path} ({len(agg)} NTAs)")

    return agg


def download_nta_demographics():
    """Download NTA-level demographic data."""
    print("\n" + "="*60)
    print("Downloading NTA Demographics")
    print("="*60)

    # NTA demographics dataset
    url = "https://data.cityofnewyork.us/resource/swpk-hqdp.json?$limit=50000"

    print("  Fetching demographic data...")
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        data = r.json()

        df = pd.DataFrame(data)
        print(f"  Downloaded {len(df)} records")
        print(f"  Years available: {df['year'].unique()}")

        # Get most recent year
        df['year'] = pd.to_numeric(df['year'], errors='coerce')
        latest_year = df['year'].max()
        df_latest = df[df['year'] == latest_year].copy()

        # Convert population to numeric
        df_latest['population'] = pd.to_numeric(df_latest['population'], errors='coerce')

        # Keep relevant columns
        df_latest = df_latest[['nta_code', 'nta_name', 'borough', 'population']].drop_duplicates()

        output_path = DATA_RAW / 'nta_demographics.csv'
        df_latest.to_csv(output_path, index=False)
        print(f"  Saved: {output_path} ({len(df_latest)} NTAs, year={latest_year})")

        return df_latest

    except Exception as e:
        print(f"  Error: {e}")
        return None


def download_building_permits():
    """Download building permits and aggregate to NTA."""
    print("\n" + "="*60)
    print("Downloading Building Permits (2020-2023)")
    print("="*60)

    # DOB NOW permits dataset
    base_url = "https://data.cityofnewyork.us/resource/rbx6-tga4.json"

    print("  Fetching permit data...")

    all_permits = []
    offset = 0
    batch_size = 50000

    while True:
        url = f"{base_url}?$select=borough,nta,job_filing_number,filing_date&$where=filing_date >= '2020-07-01' AND filing_date <= '2023-12-31'&$limit={batch_size}&$offset={offset}"

        try:
            r = requests.get(url, timeout=120)

            if r.status_code != 200:
                # Try without NTA filter
                url = f"{base_url}?$select=borough,job_filing_number,filing_date&$where=filing_date >= '2020-07-01'&$limit={batch_size}&$offset={offset}"
                r = requests.get(url, timeout=120)

            if r.status_code != 200:
                break

            batch = r.json()
            if not batch:
                break

            all_permits.extend(batch)
            print(f"    Downloaded {len(all_permits):,} permits...", end='\r')
            offset += batch_size

            if len(batch) < batch_size:
                break

            time.sleep(0.5)

        except Exception as e:
            print(f"\n  Error: {e}")
            break

    print(f"\n  Total permits: {len(all_permits):,}")

    if not all_permits:
        return None

    df = pd.DataFrame(all_permits)

    # Aggregate by borough (NTA may not be available)
    if 'nta' in df.columns:
        agg = df.groupby('nta').size().reset_index(name='permit_count')
        agg = agg.rename(columns={'nta': 'nta_code'})
    else:
        agg = df.groupby('borough').size().reset_index(name='permit_count')
        print("  Note: Aggregating by borough (NTA not available in this dataset)")

    output_path = DATA_RAW / 'building_permits_agg.csv'
    agg.to_csv(output_path, index=False)
    print(f"  Saved: {output_path}")

    return agg


def create_combined_predictors():
    """Combine all predictors into single NTA-level file."""
    print("\n" + "="*60)
    print("Creating Combined Predictors File")
    print("="*60)

    # Load PLUTO as base
    pluto_path = DATA_RAW / 'pluto_nta_aggregated.csv'
    if pluto_path.exists():
        predictors = pd.read_csv(pluto_path)
        print(f"  Loaded PLUTO: {len(predictors)} areas, {len(predictors.columns)} features")
    else:
        print("  ERROR: PLUTO data not found")
        return None

    # Add demographics if available
    demo_path = DATA_RAW / 'nta_demographics.csv'
    if demo_path.exists():
        demo = pd.read_csv(demo_path)
        predictors = predictors.merge(demo[['nta_code', 'population']], on='nta_code', how='left')
        print(f"  Added demographics")

    # Calculate population density
    if 'population' in predictors.columns and 'total_lot_area' in predictors.columns:
        predictors['pop_density'] = predictors['population'] / (predictors['total_lot_area'] / 43560 + 1)  # per acre

    # Save
    output_path = DATA_RAW / 'nta_predictors.csv'
    predictors.to_csv(output_path, index=False)

    print(f"\n  Final predictors: {len(predictors)} areas, {len(predictors.columns)} features")
    print(f"  Saved: {output_path}")

    print("\n  Available features:")
    for col in predictors.columns:
        if col != 'nta_code':
            print(f"    - {col}")

    return predictors


if __name__ == '__main__':
    DATA_RAW.mkdir(parents=True, exist_ok=True)

    download_pluto_sample()
    time.sleep(1)

    download_nta_demographics()
    time.sleep(1)

    download_building_permits()

    create_combined_predictors()

    print("\n" + "="*60)
    print("PREDICTOR DOWNLOAD COMPLETE")
    print("="*60)
