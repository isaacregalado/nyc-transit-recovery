#!/usr/bin/env python3
"""
NYC Transit Recovery Dashboard
Interactive visualization for CSE 6242 term project.
"""

import os
import json
import pandas as pd
import geopandas as gpd
import numpy as np
import folium
import branca.colormap as cm
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_RAW = PROJECT_ROOT / 'data' / 'raw'
DATA_PROCESSED = PROJECT_ROOT / 'data' / 'processed'
OUTPUT_FIGURES = PROJECT_ROOT / 'output' / 'figures'
OUTPUT_TABLES = PROJECT_ROOT / 'output' / 'tables'

# Map tile URL (free CartoDB Positron - no token required)
TILE_URL = 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png'
TILE_ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>'


def create_recovery_map(gdf, metric='recovery_index'):
    """Create minimal choropleth map for specified metric."""

    # NYC bounding box
    nyc_sw = [40.45, -74.35]
    nyc_ne = [40.95, -73.60]

    m = folium.Map(
        location=[40.7128, -74.0060],
        zoom_start=11,
        tiles=None,
        control_scale=False,
        zoom_control=True
    )

    folium.TileLayer(
        tiles=TILE_URL,
        attr=TILE_ATTR,
        name='CartoDB Positron',
        overlay=False,
        control=False
    ).add_to(m)

    # Different color scales for different metrics
    if metric == 'true_recovery_index':
        colormap = cm.LinearColormap(
            colors=['#e63946', '#f4a261', '#e9c46a', '#2a9d8f'],
            vmin=0.2,
            vmax=1.0,
            caption=''
        )
    else:
        colormap = cm.LinearColormap(
            colors=['#e76f51', '#f4a261', '#72b4d4', '#2a9d8f'],
            vmin=0.5,
            vmax=4.0,
            caption=''
        )

    def style_function(feature):
        value = feature['properties'].get(metric)
        if value is not None and not pd.isna(value):
            return {
                'fillColor': colormap(value),
                'color': 'white',
                'weight': 1.5,
                'fillOpacity': 0.85,
            }
        else:
            return {
                'fillColor': '#e8e8e8',
                'color': '#d0d0d0',
                'weight': 0.5,
                'fillOpacity': 0.4,
            }

    def highlight_function(feature):
        return {
            'fillColor': '#ffffff',
            'color': '#1a1a2e',
            'weight': 3,
            'fillOpacity': 0.3,
        }

    # Enhanced tooltip
    if metric == 'true_recovery_index':
        tooltip_fields = ['nta_name', 'borough_name', 'true_recovery_index', 'recovery_index']
        tooltip_aliases = ['Neighborhood', 'Borough', 'True Recovery', 'From Low']
    else:
        tooltip_fields = ['nta_name', 'borough_name', 'recovery_index', 'true_recovery_index']
        tooltip_aliases = ['Neighborhood', 'Borough', 'From Low', 'True Recovery']

    folium.GeoJson(
        gdf.__geo_interface__,
        style_function=style_function,
        highlight_function=highlight_function,
        tooltip=folium.GeoJsonTooltip(
            fields=tooltip_fields,
            aliases=tooltip_aliases,
            localize=True,
            sticky=False,
            labels=True,
            style="""
                background-color: rgba(255,255,255,0.98);
                border: none;
                border-radius: 12px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.18);
                padding: 16px 20px;
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
                font-size: 13px;
                line-height: 1.6;
            """
        )
    ).add_to(m)

    return m


def create_cluster_map(gdf):
    """Create choropleth map colored by recovery cluster."""

    m = folium.Map(
        location=[40.7128, -74.0060],
        zoom_start=11,
        tiles=None,
        control_scale=False,
        zoom_control=True
    )

    folium.TileLayer(
        tiles=TILE_URL,
        attr=TILE_ATTR,
        name='CartoDB Positron',
        overlay=False,
        control=False
    ).add_to(m)

    # Cluster colors matching the table (labels without " Recovery" suffix)
    cluster_colors = {
        'Near-Full': '#2a9d8f',
        'Steady': '#72b4d4',
        'Lagging': '#f4a261',
        'Struggling': '#e63946',
        # Also support labels with " Recovery" suffix for backwards compatibility
        'Near-Full Recovery': '#2a9d8f',
        'Steady Recovery': '#72b4d4',
        'Lagging Recovery': '#f4a261',
        'Struggling Recovery': '#e63946'
    }

    def style_function(feature):
        cluster_label = feature['properties'].get('cluster_label')
        if cluster_label and cluster_label in cluster_colors:
            return {
                'fillColor': cluster_colors[cluster_label],
                'color': 'white',
                'weight': 1.5,
                'fillOpacity': 0.85,
            }
        else:
            return {
                'fillColor': '#e8e8e8',
                'color': '#d0d0d0',
                'weight': 0.5,
                'fillOpacity': 0.4,
            }

    def highlight_function(feature):
        return {
            'fillColor': '#ffffff',
            'color': '#1a1a2e',
            'weight': 3,
            'fillOpacity': 0.3,
        }

    geojson_layer = folium.GeoJson(
        gdf.__geo_interface__,
        name='clusters',
        style_function=style_function,
        highlight_function=highlight_function,
        tooltip=folium.GeoJsonTooltip(
            fields=['nta_name', 'borough_name', 'cluster_label', 'true_recovery_index', 'recovery_index'],
            aliases=['Neighborhood', 'Borough', 'Cluster', 'True Recovery', 'Bounce-back'],
            localize=True,
            sticky=False,
            labels=True,
            style="""
                background-color: rgba(255,255,255,0.98);
                border: none;
                border-radius: 12px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.18);
                padding: 16px 20px;
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
                font-size: 13px;
                line-height: 1.6;
            """
        )
    )
    geojson_layer.add_to(m)

    # Add custom JavaScript for cluster filtering
    filter_js = """
    <script>
    (function() {
        // Wait for map to initialize
        setTimeout(function() {
            // Store reference to the GeoJSON layer
            window.clusterLayer = null;
            window.activeFilter = null;

            // Find the GeoJSON layer
            for (var key in window) {
                if (window[key] && window[key]._layers) {
                    var map = window[key];
                    map.eachLayer(function(layer) {
                        if (layer.feature || (layer._layers && Object.keys(layer._layers).length > 50)) {
                            window.clusterLayer = layer;
                        }
                    });
                }
            }
        }, 500);
    })();

    function filterCluster(clusterName) {
        if (!window.clusterLayer) return;

        var isToggleOff = (window.activeFilter === clusterName);
        window.activeFilter = isToggleOff ? null : clusterName;

        // Update button states
        document.querySelectorAll('.cluster-filter-btn').forEach(function(btn) {
            if (isToggleOff) {
                btn.classList.remove('active', 'dimmed');
            } else if (btn.dataset.cluster === clusterName) {
                btn.classList.add('active');
                btn.classList.remove('dimmed');
            } else {
                btn.classList.remove('active');
                btn.classList.add('dimmed');
            }
        });

        // Filter map features
        window.clusterLayer.eachLayer(function(layer) {
            if (layer.feature && layer.feature.properties) {
                var layerCluster = layer.feature.properties.cluster_label;
                if (isToggleOff || layerCluster === clusterName) {
                    layer.setStyle({fillOpacity: 0.85, opacity: 1});
                } else {
                    layer.setStyle({fillOpacity: 0.1, opacity: 0.2});
                }
            }
        });
    }
    </script>
    """

    m.get_root().html.add_child(folium.Element(filter_js))

    return m


def create_dashboard():
    """Create interactive dashboard."""

    # Load data
    gdf = gpd.read_file(DATA_PROCESSED / 'nta_analysis_ready.geojson')
    ridership = pd.read_parquet(DATA_PROCESSED / 'nta_ridership_monthly.parquet')

    clusters_path = PROJECT_ROOT / 'output' / 'tables' / 'nta_clusters.csv'
    if clusters_path.exists():
        clusters = pd.read_csv(clusters_path)
        gdf = gdf.merge(clusters[['nta_code', 'cluster', 'cluster_label']], on='nta_code', how='left')

    gdf_with_data = gdf[gdf['recovery_index'].notna()].copy()

    # Calculate insights for the cards at the top
    monthly_total = ridership.groupby('year_month')['ridership'].sum().reset_index()
    monthly_total['ridership_millions'] = monthly_total['ridership'] / 1_000_000

    # Load and add pre-COVID data to timeline
    precovid_path = DATA_RAW / 'mta_precovid_daily.csv'
    precovid_monthly = 135  # Default
    if precovid_path.exists():
        precovid = pd.read_csv(precovid_path)
        precovid['date'] = pd.to_datetime(precovid['date'])
        precovid['year_month'] = precovid['date'].dt.to_period('M').astype(str)
        precovid_by_month = precovid.groupby('year_month')['daily_ridership'].sum().reset_index()
        precovid_by_month['ridership_millions'] = precovid_by_month['daily_ridership'] / 1_000_000
        precovid_by_month = precovid_by_month.rename(columns={'daily_ridership': 'ridership'})
        precovid_by_month = precovid_by_month[['year_month', 'ridership', 'ridership_millions']]

        # Add gap months (Mar-Jun 2020) with estimated values showing decline
        gap_months = pd.DataFrame({
            'year_month': ['2020-03', '2020-04', '2020-05', '2020-06'],
            'ridership': [80_000_000, 25_000_000, 20_000_000, 22_000_000],  # Estimated decline
            'ridership_millions': [80, 25, 20, 22]
        })

        # Combine all data
        monthly_total = pd.concat([precovid_by_month, gap_months, monthly_total], ignore_index=True)
        monthly_total = monthly_total.drop_duplicates(subset=['year_month'], keep='last')
        monthly_total = monthly_total.sort_values('year_month').reset_index(drop=True)

        precovid_monthly = precovid_by_month['ridership_millions'].mean()

    # Borough averages
    borough_avg = gdf_with_data.groupby('borough_name')['recovery_index'].mean().sort_values(ascending=False)
    borough_true_avg = gdf_with_data.groupby('borough_name')['true_recovery_index'].mean().sort_values(ascending=False)

    # Top/bottom neighborhoods
    top_5_true = gdf_with_data.nlargest(5, 'true_recovery_index')[['nta_name', 'borough_name', 'recovery_index', 'true_recovery_index']]
    bottom_5_true = gdf_with_data.nsmallest(5, 'true_recovery_index')[['nta_name', 'borough_name', 'recovery_index', 'true_recovery_index']]

    # Key stats
    avg_recovery = gdf_with_data['recovery_index'].mean()
    avg_true_recovery = gdf_with_data['true_recovery_index'].mean()
    below_precovid = (gdf_with_data['true_recovery_index'] < 1.0).sum()
    total_ntas = len(gdf_with_data)
    best_true = gdf_with_data['true_recovery_index'].max()

    # Timeline insights
    peak_month = monthly_total.loc[monthly_total['ridership_millions'].idxmax()]
    low_month = monthly_total.loc[monthly_total['ridership_millions'].idxmin()]

    # Scatter data
    scatter_data = gdf_with_data[['nta_name', 'borough_name', 'recovery_index', 'true_recovery_index']].dropna()

    # Borough colors for scatter
    borough_colors = {
        'Manhattan': '#e63946',
        'Brooklyn': '#457b9d',
        'Queens': '#2a9d8f',
        'Bronx': '#f4a261',
        'Staten Island': '#9c89b8'
    }
    scatter_data['color'] = scatter_data['borough_name'].map(borough_colors)

    # Create maps
    # Create maps using Folium's built-in iframe embedding
    recovery_map = create_recovery_map(gdf, 'recovery_index')
    map_html = recovery_map._repr_html_()

    true_recovery_map = create_recovery_map(gdf, 'true_recovery_index')
    true_map_html = true_recovery_map._repr_html_()

    # Create cluster map
    cluster_map = create_cluster_map(gdf)
    cluster_map_html = cluster_map._repr_html_()

    # Key moments for timeline
    key_moments = [
        {'date': '2020-07', 'label': 'COVID Low', 'value': low_month['ridership_millions']},
        {'date': '2021-09', 'label': 'Return-to-Office Push', 'value': None},
        {'date': '2023-12', 'label': 'Current', 'value': peak_month['ridership_millions']},
    ]

    html = f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NYC Transit Recovery Analysis</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #f8f9fa;
            --bg-alt: #f0f1f3;
            --card: #ffffff;
            --text: #1a1a2e;
            --text-secondary: #6b7280;
            --text-muted: #9ca3af;
            --accent: #3b82f6;
            --danger: #e63946;
            --success: #2a9d8f;
            --warning: #f4a261;
            --shadow-sm: 0 1px 3px rgba(0,0,0,0.08);
            --shadow: 0 4px 20px rgba(0,0,0,0.08);
            --shadow-lg: 0 12px 40px rgba(0,0,0,0.12);
            --radius: 16px;
            --radius-lg: 24px;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        html {{
            scroll-behavior: smooth;
            scroll-snap-type: y mandatory;
            scroll-padding-top: 0;
        }}

        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
            font-feature-settings: 'cv02', 'cv03', 'cv04', 'cv11';
        }}

        /* Scroll snap sections */
        .snap-section {{
            scroll-snap-align: start;
            scroll-snap-stop: always;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}

        /* Progress Indicator */
        .progress-bar {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: rgba(26, 26, 46, 0.1);
            z-index: 1000;
        }}

        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, var(--danger) 0%, var(--warning) 100%);
            width: 0%;
            transition: width 0.3s ease;
        }}

        .nav-dots {{
            position: fixed;
            right: 32px;
            top: 50%;
            transform: translateY(-50%);
            display: flex;
            flex-direction: column;
            gap: 12px;
            z-index: 1000;
        }}

        .nav-dot {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: rgba(26, 26, 46, 0.15);
            cursor: pointer;
            transition: all 0.3s ease;
            position: relative;
        }}

        .nav-dot:hover {{
            background: rgba(26, 26, 46, 0.3);
            transform: scale(1.2);
        }}

        .nav-dot.active {{
            background: var(--danger);
            box-shadow: 0 0 0 4px rgba(230, 57, 70, 0.2);
        }}

        .nav-dot::before {{
            content: attr(data-label);
            position: absolute;
            right: 24px;
            top: 50%;
            transform: translateY(-50%);
            background: var(--text);
            color: white;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 500;
            white-space: nowrap;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.2s ease;
        }}

        .nav-dot:hover::before {{
            opacity: 1;
        }}

        /* Container */
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 0 48px;
        }}

        /* Sections */
        .section {{
            padding: 100px 0;
            opacity: 0;
            transform: translateY(30px);
            transition: opacity 0.8s ease, transform 0.8s ease;
        }}

        .section.visible {{
            opacity: 1;
            transform: translateY(0);
        }}

        /* Hero */
        .hero {{
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            text-align: center;
            padding: 60px 48px;
            position: relative;
            overflow: hidden;
        }}

        .hero::before {{
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle at 30% 50%, rgba(230, 57, 70, 0.03) 0%, transparent 50%),
                        radial-gradient(circle at 70% 50%, rgba(42, 157, 143, 0.03) 0%, transparent 50%);
            animation: heroGradient 20s ease infinite;
        }}

        @keyframes heroGradient {{
            0%, 100% {{ transform: translate(0, 0); }}
            50% {{ transform: translate(-5%, 5%); }}
        }}

        .hero-content {{
            position: relative;
            z-index: 1;
            max-width: 900px;
        }}

        .hero-eyebrow {{
            font-size: 13px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--danger);
            margin-bottom: 24px;
            opacity: 0;
            animation: fadeInUp 0.8s ease 0.2s forwards;
        }}

        .hero h1 {{
            font-size: clamp(40px, 6vw, 72px);
            font-weight: 800;
            letter-spacing: -0.03em;
            line-height: 1.1;
            margin-bottom: 24px;
            opacity: 0;
            animation: fadeInUp 0.8s ease 0.4s forwards;
        }}

        .hero h1 .highlight {{
            background: linear-gradient(135deg, var(--danger) 0%, #c1121f 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}

        .hero-subtitle {{
            font-size: clamp(18px, 2.5vw, 24px);
            color: var(--text-secondary);
            font-weight: 400;
            max-width: 700px;
            margin: 0 auto 48px;
            opacity: 0;
            animation: fadeInUp 0.8s ease 0.6s forwards;
        }}

        .hero-stat {{
            display: inline-flex;
            align-items: baseline;
            gap: 8px;
            opacity: 0;
            animation: fadeInUp 0.8s ease 0.8s forwards;
        }}

        .hero-stat-value {{
            font-size: clamp(64px, 10vw, 120px);
            font-weight: 800;
            letter-spacing: -0.03em;
            color: var(--danger);
            font-variant-numeric: tabular-nums;
            text-shadow: 0 0 60px rgba(230, 57, 70, 0.3);
            animation: pulse 3s ease-in-out infinite;
        }}

        .hero-stat-label {{
            font-size: 18px;
            color: var(--text-secondary);
            font-weight: 500;
        }}

        @keyframes pulse {{
            0%, 100% {{ text-shadow: 0 0 60px rgba(230, 57, 70, 0.3); }}
            50% {{ text-shadow: 0 0 80px rgba(230, 57, 70, 0.5); }}
        }}

        @keyframes fadeInUp {{
            from {{
                opacity: 0;
                transform: translateY(20px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}

        .hero-meta {{
            margin-top: 48px;
            font-size: 14px;
            color: var(--text-muted);
            opacity: 0;
            animation: fadeInUp 0.8s ease 1s forwards;
        }}

        .hero-scroll {{
            position: absolute;
            bottom: 40px;
            left: 0;
            right: 0;
            margin: 0 auto;
            width: fit-content;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 8px;
            color: var(--text-muted);
            font-size: 12px;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            opacity: 0;
            animation: fadeInUp 0.8s ease 1.2s forwards;
        }}

        .hero-scroll-icon {{
            width: 24px;
            height: 40px;
            border: 2px solid var(--text-muted);
            border-radius: 12px;
            position: relative;
        }}

        .hero-scroll-icon::before {{
            content: '';
            position: absolute;
            top: 8px;
            left: 50%;
            transform: translateX(-50%);
            width: 4px;
            height: 8px;
            background: var(--text-muted);
            border-radius: 2px;
            animation: scrollBounce 2s ease-in-out infinite;
        }}

        @keyframes scrollBounce {{
            0%, 100% {{ transform: translateX(-50%) translateY(0); opacity: 1; }}
            50% {{ transform: translateX(-50%) translateY(12px); opacity: 0.3; }}
        }}

        /* Stats Row */
        .stats-row {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 24px;
            margin-bottom: 32px;
        }}

        .stat-card {{
            background: var(--card);
            border-radius: var(--radius);
            padding: 32px;
            box-shadow: var(--shadow);
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            opacity: 0;
            transform: translateY(20px);
        }}

        .stat-card.visible {{
            opacity: 1;
            transform: translateY(0);
        }}

        .stat-card:hover {{
            transform: translateY(-8px) scale(1.02);
            box-shadow: var(--shadow-lg);
        }}

        .stat-card:active {{
            transform: translateY(-4px) scale(0.98);
        }}

        .stat-card .value {{
            font-size: 48px;
            font-weight: 700;
            letter-spacing: -0.02em;
            margin-bottom: 8px;
            font-variant-numeric: tabular-nums;
            transition: transform 0.4s var(--elastic-out);
        }}

        .stat-card:hover .value {{
            transform: scale(1.08);
        }}

        .stat-card .value.danger {{ color: var(--danger); }}
        .stat-card .value.success {{ color: var(--success); }}

        .stat-card .label {{
            font-size: 14px;
            color: var(--text-secondary);
            font-weight: 500;
            margin-bottom: 12px;
        }}

        .stat-card .change {{
            font-size: 13px;
            padding: 6px 12px;
            border-radius: 8px;
            display: inline-block;
            font-weight: 500;
        }}

        .stat-card .change.positive {{
            background: rgba(42, 157, 143, 0.1);
            color: var(--success);
        }}

        .stat-card .change.negative {{
            background: rgba(230, 57, 70, 0.1);
            color: var(--danger);
        }}

        .stat-card .change.neutral {{
            background: rgba(107, 114, 128, 0.1);
            color: var(--text-secondary);
        }}

        /* Section Headers */
        .section-header {{
            margin-bottom: 40px;
        }}

        .section-header h2 {{
            font-size: 36px;
            font-weight: 700;
            letter-spacing: -0.02em;
            margin-bottom: 12px;
        }}

        .section-header p {{
            font-size: 18px;
            color: var(--text-secondary);
            max-width: 700px;
            line-height: 1.7;
        }}

        /* Pull Quote */
        .pull-quote {{
            text-align: center;
            padding: 80px 48px;
            position: relative;
        }}

        .pull-quote::before {{
            content: '"';
            position: absolute;
            top: 40px;
            left: 50%;
            transform: translateX(-50%);
            font-size: 120px;
            font-weight: 800;
            color: rgba(230, 57, 70, 0.08);
            line-height: 1;
        }}

        .pull-quote blockquote {{
            font-size: clamp(24px, 3vw, 32px);
            font-weight: 500;
            letter-spacing: -0.01em;
            line-height: 1.5;
            max-width: 900px;
            margin: 0 auto;
            position: relative;
        }}

        .pull-quote .stat-highlight {{
            color: var(--danger);
            font-weight: 700;
        }}

        /* Elastic Animation Variables */
        :root {{
            --elastic-out: cubic-bezier(0.34, 1.56, 0.64, 1);
            --elastic-in-out: cubic-bezier(0.68, -0.55, 0.265, 1.55);
            --smooth-out: cubic-bezier(0.4, 0, 0.2, 1);
        }}

        /* Cards */
        .card {{
            background: var(--card);
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow);
            overflow: hidden;
            transition: transform 0.4s var(--elastic-out), box-shadow 0.3s var(--smooth-out);
        }}

        .card:hover {{
            transform: translateY(-4px) scale(1.01);
            box-shadow: 0 20px 40px rgba(0,0,0,0.12);
        }}

        .card:active {{
            transform: translateY(-2px) scale(0.99);
        }}

        .metric-card:hover {{
            transform: translateY(-8px) scale(1.03);
            box-shadow: 0 24px 48px rgba(0,0,0,0.3);
        }}

        .metric-card:active {{
            transform: translateY(-4px) scale(1.01);
        }}

        .card-header {{
            padding: 20px 28px;
            border-bottom: 1px solid rgba(0,0,0,0.06);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .card-header h3 {{
            font-size: 16px;
            font-weight: 600;
        }}

        .card-header .badge {{
            font-size: 12px;
            padding: 4px 10px;
            border-radius: 6px;
            font-weight: 600;
            transition: transform 0.3s var(--elastic-out), background 0.2s ease;
        }}

        .card-header .badge:hover {{
            transform: scale(1.08);
        }}

        .card-body {{
            padding: 28px;
        }}

        /* Grid */
        .grid-2 {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 24px;
        }}

        /* Map */
        .map-container {{
            height: 450px;
            border-radius: 12px;
            overflow: hidden;
            position: relative;
        }}

        .map-container iframe {{
            width: 100%;
            height: 100%;
            border: none;
        }}

        .map-container > div {{
            width: 100% !important;
            height: 100% !important;
        }}

        .map-container > div > div {{
            width: 100% !important;
            height: 100% !important;
        }}

        .map-legend {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 8px;
            padding: 16px 20px;
            background: linear-gradient(180deg, transparent 0%, var(--card) 20%);
            font-size: 13px;
            color: var(--text-secondary);
        }}

        .legend-gradient {{
            width: 200px;
            height: 8px;
            border-radius: 4px;
            background: linear-gradient(90deg, #e63946 0%, #f4a261 33%, #e9c46a 66%, #2a9d8f 100%);
        }}

        /* Charts */
        .chart {{
            height: 350px;
        }}

        /* Insight Box */
        .insight {{
            background: linear-gradient(135deg, rgba(244, 162, 97, 0.08) 0%, rgba(42, 157, 143, 0.08) 100%);
            border-radius: 12px;
            padding: 24px;
            margin-top: 24px;
            border-left: 4px solid var(--warning);
            transition: transform 0.4s var(--elastic-out), box-shadow 0.3s ease, border-left-width 0.3s ease;
        }}

        .insight:hover {{
            transform: translateX(8px) scale(1.01);
            box-shadow: 0 8px 24px rgba(0,0,0,0.08);
            border-left-width: 6px;
        }}

        .insight.aha {{
            background: linear-gradient(135deg, rgba(244, 162, 97, 0.12) 0%, rgba(251, 191, 36, 0.08) 100%);
            border-left-color: #f59e0b;
        }}

        .insight-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 12px;
        }}

        .insight-icon {{
            font-size: 24px;
            animation: none;
        }}

        .insight.aha .insight-icon {{
            animation: glow 2s ease-in-out infinite;
        }}

        @keyframes glow {{
            0%, 100% {{ filter: drop-shadow(0 0 4px rgba(251, 191, 36, 0.4)); }}
            50% {{ filter: drop-shadow(0 0 12px rgba(251, 191, 36, 0.8)); }}
        }}

        .insight h4 {{
            font-size: 15px;
            font-weight: 600;
        }}

        .insight p {{
            font-size: 14px;
            color: var(--text-secondary);
            line-height: 1.7;
        }}

        /* Tables */
        .data-table {{
            width: 100%;
            border-collapse: collapse;
        }}

        .data-table th {{
            text-align: left;
            padding: 14px 20px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            border-bottom: 2px solid rgba(0,0,0,0.06);
        }}

        .data-table td {{
            padding: 16px 20px;
            font-size: 14px;
            border-bottom: 1px solid rgba(0,0,0,0.04);
        }}

        .data-table tbody tr {{
            transition: background 0.2s ease, transform 0.3s var(--elastic-out);
        }}

        .data-table tbody tr:nth-child(odd) {{
            background: rgba(0,0,0,0.015);
        }}

        .data-table tbody tr:hover {{
            transform: scale(1.01);
        }}

        .data-table tbody tr:hover td:first-child {{
            padding-left: 28px;
        }}

        .data-table tbody tr.hovered {{
            background: rgba(59, 130, 246, 0.04);
        }}

        .data-table tr:last-child td {{
            border-bottom: none;
        }}

        .rank-badge {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 24px;
            height: 24px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 700;
            margin-right: 12px;
            transition: transform 0.3s var(--elastic-out);
        }}

        .rank-badge:hover {{
            transform: scale(1.15) rotate(-5deg);
        }}

        .rank-badge.gold {{ background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%); color: white; }}
        .rank-badge.silver {{ background: linear-gradient(135deg, #9ca3af 0%, #6b7280 100%); color: white; }}
        .rank-badge.bronze {{ background: linear-gradient(135deg, #d97706 0%, #b45309 100%); color: white; }}
        .rank-badge.default {{ background: rgba(107, 114, 128, 0.1); color: var(--text-secondary); }}

        .badge {{
            display: inline-block;
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            transition: transform 0.3s var(--elastic-out), box-shadow 0.2s ease;
            cursor: default;
        }}

        .badge:hover {{
            transform: scale(1.08);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}

        .badge.high {{ background: rgba(42, 157, 143, 0.15); color: #1e7b6e; }}
        .badge.low {{ background: rgba(230, 57, 70, 0.15); color: #c1121f; }}

        /* Cluster Filter Buttons */
        .cluster-filter-btn {{
            cursor: pointer !important;
            position: relative;
            overflow: hidden;
        }}

        .cluster-filter-btn::after {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(255,255,255,0);
            transition: background 0.3s ease;
            pointer-events: none;
        }}

        .cluster-filter-btn:hover {{
            transform: scale(1.12) translateY(-2px);
            box-shadow: 0 6px 20px rgba(0,0,0,0.25);
        }}

        .cluster-filter-btn:active {{
            transform: scale(1.05) translateY(0);
        }}

        .cluster-filter-btn.active {{
            transform: scale(1.15);
            box-shadow: 0 8px 24px rgba(0,0,0,0.3);
            outline: 3px solid white;
            outline-offset: 2px;
        }}

        .cluster-filter-btn.dimmed {{
            opacity: 0.4;
            transform: scale(0.95);
        }}

        .cluster-filter-btn.dimmed:hover {{
            opacity: 0.7;
            transform: scale(1.02);
        }}

        /* R² Metric Cards */
        .r2-container {{
            display: flex;
            gap: 24px;
            margin-bottom: 32px;
        }}

        .r2-card {{
            flex: 1;
            background: var(--bg);
            border-radius: 16px;
            padding: 28px;
            text-align: center;
            transition: transform 0.4s var(--elastic-out), box-shadow 0.3s ease;
        }}

        .r2-card:hover {{
            transform: translateY(-6px) scale(1.02);
            box-shadow: 0 16px 48px rgba(0,0,0,0.12);
        }}

        .r2-card:hover .r2-value {{
            transform: scale(1.05);
        }}

        .r2-value {{
            transition: transform 0.4s var(--elastic-out);
        }}

        .r2-card.success {{
            background: linear-gradient(135deg, rgba(42, 157, 143, 0.08) 0%, rgba(42, 157, 143, 0.04) 100%);
            border: 1px solid rgba(42, 157, 143, 0.15);
        }}

        .r2-card.danger {{
            background: linear-gradient(135deg, rgba(230, 57, 70, 0.08) 0%, rgba(230, 57, 70, 0.04) 100%);
            border: 1px solid rgba(230, 57, 70, 0.15);
        }}

        .r2-value {{
            font-size: 56px;
            font-weight: 800;
            letter-spacing: -0.03em;
            margin-bottom: 8px;
        }}

        .r2-card.success .r2-value {{ color: var(--success); }}
        .r2-card.danger .r2-value {{ color: var(--danger); }}

        .r2-label {{
            font-size: 14px;
            color: var(--text-secondary);
            font-weight: 500;
            margin-bottom: 20px;
        }}

        .r2-bar {{
            height: 8px;
            background: rgba(0,0,0,0.06);
            border-radius: 4px;
            overflow: hidden;
        }}

        .r2-bar-fill {{
            height: 100%;
            border-radius: 4px;
            transition: width 1.5s cubic-bezier(0.4, 0, 0.2, 1);
            width: 0%;
        }}

        .r2-card.success .r2-bar-fill {{
            background: linear-gradient(90deg, #2a9d8f 0%, #21867a 100%);
        }}

        .r2-card.danger .r2-bar-fill {{
            background: linear-gradient(90deg, #e63946 0%, #c1121f 100%);
        }}

        .r2-context {{
            margin-top: 12px;
            font-size: 12px;
            color: var(--text-muted);
        }}

        .r2-card.success .r2-context {{ color: #1e7b6e; }}
        .r2-card.danger .r2-context {{ color: #c1121f; }}

        /* Methodology Section */
        .methodology-section {{
            background: var(--bg-alt);
        }}

        .methodology-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 24px;
        }}

        .methodology-card {{
            background: var(--card);
            border-radius: var(--radius);
            padding: 28px;
            box-shadow: var(--shadow-sm);
            transition: transform 0.4s var(--elastic-out), box-shadow 0.3s ease;
        }}

        .methodology-card:hover {{
            transform: translateY(-6px) scale(1.02);
            box-shadow: 0 16px 40px rgba(0,0,0,0.12);
        }}

        .methodology-card:hover .icon {{
            transform: scale(1.2) rotate(-5deg);
        }}

        .methodology-card .icon {{
            font-size: 32px;
            margin-bottom: 16px;
            transition: transform 0.4s var(--elastic-out);
        }}

        .methodology-card h4 {{
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 12px;
        }}

        .methodology-card p {{
            font-size: 14px;
            color: var(--text-secondary);
            line-height: 1.7;
        }}

        /* Footer */
        .footer {{
            text-align: center;
            padding: 60px 48px 80px;
            color: var(--text-secondary);
        }}

        .footer-brand {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            margin-bottom: 24px;
        }}

        .footer-brand img {{
            height: 32px;
            opacity: 0.7;
        }}

        .footer-sources {{
            display: flex;
            justify-content: center;
            gap: 12px;
            margin-bottom: 16px;
            flex-wrap: wrap;
        }}

        .footer-sources .pill {{
            background: rgba(0,0,0,0.04);
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 500;
        }}

        .footer-meta {{
            font-size: 13px;
            color: var(--text-muted);
        }}

        /* Responsive */
        @media (max-width: 1024px) {{
            .stats-row {{ grid-template-columns: repeat(2, 1fr); }}
            .grid-2 {{ grid-template-columns: 1fr; }}
            .methodology-grid {{ grid-template-columns: 1fr; }}
            .nav-dots {{ display: none; }}
            .container {{ padding: 0 24px; }}
        }}

        @media (max-width: 640px) {{
            .stats-row {{ grid-template-columns: 1fr; }}
            .hero {{ padding: 40px 24px; }}
            .section {{ padding: 60px 0; }}
            .gauge-container {{ flex-direction: column; gap: 24px; }}
        }}
    </style>
</head>
<body>
    <!-- Password Protection -->
    <div id="password-overlay" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); z-index: 99999; display: flex; align-items: center; justify-content: center; flex-direction: column;">
        <div style="text-align: center; color: white; font-family: 'Inter', sans-serif;">
            <h1 style="font-size: 28px; margin-bottom: 8px; font-weight: 600;">NYC Transit Recovery Dashboard</h1>
            <p style="color: rgba(255,255,255,0.6); margin-bottom: 32px;">CSE 6242 - Team 002</p>
            <input type="password" id="password-input" placeholder="Enter password" style="padding: 14px 20px; font-size: 16px; border: 2px solid rgba(255,255,255,0.2); border-radius: 8px; background: rgba(255,255,255,0.1); color: white; width: 260px; text-align: center; outline: none;" onkeypress="if(event.key==='Enter')checkPassword()">
            <br><br>
            <button onclick="checkPassword()" style="padding: 12px 32px; font-size: 14px; background: #3b82f6; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 600;">Enter</button>
            <p id="password-error" style="color: #e63946; margin-top: 16px; display: none;">Incorrect password</p>
        </div>
    </div>
    <script>
        function checkPassword() {{
            var input = document.getElementById('password-input').value;
            if (input === 'cse6242') {{
                document.getElementById('password-overlay').style.display = 'none';
                sessionStorage.setItem('authenticated', 'true');
            }} else {{
                document.getElementById('password-error').style.display = 'block';
                document.getElementById('password-input').value = '';
            }}
        }}
        if (sessionStorage.getItem('authenticated') === 'true') {{
            document.getElementById('password-overlay').style.display = 'none';
        }}
    </script>

    <!-- Progress Bar -->
    <div class="progress-bar">
        <div class="progress-fill" id="progress-fill"></div>
    </div>

    <!-- Navigation Dots -->
    <nav class="nav-dots">
        <div class="nav-dot active" data-section="hero" data-label="Overview"></div>
        <div class="nav-dot" data-section="stats" data-label="Key Stats"></div>
        <div class="nav-dot" data-section="findings" data-label="Findings"></div>
        <div class="nav-dot" data-section="approach" data-label="Data"></div>
        <div class="nav-dot" data-section="charts" data-label="Timeline"></div>
        <div class="nav-dot" data-section="maps" data-label="Maps"></div>
        <div class="nav-dot" data-section="analysis" data-label="Analysis"></div>
        <div class="nav-dot" data-section="models" data-label="Models"></div>
        <div class="nav-dot" data-section="clusters" data-label="Patterns"></div>
        <div class="nav-dot" data-section="rankings" data-label="Rankings"></div>
        <div class="nav-dot" data-section="conclusion" data-label="Big Picture"></div>
        <div class="nav-dot" data-section="methodology" data-label="Methods"></div>
    </nav>

    <!-- Hero Section -->
    <section class="hero snap-section" id="hero">
        <div class="hero-content">
            <div class="hero-eyebrow">CSE 6242 · Data and Visual Analytics · Georgia Tech</div>
            <h1>The <span class="highlight">Recovery</span> is an Illusion</h1>
            <p class="hero-subtitle">
                NYC subway ridership grew 2.4x from COVID lows - but the system has only recovered to
            </p>
            <div class="hero-stat">
                <span class="hero-stat-value" data-target="{avg_true_recovery * 100:.0f}">0</span>
                <span class="hero-stat-label">% of pre-pandemic levels</span>
            </div>
            <p class="hero-meta">
                Analysis of 133 subway-served neighborhoods · January 2020 - December 2023 · 270M+ ridership records
            </p>
            <p class="hero-meta" style="margin-top: 24px; font-size: 13px;">
                <strong>Isaac Regalado · Elias Dematis · Dami Awosika · David Mongeau</strong><br>
                Spring 2026
            </p>
        </div>
        <div class="hero-scroll">
            <div class="hero-scroll-icon"></div>
            Scroll to explore
        </div>
    </section>

    <div class="container">
        <!-- Stats Row -->
        <section class="section snap-section" id="stats">
            <div class="stats-row">
                <div class="stat-card" style="transition-delay: 0ms;">
                    <div class="value" data-target="{avg_recovery:.1f}" data-suffix="x">{avg_recovery:.1f}x</div>
                    <div class="label">Recovery from COVID Low</div>
                    <div class="change positive">↑ vs Q3 2020 trough</div>
                </div>
                <div class="stat-card" style="transition-delay: 100ms;">
                    <div class="value danger" data-target="{avg_true_recovery * 100:.0f}" data-suffix="%">{avg_true_recovery:.0%}</div>
                    <div class="label">True Recovery Rate</div>
                    <div class="change negative">↓ vs Pre-COVID baseline</div>
                </div>
                <div class="stat-card" style="transition-delay: 200ms;">
                    <div class="value danger" data-target="{below_precovid}">{below_precovid}</div>
                    <div class="label">NTAs Below Pre-COVID</div>
                    <div class="change negative">of {total_ntas} with subway</div>
                </div>
                <div class="stat-card" style="transition-delay: 300ms;">
                    <div class="value success" data-target="{best_true * 100:.0f}" data-suffix="%">{best_true:.0%}</div>
                    <div class="label">Best True Recovery</div>
                    <div class="change neutral">highest performing NTA</div>
                </div>
            </div>
        </section>

        <!-- Pull Quote -->
        <div class="pull-quote snap-section">
            <blockquote>
                <span class="stat-highlight">{below_precovid} of {total_ntas} neighborhoods</span> ({below_precovid/total_ntas*100:.0f}%)
                remain below their pre-pandemic ridership. The "recovery" narrative masks a persistent structural decline.
            </blockquote>
        </div>

        <!-- Key Findings Section -->
        <section class="section snap-section" id="findings" style="background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #252542 100%); margin-left: -48px; margin-right: -48px; padding: 100px 48px; color: white; position: relative; overflow: hidden;">
            <!-- Background decoration -->
            <div style="position: absolute; top: -50%; left: -20%; width: 60%; height: 200%; background: radial-gradient(circle, rgba(230, 57, 70, 0.08) 0%, transparent 50%); pointer-events: none;"></div>
            <div style="position: absolute; bottom: -50%; right: -20%; width: 60%; height: 200%; background: radial-gradient(circle, rgba(42, 157, 143, 0.08) 0%, transparent 50%); pointer-events: none;"></div>

            <div class="section-header" style="text-align: center; max-width: 900px; margin: 0 auto 72px; position: relative;">
                <div style="font-size: 13px; font-weight: 600; letter-spacing: 0.15em; text-transform: uppercase; color: rgba(255,255,255,0.5); margin-bottom: 16px;">What We Discovered</div>
                <h2 style="color: white; font-size: 52px; font-weight: 800; letter-spacing: -0.03em; margin-bottom: 20px;">Key Findings</h2>
                <p style="color: rgba(255,255,255,0.6); font-size: 20px; max-width: 600px; margin: 0 auto;">
                    Our analysis reveals a paradox at the heart of NYC's transit recovery
                </p>
            </div>

            <!-- Three Metrics Row -->
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; max-width: 1200px; margin: 0 auto; align-items: stretch;">
                <!-- True Recovery R² Card -->
                <div class="metric-card" style="background: linear-gradient(135deg, rgba(244, 162, 97, 0.15) 0%, rgba(244, 162, 97, 0.03) 100%); border-radius: 20px; padding: 32px; border: 1px solid rgba(244, 162, 97, 0.25); backdrop-filter: blur(10px); position: relative; overflow: hidden; transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1); cursor: default;">
                    <div style="position: absolute; top: 0; left: 0; right: 0; height: 3px; background: linear-gradient(90deg, #f4a261, #e76f51);"></div>
                    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 16px;">
                        <div style="width: 40px; height: 40px; background: rgba(244, 162, 97, 0.2); border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 18px;">❓</div>
                        <div style="font-size: 11px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: #f4a261;">True Recovery Model</div>
                    </div>
                    <div style="display: flex; align-items: baseline; gap: 4px; margin-bottom: 6px;">
                        <span style="font-size: 16px; font-weight: 600; color: rgba(255,255,255,0.5);">R² =</span>
                        <span style="font-size: 52px; font-weight: 800; color: #f4a261; letter-spacing: -0.03em;">0.18</span>
                    </div>
                    <div style="font-size: 16px; font-weight: 600; color: white; margin-bottom: 10px;">Unpredictable</div>
                    <p style="color: rgba(255,255,255,0.55); font-size: 13px; line-height: 1.5; margin: 0;">
                        82% of variance remains unexplained
                    </p>
                    <div style="margin-top: 16px; padding-top: 14px; border-top: 1px solid rgba(255,255,255,0.1);">
                        <div style="height: 6px; background: rgba(255,255,255,0.1); border-radius: 3px; overflow: hidden;">
                            <div style="height: 100%; width: 18%; background: linear-gradient(90deg, #f4a261, #e76f51); border-radius: 3px; transition: width 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);"></div>
                        </div>
                    </div>
                </div>

                <!-- Main 72% Card -->
                <div class="metric-card" style="background: linear-gradient(135deg, rgba(230, 57, 70, 0.25) 0%, rgba(230, 57, 70, 0.08) 100%); border-radius: 20px; padding: 32px; border: 1px solid rgba(230, 57, 70, 0.4); text-align: center; backdrop-filter: blur(10px); position: relative; overflow: hidden; transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1); cursor: default;">
                    <div style="position: absolute; top: 0; left: 0; right: 0; height: 3px; background: linear-gradient(90deg, #e63946, #c1121f);"></div>
                    <div style="font-size: 12px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: #e63946; margin-bottom: 12px;">The Reality</div>
                    <div style="font-size: 72px; font-weight: 900; background: linear-gradient(180deg, #e63946 0%, #c1121f 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; letter-spacing: -0.04em; line-height: 1;">{avg_true_recovery:.0%}</div>
                    <div style="font-size: 18px; font-weight: 600; color: white; margin: 12px 0 10px;">True Recovery Rate</div>
                    <p style="color: rgba(255,255,255,0.6); font-size: 13px; line-height: 1.5; margin: 0;">
                        Only {avg_true_recovery:.0%} of pre-pandemic ridership, despite <span style="color: #2a9d8f;">2.4x bounce-back</span> from COVID lows
                    </p>
                </div>

                <!-- Bounce-back R² Card -->
                <div class="metric-card" style="background: linear-gradient(135deg, rgba(42, 157, 143, 0.15) 0%, rgba(42, 157, 143, 0.03) 100%); border-radius: 20px; padding: 32px; border: 1px solid rgba(42, 157, 143, 0.25); backdrop-filter: blur(10px); position: relative; overflow: hidden; transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1); cursor: default;">
                    <div style="position: absolute; top: 0; left: 0; right: 0; height: 3px; background: linear-gradient(90deg, #2a9d8f, #21867a);"></div>
                    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 16px;">
                        <div style="width: 40px; height: 40px; background: rgba(42, 157, 143, 0.2); border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 14px; color: #2a9d8f; font-weight: bold;">R²</div>
                        <div style="font-size: 11px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: #2a9d8f;">Bounce-back Model</div>
                    </div>
                    <div style="display: flex; align-items: baseline; gap: 4px; margin-bottom: 6px;">
                        <span style="font-size: 16px; font-weight: 600; color: rgba(255,255,255,0.5);">R² =</span>
                        <span style="font-size: 52px; font-weight: 800; color: #2a9d8f; letter-spacing: -0.03em;">0.54</span>
                    </div>
                    <div style="font-size: 16px; font-weight: 600; color: white; margin-bottom: 10px;">Predictable</div>
                    <p style="color: rgba(255,255,255,0.55); font-size: 13px; line-height: 1.5; margin: 0;">
                        Education + demographics explain 54%
                    </p>
                    <div style="margin-top: 16px; padding-top: 14px; border-top: 1px solid rgba(255,255,255,0.1);">
                        <div style="height: 6px; background: rgba(255,255,255,0.1); border-radius: 3px; overflow: hidden;">
                            <div style="height: 100%; width: 54%; background: linear-gradient(90deg, #2a9d8f, #21867a); border-radius: 3px; transition: width 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);"></div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Bottom Line -->
            <div style="max-width: 800px; margin: 64px auto 0; text-align: center; padding: 40px; background: linear-gradient(135deg, rgba(230, 57, 70, 0.12) 0%, rgba(230, 57, 70, 0.04) 100%); border-radius: 20px; border: 1px solid rgba(230, 57, 70, 0.2); position: relative;">
                <div style="position: absolute; top: -14px; left: 50%; transform: translateX(-50%); background: linear-gradient(135deg, #e63946, #c1121f); padding: 6px 20px; border-radius: 20px; font-size: 12px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase;">Core Finding</div>
                <p style="color: white; font-size: 22px; font-weight: 600; line-height: 1.5; margin: 0 0 16px;">
                    "Bouncing back" ≠ "Truly recovering"
                </p>
                <p style="color: rgba(255,255,255,0.7); font-size: 16px; line-height: 1.7; margin: 0;">
                    The factors that predict how much a neighborhood rebounded from COVID lows do <strong style="color: #e63946;">NOT</strong> predict whether it returned to pre-pandemic ridership. This suggests a <strong style="color: white;">permanent structural shift</strong> in transit usage.
                </p>
            </div>
        </section>

        <!-- Our Data Section -->
        <section class="section snap-section" id="approach" style="background: linear-gradient(180deg, var(--bg) 0%, var(--bg-alt) 100%); margin-left: -48px; margin-right: -48px; padding-left: 48px; padding-right: 48px;">
            <div class="section-header" style="text-align: center; max-width: 800px; margin: 0 auto 48px;">
                <h2>The Data Behind Our Analysis</h2>
                <p>
                    We integrated four public datasets to build a complete picture of each neighborhood - what it looks like, who lives there, where they work, and how they travel.
                </p>
            </div>

            <!-- Data Flow Visualization -->
            <div style="max-width: 1200px; margin: 0 auto;">
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 32px;">
                    <div class="card" style="padding: 24px; position: relative; overflow: hidden;">
                        <div style="position: absolute; top: 0; right: 0; background: var(--danger); color: white; font-size: 11px; padding: 4px 12px; border-radius: 0 0 0 12px; font-weight: 600;">SOURCE 1</div>
                        <div style="font-size: 36px; margin-bottom: 12px;">🚇</div>
                        <h4 style="font-size: 16px; margin-bottom: 8px;">MTA Ridership</h4>
                        <div style="font-size: 28px; font-weight: 700; color: var(--danger); margin-bottom: 8px;">270M+</div>
                        <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 12px;">turnstile swipes</div>
                        <p style="font-size: 13px; color: var(--text-secondary); line-height: 1.5; border-top: 1px solid rgba(0,0,0,0.06); padding-top: 12px;">
                            Every subway entry, Jan 2020 – Dec 2023. We calculated <strong>two recovery metrics</strong> for each station.
                        </p>
                    </div>
                    <div class="card" style="padding: 24px; position: relative; overflow: hidden;">
                        <div style="position: absolute; top: 0; right: 0; background: var(--accent); color: white; font-size: 11px; padding: 4px 12px; border-radius: 0 0 0 12px; font-weight: 600;">SOURCE 2</div>
                        <div style="font-size: 36px; margin-bottom: 12px;">🏢</div>
                        <h4 style="font-size: 16px; margin-bottom: 8px;">PLUTO Land Use</h4>
                        <div style="font-size: 28px; font-weight: 700; color: var(--accent); margin-bottom: 8px;">857K</div>
                        <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 12px;">property lots</div>
                        <p style="font-size: 13px; color: var(--text-secondary); line-height: 1.5; border-top: 1px solid rgba(0,0,0,0.06); padding-top: 12px;">
                            NYC's property database. We measured <strong>% residential vs commercial</strong> for each neighborhood.
                        </p>
                    </div>
                    <div class="card" style="padding: 24px; position: relative; overflow: hidden;">
                        <div style="position: absolute; top: 0; right: 0; background: var(--success); color: white; font-size: 11px; padding: 4px 12px; border-radius: 0 0 0 12px; font-weight: 600;">SOURCE 3</div>
                        <div style="font-size: 36px; margin-bottom: 12px;">💼</div>
                        <h4 style="font-size: 16px; margin-bottom: 8px;">LEHD Employment</h4>
                        <div style="font-size: 28px; font-weight: 700; color: var(--success); margin-bottom: 8px;">4.2M</div>
                        <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 12px;">jobs by industry</div>
                        <p style="font-size: 13px; color: var(--text-secondary); line-height: 1.5; border-top: 1px solid rgba(0,0,0,0.06); padding-top: 12px;">
                            Census workplace data. We scored each job by <strong>remote work potential</strong> based on industry.
                        </p>
                    </div>
                    <div class="card" style="padding: 24px; position: relative; overflow: hidden;">
                        <div style="position: absolute; top: 0; right: 0; background: var(--warning); color: white; font-size: 11px; padding: 4px 12px; border-radius: 0 0 0 12px; font-weight: 600;">SOURCE 4</div>
                        <div style="font-size: 36px; margin-bottom: 12px;">👥</div>
                        <h4 style="font-size: 16px; margin-bottom: 8px;">Census ACS</h4>
                        <div style="font-size: 28px; font-weight: 700; color: var(--warning); margin-bottom: 8px;">2,327</div>
                        <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 12px;">census tracts</div>
                        <p style="font-size: 13px; color: var(--text-secondary); line-height: 1.5; border-top: 1px solid rgba(0,0,0,0.06); padding-top: 12px;">
                            Demographics from American Community Survey: <strong>income, education, race/ethnicity</strong>.
                        </p>
                    </div>
                </div>

                <!-- Integration Arrow -->
                <div style="text-align: center; margin: 24px 0;">
                    <div style="display: inline-flex; align-items: center; gap: 16px; background: var(--card); padding: 16px 32px; border-radius: 40px; box-shadow: var(--shadow);">
                        <span style="font-size: 24px;">⬇️</span>
                        <span style="font-weight: 600; color: var(--text-secondary);">Joined to 262 neighborhoods using spatial coordinates</span>
                        <span style="font-size: 24px;">⬇️</span>
                    </div>
                </div>

                <!-- Output Features -->
                <div class="card" style="padding: 32px; text-align: center;">
                    <h4 style="font-size: 18px; margin-bottom: 20px;">Predictor Features Per Neighborhood</h4>
                    <div style="display: flex; flex-wrap: wrap; justify-content: center; gap: 12px;">
                        <span style="background: rgba(230, 57, 70, 0.1); color: var(--danger); padding: 8px 16px; border-radius: 20px; font-size: 13px; font-weight: 500;">% Bachelors Degree</span>
                        <span style="background: rgba(230, 57, 70, 0.1); color: var(--danger); padding: 8px 16px; border-radius: 20px; font-size: 13px; font-weight: 500;">Median Income</span>
                        <span style="background: rgba(230, 57, 70, 0.1); color: var(--danger); padding: 8px 16px; border-radius: 20px; font-size: 13px; font-weight: 500;">Race/Ethnicity Mix</span>
                        <span style="background: rgba(59, 130, 246, 0.1); color: var(--accent); padding: 8px 16px; border-radius: 20px; font-size: 13px; font-weight: 500;">% Commercial</span>
                        <span style="background: rgba(59, 130, 246, 0.1); color: var(--accent); padding: 8px 16px; border-radius: 20px; font-size: 13px; font-weight: 500;">% Residential</span>
                        <span style="background: rgba(42, 157, 143, 0.1); color: var(--success); padding: 8px 16px; border-radius: 20px; font-size: 13px; font-weight: 500;">Remote Work Score</span>
                        <span style="background: rgba(42, 157, 143, 0.1); color: var(--success); padding: 8px 16px; border-radius: 20px; font-size: 13px; font-weight: 500;">Job Density</span>
                    </div>
                    <p style="margin-top: 20px; font-size: 14px; color: var(--text-secondary);">
                        These features were used to predict recovery in 133 neighborhoods with complete data
                    </p>
                </div>
            </div>
        </section>

        <!-- Charts Section (moved before maps) -->
        <section class="section snap-section" id="charts">
            <div class="section-header" style="text-align: center; max-width: 800px; margin: 0 auto 40px;">
                <h2>The Collapse and Partial Recovery</h2>
                <p>
                    Pre-COVID ridership averaged 135M monthly rides. The pandemic caused an 85% collapse.
                    Recovery has been steady but incomplete - the system remains ~28% below baseline.
                </p>
            </div>
            <div class="card">
                <div class="card-body">
                    <div id="ridership-chart" style="height: 400px;"></div>
                </div>
            </div>
            <div class="grid-2" style="margin-top: 24px;">
                <div class="insight">
                    <div class="insight-header">
                        <span class="insight-icon">📉</span>
                        <h4>The Collapse</h4>
                    </div>
                    <p>
                        In April 2020, ridership plummeted to just 25M rides - an 82% drop from pre-COVID levels.
                        The subway system, backbone of NYC transit, nearly ground to a halt.
                    </p>
                </div>
                <div class="insight">
                    <div class="insight-header">
                        <span class="insight-icon">+</span>
                        <h4>The "Recovery"</h4>
                    </div>
                    <p>
                        By late 2023, ridership climbed to ~100M monthly rides - a {((peak_month['ridership_millions'] / low_month['ridership_millions']) - 1) * 100:.0f}% increase from the low.
                        But the red dashed line shows what's missing: we're still ~{100 - avg_true_recovery * 100:.0f}% below normal.
                    </p>
                </div>
            </div>
        </section>

        <!-- Borough Comparison -->
        <section class="section snap-section" id="boroughs">
            <div class="section-header">
                <h2>Recovery by Borough</h2>
                <p>Comparing bounce-back (blue) vs. true recovery (red) reveals the gap across all five boroughs.</p>
            </div>
            <div class="card">
                <div class="card-body">
                    <div id="borough-chart" class="chart"></div>
                    <div class="insight">
                        <div class="insight-header">
                            <span class="insight-icon">🏙️</span>
                            <h4>The Borough Gap</h4>
                        </div>
                        <p>
                            All boroughs show strong "recovery" from COVID lows (blue bars),
                            but true recovery to pre-COVID levels (red bars) tells a different story.
                            Manhattan shows the biggest gap - strong bounce-back but only {borough_true_avg.get('Manhattan', 0)*100:.0f}% true recovery.
                            The green line marks 100% = full recovery.
                        </p>
                    </div>
                </div>
            </div>
        </section>

        <!-- Maps Section -->
        <section class="section snap-section" id="maps">
            <div class="section-header">
                <h2>Two Views of Recovery</h2>
                <p>
                    The same data tells radically different stories depending on your baseline.
                    Recovery from COVID lows paints optimism; comparison to pre-pandemic reveals the gap.
                </p>
            </div>
            <div class="grid-2">
                <div class="card">
                    <div class="card-header">
                        <h3>Recovery from COVID Low</h3>
                        <span class="badge" style="background: rgba(42, 157, 143, 0.15); color: #1e7b6e;">Q4 2023 ÷ Q3 2020</span>
                    </div>
                    <div class="map-container">
                        {map_html}
                    </div>
                    <div class="map-legend">
                        <span>0.5x</span>
                        <div class="legend-gradient"></div>
                        <span>4.0x</span>
                    </div>
                </div>
                <div class="card">
                    <div class="card-header">
                        <h3 style="color: var(--danger);">True Recovery (vs Pre-COVID)</h3>
                        <span class="badge" style="background: rgba(230, 57, 70, 0.15); color: #c1121f;">Q4 2023 ÷ Jan-Feb 2020</span>
                    </div>
                    <div class="map-container">
                        {true_map_html}
                    </div>
                    <div class="map-legend">
                        <span>20%</span>
                        <div class="legend-gradient"></div>
                        <span>100%</span>
                    </div>
                </div>
            </div>
            <div class="insight">
                <div class="insight-header">
                    <span class="insight-icon">&gt;</span>
                    <h4>Map Comparison</h4>
                </div>
                <p>
                    The left map shows apparent success - most neighborhoods 2-3x their COVID lows.
                    The right map reveals reality - predominantly orange and red, with almost no neighborhood
                    reaching pre-COVID levels. Manhattan's business districts that appear "recovered" on the left
                    are actually still 20-40% below their pre-pandemic ridership.
                </p>
            </div>
        </section>

        <!-- Scatter Section -->
        <section class="section snap-section" id="paradox">
            <div class="section-header">
                <h2>The Recovery Paradox</h2>
                <p>
                    Each dot represents a neighborhood. Notice how strong "recovery from low" does NOT
                    predict actual return to pre-COVID levels - these are fundamentally different metrics.
                </p>
            </div>
            <div class="card">
                <div class="card-body">
                    <div id="scatter-chart" style="height: 480px;"></div>
                    <div class="insight aha">
                        <div class="insight-header">
                            <span class="insight-icon">*</span>
                            <h4>Insight</h4>
                        </div>
                        <p>
                            <strong>The "recovery" narrative conflates two different things.</strong>
                            Points in the lower-right show neighborhoods with impressive bounce-back from COVID lows
                            but still far below pre-pandemic ridership. Only points above the red dashed line have
                            truly recovered. The weak correlation (R² ≈ 0.13) between these metrics confirms
                            they measure fundamentally different phenomena.
                        </p>
                    </div>
                </div>
            </div>
        </section>

        <!-- Analysis Section -->
        <section class="section snap-section" id="analysis">
            <div class="section-header">
                <h2>What Predicts Recovery?</h2>
                <p>
                    We built predictive models using neighborhood data (land use, jobs, demographics) to see if we could explain recovery patterns.
                    <strong>R² measures how much variation we can explain</strong> (1.0 = perfect prediction, 0 = no better than guessing).
                </p>
            </div>
            <div class="card">
                <div class="card-body">
                    <div class="r2-container">
                        <div class="r2-card success">
                            <div class="r2-value">58%</div>
                            <div class="r2-label">Bounce-back Explained (CV R²)</div>
                            <div class="r2-bar">
                                <div class="r2-bar-fill" data-value="58"></div>
                            </div>
                            <div class="r2-context">Best model: Ridge</div>
                        </div>
                        <div class="r2-card danger">
                            <div class="r2-value">22%</div>
                            <div class="r2-label">True Recovery Explained (CV R²)</div>
                            <div class="r2-bar">
                                <div class="r2-bar-fill" data-value="14"></div>
                            </div>
                            <div class="r2-context">Best model: Lasso</div>
                        </div>
                    </div>
                    <div style="background: rgba(0,0,0,0.03); border-radius: 12px; padding: 20px; margin: 24px 0; text-align: center;">
                        <p style="margin: 0; font-size: 14px; color: var(--text-secondary);">
                            <strong>What we tried:</strong> 5 different model types (linear regression, random forest, gradient boosting, etc.) with 8 neighborhood features (education, income, race, land use, job composition)
                        </p>
                    </div>
                    <div class="grid-2" style="margin-top: 24px;">
                        <div style="padding-right: 24px; border-right: 1px solid rgba(0,0,0,0.06);">
                            <h4 style="font-size: 16px; font-weight: 600; margin-bottom: 16px; color: var(--success);">
                                Bounce-back: Predictable
                            </h4>
                            <p style="font-size: 14px; color: var(--text-secondary); margin-bottom: 16px;">
                                Neighborhoods with these characteristics bounced back more:
                            </p>
                            <div style="font-size: 14px; line-height: 2;">
                                <div>• <strong>Higher education levels</strong> (strongest predictor)</div>
                                <div>• More commercial land use</div>
                                <div>• Neighborhood racial composition</div>
                                <div>• More remote-work-capable jobs</div>
                            </div>
                        </div>
                        <div style="padding-left: 24px;">
                            <h4 style="font-size: 16px; font-weight: 600; margin-bottom: 16px; color: var(--danger);">
                                True Recovery: NOT Predictable
                            </h4>
                            <p style="font-size: 14px; color: var(--text-secondary); margin-bottom: 16px;">
                                No combination of features could predict true recovery:
                            </p>
                            <div style="font-size: 14px; line-height: 2;">
                                <div style="color: var(--danger);">- All 5 models failed to generalize</div>
                                <div style="color: var(--danger);">- Higher income = WORSE true recovery</div>
                                <div style="color: var(--danger);">- 78% of variation unexplained</div>
                            </div>
                        </div>
                    </div>
                    <div class="insight aha" style="margin-top: 32px;">
                        <div class="insight-header">
                            <span class="insight-icon">*</span>
                            <h4>Why This Matters</h4>
                        </div>
                        <p>
                            <strong>We threw everything we had at this problem - 5 model types, 8 features including Census demographics - and still can't predict true recovery.</strong>
                            This isn't a failure; it's a finding. True recovery depends on things we can't measure from neighborhood data:
                            which specific employers require office attendance, individual worker preferences, and lasting behavioral changes from the pandemic.
                        </p>
                    </div>
                </div>
            </div>
        </section>

        <!-- Model Comparison Section -->
        <section class="section snap-section" id="models" style="background: linear-gradient(180deg, var(--bg) 0%, var(--bg-alt) 100%); margin-left: -48px; margin-right: -48px; padding: 80px 48px;">
            <div class="section-header" style="text-align: center; max-width: 900px; margin: 0 auto 48px;">
                <h2>How We Tested Model Health</h2>
                <p>
                    We tried 5 different machine learning approaches and measured each one three ways to ensure we weren't fooling ourselves.
                </p>
            </div>

            <!-- Metric Explanation -->
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; max-width: 1000px; margin: 0 auto 48px;">
                <div class="card" style="padding: 24px; text-align: center;">
                    <div style="font-size: 32px; margin-bottom: 12px;">📚</div>
                    <h4 style="font-size: 16px; margin-bottom: 8px;">Training R²</h4>
                    <p style="font-size: 13px; color: var(--text-secondary); line-height: 1.5;">
                        How well the model fits the data it learned from. <strong>High values can be misleading</strong> if the model just memorized the data.
                    </p>
                </div>
                <div class="card" style="padding: 24px; text-align: center;">
                    <div style="font-size: 32px; margin-bottom: 12px;">🧪</div>
                    <h4 style="font-size: 16px; margin-bottom: 8px;">Test R²</h4>
                    <p style="font-size: 13px; color: var(--text-secondary); line-height: 1.5;">
                        Performance on held-out data (20%). <strong>Better indicator</strong> of real-world usefulness than training score.
                    </p>
                </div>
                <div class="card" style="padding: 24px; text-align: center; border: 2px solid var(--success);">
                    <div style="font-size: 32px; margin-bottom: 12px;">✅</div>
                    <h4 style="font-size: 16px; margin-bottom: 8px;">Cross-Validation R²</h4>
                    <p style="font-size: 13px; color: var(--text-secondary); line-height: 1.5;">
                        Average across 5 different train/test splits. <strong>Most reliable measure</strong> - what we report as our final result.
                    </p>
                </div>
            </div>

            <!-- Model Comparison Charts -->
            <div class="grid-2" style="gap: 32px; max-width: 1200px; margin: 0 auto;">
                <div class="card">
                    <div class="card-header">
                        <h3>Bounce-back Models</h3>
                        <span class="badge" style="background: var(--success); color: white;">Best: 58% CV R²</span>
                    </div>
                    <div class="card-body">
                        <div id="bounce-model-chart" style="height: 300px;"></div>
                        <div class="insight" style="margin-top: 16px; padding: 16px;">
                            <p style="font-size: 13px; margin: 0;">
                                <strong>Ridge wins</strong> with the best cross-validation score (58%). Notice how Gradient Boosting has near-perfect training (99%) but poor CV (41%) - classic overfitting.
                            </p>
                        </div>
                    </div>
                </div>
                <div class="card">
                    <div class="card-header">
                        <h3>True Recovery Models</h3>
                        <span class="badge" style="background: var(--danger); color: white;">Best: 22% CV R²</span>
                    </div>
                    <div class="card-body">
                        <div id="true-model-chart" style="height: 300px;"></div>
                        <div class="insight" style="margin-top: 16px; padding: 16px; border-left-color: var(--danger);">
                            <p style="font-size: 13px; margin: 0;">
                                <strong>Most models fail.</strong> The best (Ridge at 22%) explains only a fraction of variance. High training scores with low CV scores in ensemble models = the patterns don't generalize.
                            </p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Overfitting Explanation -->
            <div style="max-width: 800px; margin: 48px auto 0; text-align: center;">
                <div class="card" style="padding: 32px;">
                    <h4 style="font-size: 18px; margin-bottom: 16px;">What is Overfitting?</h4>
                    <p style="font-size: 14px; color: var(--text-secondary); line-height: 1.7; margin-bottom: 20px;">
                        When a model's <strong>Training R² is much higher than CV R²</strong>, it memorized the training data instead of learning real patterns.
                        Like a student who memorizes answers instead of understanding concepts - they ace the practice test but fail the real exam.
                    </p>
                    <div style="display: flex; justify-content: center; gap: 32px;">
                        <div>
                            <div style="font-size: 14px; color: var(--text-muted); margin-bottom: 4px;">Gradient Boosting (Bounce-back)</div>
                            <div><span style="color: var(--danger); font-weight: 600;">99% Train</span> → <span style="color: var(--warning); font-weight: 600;">41% CV</span></div>
                            <div style="font-size: 12px; color: var(--danger);">Overfit</div>
                        </div>
                        <div>
                            <div style="font-size: 14px; color: var(--text-muted); margin-bottom: 4px;">Ridge (Bounce-back)</div>
                            <div><span style="color: var(--success); font-weight: 600;">73% Train</span> → <span style="color: var(--success); font-weight: 600;">58% CV</span></div>
                            <div style="font-size: 12px; color: var(--success);">Stable</div>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <!-- Clustering & Spatial Analysis Section -->
        <section class="section snap-section" id="clusters" style="background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); margin-left: -48px; margin-right: -48px; padding: 80px 48px;">
            <div class="section-header" style="text-align: center; max-width: 900px; margin: 0 auto 48px;">
                <h2>Recovery Patterns</h2>
                <p>We grouped neighborhoods into four distinct recovery types and tested whether similar neighborhoods are located near each other.</p>
            </div>
            <div class="grid-2" style="gap: 32px; max-width: 1200px; margin: 0 auto;">
                <div class="card">
                    <div class="card-header">
                        <h3>Recovery Trajectory Clusters</h3>
                        <span class="badge" style="background: var(--primary); color: white;">K-means, k=4</span>
                    </div>
                    <div class="card-body" style="padding: 0;">
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>Cluster</th>
                                    <th>NTAs</th>
                                    <th>Bounce-back</th>
                                    <th>True Recovery</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td><span class="badge" style="background: #2a9d8f; color: white;">Near-Full Recovery</span></td>
                                    <td style="text-align: center;">19</td>
                                    <td style="text-align: center;"><strong>4.50x</strong></td>
                                    <td><span class="badge high">83%</span></td>
                                </tr>
                                <tr>
                                    <td><span class="badge" style="background: #72b4d4; color: white;">Steady Recovery</span></td>
                                    <td style="text-align: center;">27</td>
                                    <td style="text-align: center;">3.17x</td>
                                    <td><span class="badge" style="background: #e9c46a;">76%</span></td>
                                </tr>
                                <tr>
                                    <td><span class="badge" style="background: #f4a261; color: white;">Lagging Recovery</span></td>
                                    <td style="text-align: center;">54</td>
                                    <td style="text-align: center;">2.25x</td>
                                    <td><span class="badge" style="background: #f4a261;">74%</span></td>
                                </tr>
                                <tr>
                                    <td><span class="badge" style="background: #e63946; color: white;">Struggling Recovery</span></td>
                                    <td style="text-align: center;">33</td>
                                    <td style="text-align: center;">1.51x</td>
                                    <td><span class="badge low">61%</span></td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
                <div class="card">
                    <div class="card-header">
                        <h3>Spatial Autocorrelation</h3>
                        <span class="badge" style="background: var(--primary); color: white;">Moran's I</span>
                    </div>
                    <div class="card-body">
                        <div style="margin-bottom: 24px;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                <span style="font-weight: 500;">Bounce-back</span>
                                <span class="badge high">I = 0.68</span>
                            </div>
                            <div style="background: #e9ecef; border-radius: 4px; height: 8px; overflow: hidden;">
                                <div style="background: var(--success); height: 100%; width: 68%;"></div>
                            </div>
                            <div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">p = 0.001 · Strong spatial clustering</div>
                        </div>
                        <div style="margin-bottom: 24px;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                <span style="font-weight: 500;">True Recovery</span>
                                <span class="badge" style="background: #f4a261;">I = 0.18</span>
                            </div>
                            <div style="background: #e9ecef; border-radius: 4px; height: 8px; overflow: hidden;">
                                <div style="background: #f4a261; height: 100%; width: 18%;"></div>
                            </div>
                            <div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">p = 0.006 · Weak spatial clustering</div>
                        </div>
                        <div class="insight" style="margin-top: 16px; background: rgba(42, 157, 143, 0.1); border-left: 3px solid var(--success);">
                            <p style="margin: 0; font-size: 14px;">
                                Bounce-back clusters much more spatially (I=0.68) than true recovery (I=0.18).
                                This aligns with regression: bounce-back is predictable from neighborhood characteristics, which are themselves spatially clustered.
                            </p>
                        </div>
                    </div>
                </div>
            </div>
            <!-- Cluster Map -->
            <div style="margin-top: 48px;">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 16px;">
                    <h3 style="margin: 0; font-size: 20px; font-weight: 600;">Cluster Map</h3>
                    <div style="display: flex; gap: 8px; flex-wrap: wrap; opacity: 0.6; font-size: 11px;">
                        <span style="color: #666;">Click buttons inside map to filter →</span>
                    </div>
                </div>
                <div class="map-container" style="box-shadow: 0 4px 24px rgba(0,0,0,0.1);">
                    {cluster_map_html}
                </div>
            </div>
        </section>

        <!-- Rankings Section -->
        <section class="section snap-section" id="rankings">
            <div class="section-header">
                <h2>Neighborhood Rankings</h2>
                <p>The best and worst true recovery rates across NYC neighborhoods.</p>
            </div>
            <div class="grid-2">
                <div class="card">
                    <div class="card-header">
                        <h3>Highest True Recovery</h3>
                        <span class="badge high">Top 5</span>
                    </div>
                    <div class="card-body" style="padding: 0;">
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>Neighborhood</th>
                                    <th>True Recovery</th>
                                    <th>From Low</th>
                                </tr>
                            </thead>
                            <tbody>
                                {''.join(f"""<tr>
                                    <td>
                                        <span class="rank-badge {'gold' if i == 0 else 'silver' if i == 1 else 'bronze' if i == 2 else 'default'}">{i+1}</span>
                                        {row['nta_name'][:28]}{'...' if len(row['nta_name']) > 28 else ''}
                                    </td>
                                    <td><span class="badge high">{row['true_recovery_index']:.0%}</span></td>
                                    <td style="color: var(--text-secondary);">{row['recovery_index']:.1f}x</td>
                                </tr>""" for i, (_, row) in enumerate(top_5_true.iterrows()))}
                            </tbody>
                        </table>
                    </div>
                </div>
                <div class="card">
                    <div class="card-header">
                        <h3>Lowest True Recovery</h3>
                        <span class="badge low">Bottom 5</span>
                    </div>
                    <div class="card-body" style="padding: 0;">
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>Neighborhood</th>
                                    <th>True Recovery</th>
                                    <th>From Low</th>
                                </tr>
                            </thead>
                            <tbody>
                                {''.join(f"""<tr>
                                    <td>
                                        <span class="rank-badge default">{total_ntas - 4 + i}</span>
                                        {row['nta_name'][:28]}{'...' if len(row['nta_name']) > 28 else ''}
                                    </td>
                                    <td><span class="badge low">{row['true_recovery_index']:.0%}</span></td>
                                    <td style="color: var(--text-secondary);">{row['recovery_index']:.1f}x</td>
                                </tr>""" for i, (_, row) in enumerate(bottom_5_true.iterrows()))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </section>

        <!-- The Big Picture Section -->
        <section class="section snap-section" id="conclusion" style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); margin-left: -48px; margin-right: -48px; padding: 80px 48px; color: white;">
            <div class="section-header" style="text-align: center; max-width: 900px; margin: 0 auto 48px;">
                <h2 style="color: white; font-size: 42px;">The Big Picture</h2>
                <p style="color: rgba(255,255,255,0.7); font-size: 18px;">
                    How all the pieces fit together to tell one story
                </p>
            </div>
            <div style="max-width: 900px; margin: 0 auto;">
                <div style="display: grid; gap: 32px;">
                    <div style="display: flex; gap: 24px; align-items: flex-start;">
                        <div style="background: rgba(42, 157, 143, 0.3); color: #2a9d8f; width: 48px; height: 48px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 20px; flex-shrink: 0;">1</div>
                        <div>
                            <h4 style="color: white; font-size: 20px; margin-bottom: 8px;">The Illusion</h4>
                            <p style="color: rgba(255,255,255,0.7); font-size: 16px; line-height: 1.7;">
                                NYC subway ridership grew <strong style="color: #2a9d8f;">2.4x from COVID lows</strong>, suggesting strong recovery. But this masks reality: the system is only at <strong style="color: #e63946;">72% of pre-pandemic levels</strong>. 98% of neighborhoods remain below baseline. The "recovery" depends entirely on which baseline you choose.
                            </p>
                        </div>
                    </div>
                    <div style="display: flex; gap: 24px; align-items: flex-start;">
                        <div style="background: rgba(244, 162, 97, 0.3); color: #f4a261; width: 48px; height: 48px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 20px; flex-shrink: 0;">2</div>
                        <div>
                            <h4 style="color: white; font-size: 20px; margin-bottom: 8px;">The Divergence</h4>
                            <p style="color: rgba(255,255,255,0.7); font-size: 16px; line-height: 1.7;">
                                We can predict bounce-back (<strong style="color: #2a9d8f;">CV R² = 0.54</strong>): educated, white-collar neighborhoods bounced back most. But true recovery is unpredictable (<strong style="color: #e63946;">CV R² = 0.18</strong>) even after testing 5 model types with demographic data. The same neighborhood characteristics that explain growth from COVID lows do NOT explain return to pre-pandemic levels.
                            </p>
                        </div>
                    </div>
                    <div style="display: flex; gap: 24px; align-items: flex-start;">
                        <div style="background: rgba(114, 180, 212, 0.3); color: #72b4d4; width: 48px; height: 48px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 20px; flex-shrink: 0;">3</div>
                        <div>
                            <h4 style="color: white; font-size: 20px; margin-bottom: 8px;">The Patterns</h4>
                            <p style="color: rgba(255,255,255,0.7); font-size: 16px; line-height: 1.7;">
                                Four distinct recovery clusters emerged: <strong style="color: #2a9d8f;">Near-Full</strong> (19 NTAs, 4.5x bounce-back), <strong style="color: #72b4d4;">Steady</strong> (27 NTAs, 3.2x), <strong style="color: #f4a261;">Lagging</strong> (54 NTAs, 2.3x), and <strong style="color: #e63946;">Struggling</strong> (33 NTAs, 1.5x). Spatial analysis confirms bounce-back clusters geographically (Moran's I = 0.68), but true recovery is more randomly distributed (I = 0.18).
                            </p>
                        </div>
                    </div>
                    <div style="display: flex; gap: 24px; align-items: flex-start;">
                        <div style="background: rgba(230, 57, 70, 0.3); color: #e63946; width: 48px; height: 48px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 20px; flex-shrink: 0;">4</div>
                        <div>
                            <h4 style="color: white; font-size: 20px; margin-bottom: 8px;">The Conclusion</h4>
                            <p style="color: rgba(255,255,255,0.7); font-size: 16px; line-height: 1.7;">
                                <strong style="color: white;">"Bouncing back" and "truly recovering" are fundamentally different phenomena.</strong> The 28% gap between current ridership and pre-pandemic levels likely reflects a permanent structural shift associated with factors we cannot measure: employer return-to-office policies, individual preferences, and lasting behavioral changes. Transit planning must account for this new reality.
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <!-- Methodology Section -->
        <section class="section methodology-section snap-section" id="methodology" style="margin-left: -48px; margin-right: -48px; padding-left: 48px; padding-right: 48px;">
            <div class="section-header">
                <h2>Methodology & Limitations</h2>
                <p>Transparency about our data sources, methods, and what this analysis can and cannot tell us.</p>
            </div>
            <div class="methodology-grid">
                <div class="methodology-card">
                    <div class="icon">#</div>
                    <h4>Recovery Index Calculation</h4>
                    <p>
                        Two metrics calculated per NTA: (1) Recovery from Low = Q4 2023 ÷ Q3 2020 average monthly ridership,
                        (2) True Recovery = Q4 2023 ÷ Jan-Feb 2020 (pre-COVID baseline).
                        Stations mapped to NTAs via spatial join on coordinates.
                    </p>
                </div>
                <div class="methodology-card">
                    <div class="icon">@</div>
                    <h4>Geographic Scope</h4>
                    <p>
                        Analysis covers 133 of 262 NTAs with subway service. Results apply only to subway-served areas.
                        Bus-dependent neighborhoods may show different patterns not captured here.
                    </p>
                </div>
                <div class="methodology-card">
                    <div class="icon">~</div>
                    <h4>Model Comparison</h4>
                    <p>
                        Tested 5 models: OLS, Ridge, Lasso, Random Forest, Gradient Boosting.
                        Validated with 80/20 train-test split and 5-fold cross-validation.
                        Spatial autocorrelation tested with Moran's I.
                    </p>
                </div>
                <div class="methodology-card">
                    <div class="icon">!</div>
                    <h4>Model Limitations</h4>
                    <p>
                        Evidence of overfitting in ensemble methods: Gradient Boosting Train R² (0.98) vs CV R² (-0.26).
                        Best true recovery model (Ridge) only achieves CV R² = 0.18,
                        suggesting unmeasured factors are associated with actual recovery.
                    </p>
                </div>
                <div class="methodology-card">
                    <div class="icon">🏢</div>
                    <h4>Predictor Data</h4>
                    <p>
                        PLUTO (857K properties), LEHD (4.2M jobs), and Census ACS demographics
                        (income, education, race). 8 features total including remote work potential
                        and neighborhood demographic composition.
                    </p>
                </div>
                <div class="methodology-card">
                    <div class="icon">📅</div>
                    <h4>Temporal Scope</h4>
                    <p>
                        Analysis period: July 2020 – December 2023 (42 months).
                        Pre-COVID baseline: January 1 – February 29, 2020 (pre-pandemic).
                        Data from MTA Subway Hourly Ridership dataset.
                    </p>
                </div>
            </div>
        </section>
    </div>

    <!-- Footer -->
    <footer class="footer">
        <div class="footer-brand">
            <span style="font-weight: 600; font-size: 16px;">Georgia Institute of Technology</span>
        </div>
        <div style="margin-bottom: 20px;">
            <p style="font-size: 14px; font-weight: 500; color: var(--text);">
                Isaac Regalado · Elias Dematis · Dami Awosika · David Mongeau
            </p>
        </div>
        <div class="footer-sources">
            <span class="pill">MTA Open Data</span>
            <span class="pill">NYC Planning</span>
            <span class="pill">PLUTO</span>
            <span class="pill">Census LEHD</span>
            <span class="pill">Census ACS</span>
        </div>
        <p class="footer-meta">
            CSE 6242 Data and Visual Analytics · Spring 2026 · Analysis current as of December 2023
        </p>
    </footer>

    <script>
        // ============================================
        // SCROLL ANIMATIONS & PROGRESS
        // ============================================

        const sections = document.querySelectorAll('.section, .stat-card');
        const navDots = document.querySelectorAll('.nav-dot');
        const progressFill = document.getElementById('progress-fill');

        // Intersection Observer for fade-in animations
        const fadeObserver = new IntersectionObserver((entries) => {{
            entries.forEach(entry => {{
                if (entry.isIntersecting) {{
                    entry.target.classList.add('visible');
                }}
            }});
        }}, {{ threshold: 0.1, rootMargin: '0px 0px -50px 0px' }});

        sections.forEach(section => fadeObserver.observe(section));

        // Scroll progress
        window.addEventListener('scroll', () => {{
            const scrollTop = window.scrollY;
            const docHeight = document.documentElement.scrollHeight - window.innerHeight;
            const progress = (scrollTop / docHeight) * 100;
            progressFill.style.width = progress + '%';

            // Update active nav dot
            const sectionElements = ['hero', 'findings', 'approach', 'charts', 'maps', 'analysis', 'rankings', 'methodology'];
            let currentSection = 'hero';

            sectionElements.forEach(id => {{
                const el = document.getElementById(id);
                if (el && el.getBoundingClientRect().top < window.innerHeight / 2) {{
                    currentSection = id;
                }}
            }});

            navDots.forEach(dot => {{
                dot.classList.toggle('active', dot.dataset.section === currentSection);
            }});
        }});

        // Nav dot click
        navDots.forEach(dot => {{
            dot.addEventListener('click', () => {{
                const section = document.getElementById(dot.dataset.section);
                if (section) {{
                    section.scrollIntoView({{ behavior: 'smooth' }});
                }}
            }});
        }});

        // ============================================
        // ANIMATED COUNTERS
        // ============================================

        function animateValue(element, start, end, duration, suffix = '') {{
            const startTime = performance.now();
            const isDecimal = String(end).includes('.');

            function update(currentTime) {{
                const elapsed = currentTime - startTime;
                const progress = Math.min(elapsed / duration, 1);
                const easeOut = 1 - Math.pow(1 - progress, 3);
                const current = start + (end - start) * easeOut;

                if (isDecimal) {{
                    element.textContent = current.toFixed(1) + suffix;
                }} else {{
                    element.textContent = Math.floor(current) + suffix;
                }}

                if (progress < 1) {{
                    requestAnimationFrame(update);
                }}
            }}

            requestAnimationFrame(update);
        }}

        // Hero stat counter
        const heroStat = document.querySelector('.hero-stat-value');
        if (heroStat) {{
            const target = parseFloat(heroStat.dataset.target);
            setTimeout(() => animateValue(heroStat, 0, target, 2000, '%'), 1000);
        }}

        // Stat card counters
        const statObserver = new IntersectionObserver((entries) => {{
            entries.forEach(entry => {{
                if (entry.isIntersecting && !entry.target.dataset.animated) {{
                    entry.target.dataset.animated = 'true';
                    const valueEl = entry.target.querySelector('.value[data-target]');
                    if (valueEl) {{
                        const target = parseFloat(valueEl.dataset.target);
                        const suffix = valueEl.dataset.suffix || '';
                        animateValue(valueEl, 0, target, 1500, suffix);
                    }}
                }}
            }});
        }}, {{ threshold: 0.5 }});

        document.querySelectorAll('.stat-card').forEach(card => statObserver.observe(card));

        // R² bar animations
        const r2Observer = new IntersectionObserver((entries) => {{
            entries.forEach(entry => {{
                if (entry.isIntersecting && !entry.target.dataset.animated) {{
                    entry.target.dataset.animated = 'true';
                    const bars = entry.target.querySelectorAll('.r2-bar-fill');
                    bars.forEach((bar, i) => {{
                        const value = parseFloat(bar.dataset.value);
                        setTimeout(() => {{
                            bar.style.width = value + '%';
                        }}, 300 + (i * 150));
                    }});
                }}
            }});
        }}, {{ threshold: 0.3 }});

        document.querySelectorAll('.r2-container').forEach(rc => r2Observer.observe(rc));

        // ============================================
        // CHARTS
        // ============================================

        const chartConfig = {{ responsive: true, displayModeBar: false }};
        const chartFont = {{ family: 'Inter, -apple-system, BlinkMacSystemFont, sans-serif' }};

        // Ridership Chart
        const ridershipData = {{
            x: {json.dumps(monthly_total['year_month'].tolist())},
            y: {json.dumps(monthly_total['ridership_millions'].round(1).tolist())}
        }};

        Plotly.newPlot('ridership-chart', [
            {{
                ...ridershipData,
                type: 'scatter',
                mode: 'lines',
                name: 'Monthly Ridership',
                fill: 'tozeroy',
                line: {{ color: '#3b82f6', width: 3, shape: 'spline' }},
                fillcolor: 'rgba(59, 130, 246, 0.1)',
                hovertemplate: '<b>%{{x}}</b><br>%{{y:.0f}}M rides<extra></extra>'
            }},
            {{
                x: ridershipData.x,
                y: Array(ridershipData.x.length).fill({precovid_monthly:.1f}),
                type: 'scatter',
                mode: 'lines',
                name: 'Pre-COVID Baseline',
                line: {{ color: '#dc2626', width: 3 }},
                hoverinfo: 'skip'
            }}
        ], {{
            margin: {{ l: 50, r: 20, t: 30, b: 60 }},
            xaxis: {{
                tickangle: -45,
                tickfont: {{ size: 11, color: '#6b7280', ...chartFont }},
                gridcolor: 'rgba(0,0,0,0.04)',
                showline: false,
                nticks: 12
            }},
            yaxis: {{
                title: {{ text: 'Monthly Rides (Millions)', font: {{ size: 12, color: '#6b7280', ...chartFont }} }},
                tickfont: {{ size: 11, color: '#6b7280', ...chartFont }},
                gridcolor: 'rgba(0,0,0,0.04)',
                showline: false,
                rangemode: 'tozero'
            }},
            shapes: [{{
                type: 'rect',
                x0: ridershipData.x[0],
                x1: ridershipData.x[ridershipData.x.length - 1],
                y0: Math.max(...ridershipData.y),
                y1: {precovid_monthly:.1f},
                fillcolor: 'rgba(220, 38, 38, 0.1)',
                line: {{ width: 0 }}
            }}],
            annotations: [{{
                x: ridershipData.x[Math.floor(ridershipData.x.length * 0.75)],
                y: {precovid_monthly:.1f} + 12,
                text: '<b>Pre-COVID Baseline: {precovid_monthly:.0f}M/month</b>',
                showarrow: true,
                arrowhead: 0,
                arrowcolor: '#dc2626',
                ax: 0,
                ay: 30,
                font: {{ size: 12, color: '#dc2626', ...chartFont }}
            }},
            {{
                x: '2020-05',
                y: 20,
                text: '<b>COVID Low</b><br>20M rides',
                showarrow: true,
                arrowhead: 2,
                arrowcolor: '#1a1a2e',
                arrowwidth: 2,
                ax: 50,
                ay: -50,
                font: {{ size: 11, color: '#1a1a2e', ...chartFont }}
            }}],
            hoverlabel: {{
                bgcolor: 'white',
                bordercolor: '#e5e7eb',
                font: {{ ...chartFont, size: 13 }}
            }},
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            showlegend: false
        }}, chartConfig);

        // Borough Chart
        const boroughData = {{
            boroughs: {json.dumps(borough_avg.index.tolist())},
            fromLow: {json.dumps([round(v * 100, 1) for v in borough_avg.values.tolist()])},
            trueRecovery: {json.dumps([round(v * 100, 1) for v in borough_true_avg.reindex(borough_avg.index).values.tolist()])}
        }};

        Plotly.newPlot('borough-chart', [
            {{
                y: boroughData.boroughs,
                x: boroughData.trueRecovery,
                type: 'bar',
                orientation: 'h',
                name: 'True Recovery (%)',
                marker: {{
                    color: '#e63946',
                    line: {{ width: 0 }}
                }},
                hovertemplate: '<b>%{{y}}</b><br>True: %{{x:.0f}}% of pre-COVID<extra></extra>'
            }},
            {{
                y: boroughData.boroughs,
                x: boroughData.fromLow,
                type: 'bar',
                orientation: 'h',
                name: 'From COVID Low (%)',
                marker: {{
                    color: '#3b82f6',
                    opacity: 0.6
                }},
                hovertemplate: '<b>%{{y}}</b><br>From Low: %{{x:.0f}}%<extra></extra>'
            }}
        ], {{
            margin: {{ l: 100, r: 30, t: 40, b: 50 }},
            barmode: 'group',
            bargap: 0.3,
            bargroupgap: 0.1,
            xaxis: {{
                title: {{ text: 'Recovery (%)', font: {{ size: 12, color: '#6b7280', ...chartFont }} }},
                tickfont: {{ size: 11, color: '#6b7280', ...chartFont }},
                ticksuffix: '%',
                tickvals: [0, 50, 100, 150, 200, 250, 300],
                gridcolor: 'rgba(0,0,0,0.04)',
                showline: false,
                range: [0, 330]
            }},
            yaxis: {{
                tickfont: {{ size: 12, color: '#1a1a2e', ...chartFont }},
                showline: false
            }},
            shapes: [{{
                type: 'line',
                x0: 100, x1: 100,
                y0: -0.5, y1: 4.5,
                line: {{ color: '#16a34a', width: 3 }}
            }}],
            annotations: [{{
                x: 100, y: 5,
                text: '<b>100% = Full Recovery</b>',
                showarrow: false,
                font: {{ size: 11, color: '#16a34a', ...chartFont }}
            }}],
            legend: {{
                orientation: 'h',
                y: 1.15,
                x: 0.5,
                xanchor: 'center',
                font: {{ size: 11, ...chartFont }}
            }},
            hoverlabel: {{
                bgcolor: 'white',
                bordercolor: '#e5e7eb',
                font: {{ ...chartFont, size: 13 }}
            }},
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent'
        }}, chartConfig);

        // Scatter Chart
        const scatterData = {{
            x: {json.dumps(scatter_data['recovery_index'].tolist())},
            y: {json.dumps(scatter_data['true_recovery_index'].tolist())},
            names: {json.dumps(scatter_data['nta_name'].tolist())},
            boroughs: {json.dumps(scatter_data['borough_name'].tolist())},
            colors: {json.dumps(scatter_data['color'].tolist())}
        }};

        Plotly.newPlot('scatter-chart', [{{
            x: scatterData.x,
            y: scatterData.y,
            text: scatterData.names,
            customdata: scatterData.boroughs,
            mode: 'markers',
            type: 'scatter',
            marker: {{
                size: 11,
                color: scatterData.colors,
                opacity: 0.75,
                line: {{ width: 1.5, color: 'white' }}
            }},
            hovertemplate: '<b>%{{text}}</b><br>%{{customdata}}<br>From Low: %{{x:.2f}}x<br>True: %{{y:.0%}}<extra></extra>'
        }}], {{
            margin: {{ l: 70, r: 40, t: 40, b: 70 }},
            xaxis: {{
                title: {{ text: 'Recovery from COVID Low (×)', font: {{ size: 13, color: '#6b7280', ...chartFont }} }},
                tickfont: {{ size: 11, color: '#6b7280', ...chartFont }},
                gridcolor: 'rgba(0,0,0,0.04)',
                showline: true,
                linecolor: 'rgba(0,0,0,0.1)',
                zeroline: false
            }},
            yaxis: {{
                title: {{ text: 'True Recovery (% of Pre-COVID)', font: {{ size: 13, color: '#6b7280', ...chartFont }} }},
                tickfont: {{ size: 11, color: '#6b7280', ...chartFont }},
                tickformat: '.0%',
                gridcolor: 'rgba(0,0,0,0.04)',
                showline: true,
                linecolor: 'rgba(0,0,0,0.1)',
                zeroline: false
            }},
            shapes: [
                {{
                    type: 'line',
                    x0: 0.5, x1: 5,
                    y0: 1.0, y1: 1.0,
                    line: {{ color: '#e63946', width: 2, dash: 'dash' }}
                }},
                {{
                    type: 'rect',
                    x0: 2.5, x1: 5,
                    y0: 0.2, y1: 0.8,
                    fillcolor: 'rgba(230, 57, 70, 0.03)',
                    line: {{ width: 0 }}
                }}
            ],
            annotations: [
                {{
                    x: 4.5, y: 1.03,
                    text: 'Full Recovery Line',
                    showarrow: false,
                    font: {{ size: 11, color: '#e63946', ...chartFont }}
                }},
                {{
                    x: 3.8, y: 0.5,
                    text: '"Illusion Zone"<br>High bounce-back,<br>still below baseline',
                    showarrow: false,
                    font: {{ size: 10, color: '#9ca3af', ...chartFont }},
                    align: 'center'
                }}
            ],
            hoverlabel: {{
                bgcolor: 'white',
                bordercolor: '#e5e7eb',
                font: {{ ...chartFont, size: 13 }}
            }},
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent'
        }}, chartConfig);

        // Model Comparison Charts
        const models = ['OLS', 'Ridge', 'Lasso', 'Random<br>Forest', 'Gradient<br>Boosting'];

        // Bounce-back models
        Plotly.newPlot('bounce-model-chart', [
            {{
                name: 'Training R²',
                x: models,
                y: [0.73, 0.73, 0.66, 0.89, 0.99],
                type: 'bar',
                marker: {{ color: 'rgba(107, 114, 128, 0.4)' }},
                hovertemplate: '%{{x}}<br>Training: %{{y:.0%}}<extra></extra>'
            }},
            {{
                name: 'Test R²',
                x: models,
                y: [0.70, 0.71, 0.78, 0.87, 0.73],
                type: 'bar',
                marker: {{ color: 'rgba(59, 130, 246, 0.6)' }},
                hovertemplate: '%{{x}}<br>Test: %{{y:.0%}}<extra></extra>'
            }},
            {{
                name: 'CV R² (Final)',
                x: models,
                y: [0.52, 0.54, 0.54, 0.52, 0.35],
                type: 'bar',
                marker: {{ color: '#2a9d8f' }},
                hovertemplate: '%{{x}}<br>CV R²: %{{y:.0%}}<extra></extra>'
            }}
        ], {{
            barmode: 'group',
            margin: {{ l: 50, r: 20, t: 20, b: 60 }},
            xaxis: {{
                tickfont: {{ size: 11, color: '#6b7280', ...chartFont }}
            }},
            yaxis: {{
                title: {{ text: 'R² Score', font: {{ size: 12, color: '#6b7280', ...chartFont }} }},
                tickformat: '.0%',
                range: [0, 1],
                tickfont: {{ size: 11, color: '#6b7280', ...chartFont }},
                gridcolor: 'rgba(0,0,0,0.04)'
            }},
            legend: {{
                orientation: 'h',
                y: -0.25,
                x: 0.5,
                xanchor: 'center',
                font: {{ size: 11, ...chartFont }}
            }},
            hoverlabel: {{ bgcolor: 'white', bordercolor: '#e5e7eb', font: {{ ...chartFont, size: 12 }} }},
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent'
        }}, chartConfig);

        // True Recovery models
        Plotly.newPlot('true-model-chart', [
            {{
                name: 'Training R²',
                x: models,
                y: [0.37, 0.37, 0.00, 0.73, 0.98],
                type: 'bar',
                marker: {{ color: 'rgba(107, 114, 128, 0.4)' }},
                hovertemplate: '%{{x}}<br>Training: %{{y:.0%}}<extra></extra>'
            }},
            {{
                name: 'Test R²',
                x: models,
                y: [0.29, 0.29, -0.07, 0.17, -0.52],
                type: 'bar',
                marker: {{ color: 'rgba(59, 130, 246, 0.6)' }},
                hovertemplate: '%{{x}}<br>Test: %{{y:.0%}}<extra></extra>'
            }},
            {{
                name: 'CV R² (Final)',
                x: models,
                y: [0.17, 0.18, -0.03, 0.05, -0.26],
                type: 'bar',
                marker: {{ color: '#e63946' }},
                hovertemplate: '%{{x}}<br>CV R²: %{{y:.0%}}<extra></extra>'
            }}
        ], {{
            barmode: 'group',
            margin: {{ l: 50, r: 20, t: 20, b: 60 }},
            xaxis: {{
                tickfont: {{ size: 11, color: '#6b7280', ...chartFont }}
            }},
            yaxis: {{
                title: {{ text: 'R² Score', font: {{ size: 12, color: '#6b7280', ...chartFont }} }},
                tickformat: '.0%',
                range: [0, 1],
                tickfont: {{ size: 11, color: '#6b7280', ...chartFont }},
                gridcolor: 'rgba(0,0,0,0.04)'
            }},
            legend: {{
                orientation: 'h',
                y: -0.25,
                x: 0.5,
                xanchor: 'center',
                font: {{ size: 11, ...chartFont }}
            }},
            hoverlabel: {{ bgcolor: 'white', bordercolor: '#e5e7eb', font: {{ ...chartFont, size: 12 }} }},
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent'
        }}, chartConfig);

    </script>
</body>
</html>
'''

    output_path = OUTPUT_FIGURES / 'dashboard_apple.html'
    output_path.write_text(html)
    print(f"Dashboard saved to: {output_path}")
    return output_path


if __name__ == '__main__':
    OUTPUT_FIGURES.mkdir(parents=True, exist_ok=True)
    create_dashboard()
