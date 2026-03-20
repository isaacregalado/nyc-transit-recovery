#!/usr/bin/env python3
"""
NYC Transit Recovery Project - Data Processing Pipeline

This module handles all data cleaning, transformation, and integration
for the NYC transit recovery analysis.

Usage:
    python process_data.py

Output:
    - data/processed/nta_ridership_monthly.parquet
    - data/processed/nta_features.parquet
    - data/processed/nta_analysis_ready.parquet
"""

import pandas as pd
import geopandas as gpd
import numpy as np
from pathlib import Path
from datetime import datetime
import warnings
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', message='.*CRS.*')

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
DATA_EXTERNAL = PROJECT_ROOT / "data" / "external"


# =============================================================================
# NTA Boundaries
# =============================================================================

def load_nta_boundaries() -> gpd.GeoDataFrame:
    """Load NYC Neighborhood Tabulation Area boundaries."""
    print("Loading NTA boundaries...")

    nta_path = DATA_EXTERNAL / "nta_boundaries_2020.geojson"

    if not nta_path.exists():
        raise FileNotFoundError(f"NTA boundaries not found at {nta_path}. Run download_all.py first.")

    gdf = gpd.read_file(nta_path)

    # Standardize column names (2020 NTA format)
    gdf = gdf.rename(columns={
        'nta2020': 'nta_code',
        'ntaname': 'nta_name',
        'borocode': 'borough_code',
        'boroname': 'borough_name'
    })

    # Filter to actual neighborhoods (exclude parks, airports, cemeteries)
    # NTA codes starting with 99 are non-residential
    gdf = gdf[~gdf['nta_code'].str.startswith('99', na=False)]

    print(f"  Loaded {len(gdf)} NTAs")
    return gdf


# =============================================================================
# MTA Ridership Processing
# =============================================================================

def load_mta_ridership() -> pd.DataFrame:
    """Load MTA subway ridership data (daily aggregated version)."""
    print("Loading MTA ridership data...")

    # Try daily file first (smaller, faster), then hourly
    daily_path = DATA_RAW / "mta_subway_daily_ridership.csv"
    hourly_path = DATA_RAW / "mta_subway_hourly_ridership_2020_2024.csv"

    if daily_path.exists():
        print("  Using daily aggregated data...")
        df = pd.read_csv(
            daily_path,
            dtype={
                'station_complex_id': str,
                'station_complex': str,
                'daily_ridership': float,
                'latitude': float,
                'longitude': float
            }
        )
        # Parse date
        df['date'] = pd.to_datetime(df['date'])
        # Rename for consistency
        df = df.rename(columns={'daily_ridership': 'ridership'})
        print(f"  Loaded {len(df):,} daily records")
        return df

    elif hourly_path.exists():
        print("  Using hourly data (this may take a while)...")
        df = pd.read_csv(
            hourly_path,
            parse_dates=['transit_timestamp'],
            dtype={
                'station_complex_id': str,
                'station_complex': str,
                'borough': str,
                'ridership': float,
                'latitude': float,
                'longitude': float
            },
            low_memory=False
        )
        print(f"  Loaded {len(df):,} hourly records")
        return df

    else:
        raise FileNotFoundError(
            f"MTA data not found. Run: python src/data/download_mta_filtered.py"
        )


def aggregate_ridership_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate ridership to monthly by station."""
    print("Aggregating ridership to monthly...")

    # Handle both daily and hourly data formats
    if 'date' in df.columns:
        df['year_month'] = df['date'].dt.to_period('M')
    else:
        df['year_month'] = df['transit_timestamp'].dt.to_period('M')

    monthly = df.groupby(['station_complex_id', 'station_complex', 'latitude', 'longitude', 'year_month']).agg({
        'ridership': 'sum'
    }).reset_index()

    monthly['year_month'] = monthly['year_month'].astype(str)

    print(f"  Created {len(monthly):,} station-month records")
    return monthly


def map_stations_to_nta(stations_df: pd.DataFrame, nta_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """Spatially join stations to NTAs based on coordinates."""
    print("Mapping stations to NTAs...")

    # Get unique stations with coordinates
    stations = stations_df[['station_complex_id', 'station_complex', 'latitude', 'longitude']].drop_duplicates()

    # Create GeoDataFrame from stations
    stations_gdf = gpd.GeoDataFrame(
        stations,
        geometry=gpd.points_from_xy(stations['longitude'], stations['latitude']),
        crs="EPSG:4326"
    )

    # Ensure NTA is in same CRS
    nta_gdf = nta_gdf.to_crs("EPSG:4326")

    # Spatial join
    stations_with_nta = gpd.sjoin(stations_gdf, nta_gdf[['nta_code', 'nta_name', 'borough_name', 'geometry']],
                                   how='left', predicate='within')

    # Handle stations that didn't match (edge cases)
    unmatched = stations_with_nta['nta_code'].isna().sum()
    if unmatched > 0:
        print(f"  Warning: {unmatched} stations didn't match to NTAs")

    print(f"  Mapped {len(stations_with_nta)} stations to NTAs")
    return stations_with_nta[['station_complex_id', 'nta_code', 'nta_name', 'borough_name']]


def aggregate_ridership_to_nta(ridership_df: pd.DataFrame, station_nta_map: pd.DataFrame) -> pd.DataFrame:
    """Aggregate station-level ridership to NTA level."""
    print("Aggregating ridership to NTA level...")

    # Join ridership with NTA mapping
    df = ridership_df.merge(station_nta_map, on='station_complex_id', how='left')

    # Aggregate to NTA-month
    nta_ridership = df.groupby(['nta_code', 'nta_name', 'borough_name', 'year_month']).agg({
        'ridership': 'sum',
        'station_complex_id': 'nunique'  # Count of stations
    }).reset_index()

    nta_ridership = nta_ridership.rename(columns={'station_complex_id': 'station_count'})

    print(f"  Created {len(nta_ridership):,} NTA-month records")
    return nta_ridership


# =============================================================================
# Recovery Index Calculation
# =============================================================================

def calculate_recovery_index(nta_ridership: pd.DataFrame, station_nta_map: pd.DataFrame = None) -> pd.DataFrame:
    """
    Calculate recovery indices for each NTA.

    Two metrics:
    1. Recovery Index (from low) = Q4 2023 / Q3 2020 (COVID low point)
    2. True Recovery Index = Q4 2023 / Pre-COVID baseline (Jan-Feb 2020)

    The second metric shows actual recovery to pre-pandemic levels.
    """
    print("Calculating recovery indices...")

    # Define periods
    covid_low_months = ['2020-07', '2020-08', '2020-09']  # Q3 2020
    recovery_months = ['2023-10', '2023-11', '2023-12']   # Q4 2023

    # Calculate COVID low baseline
    covid_low = nta_ridership[nta_ridership['year_month'].isin(covid_low_months)].groupby('nta_code').agg({
        'ridership': 'mean'
    }).rename(columns={'ridership': 'covid_low_ridership'})

    # Calculate current state (Q4 2023)
    current = nta_ridership[nta_ridership['year_month'].isin(recovery_months)].groupby('nta_code').agg({
        'ridership': 'mean'
    }).rename(columns={'ridership': 'current_ridership'})

    # Join metrics
    idx = covid_low.join(current, how='inner')

    # Recovery from COVID low
    idx['recovery_index'] = idx['current_ridership'] / idx['covid_low_ridership']

    # Try to load pre-COVID baseline
    precovid_path = DATA_RAW / 'mta_precovid_daily.csv'
    if precovid_path.exists() and station_nta_map is not None:
        print("  Loading pre-COVID baseline (Jan-Feb 2020)...")
        precovid = pd.read_csv(precovid_path)
        precovid['date'] = pd.to_datetime(precovid['date'])

        # Map to NTAs
        precovid = precovid.merge(
            station_nta_map[['station_complex_id', 'nta_code']],
            on='station_complex_id',
            how='left'
        )

        # Aggregate to NTA (average monthly equivalent)
        # Jan-Feb 2020 = ~60 days, scale to monthly
        precovid_nta = precovid.groupby('nta_code').agg({
            'daily_ridership': 'sum'
        })
        # Convert to monthly average (60 days -> 30 days)
        precovid_nta['precovid_ridership'] = precovid_nta['daily_ridership'] / 2
        precovid_nta = precovid_nta.drop(columns=['daily_ridership'])

        # Join with recovery data
        idx = idx.join(precovid_nta, how='left')

        # True recovery (vs pre-COVID)
        idx['true_recovery_index'] = idx['current_ridership'] / idx['precovid_ridership']

        # Recovery gap (how far from pre-COVID levels)
        idx['recovery_gap'] = (idx['precovid_ridership'] - idx['current_ridership']) / idx['precovid_ridership'] * 100

        print(f"  Pre-COVID baseline added for {idx['precovid_ridership'].notna().sum()} NTAs")
        print(f"  Mean true recovery: {idx['true_recovery_index'].mean():.2f}x pre-COVID")
    else:
        print("  Pre-COVID data not available, using recovery from low only")
        idx['precovid_ridership'] = np.nan
        idx['true_recovery_index'] = np.nan
        idx['recovery_gap'] = np.nan

    # Handle edge cases
    idx['recovery_index'] = idx['recovery_index'].replace([np.inf, -np.inf], np.nan)
    idx['true_recovery_index'] = idx['true_recovery_index'].replace([np.inf, -np.inf], np.nan)

    # Rename for clarity
    idx = idx.rename(columns={
        'covid_low_ridership': 'baseline_ridership',
        'current_ridership': 'recovery_ridership'
    })

    # Calculate additional metrics
    idx['absolute_change'] = idx['recovery_ridership'] - idx['baseline_ridership']
    idx['pct_change'] = (idx['absolute_change'] / idx['baseline_ridership']) * 100

    print(f"\n  Recovery Metrics Summary ({len(idx)} NTAs):")
    print(f"  Recovery from COVID low: mean={idx['recovery_index'].mean():.2f}x, range=[{idx['recovery_index'].min():.2f}, {idx['recovery_index'].max():.2f}]")
    if idx['true_recovery_index'].notna().any():
        print(f"  True recovery (vs pre-COVID): mean={idx['true_recovery_index'].mean():.2f}x, range=[{idx['true_recovery_index'].min():.2f}, {idx['true_recovery_index'].max():.2f}]")
        below_precovid = (idx['true_recovery_index'] < 1.0).sum()
        print(f"  NTAs still below pre-COVID levels: {below_precovid} ({below_precovid/len(idx)*100:.0f}%)")

    return idx.reset_index()


# =============================================================================
# Building Permits Processing
# =============================================================================

def load_building_permits(nta_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """Load and process building permits, aggregate to NTA."""
    print("Loading building permits...")

    permits_path = DATA_RAW / "dob_permit_issuance.csv"

    if not permits_path.exists():
        print("  Building permits not found, skipping...")
        return None

    # Load with relevant columns only
    cols = ['Job Filing Number', 'Filing Date', 'Permit Type', 'Permit Status',
            'Borough', 'Latitude', 'Longitude']

    df = pd.read_csv(permits_path, usecols=cols, low_memory=False)

    # Parse dates and filter to analysis period
    df['Filing Date'] = pd.to_datetime(df['Filing Date'], errors='coerce')
    df = df[(df['Filing Date'] >= '2020-07-01') & (df['Filing Date'] <= '2023-12-31')]

    # Filter to rows with valid coordinates
    df = df.dropna(subset=['Latitude', 'Longitude'])

    # Create GeoDataFrame and map to NTAs
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df['Longitude'], df['Latitude']),
        crs="EPSG:4326"
    )

    nta_gdf = nta_gdf.to_crs("EPSG:4326")
    permits_with_nta = gpd.sjoin(gdf, nta_gdf[['nta_code', 'geometry']], how='left', predicate='within')

    # Aggregate to NTA
    nta_permits = permits_with_nta.groupby('nta_code').agg({
        'Job Filing Number': 'count'
    }).rename(columns={'Job Filing Number': 'permit_count'})

    print(f"  Processed {len(nta_permits)} NTAs with permit data")
    return nta_permits


# =============================================================================
# 311 Complaints Processing
# =============================================================================

def load_311_complaints(nta_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """Load and process 311 complaints, aggregate to NTA."""
    print("Loading 311 complaints...")

    complaints_path = DATA_RAW / "311_complaints_2020_present.csv"

    if not complaints_path.exists():
        print("  311 complaints not found, skipping...")
        return None

    # Load with relevant columns only (this is a large file)
    cols = ['Unique Key', 'Created Date', 'Complaint Type', 'Latitude', 'Longitude']

    # Read in chunks due to file size
    chunk_size = 500000
    chunks = []

    for chunk in pd.read_csv(complaints_path, usecols=cols, chunksize=chunk_size, low_memory=False):
        chunk['Created Date'] = pd.to_datetime(chunk['Created Date'], errors='coerce')
        chunk = chunk[(chunk['Created Date'] >= '2020-07-01') & (chunk['Created Date'] <= '2023-12-31')]
        chunk = chunk.dropna(subset=['Latitude', 'Longitude'])
        chunks.append(chunk)

    df = pd.concat(chunks, ignore_index=True)

    # Create GeoDataFrame and map to NTAs
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df['Longitude'], df['Latitude']),
        crs="EPSG:4326"
    )

    nta_gdf = nta_gdf.to_crs("EPSG:4326")
    complaints_with_nta = gpd.sjoin(gdf, nta_gdf[['nta_code', 'geometry']], how='left', predicate='within')

    # Aggregate to NTA
    nta_complaints = complaints_with_nta.groupby('nta_code').agg({
        'Unique Key': 'count'
    }).rename(columns={'Unique Key': 'complaint_count'})

    print(f"  Processed {len(nta_complaints)} NTAs with complaint data")
    return nta_complaints


# =============================================================================
# PLUTO Processing
# =============================================================================

def load_pluto_data(nta_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """Load and process PLUTO property data, aggregate to NTA."""
    print("Loading PLUTO data...")

    pluto_path = DATA_RAW / "pluto_2020.csv"

    if not pluto_path.exists():
        print("  PLUTO data not found, skipping...")
        return None

    # Load relevant columns
    cols = ['Borough', 'ZipCode', 'LandUse', 'BldgClass', 'ResArea', 'ComArea',
            'OfficeArea', 'RetailArea', 'UnitsRes', 'UnitsTotal', 'AssessTot',
            'Latitude', 'Longitude', 'NTA2020']

    df = pd.read_csv(pluto_path, usecols=cols, low_memory=False)

    # Use NTA2020 column if available, otherwise spatial join
    if 'NTA2020' in df.columns:
        df = df.rename(columns={'NTA2020': 'nta_code'})

    # Aggregate to NTA
    nta_pluto = df.groupby('nta_code').agg({
        'ResArea': 'sum',
        'ComArea': 'sum',
        'OfficeArea': 'sum',
        'RetailArea': 'sum',
        'UnitsRes': 'sum',
        'UnitsTotal': 'sum',
        'AssessTot': 'sum',
        'Borough': 'count'  # Property count
    }).rename(columns={'Borough': 'property_count'})

    # Calculate derived metrics
    nta_pluto['pct_residential'] = nta_pluto['ResArea'] / (nta_pluto['ResArea'] + nta_pluto['ComArea'] + 1)
    nta_pluto['pct_commercial'] = nta_pluto['ComArea'] / (nta_pluto['ResArea'] + nta_pluto['ComArea'] + 1)
    nta_pluto['pct_office'] = nta_pluto['OfficeArea'] / (nta_pluto['ComArea'] + 1)
    nta_pluto['pct_retail'] = nta_pluto['RetailArea'] / (nta_pluto['ComArea'] + 1)

    print(f"  Processed {len(nta_pluto)} NTAs with PLUTO data")
    return nta_pluto


# =============================================================================
# Feature Assembly
# =============================================================================

def assemble_nta_features(
    recovery_idx: pd.DataFrame,
    nta_gdf: gpd.GeoDataFrame,
    permits: pd.DataFrame = None,
    complaints: pd.DataFrame = None,
    pluto: pd.DataFrame = None
) -> gpd.GeoDataFrame:
    """Assemble all features into a single NTA-level dataset."""
    print("Assembling NTA features...")

    # Start with NTA boundaries
    features = nta_gdf[['nta_code', 'nta_name', 'borough_name', 'geometry']].copy()

    # Add recovery index
    features = features.merge(recovery_idx, on='nta_code', how='left')

    # Add permits
    if permits is not None:
        features = features.merge(permits, on='nta_code', how='left')
        features['permit_count'] = features['permit_count'].fillna(0)

    # Add complaints
    if complaints is not None:
        features = features.merge(complaints, on='nta_code', how='left')
        features['complaint_count'] = features['complaint_count'].fillna(0)

    # Add PLUTO
    if pluto is not None:
        features = features.merge(pluto, on='nta_code', how='left')

    print(f"  Assembled {len(features)} NTAs with {len(features.columns)} features")
    return features


# =============================================================================
# Main Pipeline
# =============================================================================

def run_pipeline():
    """Run the complete data processing pipeline."""
    print("\n" + "="*60)
    print("NYC TRANSIT RECOVERY - DATA PROCESSING PIPELINE")
    print("="*60)
    print(f"Started: {datetime.now().isoformat()}")

    # Create output directory
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)

    # Load NTA boundaries (required)
    nta_gdf = load_nta_boundaries()

    # Process MTA ridership
    try:
        mta_raw = load_mta_ridership()
        mta_monthly = aggregate_ridership_monthly(mta_raw)
        station_nta_map = map_stations_to_nta(mta_monthly, nta_gdf)
        nta_ridership = aggregate_ridership_to_nta(mta_monthly, station_nta_map)
        recovery_idx = calculate_recovery_index(nta_ridership, station_nta_map)

        # Save ridership data
        nta_ridership.to_parquet(DATA_PROCESSED / "nta_ridership_monthly.parquet")
        print(f"  Saved: nta_ridership_monthly.parquet")
    except FileNotFoundError as e:
        print(f"  Skipping MTA processing: {e}")
        recovery_idx = None

    # Process additional datasets
    permits = load_building_permits(nta_gdf)
    complaints = load_311_complaints(nta_gdf)
    pluto = load_pluto_data(nta_gdf)

    # Assemble features
    if recovery_idx is not None:
        features = assemble_nta_features(recovery_idx, nta_gdf, permits, complaints, pluto)

        # Save
        features.to_parquet(DATA_PROCESSED / "nta_analysis_ready.parquet")
        print(f"  Saved: nta_analysis_ready.parquet")

        # Also save as GeoJSON for visualization
        features.to_file(DATA_PROCESSED / "nta_analysis_ready.geojson", driver="GeoJSON")
        print(f"  Saved: nta_analysis_ready.geojson")

    print("\n" + "="*60)
    print(f"Pipeline completed: {datetime.now().isoformat()}")
    print("="*60)


if __name__ == "__main__":
    run_pipeline()
