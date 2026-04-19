#!/usr/bin/env python3
"""
Section 5 Experiments: Robustness and Validation
Implements experiments 5.1–5.4 from the progress report.

Usage:
    python robustness_experiments.py
"""

import pandas as pd
import geopandas as gpd
import numpy as np
from pathlib import Path
from scipy.stats import spearmanr, shapiro
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import KFold, cross_val_score
from sklearn.linear_model import Ridge, Lasso
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, calinski_harabasz_score, adjusted_rand_score
from sklearn.inspection import permutation_importance
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
import statsmodels.api as sm
from statsmodels.stats.diagnostic import het_breuschpagan
from statsmodels.stats.outliers_influence import variance_inflation_factor
import warnings
warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_EXTERNAL = PROJECT_ROOT / "data" / "external"
OUTPUT_TABLES = PROJECT_ROOT / "output" / "tables"
OUTPUT_TABLES.mkdir(parents=True, exist_ok=True)


# =============================================================================
# Data Loading
# =============================================================================

def load_data():
    """Load analysis-ready data and monthly ridership."""
    gdf = gpd.read_parquet(DATA_PROCESSED / "nta_analysis_ready.parquet")
    ridership = pd.read_parquet(DATA_PROCESSED / "nta_ridership_monthly.parquet")
    return gdf, ridership


def load_precovid_nta_ridership():
    """Load pre-COVID daily data and aggregate to NTA-monthly."""
    precovid_path = DATA_RAW / 'mta_precovid_daily.csv'
    if not precovid_path.exists():
        return None

    precovid = pd.read_csv(precovid_path)
    precovid['date'] = pd.to_datetime(precovid['date'])
    precovid['month'] = precovid['date'].dt.month

    # Load station-to-NTA mapping from NTA boundaries
    nta_gdf = gpd.read_file(DATA_EXTERNAL / "nta_boundaries_2020.geojson")
    nta_gdf = nta_gdf.rename(columns={'nta2020': 'nta_code', 'ntaname': 'nta_name', 'boroname': 'borough_name'})
    nta_gdf = nta_gdf[~nta_gdf['nta_code'].str.startswith('99', na=False)]

    stations = precovid[['station_complex_id', 'station_complex', 'latitude', 'longitude']].drop_duplicates()
    stations_gdf = gpd.GeoDataFrame(
        stations, geometry=gpd.points_from_xy(stations['longitude'], stations['latitude']), crs="EPSG:4326"
    )
    nta_gdf = nta_gdf.to_crs("EPSG:4326")
    station_nta = gpd.sjoin(stations_gdf, nta_gdf[['nta_code', 'geometry']], how='left', predicate='within')

    precovid = precovid.merge(station_nta[['station_complex_id', 'nta_code']], on='station_complex_id', how='left')
    precovid = precovid.dropna(subset=['nta_code'])

    # Aggregate by NTA and month
    nta_monthly = precovid.groupby(['nta_code', 'month']).agg(
        ridership=('daily_ridership', 'sum')
    ).reset_index()

    return nta_monthly


def get_features_and_targets(gdf, ridership):
    """Build the feature matrix matching recovery_analysis.py."""
    pivot = ridership.pivot(index='nta_code', columns='year_month', values='ridership')

    predictor_path = DATA_RAW / 'nta_predictors.csv'
    predictors = pd.read_csv(predictor_path) if predictor_path.exists() else pd.DataFrame()

    emp_path = DATA_RAW / 'nta_employment.csv'
    employment = pd.read_csv(emp_path) if emp_path.exists() else pd.DataFrame()

    census_path = DATA_RAW / 'census_acs_demographics.csv'
    crosswalk_path = DATA_EXTERNAL / 'tract_nta_crosswalk.csv'

    df = gdf.copy()
    if len(predictors):
        df = df.merge(predictors, on='nta_code', how='inner')
    if len(employment):
        df = df.merge(employment, on='nta_code', how='left')

    if census_path.exists() and crosswalk_path.exists():
        census = pd.read_csv(census_path)
        crosswalk = pd.read_csv(crosswalk_path)
        census['median_income'] = census['median_income'].apply(lambda x: x if x > 0 else np.nan)
        census['tract_fips'] = census['tract_geoid'].astype(str)
        crosswalk['tract_fips'] = crosswalk['tract_fips'].astype(str)
        census_nta = census.merge(crosswalk, on='tract_fips', how='inner')
        nta_demo = census_nta.groupby('nta_code').agg({
            'median_income': 'median', 'pct_bachelors': 'mean',
            'pct_white': 'mean', 'pct_black': 'mean',
            'pct_asian': 'mean', 'pct_hispanic': 'mean',
        }).reset_index()
        df = df.merge(nta_demo, on='nta_code', how='left')

    feature_cols = [
        'pct_commercial', 'commercial_density', 'residential_density',
        'remote_work_score', 'pct_bachelors', 'median_income',
        'pct_white', 'pct_black', 'pct_asian', 'pct_hispanic',
    ]
    available = [f for f in feature_cols if f in df.columns and df[f].notna().sum() > len(df) * 0.5]
    for col in available:
        df[col] = df[col].fillna(df[col].median())

    return df, pivot, available


# =============================================================================
# 5.1 Temporal Robustness
# =============================================================================

def experiment_5_1(df, pivot, features):
    """Test sensitivity of recovery metrics to baseline window choice."""
    print("\n" + "=" * 70)
    print("EXPERIMENT 5.1: TEMPORAL ROBUSTNESS OF RECOVERY METRICS")
    print("=" * 70)

    kfold = KFold(n_splits=5, shuffle=True, random_state=42)
    results = []

    # Load pre-COVID data for True Recovery variants
    precovid_nta = load_precovid_nta_ridership()

    # --- TRUE RECOVERY variants ---
    # Pre-COVID data has Jan (month=1) and Feb (month=2)
    if precovid_nta is not None:
        print("\n--- True Recovery Sensitivity ---")

        # Compute pre-COVID baselines by NTA for different windows
        tr_denoms = {}

        # Jan 2020 only
        jan = precovid_nta[precovid_nta['month'] == 1].groupby('nta_code')['ridership'].sum()
        tr_denoms['Jan 2020'] = jan

        # Jan-Feb 2020 (monthly average)
        janfeb = precovid_nta.groupby('nta_code')['ridership'].sum() / 2
        tr_denoms['Jan-Feb 2020'] = janfeb

        # Numerator variants from monthly ridership
        numer_windows = {
            'Q3 2023': ['2023-07', '2023-08', '2023-09'],
            'Q4 2023': ['2023-10', '2023-11', '2023-12'],
        }

        # Primary true recovery metric (Jan-Feb / Q4 2023) from gdf
        primary_tr = df.set_index('nta_code')['true_recovery_index']

        for dname, denom_series in tr_denoms.items():
            for nname, nmonths in numer_windows.items():
                numer_cols = [c for c in pivot.columns if any(c.startswith(m) for m in nmonths)]
                if not numer_cols:
                    continue
                numer = pivot[numer_cols].mean(axis=1)

                # Compute metric
                common = denom_series.index.intersection(numer.index).intersection(df['nta_code'])
                common = common.intersection(primary_tr.dropna().index)
                if len(common) < 20:
                    continue

                metric = numer[common] / denom_series[common]
                metric = metric.replace([np.inf, -np.inf], np.nan).dropna()
                common = metric.index.intersection(primary_tr.dropna().index)

                rho, p_rho = spearmanr(metric[common], primary_tr[common])

                # Ridge regression
                X = df.set_index('nta_code').loc[common, features]
                y = metric[common]
                X = X.replace([np.inf, -np.inf], np.nan).fillna(X.median())

                pipe = Pipeline([('scaler', StandardScaler()), ('model', Ridge(alpha=1.0))])
                cv = cross_val_score(pipe, X, y, cv=kfold, scoring='r2')

                results.append({
                    'Metric': 'True Recovery', 'Denominator': dname, 'Numerator': nname,
                    'Spearman rho': round(rho, 3), 'Spearman p': round(p_rho, 4),
                    'Ridge CV R²': round(cv.mean(), 3), 'n': len(common),
                })
                print(f"  {dname} / {nname}: rho={rho:.3f}, Ridge CV R²={cv.mean():.3f} (n={len(common)})")
    else:
        print("\n  [SKIP] Pre-COVID data not available for True Recovery sensitivity")

    # --- BOUNCE-BACK variants ---
    print("\n--- Bounce-back Sensitivity ---")

    bb_denoms = {
        'Q3 2020': ['2020-07', '2020-08', '2020-09'],
        'Jul 2020': ['2020-07'],
        'Q4 2020': ['2020-10', '2020-11', '2020-12'],
    }

    numer_windows = {
        'Q3 2023': ['2023-07', '2023-08', '2023-09'],
        'Q4 2023': ['2023-10', '2023-11', '2023-12'],
    }

    # Primary bounce-back
    primary_bb = df.set_index('nta_code')['recovery_index']

    for dname, dmonths in bb_denoms.items():
        denom_cols = [c for c in pivot.columns if any(c.startswith(m) for m in dmonths)]
        if not denom_cols:
            continue
        denom = pivot[denom_cols].mean(axis=1)

        for nname, nmonths in numer_windows.items():
            numer_cols = [c for c in pivot.columns if any(c.startswith(m) for m in nmonths)]
            if not numer_cols:
                continue
            numer = pivot[numer_cols].mean(axis=1)

            common = denom.index.intersection(numer.index).intersection(df['nta_code'])
            common = common.intersection(primary_bb.dropna().index)
            if len(common) < 20:
                continue

            metric = numer[common] / denom[common].replace(0, np.nan)
            metric = metric.replace([np.inf, -np.inf], np.nan).dropna()
            common = metric.index.intersection(primary_bb.dropna().index)

            rho, p_rho = spearmanr(metric[common], primary_bb[common])

            X = df.set_index('nta_code').loc[common, features]
            y = metric[common]
            X = X.replace([np.inf, -np.inf], np.nan).fillna(X.median())

            pipe = Pipeline([('scaler', StandardScaler()), ('model', Ridge(alpha=1.0))])
            cv = cross_val_score(pipe, X, y, cv=kfold, scoring='r2')

            results.append({
                'Metric': 'Bounce-back', 'Denominator': dname, 'Numerator': nname,
                'Spearman rho': round(rho, 3), 'Spearman p': round(p_rho, 4),
                'Ridge CV R²': round(cv.mean(), 3), 'n': len(common),
            })
            print(f"  {dname} / {nname}: rho={rho:.3f}, Ridge CV R²={cv.mean():.3f} (n={len(common)})")

    results_df = pd.DataFrame(results)
    results_df.to_csv(OUTPUT_TABLES / 'experiment_5_1_temporal_robustness.csv', index=False)
    print(f"\nSaved: {OUTPUT_TABLES / 'experiment_5_1_temporal_robustness.csv'}")
    return results_df


# =============================================================================
# 5.2 Cluster Stability
# =============================================================================

def experiment_5_2(df, pivot):
    """Evaluate optimal K and cluster stability via bootstrap."""
    print("\n" + "=" * 70)
    print("EXPERIMENT 5.2: CLUSTER STABILITY ANALYSIS")
    print("=" * 70)

    months = [c for c in pivot.columns if '2020-07' <= c <= '2023-12']
    traj = pivot[months].dropna()
    baseline = traj['2020-07']
    normalized = traj.div(baseline, axis=0)
    common = normalized.index.intersection(df['nta_code'])
    X = normalized.loc[common].values

    # --- K sweep ---
    print("\n--- K Sweep (K=2 to K=8) ---")
    k_results = []
    for k in range(2, 9):
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X)
        sil = silhouette_score(X, labels)
        ch = calinski_harabasz_score(X, labels)
        inertia = km.inertia_
        k_results.append({'K': k, 'Silhouette': round(sil, 3),
                          'Calinski-Harabasz': round(ch, 1), 'Inertia': round(inertia, 1)})
        print(f"  K={k}: Silhouette={sil:.3f}, CH={ch:.1f}, Inertia={inertia:.1f}")

    k_df = pd.DataFrame(k_results)
    k_df.to_csv(OUTPUT_TABLES / 'experiment_5_2_k_sweep.csv', index=False)

    # --- Bootstrap stability (K=4) ---
    print("\n--- Bootstrap Stability (K=4, 1000 iterations) ---")
    original_km = KMeans(n_clusters=4, random_state=42, n_init=10)
    original_labels = original_km.fit_predict(X)

    ari_scores = []
    n = len(X)
    np.random.seed(42)
    for i in range(1000):
        idx = np.random.choice(n, size=n, replace=True)
        X_boot = X[idx]
        boot_km = KMeans(n_clusters=4, random_state=42, n_init=10)
        boot_labels = boot_km.fit_predict(X_boot)
        ari = adjusted_rand_score(original_labels[idx], boot_labels)
        ari_scores.append(ari)

    mean_ari = np.mean(ari_scores)
    std_ari = np.std(ari_scores)
    print(f"  Mean ARI: {mean_ari:.3f} (+/- {std_ari:.3f})")
    print(f"  Median ARI: {np.median(ari_scores):.3f}")
    print(f"  ARI > 0.7: {np.mean(np.array(ari_scores) > 0.7)*100:.1f}% of iterations")

    stability_df = pd.DataFrame({
        'Metric': ['Mean ARI', 'Std ARI', 'Median ARI', 'Pct ARI > 0.7'],
        'Value': [round(mean_ari, 3), round(std_ari, 3),
                  round(np.median(ari_scores), 3),
                  round(np.mean(np.array(ari_scores) > 0.7) * 100, 1)]
    })
    stability_df.to_csv(OUTPUT_TABLES / 'experiment_5_2_bootstrap_stability.csv', index=False)
    print(f"\nSaved: experiment_5_2_k_sweep.csv, experiment_5_2_bootstrap_stability.csv")
    return k_df, stability_df


# =============================================================================
# 5.3 Feature Importance & Model Diagnostics
# =============================================================================

def experiment_5_3(df, features):
    """OLS diagnostics and permutation feature importance."""
    print("\n" + "=" * 70)
    print("EXPERIMENT 5.3: FEATURE IMPORTANCE & MODEL DIAGNOSTICS")
    print("=" * 70)

    all_results = []

    for target_name, target_col in [('Bounce-back', 'recovery_index'), ('True Recovery', 'true_recovery_index')]:
        print(f"\n--- {target_name} ---")
        y = df.set_index('nta_code')[target_col].dropna()
        common = y.index.intersection(df.set_index('nta_code').index)
        X = df.set_index('nta_code').loc[common, features]
        y = y[common]
        X = X.replace([np.inf, -np.inf], np.nan).fillna(X.median())

        scaler = StandardScaler()
        X_scaled = pd.DataFrame(scaler.fit_transform(X), columns=X.columns, index=X.index)
        X_const = sm.add_constant(X_scaled)

        model = sm.OLS(y, X_const).fit()

        # Residual normality
        stat_sw, p_sw = shapiro(model.resid)
        print(f"  Shapiro-Wilk: W={stat_sw:.4f}, p={p_sw:.4f} ({'Normal' if p_sw > 0.05 else 'Non-normal'})")

        # Homoscedasticity
        bp_stat, bp_p, _, _ = het_breuschpagan(model.resid, X_const)
        print(f"  Breusch-Pagan: LM={bp_stat:.4f}, p={bp_p:.4f} ({'Homoscedastic' if bp_p > 0.05 else 'Heteroscedastic'})")

        # VIF
        vif_values = {}
        for i, col in enumerate(X_const.columns):
            if col != 'const':
                vif = variance_inflation_factor(X_const.values, i)
                vif_values[col] = round(float(vif), 2)
        high_vif = {k: v for k, v in vif_values.items() if v > 5}
        print(f"  High VIF (>5): {high_vif if high_vif else 'None'}")

        # Permutation importance (RF)
        rf_pipe = Pipeline([('scaler', StandardScaler()),
                            ('model', RandomForestRegressor(n_estimators=100, random_state=42, max_depth=5))])
        rf_pipe.fit(X, y)
        perm = permutation_importance(rf_pipe, X, y, n_repeats=30, random_state=42)
        perm_imp = pd.Series(perm.importances_mean, index=features).sort_values(ascending=False)
        print(f"  Permutation Importance (top 5):")
        for feat, imp in perm_imp.head(5).items():
            print(f"    {feat}: {imp:.4f}")

        # OLS coefficients
        ols_coefs = model.params.drop('const').abs().sort_values(ascending=False)
        print(f"  OLS |coef| ranking (top 5):")
        for feat, coef in ols_coefs.head(5).items():
            print(f"    {feat}: {coef:.4f}")

        # Rank correlation OLS vs RF
        common_feats = perm_imp.index.intersection(ols_coefs.index)
        rho, p = spearmanr(perm_imp[common_feats].rank(), ols_coefs[common_feats].rank())
        print(f"  OLS vs RF ranking correlation: rho={rho:.3f}, p={p:.3f}")

        # Test removing high-VIF features
        cv_reduced_val = None
        cv_full_val = None
        if high_vif:
            reduced_features = [f for f in features if f not in high_vif]
            X_reduced = X[reduced_features]
            kfold = KFold(n_splits=5, shuffle=True, random_state=42)
            pipe_full = Pipeline([('scaler', StandardScaler()), ('model', Ridge(alpha=1.0))])
            pipe_reduced = Pipeline([('scaler', StandardScaler()), ('model', Ridge(alpha=1.0))])
            cv_full_val = cross_val_score(pipe_full, X, y, cv=kfold, scoring='r2').mean()
            cv_reduced_val = cross_val_score(pipe_reduced, X_reduced, y, cv=kfold, scoring='r2').mean()
            print(f"  Ridge CV R² full: {cv_full_val:.3f}, without high-VIF: {cv_reduced_val:.3f}, diff: {cv_full_val - cv_reduced_val:.3f}")

        all_results.append({
            'Target': target_name,
            'Shapiro W': round(float(stat_sw), 4), 'Shapiro p': round(float(p_sw), 4),
            'BP LM': round(float(bp_stat), 4), 'BP p': round(float(bp_p), 4),
            'OLS-RF rank rho': round(float(rho), 3),
            'High VIF features': str(high_vif) if high_vif else 'None',
            'CV R² full': round(float(cv_full_val), 3) if cv_full_val is not None else None,
            'CV R² no high-VIF': round(float(cv_reduced_val), 3) if cv_reduced_val is not None else None,
        })

    diag_df = pd.DataFrame(all_results)
    diag_df.to_csv(OUTPUT_TABLES / 'experiment_5_3_diagnostics.csv', index=False)
    print(f"\nSaved: {OUTPUT_TABLES / 'experiment_5_3_diagnostics.csv'}")
    return diag_df


# =============================================================================
# 5.4 Feature Group Ablation
# =============================================================================

def experiment_5_4(df, features):
    """Ablation study: which feature groups matter for each metric?"""
    print("\n" + "=" * 70)
    print("EXPERIMENT 5.4: FEATURE GROUP ABLATION STUDY")
    print("=" * 70)

    groups = {
        'Land Use': ['pct_commercial', 'commercial_density', 'residential_density'],
        'Employment': ['remote_work_score'],
        'Demographics': ['pct_bachelors', 'median_income', 'pct_white', 'pct_black', 'pct_asian', 'pct_hispanic'],
    }
    groups = {k: [f for f in v if f in features] for k, v in groups.items()}

    kfold = KFold(n_splits=5, shuffle=True, random_state=42)
    results = []

    for target_name, target_col in [('Bounce-back', 'recovery_index'), ('True Recovery', 'true_recovery_index')]:
        print(f"\n--- {target_name} ---")
        y = df.set_index('nta_code')[target_col].dropna()
        common = y.index.intersection(df.set_index('nta_code').index)
        X_full = df.set_index('nta_code').loc[common, features]
        y = y[common]
        X_full = X_full.replace([np.inf, -np.inf], np.nan).fillna(X_full.median())

        # Individual groups
        for gname, gcols in groups.items():
            if not gcols:
                continue
            X_g = X_full[gcols]
            pipe = Pipeline([('scaler', StandardScaler()), ('model', Ridge(alpha=1.0))])
            cv = cross_val_score(pipe, X_g, y, cv=kfold, scoring='r2')
            results.append({'Target': target_name, 'Features': gname,
                            'CV R²': round(cv.mean(), 3), 'CV Std': round(cv.std(), 3)})
            print(f"  {gname}: CV R²={cv.mean():.3f} (+/- {cv.std():.3f})")

        # Pairwise groups
        group_names = list(groups.keys())
        for i in range(len(group_names)):
            for j in range(i + 1, len(group_names)):
                pair_name = f"{group_names[i]} + {group_names[j]}"
                pair_cols = groups[group_names[i]] + groups[group_names[j]]
                if not pair_cols:
                    continue
                X_p = X_full[pair_cols]
                pipe = Pipeline([('scaler', StandardScaler()), ('model', Ridge(alpha=1.0))])
                cv = cross_val_score(pipe, X_p, y, cv=kfold, scoring='r2')
                results.append({'Target': target_name, 'Features': pair_name,
                                'CV R²': round(cv.mean(), 3), 'CV Std': round(cv.std(), 3)})
                print(f"  {pair_name}: CV R²={cv.mean():.3f} (+/- {cv.std():.3f})")

        # Full model
        pipe = Pipeline([('scaler', StandardScaler()), ('model', Ridge(alpha=1.0))])
        cv = cross_val_score(pipe, X_full, y, cv=kfold, scoring='r2')
        results.append({'Target': target_name, 'Features': 'All',
                        'CV R²': round(cv.mean(), 3), 'CV Std': round(cv.std(), 3)})
        print(f"  All: CV R²={cv.mean():.3f} (+/- {cv.std():.3f})")

    ablation_df = pd.DataFrame(results)
    ablation_df.to_csv(OUTPUT_TABLES / 'experiment_5_4_ablation.csv', index=False)
    print(f"\nSaved: {OUTPUT_TABLES / 'experiment_5_4_ablation.csv'}")
    return ablation_df


# =============================================================================
# Main
# =============================================================================

def main():
    print("=" * 70)
    print("SECTION 5 EXPERIMENTS: ROBUSTNESS AND VALIDATION")
    print("=" * 70)

    gdf, ridership = load_data()
    df, pivot, features = get_features_and_targets(gdf, ridership)
    print(f"Loaded: {len(df)} NTAs, {len(features)} features")
    print(f"Features: {features}")

    r1 = experiment_5_1(df, pivot, features)
    r2 = experiment_5_2(df, pivot)
    r3 = experiment_5_3(df, features)
    r4 = experiment_5_4(df, features)

    print("\n" + "=" * 70)
    print("ALL EXPERIMENTS COMPLETE")
    print("=" * 70)
    print(f"Results saved to: {OUTPUT_TABLES}/experiment_5_*.csv")


if __name__ == '__main__':
    main()
