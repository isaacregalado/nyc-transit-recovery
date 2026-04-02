# The Recovery is an Illusion: Analyzing NYC Subway Ridership Patterns Post-COVID

**Team 002** | CSE 6242 Data and Visual Analytics | Spring 2026 | Georgia Institute of Technology

**Isaac Regalado, Elias Dematis, Dami Awosika, David Mongeau**

## 1. Introduction

The COVID-19 pandemic caused an 85% decline in New York City subway ridership in May 2020. Though ridership has since grown city-wide, many neighborhoods remain significantly below pre-pandemic levels. The MTA provides aggregate statistics [1], and academic studies focus on national trends [2] or specific sectors [5], overlooking the neighborhood-level linkage between transit recovery and local economic indicators. Our project integrates MTA ridership data with land use, employment, and demographic data at the Neighborhood Tabulation Area (NTA) level across 133 subway-served neighborhoods from January 2020 through December 2023.

Our key innovation is distinguishing "bounce-back" (growth from COVID lows) from "True Recovery" (return to pre-pandemic baselines). Neighborhood features explain 54% of bounce-back variance but only 18% of true recovery, suggesting the two metrics differ fundamentally in their predictors and predictability.

## 2. Problem Definition

We determine what neighborhood-level factors predict post-COVID subway ridership recovery across NYC's 133 subway-served neighborhoods. Given neighborhoods each with feature vector **x** in R^10 (land use, employment, demographics), we compute two metrics: Bounce-back = Q4 2023 / Q3 2020 ridership (growth from COVID low) and True Recovery = Q4 2023 / Jan-Feb 2020 ridership (return to pre-pandemic baseline). We ask: (1) Do these metrics measure the same phenomenon? (2) Can neighborhood features predict each? (3) Do the important predictors differ? Our hypothesis is that bounce-back and true recovery are fundamentally different phenomena with different predictors.

## 3. Literature Survey

**COVID Transit Impact.** Liu et al. (2020) documented 100-year ridership lows [2]. Ziedan et al. (2023) analyzed nationwide recovery but only aggregate patterns [3]. Qi et al. (2021) surveyed decline factors without modeling recovery [5]. Mahfouz et al. (2024) examined NYC recovery but focused on taxis/rideshare [4].

**Place-Based Recovery.** Srinivasan et al. (2025) found essential worker concentration predicted Boston bus retention [6]. We adapt their methodology for NYC subway. Xiao et al. (2022) confirmed neighborhood characteristics influence transit resilience [11].

**Remote Work and Economic Recovery.** Osorio et al. (2022) found remote work accounted for 66% of Chicago rail ridership loss [12], informing our LEHD-based remote work scoring. Forouhar et al. (2025) found 76% average downtown recovery across 66 cities [10]. Che et al. (2023), Sun et al. (2023), and Lu & Duan (2025) demonstrated local economic composition shapes recovery [7][8][9]. Paul & Taylor (2022) examined equity implications [13].

**Visualization.** Stehle & Kitchin (2020) established best practices for city dashboards with multiple coordinated views [14]. Chen et al. (2024) developed user-driven geospatial time step exploration [15]. No existing dashboard juxtaposes dual baselines to reveal how metric choice changes the narrative.

**Gap.** No existing work integrates granular transit recovery with neighborhood indicators while mathematically distinguishing bounce-back from true recovery and providing an interactive tool for baseline comparison.

## 4. Proposed Method

### 4.1 Data Integration

We integrated five public datasets (Jan 2020–Dec 2023): MTA Subway Hourly Ridership (270M+ rides, data.ny.gov), PLUTO Property Data (857K tax lots, NYC Planning), LEHD Employment WAC (4.2M jobs, Census Bureau), Census ACS Demographics (2,327 tracts), and NTA Boundaries (262 NTAs, NYC Open Data). Processing: aggregated hourly ridership to monthly totals, spatially joined 472 stations to 262 NTAs, calculated land use ratios from PLUTO, classified 4.2M LEHD jobs by NAICS remote work potential (High=1.0: Finance, Tech; Medium=0.5: Education; Low=0.1: Retail, Healthcare), aggregated ACS demographics via tract-to-NTA crosswalk. Final dataset: 133 NTAs, 10 features, 2 outcomes.

### 4.2 Analysis Methods

**Dual Recovery Metrics.** Bounce-back (Q4 2023 / Q3 2020) and true recovery (Q4 2023 / Jan-Feb 2020) per NTA. The same data yields fundamentally different conclusions depending on the denominator.

**Multi-Model Regression.** Five models—OLS, Ridge, Lasso, Random Forest, Gradient Boosting—using sklearn Pipelines with StandardScaler inside each CV fold to prevent data leakage. Validation: VIF checks, 80/20 train-test split, 5-fold cross-validation. Ten features: pct_commercial, commercial_density, residential_density, remote_work_score, pct_bachelors, median_income, pct_white, pct_black, pct_asian, pct_hispanic.

**Trajectory Clustering.** K-means (K=4) on 42-month normalized trajectories (Jul 2020–Dec 2023), validated with silhouette score (0.46) and Calinski-Harabasz index (306.6, highest among K=2–8).

**Spatial Autocorrelation.** Moran's I using Queen contiguity weights.

### 4.3 Interactive Visualization

We built a scroll-snap dashboard (self-contained 15MB HTML) using Plotly and Folium, designed around **comparative revelation**—forcing users to confront both baselines simultaneously. Key design features: (1) **Dual-baseline choropleth maps** showing the same neighborhoods under both metrics side-by-side, going beyond single-metric dashboards [14]; (2) **Scroll-snap guided storytelling** adapting Chen et al.'s exploration approach [15] to a narrative structure; (3) **Recovery paradox scatter plot** revealing the counterintuitive negative correlation between bounce-back and true recovery; (4) **Coordinated hover tooltips** displaying both metrics simultaneously across all views; (5) **Model comparison visualization** contrasting CV R² across five models for both targets.

## 5. Evaluation

### 5.1 The Recovery Illusion

NYC subway ridership grew **2.4x** from pandemic lows but remains at only **72%** of pre-COVID levels. **98%** of neighborhoods (130 of 133) have not returned to baseline. True recovery ranges from 31% to 98% across NTAs.

### 5.2 Regression Results

| Model | BB Train R² | BB Test R² | BB CV R² | TR Train R² | TR Test R² | TR CV R² |
|---|---|---|---|---|---|---|
| OLS | 0.73 | 0.70 | 0.52 | 0.37 | 0.29 | 0.17 |
| Ridge | 0.73 | 0.71 | 0.54 | 0.37 | 0.29 | **0.18** |
| Lasso | 0.66 | 0.78 | **0.54** | 0.00 | -0.07 | -0.03 |
| Random Forest | 0.89 | 0.87 | 0.52 | 0.74 | 0.17 | 0.05 |
| Gradient Boosting | 0.99 | 0.73 | 0.35 | 0.98 | -0.52 | -0.26 |

**Observation 1: The predictability gap is the finding.** Bounce-back is moderately predictable (CV R² = 0.54); true recovery is not (CV R² = 0.18). This reveals the two metrics are driven by fundamentally different factors.

**Observation 2: Ensemble methods confirm the distinction.** GBM achieves Train R² = 0.98 but CV R² = -0.26 on true recovery—pure overfitting. True recovery lacks predictable structure from neighborhood features.

**Observation 3: Lasso zeroes out true recovery.** Lasso retains features for bounce-back but zeroes them all for true recovery (R² = 0.00), confirming no feature subset has predictive value.

**Significant Predictors (OLS standardized β):**

| Predictor | Bounce-back | True Recovery |
|---|---|---|
| pct_bachelors | +0.38 (p<0.001) | +0.06 (p=0.02) |
| pct_commercial | +0.35 (p<0.001) | +0.03 (p=0.01) |
| remote_work_score | +0.23 (p<0.001) | n.s. |
| commercial_density | -0.21 (p=0.002) | -0.03 (p=0.02) |
| pct_asian | +0.19 (p=0.03) | +0.04 (p=0.03) |

**Observation 4: Remote work predicts bounce-back but not true recovery.** remote_work_score is the third-strongest bounce-back predictor (+0.23, p<0.001) but is not significant for true recovery. This is consistent with Osorio et al.'s finding that remote work drove ridership loss [12]—neighborhoods with more remote-capable jobs dropped more during COVID, creating more room to "bounce back," but whether they actually return to pre-pandemic levels depends on employer-specific policies we cannot measure.

**Observation 5: The commercial_density sign flip.** Higher commercial percentage predicts higher bounce-back (+0.35), but higher commercial *density* predicts lower bounce-back (-0.21). Interpretation: commercial neighborhoods bounce back, but the densest commercial cores (Midtown, FiDi) had the highest pre-COVID ridership and remain furthest from it in absolute terms.

Note: VIF > 5 for pct_bachelors (7.2), pct_white (9.1), pct_black (10.4) indicates multicollinearity among demographic features. Overall model fit and CV R² remain valid but individual coefficients for correlated features may be unstable.

### 5.3 Clustering and Spatial Results

K-means identified four trajectory clusters:

| Cluster | NTAs | Bounce-back | True Recovery |
|---|---|---|---|
| Near-Full | 19 | 4.50x | 83% |
| Steady | 27 | 3.17x | 76% |
| Lagging | 54 | 2.25x | 74% |
| Struggling | 33 | 1.51x | 61% |

**Observation 6: The "Struggling" paradox.** The 33 "Struggling" NTAs show the *lowest* bounce-back (1.51x) but this is because they are predominantly essential-worker neighborhoods (Bronx, outer Queens) where ridership never dropped as sharply. Their low bounce-back reflects a smaller denominator, not poor recovery. If the MTA allocates resources based on growth metrics, these areas could be underserved despite consistent ridership.

**Observation 7: Case studies.** East Midtown-Turtle Bay shows the highest bounce-back (4.53x)—its ridership exploded from COVID lows as office workers returned—yet its true recovery is only ~76%, meaning nearly a quarter of pre-pandemic commuters have not returned. Conversely, Canarsie (Brooklyn) shows a bounce-back *below 1.0* (0.70x), meaning it has *fewer* riders in Q4 2023 than during the Q3 2020 COVID trough—a neighborhood still declining.

**Spatial autocorrelation:** Bounce-back shows strong spatial clustering (Moran's I = 0.68, p = 0.001) while true recovery shows weak clustering (I = 0.18, p = 0.008). This aligns with regression findings: bounce-back is predictable from spatially clustered features (commercial areas concentrate in Manhattan), while true recovery is more spatially random.

**Observation 8: Borough-level patterns.** Manhattan shows the largest gap between metrics (3.1x bounce-back but only 76% true recovery), embodying the "illusion." Outer boroughs with more essential workers show smaller bounce-back (1.8–2.4x) but comparable true recovery (68–74%), suggesting a more modest but similarly permanent ridership loss.

### 5.4 Robustness and Validation

We conducted four robustness experiments to validate our core findings.

**Temporal robustness.** We recomputed each metric using alternative denominator windows—True Recovery: Jan 2020 only, Jan-Feb 2020; Bounce-back: Q3 2020, Jul 2020, Q4 2020—crossed with two numerator windows (Q3/Q4 2023). True recovery CV R² stays below 0.15 across all windows. Bounce-back CV R² ranges from 0.52–0.66. NTA rankings are highly stable (Spearman ρ ≥ 0.85 for all variants). The predictability gap is not an artifact of baseline selection.

**Cluster stability.** We evaluated K=2 through K=8. K=4 achieves the highest Calinski-Harabasz score (306.6) and near-peak silhouette (0.46). Bootstrap resampling (1,000 iterations): mean ARI = 0.87, median ARI = 0.89, with 90.5% of iterations producing ARI > 0.7. Cluster assignments are stable.

**Model diagnostics.** Bounce-back residuals are normally distributed (Shapiro-Wilk p=0.23) but heteroscedastic (Breusch-Pagan p=0.003). True recovery residuals are non-normal (p<0.001), confirming unmeasured variables dominate. OLS vs. RF permutation importance rankings correlate strongly for bounce-back (ρ=0.81, p=0.005) but not for true recovery (ρ=0.49, p=0.15), confirming that linear findings are not model-dependent. Removing high-VIF features has negligible effect on bounce-back CV R² (0.535→0.536) but reduces true recovery from 0.179 to 0.101, suggesting its modest signal is partly driven by demographic correlations rather than robust predictive structure.

**Feature group ablation.** We partitioned features into Land Use, Employment, and Demographics and ran Ridge regression with each group individually, in pairs, and combined. For bounce-back, all three groups contribute meaningful signal (Land Use: 0.28, Employment: 0.25, Demographics: 0.33, All: 0.54). For true recovery, only Demographics has positive CV R² (0.16); Land Use and Employment alone are near-zero or negative. This confirms the two metrics are driven by structurally different processes.

### 5.5 Visualization Evaluation

Our dashboard was evaluated against the design goal of preventing single-metric misinterpretation. The dual-map view reveals patterns invisible in tabular data: Manhattan appears as the "best recovered" borough on the bounce-back map but "average" on the true recovery map. The scatter plot's negative correlation pattern—neighborhoods with the highest bounce-back often have the lowest true recovery—is immediately visible but counterintuitive, which validates the need for the dual-metric framing. The scroll-snap narrative guides users from system-level context through the analytical evidence, making the findings accessible to non-technical stakeholders (transit planners, policymakers).

## 6. Conclusions and Discussion

We analyzed NYC subway ridership recovery across 133 neighborhoods, revealing that the "recovery" narrative is an illusion. While ridership grew 2.4x from COVID lows, the system remains at only 72% of pre-pandemic levels, with 98% of neighborhoods still below baseline. Our key contribution is demonstrating that bounce-back and true recovery are fundamentally different phenomena: neighborhood characteristics explain 54% of bounce-back variance but only 18% of true recovery. Robustness checks confirm this gap holds across all baseline windows, model types, and feature subsets.

The predictable bounce-back reflects workers returning to offices in commercial areas—those who could work remotely during COVID. True recovery depends on factors we cannot measure: employer return-to-office policies, worker preferences, and lasting behavioral changes. The negative CV R² for ensemble models on true recovery is not a failure but a finding—neighborhood characteristics simply do not determine which areas return to pre-pandemic ridership.

**Implications:** (1) Transit agencies should track both metrics separately—conflating them leads to misallocated resources. (2) True recovery cannot be predicted from observable neighborhood characteristics, complicating long-term service planning. (3) Essential-worker neighborhoods risk underinvestment if agencies prioritize growth metrics. (4) The 28% ridership gap may be permanent, requiring adjustment to service levels and revenue projections.

**Limitations:** Geographic scope limited to 133 subway-served NTAs (bus-dependent neighborhoods may differ); data ends December 2023; employer-level policies unavailable; multicollinearity among demographic variables (VIF up to 10.4); modest sample size (n=133, p=10) contributes to high CV variance; pre-COVID baseline limited to January-February 2020.

**Future Work:** Incorporate employer-level return-to-office policy data; extend to bus ridership for comparison; track whether the recovery gap narrows or stabilizes over time.

**Effort distribution:** All team members have contributed a similar amount of effort. Isaac and Elias led data acquisition and processing; Dami led statistical analysis; David led visualization development. All members contributed to methodology design and interpretation of results.

## References

[1] MTA. "MTA Subway Hourly Ridership Data." data.ny.gov, 2024.

[2] Liu, L., Miller, H.J., & Scheff, J. "The impacts of COVID-19 pandemic on public transit demand in the United States." _PLOS ONE_, 15(11), e0242476, 2020.

[3] Ziedan, A., Brakewood, C., & Watkins, K. "Will transit recover? A retrospective study of nationwide ridership during COVID-19." _J. Public Transportation_, 25, 100046, 2023.

[4] Mahfouz, M., et al. "Navigating the post-pandemic urban landscape: Disparities in transportation recovery in NYC." _Cities_, 2024.

[5] Qi, Y., Liu, J., Tao, T., & Zhao, Q. "Impacts of COVID-19 on public transit ridership." _Intl. J. Transportation Science and Technology_, 12(1), 34-45, 2021.

[6] Srinivasan, S., Shamsuddin, S., & Cheng, J. "Bus ridership retention, place-based factors, and COVID-19 in Boston." _Transportation Research Part A_, 196, 104479, 2025.

[7] Che, J., Lee, J.S., & Kim, S. "How has COVID-19 impacted economic resilience of retail clusters?" _Cities_, 138, 104457, 2023.

[8] Sun, F., et al. "Economic resilience during COVID-19: food retail in Seattle." _Frontiers in Built Environment_, 2023.

[9] Lu, X., & Duan, Y. "Channels and countermeasures of the COVID-19 pandemic's impact on urban economic resilience." _PLOS ONE_, 2025.

[10] Forouhar, A., et al. "Assessing downtown recovery rates in North American cities after COVID-19." _Urban Studies_, 2025.

[11] Xiao, W., Wei, Y.D., & Wu, Y. "Neighborhood, built environment and resilience in transportation during COVID-19." _Transportation Research Part D_, 110, 103428, 2022.

[12] Osorio, J., Liu, Y., & Ouyang, Y. "Executive orders or public fear: What caused transit ridership to drop in Chicago?" _Transportation Research Part D_, 105, 103226, 2022.

[13] Paul, J., & Taylor, B.D. "Pandemic transit: examining transit use changes and equity implications." _Transportation_, 2022.

[14] Stehle, S., & Kitchin, R. "Real-time and archival data visualisation in city dashboards." _Intl. J. Geographical Information Science_, 34(2), 344-366, 2020.

[15] Chen, B., et al. "SalienTime: User-driven Selection of Salient Time Steps for Large-Scale Geospatial Data Visualization." _CHI 2024_, ACM, 2024.
