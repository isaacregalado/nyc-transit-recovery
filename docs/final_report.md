# The Recovery is an Illusion: Analyzing NYC Subway Ridership Patterns Post-COVID

**Team 002** | CSE 6242 Data and Visual Analytics | Spring 2026 | Georgia Institute of Technology

**Isaac Regalado, Elias Dematis, Dami Awosika, David Mongeau**

---

## 1. Introduction

The COVID-19 pandemic caused unprecedented disruption to urban transit systems. NYC subway ridership plummeted from approximately 135 million monthly rides to just 20 million in May 2020—an 85% collapse. As cities reopened, transit agencies and urban planners sought to understand recovery patterns and predict which areas would return to normal ridership levels.

However, the standard "recovery" narrative is misleading. Media reports celebrating ridership growth from pandemic lows obscure a troubling reality: many neighborhoods remain far below pre-pandemic ridership. This distinction matters for transit planning, service allocation, and understanding the long-term impacts of remote work on urban mobility. The MTA serves 3.5 million daily riders and needs data-driven, neighborhood-level insights—yet no existing tool integrates transit recovery data with local economic and demographic indicators in an interactive visualization that exposes how baseline selection changes the recovery story.

---

## 2. Problem Definition

We aim to determine what neighborhood-level economic and demographic factors predict the speed and magnitude of post-COVID subway ridership recovery across NYC's 133 subway-served neighborhoods.

Formally, given a set of neighborhoods $N = \{n_1, ..., n_{133}\}$, each with feature vector $\mathbf{x}_i \in \mathbb{R}^{10}$ (land use, employment, demographics), we compute two recovery metrics per neighborhood:

$$\text{Bounce-back}_i = \frac{\text{Q4 2023 Ridership}_i}{\text{Q3 2020 Ridership}_i}, \quad \text{True Recovery}_i = \frac{\text{Q4 2023 Ridership}_i}{\text{Jan-Feb 2020 Ridership}_i}$$

We then ask: (1) Do these two metrics measure the same phenomenon? (2) Can $\mathbf{x}_i$ predict each metric via regression? (3) What are the most important predictors, and do they differ between the two metrics?

Our hypothesis is that "bouncing back" from a pandemic low and "truly recovering" to pre-pandemic levels are fundamentally different phenomena with different predictors, and that standard recovery narratives mislead by conflating the two.

---

## 3. Literature Survey

**COVID Transit Impact.** Liu, Miller & Scheff (2020) documented that US transit ridership fell to 100-year lows during COVID [2]. Ziedan, Brakewood & Watkins (2023) retrospectively analyzed nationwide recovery, identifying June 2021 as an inflection point, but examined only aggregate patterns without neighborhood-level granularity [3]. Qi et al. (2021) surveyed factors affecting ridership decline but did not model recovery trajectories [5]. Mahfouz et al. (2024) examined NYC transportation recovery but focused on taxis and rideshare rather than subway-economic linkages [4].

**Place-Based Recovery Analysis.** Srinivasan et al. (2025) analyzed Boston bus ridership retention using spatial regression, finding essential worker concentration predicted retention [6]. We adapted their place-based methodology for NYC subway. Xiao, Wei & Wu (2022) confirmed that neighborhood characteristics influence transit resilience in Wuhan [11].

**Remote Work and Economic Recovery.** Osorio, Liu & Ouyang (2022) found remote work accounted for 66% of Chicago rail ridership loss, with lower-income areas showing smaller declines due to essential work [12]. This directly informed our LEHD-based remote work scoring. Forouhar et al. (2025) found 76% average downtown recovery across 66 North American cities [10]. Che, Lee & Kim (2023) and Sun et al. (2023) demonstrated that local economic composition shapes recovery at the retail level [7][8]. Lu & Duan (2025) studied channels of COVID economic impact on urban resilience [9].

**Visualization.** Stehle & Kitchin (2020) established best practices for real-time city dashboards, emphasizing the need for multiple coordinated views [14]. Chen et al. (2024) developed user-driven techniques for exploring salient time steps in geospatial data [15]. Paul & Taylor (2022) studied equity implications of pandemic transit changes [13]. Existing dashboards show single recovery metrics; none juxtapose dual baselines to reveal how metric choice changes the narrative—the core design principle of our visualization.

**Gap.** No existing work integrates granular transit recovery data with neighborhood economic indicators while (a) mathematically distinguishing between bounce-back and true recovery and (b) providing an interactive tool that lets users explore how baseline selection changes the story.

---

## 4. Proposed Method

### 4.1 Data Integration

We integrated four public datasets (Jan 2020–Dec 2023): MTA Subway Hourly Ridership (270M+ rides from data.ny.gov), PLUTO Property Data (857K tax lots from NYC Planning), LEHD Employment WAC (4.2M jobs from Census Bureau), and Census ACS Demographics (2,327 tracts). Processing pipeline: (1) aggregate hourly ridership to monthly totals, spatially join 472 stations to 262 NTAs; (2) calculate land use ratios from PLUTO; (3) aggregate LEHD employment via tract-to-NTA crosswalk; (4) score remote work potential by classifying 20 NAICS codes (High=1.0: Finance, Tech, Professional; Medium=0.5: Education, Real Estate; Low=0.1: Retail, Healthcare); (5) aggregate ACS demographics from tracts to NTAs. Final dataset: 133 NTAs with subway service, 10 features, 2 outcomes.

### 4.2 Analysis Methods

**Dual Recovery Metrics.** We compute both bounce-back (Q4 2023 / Q3 2020) and true recovery (Q4 2023 / Jan-Feb 2020) per NTA. This is our core analytical innovation: the same data yields fundamentally different conclusions depending on the denominator.

**Multi-Model Regression.** We compare five model types—OLS, Ridge, Lasso, Random Forest, Gradient Boosting—using sklearn Pipelines that include StandardScaler inside each CV fold to prevent data leakage. Validation: VIF checks for multicollinearity, 80/20 train-test split, and 5-fold cross-validation. Features: `pct_commercial`, `commercial_density`, `residential_density`, `remote_work_score`, `pct_bachelors`, `median_income`, `pct_white`, `pct_black`, `pct_asian`, `pct_hispanic`.

**Trajectory Clustering.** K-means (k=4) on 42-month normalized ridership trajectories (Jul 2020–Dec 2023). We chose k=4 for interpretability, validated with silhouette score (0.46).

**Spatial Autocorrelation.** Moran's I using Queen contiguity weights to test whether recovery clusters geographically.

### 4.3 Interactive Visualization

Our dashboard addresses a key limitation of existing transit dashboards: they present a single recovery metric, which can mislead. Our visualization is designed around the principle of **comparative revelation**—forcing users to confront both baselines simultaneously so they cannot inadvertently cherry-pick the more optimistic narrative.

**Design innovations over existing approaches:**

1. **Dual-baseline choropleth maps.** Two side-by-side maps of identical neighborhoods, colored by bounce-back (left) and true recovery (right). The visual contrast—Manhattan glowing green on one map and red on the other—immediately communicates the "recovery illusion" without requiring statistical literacy. This goes beyond Stehle & Kitchin's single-metric dashboard design [14].

2. **Scroll-snap guided storytelling.** Rather than presenting all visualizations simultaneously (which causes dashboard fatigue), we use CSS scroll-snap sections that guide users through a curated analytical narrative: system-wide context → dual maps → paradox scatter plot → regression evidence → neighborhood rankings. Each section builds on the prior insight. This adapts Chen et al.'s user-driven time step exploration [15] to a narrative structure.

3. **Recovery paradox scatter plot.** An interactive scatter plot of bounce-back (x) vs. true recovery (y) per neighborhood reveals the counterintuitive negative correlation—neighborhoods that "bounced back" most are often farthest from pre-COVID levels. Hover tooltips show both metrics, neighborhood name, and borough, preventing users from interpreting either metric in isolation.

4. **Coordinated hover tooltips.** All map and chart interactions display both recovery metrics simultaneously. A user hovering over any neighborhood always sees the full picture, reinforcing the dual-metric framing throughout the exploration.

5. **Model comparison visualization.** Side-by-side bar charts of Train/Test/CV R² across five models for both targets. The visual contrast between the green bounce-back bars (CV R² ~0.54) and the near-zero true recovery bars immediately communicates the "different phenomena" finding.

**Technology:** Python-generated HTML using Plotly (charts), Folium with Mapbox tiles (maps), and vanilla JavaScript for scroll-snap navigation and animated counters. The entire dashboard is a single self-contained HTML file (15MB) requiring no server—users simply open it in a browser.

---

## 5. Evaluation

### 5.1 The Recovery Illusion

| Metric                | Value                   |
| --------------------- | ----------------------- |
| Average Bounce-back   | **2.4x** from COVID low |
| Average True Recovery | **72%** of pre-COVID    |
| NTAs Below Pre-COVID  | **98%** (130 of 133)    |
| Best True Recovery    | 98%                     |
| Worst True Recovery   | 31%                     |

NYC subway ridership grew 2.4x from pandemic lows but remains 28% below pre-pandemic levels. 98% of neighborhoods have not returned to baseline.

### 5.2 Regression Results

**Model Comparison: Bounce-back**

| Model             | Train R² | Test R² | CV R²    |
| ----------------- | -------- | ------- | -------- |
| OLS               | 0.73     | 0.70    | 0.52     |
| Ridge             | 0.73     | 0.71    | 0.54     |
| Lasso             | 0.66     | 0.78    | **0.54** |
| Random Forest     | 0.89     | 0.87    | 0.52     |
| Gradient Boosting | 0.99     | 0.73    | 0.35     |

**Model Comparison: True Recovery**

| Model             | Train R² | Test R² | CV R²    |
| ----------------- | -------- | ------- | -------- |
| OLS               | 0.37     | 0.29    | 0.17     |
| Ridge             | 0.37     | 0.29    | **0.18** |
| Lasso             | 0.00     | -0.07   | -0.03    |
| Random Forest     | 0.74     | 0.17    | 0.05     |
| Gradient Boosting | 0.98     | -0.52   | -0.26    |

**Observation 1: The predictability gap is the finding.** Bounce-back is moderately predictable (Lasso CV R² = 0.54); true recovery is not (Ridge CV R² = 0.18). This is not a modeling failure—it reveals that the two metrics are driven by fundamentally different factors.

**Observation 2: Ensemble methods expose the distinction.** Gradient Boosting achieves Train R² = 0.99 on bounce-back (real signal) but Train R² = 0.98 with CV R² = -0.26 on true recovery (pure overfitting). The model finds patterns in training data that do not generalize—strong evidence that true recovery lacks predictable structure from neighborhood features.

**Observation 3: Linear models are more honest.** OLS shows stable Train-Test gaps for both targets (0.03 for bounce-back, 0.08 for true recovery), suggesting the signal that exists is linear. The Lasso's feature selection confirms this: it retains features for bounce-back but zeroes them all out for true recovery (R² = 0.00).

**Significant Predictors (OLS):**

| Predictor            | Bounce-back      | True Recovery   |
| -------------------- | ---------------- | --------------- |
| `pct_bachelors`      | +0.38 (p<0.001)  | +0.06 (p=0.02)  |
| `pct_commercial`     | +0.35 (p<0.001)  | +0.03 (p=0.01)  |
| `remote_work_score`  | +0.23 (p<0.001)  | n.s.             |
| `commercial_density` | -0.21 (p=0.002)  | -0.03 (p=0.02)  |
| `pct_asian`          | +0.19 (p=0.03)   | +0.04 (p=0.03)  |

**Observation 4: Remote work predicts bounce-back but not true recovery.** `remote_work_score` is the third-strongest bounce-back predictor (+0.23, p<0.001) but is not significant for true recovery. This is consistent with Osorio et al.'s finding that remote work drove ridership loss [12]—neighborhoods with more remote-capable jobs dropped more during COVID, creating more room to "bounce back," but whether they actually return to pre-pandemic levels depends on employer-specific policies we cannot measure.

**Observation 5: The `commercial_density` sign flip.** Higher commercial percentage predicts higher bounce-back (+0.35), but higher commercial *density* predicts lower bounce-back (-0.21). Interpretation: commercial neighborhoods bounce back, but the densest commercial cores (Midtown, FiDi) had the highest pre-COVID ridership and remain furthest from it in absolute terms.

Note: VIF > 5 for `pct_bachelors` (7.35), `pct_white` (9.82), `pct_black` (11.34), `pct_hispanic` (5.36) indicates multicollinearity. Overall model fit and CV R² remain valid but individual coefficients for correlated features may be unstable.

### 5.3 Clustering and Spatial Results

K-means identified four trajectory clusters:

| Label               | NTAs | Bounce-back | True Recovery |
| ------------------- | ---- | ----------- | ------------- |
| Near-Full Recovery  | 19   | 4.50x       | 83%           |
| Steady Recovery     | 27   | 3.17x       | 76%           |
| Lagging Recovery    | 54   | 2.25x       | 74%           |
| Struggling Recovery | 33   | 1.51x       | 61%           |

**Observation 6: The "Struggling" paradox.** The 33 "Struggling" NTAs show the *lowest* bounce-back (1.51x) but this is because they are predominantly essential-worker neighborhoods (Bronx, outer Queens) where ridership never dropped as sharply. Their low bounce-back is not a sign of poor recovery—it reflects a smaller denominator. Their true recovery (61%) is genuinely low, however, suggesting even these areas lost riders permanently.

**Observation 7: Case studies.** East Midtown-Turtle Bay shows the highest bounce-back (4.53x)—its ridership exploded from COVID lows as office workers returned—yet its true recovery is only ~76%, meaning nearly a quarter of pre-pandemic commuters have not returned. Conversely, Canarsie (Brooklyn) shows a bounce-back *below 1.0* (0.70x), meaning it has *fewer* riders in Q4 2023 than during the Q3 2020 COVID trough—a neighborhood still declining.

**Spatial autocorrelation:** Bounce-back shows strong spatial clustering (Moran's I = 0.68, p = 0.001) while true recovery shows weak clustering (I = 0.18, p = 0.008). This aligns with regression findings: bounce-back is predictable from spatially clustered features (commercial areas concentrate in Manhattan), while true recovery is more spatially random.

**Observation 8: Borough-level patterns.** Manhattan shows the largest gap between metrics (3.1x bounce-back but only 76% true recovery), embodying the "illusion." Outer boroughs with more essential workers show smaller bounce-back but similar true recovery rates (68-74%), suggesting a more modest but comparably permanent ridership loss.

### 5.4 Visualization Evaluation

Our dashboard was evaluated against the design goal of preventing single-metric misinterpretation. The dual-map view reveals patterns invisible in tabular data: for example, Manhattan appears as the "best recovered" borough on the bounce-back map but "average" on the true recovery map. The scatter plot's negative correlation pattern—neighborhoods with the highest bounce-back often have the lowest true recovery—is immediately visible but counterintuitive, which validates the need for the dual-metric framing. The scroll-snap narrative guides users from system-level context through the analytical evidence, making the findings accessible to non-technical stakeholders (transit planners, policymakers).

---

## 6. Conclusions and Discussion

We analyzed NYC subway ridership recovery across 133 neighborhoods, revealing that the "recovery" narrative is an illusion. While ridership grew 2.4x from COVID lows, the system remains at only 72% of pre-pandemic levels. Our key contribution is demonstrating that bounce-back and true recovery are fundamentally different phenomena: land use, employment, and demographic characteristics explain 54% of bounce-back variance but only 18% of true recovery.

The predictable bounce-back reflects workers returning to offices in commercial areas—those who could work remotely during COVID. True recovery is associated with factors we cannot measure: employer return-to-office policies, worker preferences, and lasting behavioral changes. The negative CV R² for ensemble models is not a failure but a finding—neighborhood characteristics simply do not determine which areas return to pre-pandemic ridership. This is an observational study; we identify associations rather than causal relationships.

**Implications:** (1) Transit agencies should track both metrics separately—conflating them leads to misallocated resources. (2) True recovery cannot be predicted from observable neighborhood characteristics, complicating long-term service planning. (3) The 28% ridership gap may be permanent, requiring adjustment to service levels and revenue projections.

**Limitations:** Geographic scope limited to 133 subway-served NTAs (bus-dependent neighborhoods may differ); data ends December 2023; employer-level policies unavailable; multicollinearity among demographic variables (VIF up to 11.3); modest sample size (133 NTAs, 10 features) contributes to high CV variance.

**Future Work:** Incorporate employer-level return-to-office policy data; extend to bus ridership for comparison; track whether the recovery gap narrows or stabilizes over time.

**Effort distribution:** All team members have contributed a similar amount of effort. Isaac led data engineering and pipeline development; Elias led statistical analysis; Dami led clustering and spatial analysis; David led visualization and dashboard development.

---

## References

[1] MTA. "MTA Subway Hourly Ridership Data." data.ny.gov, 2024.

[2] Liu, L., Miller, H.J., & Scheff, J. "The impacts of COVID-19 pandemic on public transit demand in the United States." _PLOS ONE_, 15(11), e0242476, 2020.

[3] Ziedan, A., Brakewood, C., & Watkins, K. "Will transit recover? A retrospective study of nationwide ridership during COVID-19." _Journal of Public Transportation_, 25, 100046, 2023.

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
