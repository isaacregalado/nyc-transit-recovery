#!/usr/bin/env python3
"""
Process LEHD LODES employment data to calculate remote work potential by NTA.

LEHD WAC (Workplace Area Characteristics) contains jobs by industry at census block level.
We aggregate to NTAs and calculate what % of jobs are in "remote-work-capable" industries.
"""

import pandas as pd
import geopandas as gpd
from pathlib import Path
import numpy as np

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_RAW = PROJECT_ROOT / 'data' / 'raw'
DATA_PROCESSED = PROJECT_ROOT / 'data' / 'processed'
DATA_EXTERNAL = PROJECT_ROOT / 'data' / 'external'

# NYC county FIPS codes (first 5 digits of census block)
NYC_COUNTIES = {
    '36005': 'Bronx',
    '36047': 'Brooklyn',
    '36061': 'Manhattan',
    '36081': 'Queens',
    '36085': 'Staten Island'
}

# Industry codes and their remote work potential
# Based on research on which industries shifted to remote work during COVID
INDUSTRY_CODES = {
    'CNS01': ('Agriculture', 'low'),
    'CNS02': ('Mining', 'low'),
    'CNS03': ('Utilities', 'low'),
    'CNS04': ('Construction', 'low'),
    'CNS05': ('Manufacturing', 'low'),
    'CNS06': ('Wholesale Trade', 'low'),
    'CNS07': ('Retail Trade', 'low'),
    'CNS08': ('Transportation & Warehousing', 'low'),
    'CNS09': ('Information', 'high'),  # Tech, media, telecom
    'CNS10': ('Finance & Insurance', 'high'),  # Banking, insurance
    'CNS11': ('Real Estate', 'medium'),
    'CNS12': ('Professional/Scientific/Technical', 'high'),  # Consulting, legal, accounting
    'CNS13': ('Management of Companies', 'high'),  # Corporate HQs
    'CNS14': ('Administrative Support', 'medium'),
    'CNS15': ('Educational Services', 'medium'),
    'CNS16': ('Healthcare', 'low'),  # nurses, doctors etc - cant work from home obviously
    'CNS17': ('Arts/Entertainment', 'low'),
    'CNS18': ('Accommodation & Food Services', 'low'),  # Restaurants, hotels
    'CNS19': ('Other Services', 'low'),
    'CNS20': ('Public Administration', 'medium'),
}

HIGH_REMOTE = ['CNS09', 'CNS10', 'CNS12', 'CNS13']
MEDIUM_REMOTE = ['CNS11', 'CNS14', 'CNS15', 'CNS20']
LOW_REMOTE = ['CNS01', 'CNS02', 'CNS03', 'CNS04', 'CNS05', 'CNS06', 'CNS07',
              'CNS08', 'CNS16', 'CNS17', 'CNS18', 'CNS19']


def load_and_filter_lehd():
    """Load LEHD data and filter to NYC."""
    print("Loading LEHD WAC data...")

    df = pd.read_csv(DATA_RAW / 'ny_wac_2019.csv.gz', compression='gzip')
    print(f"  Total NY records: {len(df):,}")

    # Convert geocode to string and extract county FIPS
    df['w_geocode'] = df['w_geocode'].astype(str).str.zfill(15)
    df['county_fips'] = df['w_geocode'].str[:5]

    # Filter to NYC
    df_nyc = df[df['county_fips'].isin(NYC_COUNTIES.keys())].copy()
    print(f"  NYC records: {len(df_nyc):,}")

    # Extract census tract (first 11 digits of block code)
    df_nyc['tract_fips'] = df_nyc['w_geocode'].str[:11]

    return df_nyc


def calculate_remote_potential(df):
    """Calculate remote work potential metrics."""
    print("Calculating remote work potential...")

    # Total jobs
    df['total_jobs'] = df['C000']

    # Jobs by remote potential
    df['high_remote_jobs'] = df[HIGH_REMOTE].sum(axis=1)
    df['medium_remote_jobs'] = df[MEDIUM_REMOTE].sum(axis=1)
    df['low_remote_jobs'] = df[LOW_REMOTE].sum(axis=1)

    # Key industry jobs
    df['finance_jobs'] = df['CNS10']
    df['professional_jobs'] = df['CNS12']
    df['info_tech_jobs'] = df['CNS09']
    df['retail_jobs'] = df['CNS07']
    df['food_service_jobs'] = df['CNS18']
    df['healthcare_jobs'] = df['CNS16']

    return df


def aggregate_to_tract(df):
    """Aggregate block-level data to census tract."""
    print("Aggregating to census tract level...")

    agg_cols = ['total_jobs', 'high_remote_jobs', 'medium_remote_jobs', 'low_remote_jobs',
                'finance_jobs', 'professional_jobs', 'info_tech_jobs',
                'retail_jobs', 'food_service_jobs', 'healthcare_jobs']

    tract_df = df.groupby('tract_fips')[agg_cols].sum().reset_index()
    print(f"  Census tracts: {len(tract_df):,}")

    return tract_df


def load_tract_to_nta_crosswalk():
    """Load or create tract to NTA mapping."""
    print("Loading tract-to-NTA crosswalk...")

    # Try to load existing crosswalk
    crosswalk_path = DATA_EXTERNAL / 'tract_nta_crosswalk.csv'
    if crosswalk_path.exists():
        return pd.read_csv(crosswalk_path)

    # Need to create crosswalk using spatial join
    print("  Creating crosswalk from spatial data...")

    # Load NTA boundaries
    nta_path = DATA_EXTERNAL / 'nta_boundaries_2020.geojson'
    if not nta_path.exists():
        nta_path = DATA_PROCESSED / 'nta_analysis_ready.geojson'

    gdf_nta = gpd.read_file(nta_path)

    # Standardize NTA code column
    if 'nta2020' in gdf_nta.columns:
        gdf_nta = gdf_nta.rename(columns={'nta2020': 'nta_code'})
    elif 'NTACode' in gdf_nta.columns:
        gdf_nta = gdf_nta.rename(columns={'NTACode': 'nta_code'})

    # Load census tract boundaries
    # Try to download from Census
    tract_url = "https://www2.census.gov/geo/tiger/TIGER2020/TRACT/tl_2020_36_tract.zip"
    tract_path = DATA_EXTERNAL / 'ny_tracts_2020.zip'

    if not tract_path.exists():
        print("  Downloading census tract boundaries...")
        import requests
        r = requests.get(tract_url, timeout=120)
        with open(tract_path, 'wb') as f:
            f.write(r.content)

    gdf_tract = gpd.read_file(f"zip://{tract_path}")

    # Filter to NYC counties
    nyc_county_fps = ['005', '047', '061', '081', '085']
    gdf_tract = gdf_tract[gdf_tract['COUNTYFP'].isin(nyc_county_fps)].copy()

    # Create tract FIPS
    gdf_tract['tract_fips'] = gdf_tract['STATEFP'] + gdf_tract['COUNTYFP'] + gdf_tract['TRACTCE']

    # Ensure same CRS
    if gdf_tract.crs != gdf_nta.crs:
        gdf_tract = gdf_tract.to_crs(gdf_nta.crs)

    # Calculate tract centroids for assignment
    gdf_tract['centroid'] = gdf_tract.geometry.centroid
    gdf_tract_points = gdf_tract.set_geometry('centroid')

    # Spatial join - assign each tract to an NTA based on centroid
    joined = gpd.sjoin(gdf_tract_points[['tract_fips', 'centroid']],
                       gdf_nta[['nta_code', 'geometry']],
                       how='left', predicate='within')

    crosswalk = joined[['tract_fips', 'nta_code']].dropna()
    print(f"  Mapped {len(crosswalk)} tracts to NTAs")

    # Save crosswalk
    crosswalk.to_csv(crosswalk_path, index=False)

    return crosswalk


def aggregate_to_nta(tract_df, crosswalk):
    """Aggregate tract-level data to NTA."""
    print("Aggregating to NTA level...")

    # Merge tract data with crosswalk
    merged = tract_df.merge(crosswalk, on='tract_fips', how='inner')
    print(f"  Tracts matched to NTAs: {len(merged):,}")

    # Aggregate to NTA
    agg_cols = ['total_jobs', 'high_remote_jobs', 'medium_remote_jobs', 'low_remote_jobs',
                'finance_jobs', 'professional_jobs', 'info_tech_jobs',
                'retail_jobs', 'food_service_jobs', 'healthcare_jobs']

    nta_df = merged.groupby('nta_code')[agg_cols].sum().reset_index()

    # Calculate percentages
    nta_df['pct_high_remote'] = nta_df['high_remote_jobs'] / (nta_df['total_jobs'] + 1)
    nta_df['pct_medium_remote'] = nta_df['medium_remote_jobs'] / (nta_df['total_jobs'] + 1)
    nta_df['pct_low_remote'] = nta_df['low_remote_jobs'] / (nta_df['total_jobs'] + 1)

    # Remote work potential score (weighted)
    nta_df['remote_work_score'] = (
        nta_df['pct_high_remote'] * 1.0 +
        nta_df['pct_medium_remote'] * 0.5 +
        nta_df['pct_low_remote'] * 0.1
    )

    # Specific industry shares
    nta_df['pct_finance'] = nta_df['finance_jobs'] / (nta_df['total_jobs'] + 1)
    nta_df['pct_professional'] = nta_df['professional_jobs'] / (nta_df['total_jobs'] + 1)
    nta_df['pct_info_tech'] = nta_df['info_tech_jobs'] / (nta_df['total_jobs'] + 1)
    nta_df['pct_retail'] = nta_df['retail_jobs'] / (nta_df['total_jobs'] + 1)
    nta_df['pct_food_service'] = nta_df['food_service_jobs'] / (nta_df['total_jobs'] + 1)
    nta_df['pct_healthcare'] = nta_df['healthcare_jobs'] / (nta_df['total_jobs'] + 1)

    # Office job share (finance + professional + info tech + management)
    nta_df['pct_office_jobs'] = nta_df['pct_finance'] + nta_df['pct_professional'] + nta_df['pct_info_tech']

    print(f"  NTAs with employment data: {len(nta_df)}")

    return nta_df


def main():
    """Main processing pipeline."""
    print("="*60)
    print("Processing Employment Data for Remote Work Analysis")
    print("="*60)

    # Load and process LEHD data
    df = load_and_filter_lehd()
    df = calculate_remote_potential(df)
    tract_df = aggregate_to_tract(df)

    # Load crosswalk and aggregate to NTA
    crosswalk = load_tract_to_nta_crosswalk()
    nta_employment = aggregate_to_nta(tract_df, crosswalk)

    # Save
    output_path = DATA_RAW / 'nta_employment.csv'
    nta_employment.to_csv(output_path, index=False)
    print(f"\nSaved: {output_path}")

    # Summary stats
    print("\n" + "="*60)
    print("Summary Statistics")
    print("="*60)
    print(f"Total NTAs: {len(nta_employment)}")
    print(f"Total jobs in NYC: {nta_employment['total_jobs'].sum():,.0f}")
    print(f"\nRemote work potential distribution:")
    print(f"  High remote jobs: {nta_employment['high_remote_jobs'].sum():,.0f} ({nta_employment['high_remote_jobs'].sum()/nta_employment['total_jobs'].sum()*100:.1f}%)")
    print(f"  Medium remote jobs: {nta_employment['medium_remote_jobs'].sum():,.0f} ({nta_employment['medium_remote_jobs'].sum()/nta_employment['total_jobs'].sum()*100:.1f}%)")
    print(f"  Low remote jobs: {nta_employment['low_remote_jobs'].sum():,.0f} ({nta_employment['low_remote_jobs'].sum()/nta_employment['total_jobs'].sum()*100:.1f}%)")

    print(f"\nTop 5 NTAs by office job share:")
    top_office = nta_employment.nlargest(5, 'pct_office_jobs')[['nta_code', 'total_jobs', 'pct_office_jobs']]
    for _, row in top_office.iterrows():
        print(f"  {row['nta_code']}: {row['pct_office_jobs']*100:.1f}% office jobs ({row['total_jobs']:,.0f} total)")

    return nta_employment


if __name__ == '__main__':
    main()
