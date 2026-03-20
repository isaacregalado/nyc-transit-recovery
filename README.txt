DESCRIPTION
===========
NYC Transit Recovery Analysis - CSE 6242 Team 002

This project analyzes NYC subway ridership recovery patterns post-COVID,
integrating MTA ridership data with land use (PLUTO), employment (Census LEHD),
and demographic (Census ACS) datasets across 133 subway-served neighborhoods.

Key finding: NYC subway ridership has only recovered to 72% of pre-COVID levels
despite appearing to grow 2.4x from the pandemic trough. "Bouncing back" and
"truly recovering" are fundamentally different phenomena - land use and
demographics explain 54% of bounce-back variance but only 18% of true recovery.

The project includes:
- Automated data pipeline (download, process, analyze)
- Dual recovery metrics (bounce-back vs. true recovery)
- Multi-model regression (OLS, Ridge, Lasso, RF, GBM with 5-fold CV)
- K-means clustering of recovery trajectories
- Spatial autocorrelation analysis (Moran's I)
- Interactive scroll-snap storytelling dashboard

INSTALLATION
============
Requirements: Python 3.8+

1. Install dependencies:
   pip install -r requirements.txt

2. Download data (automated):
   python src/data/download_all.py

   Note: The MTA ridership dataset is ~500MB. LEHD and Census ACS data
   require separate download (see src/data/download_predictors.py).

   Pre-computed processed data is included in data/processed/ for
   convenience (nta_analysis_ready.parquet, nta_ridership_monthly.parquet).

EXECUTION
=========
Option 1: Run full pipeline
   python run_pipeline.py

   This will:
   1. Download data (if not present)
   2. Process and clean data
   3. Run recovery analysis (clustering + regression)
   4. Generate the interactive dashboard

Option 2: Run individual steps
   python src/data/process_data.py          # Process raw data
   python src/data/process_employment.py    # Process LEHD employment data
   python src/analysis/recovery_analysis.py # Run analysis
   python src/visualization/apple_dashboard.py  # Generate dashboard

Option 3: View dashboard only
   python run_pipeline.py --dashboard-only
   Then open output/figures/dashboard_apple.html in a web browser.

Output files are saved to:
   output/tables/  - CSV files with regression results, cluster assignments
   output/figures/ - PNG visualizations and HTML dashboard
