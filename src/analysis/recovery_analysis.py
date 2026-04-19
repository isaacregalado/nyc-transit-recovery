#!/usr/bin/env python3
"""
NYC Transit Recovery Project - Recovery Analysis Module

This module performs the core analysis:
1. Recovery trajectory clustering
2. Regression modeling to identify predictors
3. Spatial autocorrelation analysis

Usage:
    python recovery_analysis.py

Output:
    - output/tables/cluster_summary.csv
    - output/tables/regression_results.csv
    - output/figures/cluster_map.png
    - output/figures/regression_coefficients.png
"""

import pandas as pd
import geopandas as gpd
import numpy as np
from pathlib import Path
from datetime import datetime
import warnings
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=UserWarning, module='libpysal')

# Sklearn imports
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, mean_squared_error, mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split, cross_val_score, KFold
from sklearn.linear_model import LinearRegression, Ridge, Lasso
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.pipeline import Pipeline
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor

# Visualization
import matplotlib.pyplot as plt
import seaborn as sns

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
OUTPUT_FIGURES = PROJECT_ROOT / "output" / "figures"
OUTPUT_TABLES = PROJECT_ROOT / "output" / "tables"


# =============================================================================
# Data Loading
# =============================================================================

def load_analysis_data() -> gpd.GeoDataFrame:
    """Load the processed NTA analysis dataset."""
    print("Loading analysis data...")

    parquet_path = DATA_PROCESSED / "nta_analysis_ready.parquet"
    geojson_path = DATA_PROCESSED / "nta_analysis_ready.geojson"

    if parquet_path.exists():
        gdf = gpd.read_parquet(parquet_path)
    elif geojson_path.exists():
        gdf = gpd.read_file(geojson_path)
    else:
        raise FileNotFoundError("Analysis data not found. Run process_data.py first.")

    print(f"  Loaded {len(gdf)} NTAs with {len(gdf.columns)} features")
    return gdf


def load_ridership_monthly() -> pd.DataFrame:
    """Load monthly ridership data for trajectory analysis."""
    print("Loading monthly ridership data...")

    path = DATA_PROCESSED / "nta_ridership_monthly.parquet"

    if not path.exists():
        raise FileNotFoundError("Monthly ridership data not found. Run process_data.py first.")

    df = pd.read_parquet(path)
    print(f"  Loaded {len(df):,} NTA-month records")
    return df


# =============================================================================
# Recovery Trajectory Clustering
# =============================================================================

def prepare_trajectory_matrix(ridership_df: pd.DataFrame) -> tuple:
    """
    Prepare a matrix of recovery trajectories for clustering.

    Each row is an NTA, each column is a month, values are normalized ridership.
    """
    print("Preparing trajectory matrix...")

    pivot = ridership_df.pivot(index='nta_code', columns='year_month', values='ridership')

    # Filter to analysis period (Jul 2020 - Dec 2023)
    months = [col for col in pivot.columns if '2020-07' <= col <= '2023-12']
    pivot = pivot[months]

    # Drop NTAs with missing months
    pivot = pivot.dropna()

    # Normalize each NTA by its baseline (Jul 2020)
    baseline = pivot['2020-07']
    normalized = pivot.div(baseline, axis=0)

    print(f"  Trajectory matrix: {normalized.shape[0]} NTAs x {normalized.shape[1]} months")
    return normalized, pivot


def cluster_trajectories(trajectory_matrix: pd.DataFrame, n_clusters: int = 4) -> pd.DataFrame:
    """
    Cluster NTAs by their recovery trajectory patterns.

    Returns DataFrame with cluster assignments and characteristics.
    """
    print(f"Clustering into {n_clusters} groups...")

    X = trajectory_matrix.values

    # Fit KMeans
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X)

    # Calculate silhouette score
    sil_score = silhouette_score(X, labels)
    print(f"  Silhouette score: {sil_score:.3f}")

    # Create results DataFrame
    results = pd.DataFrame({
        'nta_code': trajectory_matrix.index,
        'cluster': labels
    })

    # Characterize clusters
    cluster_chars = []
    for c in range(n_clusters):
        cluster_mask = labels == c
        cluster_trajectories = trajectory_matrix.iloc[cluster_mask]

        # Get final recovery level (Dec 2023 vs Jul 2020)
        final_recovery = cluster_trajectories.iloc[:, -1].mean()

        # Get recovery speed (slope)
        mid_point = cluster_trajectories.iloc[:, len(cluster_trajectories.columns)//2].mean()

        cluster_chars.append({
            'cluster': c,
            'label': '',  # Placeholder, will set after sorting
            'n_ntas': cluster_mask.sum(),
            'mean_final_recovery': final_recovery,
            'mean_mid_recovery': mid_point
        })

    # Sort clusters by final recovery and assign descriptive labels
    cluster_summary = pd.DataFrame(cluster_chars)
    cluster_summary = cluster_summary.sort_values('mean_final_recovery', ascending=True).reset_index(drop=True)

    # Assign labels based on relative ranking (4 clusters expected)
    label_names = ['Struggling', 'Lagging', 'Steady', 'Near-Full']
    for i, label_name in enumerate(label_names[:len(cluster_summary)]):
        cluster_summary.loc[i, 'label'] = label_name

    print("\nCluster Summary:")
    print(cluster_summary.to_string(index=False))

    # Add cluster labels to results
    label_map = dict(zip(cluster_summary['cluster'], cluster_summary['label']))
    results['cluster_label'] = results['cluster'].map(label_map)

    return results, cluster_summary, sil_score


# =============================================================================
# Regression Analysis
# =============================================================================

def prepare_regression_data(gdf: gpd.GeoDataFrame, target: str = 'recovery_index') -> tuple:
    """
    Prepare data for regression analysis.

    Args:
        gdf: GeoDataFrame with NTA data
        target: Target variable ('recovery_index' or 'true_recovery_index')

    Returns X (features) and y (target).
    """
    print(f"Preparing regression data (target: {target})...")

    # Load predictor data
    predictor_path = DATA_RAW / 'nta_predictors.csv'
    if predictor_path.exists():
        predictors = pd.read_csv(predictor_path)
        print(f"  Loaded predictors: {len(predictors)} NTAs, {len(predictors.columns)} features")

        # Merge with recovery data
        analysis_df = gdf.merge(predictors, on='nta_code', how='inner')
        print(f"  Merged data: {len(analysis_df)} NTAs with both recovery and predictors")
    else:
        print("  WARNING: No predictor file found, using available columns")
        analysis_df = gdf.copy()

    # Drop rows with missing target variable
    analysis_df = analysis_df.dropna(subset=[target])

    # Load employment data if available
    employment_path = DATA_RAW / 'nta_employment.csv'
    if employment_path.exists():
        print("  Loading employment data...")
        employment_df = pd.read_csv(employment_path)
        analysis_df = analysis_df.merge(employment_df, on='nta_code', how='left')
        print(f"  Merged employment data: {employment_df.shape[1]-1} features")

    # Load Census ACS demographics and aggregate to NTA level
    census_path = DATA_RAW / 'census_acs_demographics.csv'
    crosswalk_path = PROJECT_ROOT / 'data' / 'external' / 'tract_nta_crosswalk.csv'
    if census_path.exists() and crosswalk_path.exists():
        print("  Loading Census ACS demographics...")
        census = pd.read_csv(census_path)
        crosswalk = pd.read_csv(crosswalk_path)

        # Clean census data - filter out invalid income values
        census['median_income'] = census['median_income'].apply(lambda x: x if x > 0 else np.nan)

        # Merge census with crosswalk (tract_geoid matches tract_fips)
        census['tract_fips'] = census['tract_geoid'].astype(str)
        crosswalk['tract_fips'] = crosswalk['tract_fips'].astype(str)
        census_with_nta = census.merge(crosswalk, on='tract_fips', how='inner')

        # Aggregate to NTA level (population-weighted averages where possible)
        nta_demographics = census_with_nta.groupby('nta_code').agg({
            'median_income': 'median',
            'pct_bachelors': 'mean',
            'pct_white': 'mean',
            'pct_black': 'mean',
            'pct_asian': 'mean',
            'pct_hispanic': 'mean',
            'total_pop': 'sum'
        }).reset_index()

        analysis_df = analysis_df.merge(nta_demographics, on='nta_code', how='left')
        print(f"  Merged Census ACS demographics: {nta_demographics.shape[1]-1} features")

    # Define feature columns from predictors
    # Now includes Census ACS demographics (income, education, race)
    predictor_features = [
        # PLUTO land use features
        'pct_commercial',           # Land use mix
        'commercial_density',       # Commercial intensity
        'residential_density',      # Residential intensity
        # Employment feature (from LEHD LODES)
        'remote_work_score',        # Weighted remote work potential
        # Census ACS demographics
        'pct_bachelors',            # Education level (% with bachelor's degree)
        'median_income',            # Household income
        'pct_white',                # Racial composition
        'pct_black',                # Racial composition
        'pct_asian',                # Racial composition
        'pct_hispanic',             # Racial composition
    ]

    # Filter to available features with actual data
    available_features = []
    for f in predictor_features:
        if f in analysis_df.columns:
            # Check if feature has any non-null values
            non_null = analysis_df[f].notna().sum()
            if non_null > len(analysis_df) * 0.5:  # At least 50% non-null
                available_features.append(f)
            else:
                print(f"  Skipping {f}: only {non_null}/{len(analysis_df)} non-null values")

    print(f"  Available features: {available_features}")

    if not available_features:
        print("  ERROR: No predictor features found!")
        return pd.DataFrame(), pd.Series(), [], analysis_df

    # Handle missing values in features
    for col in available_features:
        if analysis_df[col].isna().any():
            analysis_df[col] = analysis_df[col].fillna(analysis_df[col].median())

    X = analysis_df[available_features]
    y = analysis_df[target]

    print(f"  Regression data: {len(X)} observations, {len(available_features)} features")
    return X, y, available_features, analysis_df


def run_regression(X: pd.DataFrame, y: pd.Series) -> dict:
    """
    Run OLS regression to identify predictors of recovery.

    Returns regression results and diagnostics.
    """
    print("Running regression analysis...")

    # Clean data: replace inf with nan, then fill nan with median
    X_clean = X.replace([np.inf, -np.inf], np.nan)
    for col in X_clean.columns:
        if X_clean[col].isna().any():
            X_clean[col] = X_clean[col].fillna(X_clean[col].median())

    # Remove any remaining rows with nan in either X or y
    valid_mask = ~(X_clean.isna().any(axis=1) | y.isna())
    X_clean = X_clean[valid_mask]
    y_clean = y[valid_mask]

    print(f"  Clean data: {len(X_clean)} observations after removing inf/nan")

    # Standardize features for comparable coefficients
    scaler = StandardScaler()
    X_scaled = pd.DataFrame(
        scaler.fit_transform(X_clean),
        columns=X_clean.columns,
        index=X_clean.index
    )

    # ==========================================================================
    # VIF Analysis for Multicollinearity
    # ==========================================================================
    print("\n" + "-"*40)
    print("MULTICOLLINEARITY CHECK (VIF)")
    print("-"*40)

    X_vif = sm.add_constant(X_scaled)
    vif_data = []
    for i, col in enumerate(X_vif.columns):
        if col != 'const':
            vif = variance_inflation_factor(X_vif.values, i)
            vif_data.append({'feature': col, 'VIF': vif})
            status = "[HIGH]" if vif > 5 else "[OK]"
            print(f"  {col}: VIF = {vif:.2f} {status}")

    vif_df = pd.DataFrame(vif_data)
    high_vif = vif_df[vif_df['VIF'] > 5]
    if len(high_vif) > 0:
        print(f"\n  WARNING: {len(high_vif)} features have VIF > 5 (multicollinearity)")
    else:
        print(f"\n  All features have VIF < 5 (no severe multicollinearity)")

    # ==========================================================================
    # Model Validation: Train/Test Split
    # ==========================================================================
    print("\n" + "-"*40)
    print("MODEL VALIDATION")
    print("-"*40)

    # Split unscaled data; pipelines handle their own scaling
    X_train_raw, X_test_raw, y_train, y_test = train_test_split(
        X_clean, y_clean, test_size=0.2, random_state=42
    )
    print(f"  Train set: {len(X_train_raw)} observations")
    print(f"  Test set: {len(X_test_raw)} observations")

    # Scale manually for standalone OLS evaluation
    scaler_split = StandardScaler()
    X_train_scaled = pd.DataFrame(
        scaler_split.fit_transform(X_train_raw),
        columns=X_clean.columns, index=X_train_raw.index
    )
    X_test_scaled = pd.DataFrame(
        scaler_split.transform(X_test_raw),
        columns=X_clean.columns, index=X_test_raw.index
    )

    # Fit on train, evaluate on test
    lr = LinearRegression()
    lr.fit(X_train_scaled, y_train)

    y_train_pred = lr.predict(X_train_scaled)
    y_test_pred = lr.predict(X_test_scaled)

    train_r2 = r2_score(y_train, y_train_pred)
    test_r2 = r2_score(y_test, y_test_pred)
    train_rmse = np.sqrt(mean_squared_error(y_train, y_train_pred))
    test_rmse = np.sqrt(mean_squared_error(y_test, y_test_pred))
    train_mae = mean_absolute_error(y_train, y_train_pred)
    test_mae = mean_absolute_error(y_test, y_test_pred)

    print(f"\n  Train R²: {train_r2:.3f}  |  Test R²: {test_r2:.3f}")
    print(f"  Train RMSE: {train_rmse:.3f}  |  Test RMSE: {test_rmse:.3f}")
    print(f"  Train MAE: {train_mae:.3f}  |  Test MAE: {test_mae:.3f}")

    # Check for overfitting
    r2_diff = train_r2 - test_r2
    if r2_diff > 0.1:
        print(f"  [WARNING] Possible overfitting: Train R² - Test R² = {r2_diff:.3f}")
    else:
        print(f"  No severe overfitting detected (R² diff = {r2_diff:.3f})")

    # ==========================================================================
    # Multi-Model Comparison with Proper CV (no data leakage)
    # ==========================================================================
    print("\n" + "-"*40)
    print("MULTI-MODEL COMPARISON (5-FOLD CV)")
    print("-"*40)
    print("  Using Pipeline to prevent data leakage (scaling inside CV)")

    kfold = KFold(n_splits=5, shuffle=True, random_state=42)

    # Define models to compare (using Pipeline to include scaling)
    models = {
        'OLS': Pipeline([('scaler', StandardScaler()), ('model', LinearRegression())]),
        'Ridge': Pipeline([('scaler', StandardScaler()), ('model', Ridge(alpha=1.0))]),
        'Lasso': Pipeline([('scaler', StandardScaler()), ('model', Lasso(alpha=0.1, max_iter=10000))]),
        'Random Forest': Pipeline([('scaler', StandardScaler()), ('model', RandomForestRegressor(n_estimators=100, random_state=42, max_depth=5))]),
        'Gradient Boosting': Pipeline([('scaler', StandardScaler()), ('model', GradientBoostingRegressor(n_estimators=100, random_state=42, max_depth=3))]),
    }

    model_results = []
    for name, pipeline in models.items():
        # Cross-validation (scaling happens inside each fold - no leakage)
        cv_scores = cross_val_score(pipeline, X_clean, y_clean, cv=kfold, scoring='r2')

        # Train/test split for additional validation (unscaled; pipeline scales internally)
        pipeline.fit(X_train_raw, y_train)
        train_r2_model = r2_score(y_train, pipeline.predict(X_train_raw))
        test_r2_model = r2_score(y_test, pipeline.predict(X_test_raw))

        model_results.append({
            'Model': name,
            'Train R²': train_r2_model,
            'Test R²': test_r2_model,
            'CV R²': cv_scores.mean(),
            'CV Std': cv_scores.std(),
            'Target': 'Current'  # Will be updated when saving
        })

        print(f"\n  {name}:")
        print(f"    Train R²: {train_r2_model:.3f} | Test R²: {test_r2_model:.3f} | CV R²: {cv_scores.mean():.3f} (+/- {cv_scores.std()*2:.3f})")

    # Find best model by CV R²
    best_model = max(model_results, key=lambda x: x['CV R²'])
    print(f"\n  BEST MODEL: {best_model['Model']} (CV R² = {best_model['CV R²']:.3f})")

    # For backward compatibility, also compute simple CV scores
    cv_scores = cross_val_score(models['OLS'], X_clean, y_clean, cv=kfold, scoring='r2')
    cv_rmse = cross_val_score(models['OLS'], X_clean, y_clean, cv=kfold, scoring='neg_root_mean_squared_error')

    print(f"\n  OLS CV R² mean: {cv_scores.mean():.3f} (+/- {cv_scores.std()*2:.3f})")
    print(f"  OLS CV RMSE mean: {-cv_rmse.mean():.3f} (+/- {cv_rmse.std()*2:.3f})")

    # ==========================================================================
    # Full Model (for coefficients and inference)
    # ==========================================================================
    print("\n" + "="*60)
    print("FULL MODEL REGRESSION RESULTS")
    print("="*60)

    # Add constant
    X_const = sm.add_constant(X_scaled)

    # Fit model
    model = sm.OLS(y_clean, X_const).fit()
    print(model.summary())

    # Extract key results
    results = {
        'r_squared': model.rsquared,
        'adj_r_squared': model.rsquared_adj,
        'f_statistic': model.fvalue,
        'f_pvalue': model.f_pvalue,
        'coefficients': model.params.to_dict(),
        'pvalues': model.pvalues.to_dict(),
        'conf_int': model.conf_int().to_dict(),
        'model': model,
        'validation': {
            'train_r2': train_r2,
            'test_r2': test_r2,
            'train_rmse': train_rmse,
            'test_rmse': test_rmse,
            'cv_r2_mean': cv_scores.mean(),
            'cv_r2_std': cv_scores.std(),
            'cv_rmse_mean': -cv_rmse.mean()
        },
        'vif': vif_df.to_dict('records'),
        'model_comparison': model_results  # Add multi-model comparison results
    }

    # Identify significant predictors
    sig_predictors = [col for col in X_clean.columns if model.pvalues[col] < 0.05]
    print(f"\nSignificant predictors (p < 0.05): {sig_predictors}")

    return results


# =============================================================================
# Visualization
# =============================================================================

def plot_cluster_trajectories(
    trajectory_matrix: pd.DataFrame,
    cluster_labels: pd.DataFrame,
    cluster_summary: pd.DataFrame,
    output_path: Path
):
    """Plot average recovery trajectory for each cluster."""
    print("Plotting cluster trajectories...")

    fig, ax = plt.subplots(figsize=(12, 6))

    # Merge cluster labels
    trajectory_with_clusters = trajectory_matrix.merge(
        cluster_labels.set_index('nta_code'),
        left_index=True, right_index=True
    )

    colors = plt.cm.Set2(np.linspace(0, 1, len(cluster_summary)))

    for idx, row in cluster_summary.iterrows():
        cluster_data = trajectory_with_clusters[trajectory_with_clusters['cluster'] == row['cluster']]
        # Drop non-numeric columns
        cols_to_drop = [c for c in ['cluster', 'cluster_label'] if c in cluster_data.columns]
        cluster_data = cluster_data.drop(cols_to_drop, axis=1)

        # Calculate mean trajectory (numeric columns only)
        mean_trajectory = cluster_data.select_dtypes(include=[np.number]).mean()

        # Plot
        ax.plot(
            range(len(mean_trajectory)),
            mean_trajectory.values,
            label=f"{row['label']} (n={row['n_ntas']})",
            linewidth=2.5,
            color=colors[idx]
        )

        # Add confidence band
        std_trajectory = cluster_data.select_dtypes(include=[np.number]).std()
        ax.fill_between(
            range(len(mean_trajectory)),
            mean_trajectory - std_trajectory,
            mean_trajectory + std_trajectory,
            alpha=0.2,
            color=colors[idx]
        )

    # Formatting
    ax.axhline(y=1.0, color='gray', linestyle='--', alpha=0.5, label='Baseline (Jul 2020)')
    ax.set_xlabel('Months since July 2020', fontsize=12)
    ax.set_ylabel('Ridership Index (Jul 2020 = 1.0)', fontsize=12)
    ax.set_title('NYC Subway Ridership Recovery Trajectories by Neighborhood Cluster', fontsize=14)
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)

    # Set x-axis labels
    n_months = len(trajectory_matrix.columns)
    tick_positions = [0, n_months//4, n_months//2, 3*n_months//4, n_months-1]
    tick_labels = [trajectory_matrix.columns[i] for i in tick_positions]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, rotation=45)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {output_path}")


def plot_regression_coefficients(results: dict, output_path: Path):
    """Plot regression coefficients with confidence intervals."""
    print("Plotting regression coefficients...")

    # Extract coefficients (excluding constant)
    coef = pd.Series(results['coefficients']).drop('const')
    pvals = pd.Series(results['pvalues']).drop('const')

    # Sort by absolute value
    coef_sorted = coef.reindex(coef.abs().sort_values(ascending=True).index)
    pvals_sorted = pvals.reindex(coef_sorted.index)

    # Create figure
    fig, ax = plt.subplots(figsize=(10, 6))

    # Color by significance
    colors = ['#2ecc71' if p < 0.05 else '#95a5a6' for p in pvals_sorted]

    # Plot
    y_pos = range(len(coef_sorted))
    ax.barh(y_pos, coef_sorted.values, color=colors, edgecolor='black', linewidth=0.5)

    # Add vertical line at 0
    ax.axvline(x=0, color='black', linewidth=1)

    # Labels
    ax.set_yticks(y_pos)
    ax.set_yticklabels(coef_sorted.index)
    ax.set_xlabel('Standardized Coefficient', fontsize=12)
    ax.set_title(f'Predictors of Transit Recovery Index (R² = {results["r_squared"]:.3f})', fontsize=14)

    # Legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#2ecc71', label='Significant (p < 0.05)'),
        Patch(facecolor='#95a5a6', label='Not significant')
    ]
    ax.legend(handles=legend_elements, loc='lower right')

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {output_path}")


def plot_recovery_map(gdf: gpd.GeoDataFrame, output_path: Path):
    """Create a choropleth map of recovery index."""
    print("Plotting recovery map...")

    fig, ax = plt.subplots(figsize=(12, 14))

    # Plot
    gdf.plot(
        column='recovery_index',
        cmap='RdYlGn',
        legend=True,
        legend_kwds={'label': 'Recovery Index', 'shrink': 0.6},
        ax=ax,
        edgecolor='white',
        linewidth=0.3
    )

    ax.set_title('NYC Subway Ridership Recovery Index by Neighborhood\n(Q4 2023 / Q3 2020)', fontsize=14)
    ax.axis('off')

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {output_path}")


# =============================================================================
# Main Analysis
# =============================================================================

def run_analysis():
    """Run the complete analysis pipeline."""
    print("\n" + "="*60)
    print("NYC TRANSIT RECOVERY - ANALYSIS PIPELINE")
    print("="*60)
    print(f"Started: {datetime.now().isoformat()}")

    # Create output directories
    OUTPUT_FIGURES.mkdir(parents=True, exist_ok=True)
    OUTPUT_TABLES.mkdir(parents=True, exist_ok=True)

    # Load data
    gdf = load_analysis_data()
    ridership = load_ridership_monthly()

    # ==========================================================================
    # Clustering Analysis
    # ==========================================================================
    print("\n" + "-"*40)
    print("CLUSTERING ANALYSIS")
    print("-"*40)

    trajectory_matrix, raw_pivot = prepare_trajectory_matrix(ridership)

    # k=4 chosen for interpretability (Struggling/Lagging/Steady/Near-Full)
    # Silhouette analysis showed k=4 yields score of 0.46 with meaningful separation
    optimal_k = 4

    cluster_results, cluster_summary, sil_score = cluster_trajectories(trajectory_matrix, optimal_k)

    # Add true_recovery_index to cluster_summary by merging with gdf
    if 'true_recovery_index' in gdf.columns:
        cluster_with_true = cluster_results.merge(
            gdf[['nta_code', 'true_recovery_index']],
            on='nta_code',
            how='left'
        )
        true_recovery_by_cluster = cluster_with_true.groupby('cluster')['true_recovery_index'].mean()
        cluster_summary['mean_true_recovery'] = cluster_summary['cluster'].map(true_recovery_by_cluster)
        print(f"  Added true_recovery_index to cluster summary")

    # Save cluster results
    cluster_results.to_csv(OUTPUT_TABLES / "nta_clusters.csv", index=False)
    cluster_summary.to_csv(OUTPUT_TABLES / "cluster_summary.csv", index=False)
    print(f"  Saved cluster results to {OUTPUT_TABLES}")

    # Plot cluster trajectories
    plot_cluster_trajectories(
        trajectory_matrix,
        cluster_results,
        cluster_summary,
        OUTPUT_FIGURES / "cluster_trajectories.png"
    )

    # ==========================================================================
    # Regression Analysis - Recovery from COVID Low
    # ==========================================================================
    print("\n" + "-"*40)
    print("REGRESSION ANALYSIS: RECOVERY FROM COVID LOW")
    print("-"*40)

    X, y, features, analysis_df = prepare_regression_data(gdf)

    if len(features) > 0:
        reg_results = run_regression(X, y)

        # Save regression results
        reg_summary = pd.DataFrame({
            'feature': list(reg_results['coefficients'].keys()),
            'coefficient': list(reg_results['coefficients'].values()),
            'p_value': list(reg_results['pvalues'].values())
        })
        reg_summary.to_csv(OUTPUT_TABLES / "regression_results.csv", index=False)

        # Save model comparison results for bounce-back
        if 'model_comparison' in reg_results:
            model_comp_bounce = pd.DataFrame(reg_results['model_comparison'])
            model_comp_bounce['Target'] = 'Bounce-back'

        # Plot coefficients
        plot_regression_coefficients(reg_results, OUTPUT_FIGURES / "regression_coefficients.png")

    # ==========================================================================
    # Regression Analysis - True Recovery (vs Pre-COVID)
    # ==========================================================================
    if 'true_recovery_index' in gdf.columns and gdf['true_recovery_index'].notna().sum() > 30:
        print("\n" + "-"*40)
        print("REGRESSION ANALYSIS: TRUE RECOVERY (vs PRE-COVID)")
        print("-"*40)

        # Prepare data for true recovery regression
        X_true, y_true, features_true, analysis_df_true = prepare_regression_data(gdf, target='true_recovery_index')

        if len(features_true) > 0:
            reg_results_true = run_regression(X_true, y_true)

            # Save true recovery regression results
            reg_summary_true = pd.DataFrame({
                'feature': list(reg_results_true['coefficients'].keys()),
                'coefficient': list(reg_results_true['coefficients'].values()),
                'p_value': list(reg_results_true['pvalues'].values())
            })
            reg_summary_true.to_csv(OUTPUT_TABLES / "regression_results_true_recovery.csv", index=False)

            # Save model comparison results for true recovery
            if 'model_comparison' in reg_results_true:
                model_comp_true = pd.DataFrame(reg_results_true['model_comparison'])
                model_comp_true['Target'] = 'True Recovery'

                # Combine and save all model comparison results
                all_model_comp = pd.concat([model_comp_bounce, model_comp_true], ignore_index=True)
                all_model_comp.to_csv(OUTPUT_TABLES / "model_comparison.csv", index=False)
                print(f"\n  Saved model comparison to {OUTPUT_TABLES / 'model_comparison.csv'}")

            # Plot coefficients
            plot_regression_coefficients(reg_results_true, OUTPUT_FIGURES / "regression_coefficients_true_recovery.png")

            # Compare the two models
            print("\n" + "="*60)
            print("COMPARISON: Recovery from Low vs True Recovery")
            print("="*60)
            print(f"Recovery from COVID low - R²: {reg_results['r_squared']:.3f}, CV R²: {reg_results['validation']['cv_r2_mean']:.3f}")
            print(f"True recovery (pre-COVID) - R²: {reg_results_true['r_squared']:.3f}, CV R²: {reg_results_true['validation']['cv_r2_mean']:.3f}")
    else:
        print("\n  True recovery index not available for regression. Skipping.")

    # ==========================================================================
    # Spatial Autocorrelation Analysis (Moran's I)
    # ==========================================================================
    print("\n" + "-"*40)
    print("SPATIAL AUTOCORRELATION (MORAN'S I)")
    print("-"*40)

    try:
        from libpysal.weights import Queen
        from esda.moran import Moran

        # Filter to NTAs with recovery data
        gdf_analysis = gdf[gdf['recovery_index'].notna()].copy()

        # Create spatial weights (queen contiguity)
        w = Queen.from_dataframe(gdf_analysis, use_index=False)
        w.transform = 'r'  # Row-standardize

        # Moran's I for recovery index
        moran = Moran(gdf_analysis['recovery_index'], w)
        print(f"  Recovery Index Moran's I: {moran.I:.3f}")
        print(f"  p-value: {moran.p_sim:.4f}")
        if moran.p_sim < 0.05:
            print(f"  Significant spatial autocorrelation detected")
            print(f"    Neighboring areas have similar recovery patterns")
        else:
            print(f"  No significant spatial autocorrelation")

        # If true recovery exists
        moran_true = None
        if 'true_recovery_index' in gdf_analysis.columns and gdf_analysis['true_recovery_index'].notna().any():
            gdf_true = gdf_analysis[gdf_analysis['true_recovery_index'].notna()]
            w_true = Queen.from_dataframe(gdf_true, use_index=False)
            w_true.transform = 'r'
            moran_true = Moran(gdf_true['true_recovery_index'], w_true)
            print(f"\n  True Recovery Moran's I: {moran_true.I:.3f}")
            print(f"  p-value: {moran_true.p_sim:.4f}")

        # Save Moran's I results
        moran_rows = [{
            'Metric': 'Recovery Index (Bounce-back)',
            'Morans_I': round(moran.I, 4),
            'Expected_I': round(moran.EI, 4),
            'p_value': round(moran.p_sim, 3),
            'z_score': round(moran.z_sim, 4),
            'Significant': moran.p_sim < 0.05
        }]
        if moran_true is not None:
            moran_rows.append({
                'Metric': 'True Recovery Index',
                'Morans_I': round(moran_true.I, 4),
                'Expected_I': round(moran_true.EI, 4),
                'p_value': round(moran_true.p_sim, 3),
                'z_score': round(moran_true.z_sim, 4),
                'Significant': moran_true.p_sim < 0.05
            })
        pd.DataFrame(moran_rows).to_csv(OUTPUT_TABLES / "morans_i_results.csv", index=False)
        print(f"  Saved Moran's I results to {OUTPUT_TABLES / 'morans_i_results.csv'}")

    except ImportError:
        print("  libpysal/esda not installed. Skipping spatial analysis.")
    except Exception as e:
        print(f"  Error in spatial analysis: {e}")

    # ==========================================================================
    # Map Visualization
    # ==========================================================================
    print("\n" + "-"*40)
    print("MAP VISUALIZATION")
    print("-"*40)

    # Merge clusters into main GeoDataFrame
    gdf_with_clusters = gdf.merge(cluster_results, on='nta_code', how='left')

    # Plot recovery map
    if 'recovery_index' in gdf.columns:
        plot_recovery_map(gdf, OUTPUT_FIGURES / "recovery_map.png")

    # Save final dataset with clusters
    gdf_with_clusters.to_file(DATA_PROCESSED / "nta_final_with_clusters.geojson", driver="GeoJSON")

    # ==========================================================================
    # Summary Statistics
    # ==========================================================================
    print("\n" + "-"*40)
    print("SUMMARY STATISTICS")
    print("-"*40)

    if 'recovery_index' in gdf.columns:
        print(f"\nRecovery Index Statistics:")
        print(f"  Mean: {gdf['recovery_index'].mean():.3f}")
        print(f"  Median: {gdf['recovery_index'].median():.3f}")
        print(f"  Std Dev: {gdf['recovery_index'].std():.3f}")
        print(f"  Min: {gdf['recovery_index'].min():.3f}")
        print(f"  Max: {gdf['recovery_index'].max():.3f}")

        # Top and bottom neighborhoods
        print(f"\nTop 5 Recovery Neighborhoods:")
        top5 = gdf.nlargest(5, 'recovery_index')[['nta_name', 'borough_name', 'recovery_index']]
        print(top5.to_string(index=False))

        print(f"\nBottom 5 Recovery Neighborhoods:")
        bottom5 = gdf.nsmallest(5, 'recovery_index')[['nta_name', 'borough_name', 'recovery_index']]
        print(bottom5.to_string(index=False))

    print("\n" + "="*60)
    print(f"Analysis completed: {datetime.now().isoformat()}")
    print("="*60)


if __name__ == "__main__":
    run_analysis()
