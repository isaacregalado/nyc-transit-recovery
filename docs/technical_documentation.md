# Technical Documentation: NYC Transit Recovery Analysis

**Project:** CSE 6242 Data and Visual Analytics | Spring 2026
**Team:** Isaac Regalado, Elias Dematis, Dami Awosika, David Mongeau

This document provides complete technical details on data acquisition, processing, analysis, and visualization. Use this to understand or rerun any part of the pipeline.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Environment Setup](#2-environment-setup)
3. [Data Acquisition](#3-data-acquisition)
4. [Data Processing](#4-data-processing)
5. [Feature Engineering](#5-feature-engineering)
6. [Analysis Pipeline](#6-analysis-pipeline)
7. [Visualization](#7-visualization)
8. [File Structure](#8-file-structure)
9. [Rerunning the Pipeline](#9-rerunning-the-pipeline)

---

## 1. Project Overview

### Research Question

What neighborhood-level economic and demographic factors predict the speed and magnitude of post-COVID subway ridership recovery across NYC's neighborhoods?

### Dual Metrics

We developed two distinct recovery metrics:

- **Recovery Index (Bounce-back):** Q4 2023 / Q3 2020 - measures growth from COVID low
- **True Recovery Index:** Q4 2023 / Jan-Feb 2020 - measures return to pre-pandemic levels

### Main Result

These metrics have different predictors:

- Bounce-back: CV R² = 0.54 (predictable from land use + employment + demographics)
- True Recovery: CV R² = 0.18 (NOT predictable - 82% unexplained)

---

## 2. Environment Setup

### Requirements

```bash
pip install -r requirements.txt
```

### Key Dependencies

```
pandas>=2.0.0
geopandas>=0.14.0
numpy>=1.24.0
scikit-learn>=1.3.0
statsmodels>=0.14.0
folium>=0.15.0
plotly>=5.18.0
requests>=2.31.0
shapely>=2.0.0
branca>=0.7.0
```

### Python Version

Python 3.10+ recommended

---

## 3. Data Acquisition

### 3.1 MTA Subway Ridership Data

**Source:** https://data.ny.gov/Transportation/MTA-Subway-Hourly-Ridership-Beginning-July-2020/wujg-7c2s

**Script:** `src/data/download_mta_filtered.py`

**What it does:**

1. Downloads hourly ridership data via Socrata API
2. Filters to July 2020 - December 2023
3. Contains columns: transit_timestamp, station_complex_id, ridership, etc.

**Output:** `data/raw/mta_subway_hourly_ridership_2020_2024.csv` (~1.1GB)

**To rerun:**

```bash
python src/data/download_mta_filtered.py
```

**Note:** We deleted this large file to save space. The processed data is preserved in `data/processed/`.

### 3.2 Pre-COVID Baseline Data

**Source:** Same MTA dataset, January-February 2020

**Script:** `src/data/download_mta_filtered.py` (with date filter modification)

**Output:** `data/raw/mta_precovid_daily.csv`

**Purpose:** Establishes true pre-pandemic baseline for "True Recovery Index"

### 3.3 NTA Boundaries (Neighborhood Tabulation Areas)

**Source:** NYC Open Data - 2020 NTA boundaries

**Script:** `src/data/download_predictors.py`

**Output:** `data/external/nta_boundaries_2020.geojson`

**Details:**

- 262 NTAs covering all 5 boroughs
- Used as spatial aggregation unit
- Contains nta_code, nta_name, borough_name, geometry

### 3.4 PLUTO Property Data

**Source:** NYC Department of City Planning - PLUTO 22v1

**Script:** `src/data/download_predictors.py`

**Processing:**

1. Downloaded full PLUTO dataset (~300MB)
2. Spatially joined to NTAs
3. Aggregated land use statistics per NTA

**Output:** `data/raw/pluto_nta_aggregated.csv`

**Features extracted:**

- `pct_commercial` - % of land area in commercial use
- `pct_residential` - % of land area in residential use
- `residential_density` - residential units per acre
- `commercial_density` - commercial sqft per acre
- `avg_building_age` - average year built
- `property_count` - number of tax lots
- `total_res_units` - total residential units

### 3.5 LEHD Employment Data (Census)

**Source:** Census LEHD LODES - Workplace Area Characteristics (WAC)

**URL:** https://lehd.ces.census.gov/data/lodes/LODES8/ny/wac/

**Script:** `src/data/process_employment.py`

**Processing:**

1. Downloaded NY state WAC data for 2019 (pre-COVID employment)
2. Filtered to NYC counties (FIPS: 36005, 36047, 36061, 36081, 36085)
3. Aggregated from census block to census tract
4. Created tract-to-NTA crosswalk via spatial join
5. Aggregated to NTA level
6. Calculated remote work potential scores

**Output:** `data/raw/nta_employment.csv`

**Features extracted:**

- `total_jobs` - total employment in NTA
- `high_remote_jobs` - jobs in high remote-work-potential industries
- `medium_remote_jobs` - jobs in medium remote-work-potential industries
- `low_remote_jobs` - jobs in low remote-work-potential industries
- `remote_work_score` - weighted score (high*1.0 + medium*0.5 + low\*0.1)
- `pct_finance`, `pct_professional`, `pct_retail`, etc. - industry shares

**Remote Work Classification (NAICS codes):**

```python
HIGH_REMOTE = ['CNS09', 'CNS10', 'CNS12', 'CNS13']  # Info, Finance, Professional, Management
MEDIUM_REMOTE = ['CNS11', 'CNS14', 'CNS15', 'CNS20']  # Real Estate, Admin, Education, Public Admin
LOW_REMOTE = ['CNS01'-'CNS08', 'CNS16'-'CNS19']  # Retail, Healthcare, Food Service, etc.
```

**To rerun:**

```bash
python src/data/process_employment.py
```

---

## 4. Data Processing

### 4.1 Ridership Aggregation

**Script:** `src/data/process_data.py`

**Steps:**

1. Load hourly ridership data
2. Parse timestamps and extract year-month
3. Aggregate to monthly totals per station
4. Map stations to NTAs via spatial join (station coordinates to NTA polygons)
5. Aggregate to monthly totals per NTA

**Station-to-NTA Mapping:**

- 472 unique subway stations
- Mapped using station lat/lon coordinates
- Spatial join with NTA boundary polygons
- 133 NTAs have at least one subway station

### 4.2 Recovery Index Calculation

**Baseline Period (Q3 2020):** July-September 2020

- Represents the COVID low point
- Average monthly ridership per NTA

**Recovery Period (Q4 2023):** October-December 2023

- Most recent complete quarter
- Average monthly ridership per NTA

**Recovery Index Formula:**

```python
recovery_index = q4_2023_ridership / q3_2020_ridership
```

### 4.3 True Recovery Index Calculation

**Pre-COVID Baseline:** January-February 2020

- Before COVID impact
- Average monthly ridership per NTA

**True Recovery Formula:**

```python
true_recovery_index = q4_2023_ridership / jan_feb_2020_ridership
```

### 4.4 Output Files

**Primary analysis file:** `data/processed/nta_analysis_ready.geojson`

Contains per NTA:

- `nta_code`, `nta_name`, `borough_name`
- `baseline_ridership` (Q3 2020)
- `recovery_ridership` (Q4 2023)
- `recovery_index`
- `precovid_ridership` (Jan-Feb 2020)
- `true_recovery_index`
- `geometry` (polygon)

---

## 5. Feature Engineering

### 5.1 Land Use Features (from PLUTO)

| Feature               | Description            | Calculation                             |
| --------------------- | ---------------------- | --------------------------------------- |
| `pct_commercial`      | Commercial land share  | sum(commercial_area) / sum(total_area)  |
| `pct_residential`     | Residential land share | sum(residential_area) / sum(total_area) |
| `residential_density` | Housing density        | total_res_units / nta_area_acres        |
| `commercial_density`  | Commercial intensity   | commercial_sqft / nta_area_acres        |
| `avg_building_age`    | Building stock age     | mean(year_built)                        |
| `property_count`      | Development intensity  | count(tax_lots)                         |
| `total_res_units`     | Housing stock size     | sum(residential_units)                  |

### 5.2 Employment Features (from LEHD)

| Feature             | Description                 | Calculation                             |
| ------------------- | --------------------------- | --------------------------------------- |
| `total_jobs`        | Total employment            | sum(C000)                               |
| `remote_work_score` | Remote work potential       | (high*1.0 + med*0.5 + low\*0.1) / total |
| `pct_finance`       | Finance sector share        | CNS10 / total_jobs                      |
| `pct_professional`  | Professional services share | CNS12 / total_jobs                      |
| `pct_retail`        | Retail sector share         | CNS07 / total_jobs                      |
| `office_share`      | Office job concentration    | (finance + professional + info) / total |
| `retail_share`      | Retail job concentration    | (retail + food_service) / total         |

### 5.3 Feature Selection

**Final features used in regression (9 total):**

1. `pct_commercial`
2. `commercial_density`
3. `residential_density`
4. `office_share`
5. `retail_share`
6. `avg_building_age`
7. `property_count`
8. `total_res_units`
9. `remote_work_score`

**VIF Check:** All features have VIF < 5 (no severe multicollinearity)

---

## 6. Analysis Pipeline

### 6.1 Regression Analysis

**Script:** `src/analysis/recovery_analysis.py`

**Method:** Ordinary Least Squares (OLS) with standardized coefficients

**Standardization:**

```python
from sklearn.preprocessing import StandardScaler
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)
```

**Model 1: Recovery from COVID Low**

```python
import statsmodels.api as sm
X_with_const = sm.add_constant(X_scaled)
model = sm.OLS(y_recovery_index, X_with_const).fit()
```

**Results:**

- R² = 0.732
- Adjusted R² = 0.715
- CV R² = 0.568
- Significant predictors: pct_commercial (+0.34), pct_bachelors (+0.38), remote_work_score (+0.24), pct_asian (+0.13)

**Model 2: True Recovery**

```python
model = sm.OLS(y_true_recovery_index, X_with_const).fit()
```

**Results:**

- R² = 0.371
- Adjusted R² = 0.330
- CV R² = 0.210
- Significant predictors: pct_commercial (+0.03), pct_bachelors (+0.05), pct_white (+0.04), pct_asian (+0.04)

### 6.2 Validation

**Train-Test Split:**

```python
from sklearn.model_selection import train_test_split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
```

**Cross-Validation:**

```python
from sklearn.model_selection import cross_val_score
cv_scores = cross_val_score(model, X, y, cv=5, scoring='r2')
```

**Results (best performing model by CV R²):**
| Model | Best Model | Train R² | Test R² | CV R² (5-fold) |
|-------|------------|----------|---------|----------------|
| Bounce-back | Lasso | 0.66 | 0.78 | 0.54 |
| True Recovery | Ridge | 0.37 | 0.29 | 0.18 |

### 6.3 Multicollinearity Check (VIF)

```python
from statsmodels.stats.outliers_influence import variance_inflation_factor

def calculate_vif(X):
    vif_data = pd.DataFrame()
    vif_data["feature"] = X.columns
    vif_data["VIF"] = [variance_inflation_factor(X.values, i) for i in range(X.shape[1])]
    return vif_data
```

**Threshold:** VIF < 5 (all features passed)

### 6.4 Spatial Autocorrelation (Moran's I)

```python
from libpysal.weights import Queen
from esda.moran import Moran
from shapely import wkb

# Load data and convert geometry
analysis = pd.read_parquet('data/processed/nta_analysis_ready.parquet')
analysis['geometry'] = analysis['geometry'].apply(lambda x: wkb.loads(x))
gdf = gpd.GeoDataFrame(analysis, geometry='geometry', crs='EPSG:4326')

# Filter to NTAs with subway service
subway_gdf = gdf[gdf['recovery_index'].notna()].reset_index(drop=True)

# Create Queen contiguity weights
w = Queen.from_dataframe(subway_gdf, use_index=False)
print(f"Average neighbors: {w.mean_neighbors:.2f}")  # 3.68

# Run Moran's I
moran_recovery = Moran(subway_gdf['recovery_index'].values, w)
moran_true = Moran(subway_gdf['true_recovery_index'].values, w)
```

**Results:**

| Metric        | Moran's I | p-value | z-score | Interpretation             |
| ------------- | --------- | ------- | ------- | -------------------------- |
| Bounce-back   | 0.68      | 0.001   | 10.44   | Strong positive clustering |
| True Recovery | 0.18      | 0.006   | 2.77    | Weak positive clustering   |

**Output:** `output/tables/morans_i_results.csv`

### 6.5 Trajectory Clustering (K-means)

**Method:** K-means clustering on bounce-back and true recovery metrics

```python
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# Features: both recovery metrics
features = subway_gdf[['recovery_index', 'true_recovery_index']].copy()

# Standardize
scaler = StandardScaler()
features_scaled = scaler.fit_transform(features)

# K-means with k=4
kmeans = KMeans(n_clusters=4, random_state=42, n_init=10)
clusters = kmeans.fit_predict(features_scaled)
```

**Results:**

| Cluster | Label               | NTAs | Bounce-back | True Recovery |
| ------- | ------------------- | ---- | ----------- | ------------- |
| 1       | Near-Full Recovery  | 19   | 4.50x       | 83%           |
| 2       | Steady Recovery     | 27   | 3.17x       | 76%           |
| 3       | Lagging Recovery    | 54   | 2.25x       | 74%           |
| 4       | Struggling Recovery | 33   | 1.51x       | 61%           |

**Output:** `output/tables/nta_clusters.csv`, `output/tables/cluster_summary.csv`

---

## 7. Visualization

### 7.1 Dashboard Generation

**Script:** `src/visualization/apple_dashboard.py`

**Technologies:**

- Folium for choropleth maps
- Plotly.js for interactive charts
- Custom HTML/CSS/JS for layout and animations

**To regenerate:**

```bash
python src/visualization/apple_dashboard.py
```

**Output:** `output/figures/dashboard_apple.html`

### 7.2 Map Creation

```python
import folium
import branca.colormap as cm

def create_recovery_map(gdf, metric='recovery_index'):
    m = folium.Map(location=[40.7128, -74.0060], zoom_start=11)

    colormap = cm.LinearColormap(
        colors=['#e63946', '#f4a261', '#e9c46a', '#2a9d8f'],
        vmin=0.2, vmax=1.0
    )

    folium.GeoJson(
        gdf.__geo_interface__,
        style_function=lambda feature: {
            'fillColor': colormap(feature['properties'][metric]),
            'color': 'white',
            'weight': 1.5,
            'fillOpacity': 0.85,
        },
        highlight_function=lambda feature: {
            'fillColor': '#ffffff',
            'color': '#1a1a2e',
            'weight': 3,
            'fillOpacity': 0.3,
        }
    ).add_to(m)

    return m
```

### 7.3 Charts (Plotly)

**Ridership Timeline:**

```javascript
Plotly.newPlot("ridership-chart", [
  {
    x: dates,
    y: ridership_millions,
    type: "scatter",
    mode: "lines",
    fill: "tozeroy",
  },
]);
```

**Borough Comparison:**

```javascript
Plotly.newPlot("borough-chart", [
  {
    y: boroughs,
    x: true_recovery,
    type: "bar",
    orientation: "h",
    name: "True Recovery",
  },
  {
    y: boroughs,
    x: from_low,
    type: "bar",
    orientation: "h",
    name: "From COVID Low",
  },
]);
```

---

## 8. File Structure

```
nyc-transit-recovery/
├── data/
│   ├── raw/                          # Original/downloaded data
│   │   ├── mta_precovid_daily.csv    # Pre-COVID ridership baseline
│   │   ├── nta_demographics.csv      # NTA population data
│   │   ├── nta_employment.csv        # LEHD employment by NTA
│   │   ├── nta_predictors.csv        # PLUTO land use features
│   │   ├── ny_wac_2019.csv.gz        # Raw LEHD data (compressed)
│   │   └── pluto_nta_aggregated.csv  # Aggregated PLUTO data
│   ├── processed/                    # Analysis-ready data
│   │   ├── nta_analysis_ready.geojson    # Main analysis file
│   │   ├── nta_analysis_ready.parquet    # Same, parquet format
│   │   ├── nta_final_with_clusters.geojson
│   │   └── nta_ridership_monthly.parquet # Monthly ridership by NTA
│   └── external/                     # Reference data
│       ├── nta_boundaries_2020.geojson   # NTA polygons
│       ├── ny_tracts_2020.zip            # Census tract boundaries
│       └── tract_nta_crosswalk.csv       # Tract-to-NTA mapping
├── src/
│   ├── data/                         # Data processing scripts
│   │   ├── download_all.py           # Master download script
│   │   ├── download_mta_filtered.py  # MTA data download
│   │   ├── download_predictors.py    # PLUTO/NTA download
│   │   ├── process_data.py           # Data processing
│   │   └── process_employment.py     # LEHD processing
│   ├── analysis/                     # Analysis scripts
│   │   └── recovery_analysis.py      # Regression & validation
│   └── visualization/                # Visualization scripts
│       └── apple_dashboard.py        # Dashboard generator
├── output/
│   ├── figures/                      # Generated visualizations
│   │   ├── dashboard_apple.html      # Main dashboard
│   │   ├── recovery_map.png          # Static map
│   │   └── regression_coefficients*.png
│   └── tables/                       # Generated tables
│       ├── regression_results.csv
│       ├── regression_results_true_recovery.csv
│       ├── cluster_summary.csv
│       └── nta_clusters.csv
├── docs/                             # Documentation
│   ├── proposal.md                   # Project proposal
│   ├── final_report.md               # Final report
│   ├── references.bib                # Bibliography
│   └── technical_documentation.md    # This file
├── README.md
├── requirements.txt
└── run_pipeline.py                   # Master pipeline script
```

---

## 9. Rerunning the Pipeline

### Full Pipeline (if starting from scratch)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Download all data (takes ~30 minutes)
python src/data/download_all.py

# 3. Process employment data
python src/data/process_employment.py

# 4. Run analysis
python src/analysis/recovery_analysis.py

# 5. Generate dashboard
python src/visualization/apple_dashboard.py
```

### Quick Regeneration (data already processed)

```bash
# Just regenerate analysis and dashboard
python src/analysis/recovery_analysis.py
python src/visualization/apple_dashboard.py
```

### Individual Components

```bash
# Regenerate just the dashboard
python src/visualization/apple_dashboard.py

# Rerun just the regression analysis
python src/analysis/recovery_analysis.py

# Reprocess employment data
python src/data/process_employment.py
```

### Hosting the Dashboard

```bash
# Start local server
cd output/figures
python -m http.server 8080

# In another terminal, start ngrok tunnel
ngrok http 8080

# Share the ngrok URL with others
```

---

## Appendix: Key Numbers (Verified)

| Metric                | Value         | Source                                     |
| --------------------- | ------------- | ------------------------------------------ |
| True Recovery Rate    | 72.30%        | `gdf['true_recovery_index'].mean()`        |
| Bounce-back Rate      | 2.37x         | `gdf['recovery_index'].mean()`             |
| NTAs Below Pre-COVID  | 98% (130/133) | `(gdf['true_recovery_index'] < 1.0).sum()` |
| R² (Bounce-back)      | 0.734         | OLS full-model regression                  |
| R² (True Recovery)    | 0.373         | OLS full-model regression                  |
| CV R² (Bounce-back)   | 0.54          | 5-fold cross-validation (Lasso best)       |
| CV R² (True Recovery) | 0.18          | 5-fold cross-validation (Ridge best)       |
| Predictor Features    | 10            | PLUTO + LEHD + Census ACS                  |
| NTAs with Subway      | 133           | Spatial join count                         |
| Total NTAs            | 262           | NTA boundary file                          |
| Total Jobs (NYC)      | 4.2M          | LEHD WAC data                              |
| PLUTO Properties      | 857K          | PLUTO dataset                              |

---

_Last updated: March 19, 2026_
