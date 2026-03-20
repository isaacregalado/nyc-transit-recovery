#!/usr/bin/env python3
"""
Generate Figure 2: Choropleth map of the 4 Recovery Clusters.
"""

import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_PROCESSED = PROJECT_ROOT / 'data' / 'processed'
OUTPUT_FIGURES = PROJECT_ROOT / 'output' / 'figures'

# Load cluster data
gdf = gpd.read_file(DATA_PROCESSED / 'nta_final_with_clusters.geojson')
print(f"Loaded {len(gdf)} NTAs")
print(f"Columns: {list(gdf.columns)}")

# Check cluster distribution
print(f"\nCluster distribution:")
print(gdf['cluster_label'].value_counts())

# Define cluster colors and order (matching the report's Table 4)
cluster_info = {
    'Near-Full': {'color': '#2a9d8f', 'order': 1, 'desc': 'Mixed-use areas with local leisure travel'},
    'Steady': {'color': '#72b4d4', 'order': 2, 'desc': 'Residential hubs with essential transit'},
    'Lagging': {'color': '#f4a261', 'order': 3, 'desc': 'Manhattan core & wealthy suburbs'},
    'Struggling': {'color': '#e63946', 'order': 4, 'desc': 'Outer-borough areas with service cuts'},
}

# Create figure with map
fig, ax = plt.subplots(1, 1, figsize=(12, 14))

# Plot NTAs without subway service (gray background)
gdf_no_subway = gdf[gdf['cluster_label'].isna()]
if len(gdf_no_subway) > 0:
    gdf_no_subway.plot(ax=ax, color='#e8e8e8', edgecolor='#d0d0d0', linewidth=0.3)

# Plot each cluster with its color
for cluster_name, info in cluster_info.items():
    cluster_data = gdf[gdf['cluster_label'] == cluster_name]
    if len(cluster_data) > 0:
        cluster_data.plot(ax=ax, color=info['color'], edgecolor='white', linewidth=0.5)
        print(f"  {cluster_name}: {len(cluster_data)} NTAs")

# Set map bounds to NYC
ax.set_xlim([-74.3, -73.65])
ax.set_ylim([40.49, 40.92])

# Remove axes
ax.set_axis_off()

# Title
ax.set_title('Figure 2: NYC Subway Recovery Clusters\n133 Neighborhoods Classified by Recovery Trajectory',
             fontsize=16, fontweight='bold', pad=20)

# Create legend
legend_patches = []
for cluster_name in ['Near-Full', 'Steady', 'Lagging', 'Struggling']:
    info = cluster_info[cluster_name]
    count = len(gdf[gdf['cluster_label'] == cluster_name])
    patch = mpatches.Patch(
        color=info['color'],
        label=f"{cluster_name} (n={count})\n   {info['desc']}"
    )
    legend_patches.append(patch)

# Add "No Subway" to legend
legend_patches.append(mpatches.Patch(
    color='#e8e8e8',
    label=f"No Subway Service (n={len(gdf_no_subway)})"
))

# Position legend
legend = ax.legend(
    handles=legend_patches,
    loc='lower left',
    fontsize=10,
    frameon=True,
    facecolor='white',
    edgecolor='gray',
    framealpha=0.95,
    title='Recovery Clusters',
    title_fontsize=12
)

# Add borough labels
borough_labels = {
    'Manhattan': (-73.97, 40.78),
    'Brooklyn': (-73.95, 40.65),
    'Queens': (-73.82, 40.73),
    'Bronx': (-73.87, 40.86),
    'Staten Island': (-74.15, 40.58),
}

for borough, (lon, lat) in borough_labels.items():
    ax.annotate(borough, xy=(lon, lat), fontsize=11, fontweight='bold',
                ha='center', va='center', color='#333333',
                bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.7, edgecolor='none'))

plt.tight_layout()

# Save figure
output_path = OUTPUT_FIGURES / 'figure2_cluster_map.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
print(f"\nSaved figure to: {output_path}")

# Also save as PDF
output_pdf = OUTPUT_FIGURES / 'figure2_cluster_map.pdf'
plt.savefig(output_pdf, dpi=300, bbox_inches='tight', facecolor='white')
print(f"Saved PDF to: {output_pdf}")

print("\nDone!")
