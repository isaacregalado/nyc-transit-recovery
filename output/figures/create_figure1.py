#!/usr/bin/env python3
"""
Generate Figure 1: Side-by-side scatter plots showing the strong correlation
of features with Bounce-back vs. the weak correlation with True Recovery.
"""

import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from scipy import stats

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_RAW = PROJECT_ROOT / 'data' / 'raw'
DATA_EXTERNAL = PROJECT_ROOT / 'data' / 'external'
DATA_PROCESSED = PROJECT_ROOT / 'data' / 'processed'
OUTPUT_FIGURES = PROJECT_ROOT / 'output' / 'figures'

# Load recovery data
gdf = gpd.read_file(DATA_PROCESSED / 'nta_analysis_ready.geojson')
gdf_subway = gdf[gdf['recovery_index'].notna()].copy()
print(f"Loaded {len(gdf_subway)} NTAs with subway service")

# Load feature data from separate files
pluto_df = pd.read_csv(DATA_RAW / 'pluto_nta_aggregated.csv')
employment_df = pd.read_csv(DATA_RAW / 'nta_employment.csv')

# Load Census data and aggregate to NTA using crosswalk
census_df = pd.read_csv(DATA_RAW / 'census_acs_demographics.csv')
crosswalk_df = pd.read_csv(DATA_EXTERNAL / 'tract_nta_crosswalk.csv')

# Clean and merge census with crosswalk
census_df['tract_fips'] = census_df['tract_geoid'].astype(str)
crosswalk_df['tract_fips'] = crosswalk_df['tract_fips'].astype(str)
census_with_nta = census_df.merge(crosswalk_df, on='tract_fips', how='inner')

# Aggregate to NTA level
nta_demographics = census_with_nta.groupby('nta_code').agg({
    'median_income': 'median',
    'pct_bachelors': 'mean',
    'pct_white': 'mean',
    'pct_asian': 'mean',
}).reset_index()

print(f"PLUTO data: {len(pluto_df)} rows")
print(f"Employment data: {len(employment_df)} rows")
print(f"Census aggregated to NTA: {len(nta_demographics)} rows")

# Merge features with recovery data
gdf_merged = gdf_subway.merge(
    pluto_df[['nta_code', 'pct_commercial', 'commercial_density']],
    on='nta_code', how='left'
)
gdf_merged = gdf_merged.merge(
    employment_df[['nta_code', 'remote_work_score']],
    on='nta_code', how='left'
)
gdf_merged = gdf_merged.merge(
    nta_demographics[['nta_code', 'pct_bachelors', 'median_income']],
    on='nta_code', how='left'
)

print(f"Merged data: {len(gdf_merged)} rows")
print(f"Columns after merge: {list(gdf_merged.columns)}")

# Key features to plot (top predictors from Table 3)
features = {
    'pct_bachelors': 'Education (% Bachelor\'s+)',
    'pct_commercial': 'Commercial Land Use (%)',
    'remote_work_score': 'Remote Work Score'
}

# Set up the figure - 2 rows x 3 columns
fig, axes = plt.subplots(2, 3, figsize=(14, 9))

# Style settings
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.facecolor'] = '#fafafa'
plt.rcParams['figure.facecolor'] = 'white'
plt.rcParams['axes.grid'] = True
plt.rcParams['grid.alpha'] = 0.3

colors = {
    'bounce': '#2a9d8f',  # Teal for bounce-back
    'true': '#e63946'      # Red for true recovery
}

for col_idx, (feature, label) in enumerate(features.items()):
    # Top row: Bounce-back
    ax_top = axes[0, col_idx]
    x = gdf_merged[feature]
    y_bounce = gdf_merged['recovery_index']

    # Remove NaN values
    mask = ~(x.isna() | y_bounce.isna())
    x_clean = x[mask].values
    y_bounce_clean = y_bounce[mask].values

    if len(x_clean) > 5:
        # Scatter plot
        ax_top.scatter(x_clean, y_bounce_clean, alpha=0.6, s=50, c=colors['bounce'],
                      edgecolors='white', linewidth=0.5)

        # Regression line
        slope, intercept, r_value, p_value, std_err = stats.linregress(x_clean, y_bounce_clean)
        x_line = np.linspace(x_clean.min(), x_clean.max(), 100)
        y_line = slope * x_line + intercept
        ax_top.plot(x_line, y_line, color=colors['bounce'], linewidth=2.5, linestyle='-', alpha=0.9)

        # Annotations
        r_squared = r_value ** 2
        ax_top.annotate(f'R² = {r_squared:.2f}',
                        xy=(0.95, 0.95), xycoords='axes fraction',
                        ha='right', va='top', fontsize=12, fontweight='bold',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8, edgecolor='gray'))

    ax_top.set_xlabel(label, fontsize=11)
    if col_idx == 0:
        ax_top.set_ylabel('Bounce-back Index\n(Q4 2023 / Q3 2020)', fontsize=11)
    ax_top.set_title(f'{label}', fontsize=12, fontweight='bold')

    # Bottom row: True Recovery
    ax_bottom = axes[1, col_idx]
    y_true = gdf_merged['true_recovery_index']

    # Remove NaN values
    mask = ~(x.isna() | y_true.isna())
    x_clean = x[mask].values
    y_true_clean = y_true[mask].values

    if len(x_clean) > 5:
        # Scatter plot
        ax_bottom.scatter(x_clean, y_true_clean, alpha=0.6, s=50, c=colors['true'],
                         edgecolors='white', linewidth=0.5)

        # Regression line
        slope, intercept, r_value, p_value, std_err = stats.linregress(x_clean, y_true_clean)
        x_line = np.linspace(x_clean.min(), x_clean.max(), 100)
        y_line = slope * x_line + intercept
        ax_bottom.plot(x_line, y_line, color=colors['true'], linewidth=2.5, linestyle='-', alpha=0.9)

        # Annotations
        r_squared = r_value ** 2
        ax_bottom.annotate(f'R² = {r_squared:.2f}',
                           xy=(0.95, 0.95), xycoords='axes fraction',
                           ha='right', va='top', fontsize=12, fontweight='bold',
                           bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8, edgecolor='gray'))

    ax_bottom.set_xlabel(label, fontsize=11)
    if col_idx == 0:
        ax_bottom.set_ylabel('True Recovery Index\n(Q4 2023 / Jan-Feb 2020)', fontsize=11)

# Add row labels on the left
fig.text(0.02, 0.72, 'BOUNCE-BACK\n(Predictable)', fontsize=13, fontweight='bold',
         color=colors['bounce'], ha='left', va='center', rotation=90)
fig.text(0.02, 0.28, 'TRUE RECOVERY\n(Unpredictable)', fontsize=13, fontweight='bold',
         color=colors['true'], ha='left', va='center', rotation=90)

# Main title
fig.suptitle('Figure 1: Feature Correlations with Recovery Metrics\n'
             'Strong predictors of Bounce-back fail to predict True Recovery',
             fontsize=14, fontweight='bold', y=0.98)

plt.tight_layout(rect=[0.05, 0.02, 1, 0.95])

# Save figure
output_path = OUTPUT_FIGURES / 'figure1_feature_correlations.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
print(f"\nSaved figure to: {output_path}")

# Also save as PDF for the report
output_pdf = OUTPUT_FIGURES / 'figure1_feature_correlations.pdf'
plt.savefig(output_pdf, dpi=300, bbox_inches='tight', facecolor='white')
print(f"Saved PDF to: {output_pdf}")

print("\nDone!")
