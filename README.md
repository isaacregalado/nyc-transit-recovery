# NYC Transit Recovery Analysis

**CSE 6242 - Data and Visual Analytics | Spring 2026**
**Georgia Institute of Technology**

## Team Members

**Isaac Regalado** | **Elias Dematis** | **Dami Awosika** | **David Mongeau**

## Project Overview

This project analyzes NYC subway ridership recovery patterns post-COVID and identifies neighborhood-level economic and demographic factors that predict recovery speed. We found that **"bouncing back" and "truly recovering" are fundamentally different phenomena.**

### Key Findings

| Metric                | Value    | Meaning                                      |
| --------------------- | -------- | -------------------------------------------- |
| True Recovery         | **72%**  | NYC subway ridership vs. pre-COVID levels    |
| Bounce-back           | **2.4x** | Recovery from COVID lows (misleading metric) |
| CV R² (Bounce-back)   | **0.54** | Demographics + land use explain bounce-back  |
| CV R² (True Recovery) | **0.18** | But NOT true recovery (5 models tested)      |

### Research Question

> What neighborhood-level economic and demographic factors predict the speed and magnitude of post-COVID subway ridership recovery across NYC's 133 subway-served neighborhoods?

### Analysis Window

**January 2020 - December 2023** (Pre-COVID baseline through recovery)

## Live Demo

**[Interactive Dashboard & Poster](https://isaacregalado.github.io/nyc-transit-recovery/)**

## Project Structure

```
nyc-transit-recovery/
├── data/
│   ├── raw/                 # Original downloaded data
│   ├── processed/           # Cleaned, transformed data
│   └── external/            # Reference data (NTA boundaries, etc.)
├── src/
│   ├── data/                # Data download and processing scripts
│   ├── analysis/            # Analysis, modeling, and robustness experiments
│   └── visualization/       # Dashboard generation code
├── docs/                    # Final report, dashboard, and poster (GitHub Pages)
└── output/
    ├── figures/             # Generated visualizations
    └── tables/              # Generated tables and results
```

## Datasets

| Dataset                     | Source        | Records      | Use                      |
| --------------------------- | ------------- | ------------ | ------------------------ |
| MTA Subway Hourly Ridership | data.ny.gov   | 270M+ rides  | Recovery metrics         |
| PLUTO Property Data         | NYC Planning  | 857K lots    | Land use characteristics |
| LEHD Employment (WAC)       | Census LEHD   | 4.2M jobs    | Remote work potential    |
| Census ACS Demographics     | Census Bureau | 2,327 tracts | Income, education, race  |
| NTA Boundaries              | NYC Open Data | 262 NTAs     | Spatial aggregation      |

## Methodology

1. **Data Integration**: Join all datasets to 262 Neighborhood Tabulation Areas (NTAs)
2. **Dual Recovery Metrics**:
   - Bounce-back: Q4 2023 / Q3 2020 (growth from COVID low)
   - True Recovery: Q4 2023 / Jan-Feb 2020 (return to pre-COVID baseline)
3. **Remote Work Scoring**: Classify 4.2M jobs by industry remote work potential
4. **Multi-Model Regression**: OLS, Ridge, Lasso, Random Forest, Gradient Boosting with 5-fold CV
5. **Clustering**: K-means (K=4) identifying distinct recovery trajectories
6. **Spatial Analysis**: Moran's I confirming spatial autocorrelation patterns
7. **Robustness**: Temporal sensitivity, cluster stability, model diagnostics, feature ablation
8. **Visualization**: Interactive dashboard with scroll-snap storytelling

## Setup

```bash
pip install -r requirements.txt
python run_pipeline.py
```

## Deliverables

| Deliverable           | Location                 |
| --------------------- | ------------------------ |
| Final Report          | `docs/final_report.md`   |
| Interactive Dashboard | `docs/dashboard.html`    |
| Poster                | `docs/poster.html`       |
| Analysis Code         | `src/`                   |

## License

This project is for academic purposes only (Georgia Tech CSE 6242).
