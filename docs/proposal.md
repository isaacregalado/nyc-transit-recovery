# Predicting Neighborhood Transit Recovery: Analyzing NYC Subway Ridership Patterns and Economic Factors Post-COVID

**Team 002** | CSE 6242 Data and Visual Analytics | Spring 2026

**Team Members:** Isaac Regalado, Elias Dematis, Dami Awosika, David Mongeau

---

## 1. Introduction and Problem Statement

**What are we trying to do?** We aim to identify which NYC neighborhoods recovered fastest from COVID-19's impact on subway ridership and determine what economic and demographic factors predict faster recovery. Our analysis window covers January 2020 through December 2023 across NYC's Neighborhood Tabulation Areas (NTAs), with January–February 2020 serving as the pre-COVID baseline.

**Who cares?** The NYC Metropolitan Transportation Authority (MTA) serves 3.5 million daily riders and needs data-driven insights for service planning. Urban planners require evidence for equitable recovery investment. Researchers studying urban resilience need neighborhood-level analysis rather than city-wide aggregates. Our interactive tool will enable stakeholders to explore these patterns visually.

## 2. Current Practice and Limitations

Existing approaches have significant limitations. The MTA publishes aggregate ridership statistics but provides no neighborhood-level recovery analysis [1]. Academic studies focus on national trends: Liu et al. (2020) documented the 100-year low in US transit demand but analyzed only aggregate patterns [2]. Ziedan et al. (2023) identified June 2021 as a national recovery turning point but didn't examine neighborhood variation [3]. Mahfouz et al. (2024) examined NYC specifically but focused on taxis and rideshare rather than subway-economic linkages [4]. No existing tool integrates transit recovery data with neighborhood economic indicators in an interactive visualization.

## 3. Our Approach and Expected Innovation

We hypothesize that the standard "recovery" narrative is misleading. We develop two distinct metrics:

1. **Recovery Index** (Bounce-back): Q4 2023 ridership / Q3 2020 ridership - measures recovery from COVID lows
2. **True Recovery Index**: Q4 2023 ridership / Jan-Feb 2020 ridership - measures actual return to pre-pandemic levels

This distinction should reveal whether "bouncing back" and "truly recovering" are different phenomena with different predictors.

Our analytical approach has three components:

1. _Dual Recovery Metrics_ quantifying each neighborhood's bounce-back vs. true recovery
2. _Trajectory Clustering_ using k-means to group neighborhoods into recovery patterns
3. _Predictive Regression_ with cross-validation identifying which neighborhood characteristics - commercial density, residential composition, and remote work potential - predict recovery

The interactive dashboard will feature:

1. A choropleth map comparing recovery metrics side-by-side (bounce-back vs. true recovery)
2. Animated ridership timeline from January 2020 through December 2023
3. Key findings section with statistical results
4. Drill-down capability with tooltips for any neighborhood
5. Storytelling flow to guide users through the analysis

**Why will it succeed?** All datasets are publicly available from official sources (MTA, NYC Open Data, Census). Our methodology follows established approaches in published literature. The team combines skills in data engineering, statistical analysis, and interactive visualization.

## 4. Literature Survey

**COVID Transit Impact:** Liu, Miller & Scheff (2020) documented that US transit ridership fell to 100-year lows during COVID, establishing the severity baseline [2]. Ziedan, Brakewood & Watkins (2023) retrospectively analyzed nationwide recovery through June 2022, identifying inflection points [3]. Srinivasan et al. (2025) analyzed Boston bus ridership retention using spatial regression, finding essential worker concentration predicted retention [6]. We will adapt their place-based methodology for NYC.

**Economic Recovery:** Che, Lee & Kim (2023) showed neighborhood-level retail clusters recovered faster than district-level clusters [7]. Forouhar et al. (2025) found 76% average downtown recovery across 66 North American cities, with sector composition explaining variation [8]. Sun et al. (2023) identified that residential density predicted food retail survival during COVID [9].

**Transit-Economy Linkage:** Osorio, Liu & Ouyang (2022) found remote work accounted for 66% of Chicago rail ridership loss, with lower-income areas showing smaller declines due to essential work [10]. This informs our use of employment data with remote work potential scoring.

## 5. Data

We will integrate four primary public datasets:

| Dataset                     | Source        | Size   | Granularity               | Use                      |
| --------------------------- | ------------- | ------ | ------------------------- | ------------------------ |
| MTA Subway Hourly Ridership | data.ny.gov   | ~500MB | Hourly, station-level     | Recovery metrics         |
| PLUTO Property Data         | NYC Planning  | ~300MB | Tax lot (857K properties) | Land use characteristics |
| LEHD Employment (WAC)       | Census LEHD   | ~100MB | Census block              | Remote work potential    |
| NTA Boundaries              | NYC Open Data | ~5MB   | 262 neighborhoods         | Spatial aggregation unit |

**Data Processing Pipeline:**

1. Aggregate ridership records to monthly totals by station
2. Spatially join subway stations to NTAs
3. Process PLUTO property records for land use ratios
4. Calculate remote work potential from jobs using NAICS industry codes
5. Create tract-to-NTA crosswalk via spatial join for employment data

## 6. Proposed Methodology

**Spatial Analysis:**

- Join subway stations to NTAs using coordinate-based spatial analysis
- Analyze only NTAs with subway service

**Statistical Validation:**

- Variance Inflation Factor (VIF) checks for multicollinearity
- 80/20 train-test split validation
- 5-fold cross-validation
- Moran's I for spatial autocorrelation

**Remote Work Scoring:**
We will classify NAICS industry codes by remote work potential:

- **High**: Information, Finance, Professional Services, Management (weight: 1.0)
- **Medium**: Real Estate, Admin Support, Education, Public Admin (weight: 0.5)
- **Low**: Retail, Healthcare, Food Service, Manufacturing, etc. (weight: 0.1)

## 7. Risks and Mitigations

| Risk                     | Mitigation                                                           |
| ------------------------ | -------------------------------------------------------------------- |
| Weak predictive signal   | Multiple model specifications; valuable insights even with modest R² |
| Data quality issues      | Cross-validate with multiple sources; document limitations           |
| Visualization complexity | Use established libraries (Plotly, Folium); iterative development    |

**Payoffs:** Actionable insights for MTA service planning; publishable methodology for urban resilience research; reusable interactive tool for NYC neighborhood analysis.

## 8. Cost

All data is freely available from public sources. Computing uses personal machines and free cloud tiers. Software is open source (Python, Plotly, Folium). **Total cost: $0.**

## 9. Timeline

| Week  | Dates           | Activities                                  | Owner        |
| ----- | --------------- | ------------------------------------------- | ------------ |
| 1-2   | Jan 27 - Feb 9  | Data acquisition, cleaning, NTA integration | Isaac, Elias |
| 3-4   | Feb 10 - Feb 23 | Recovery index calculation, EDA             | All          |
| 5-6   | Feb 24 - Mar 9  | Clustering and regression analysis          | Dami         |
| 6-7   | Mar 10 - Mar 23 | Interactive visualization development       | David        |
| 8-9   | Mar 24 - Apr 6  | Integration, testing, iteration             | All          |
| 10-11 | Apr 7 - Apr 20  | Final report and poster preparation         | All          |

## 10. Success Metrics

**Midterm checkpoints:** All data integrated; recovery index calculated for NTAs; initial clustering results; visualization wireframes complete.

**Final success criteria:**

- Regression model identifies 3+ significant predictors (p<0.05)
- Clustering achieves meaningful separation of recovery patterns
- Interactive visualization supports map exploration and drill-down
- Findings documented with actionable insights for transit planning

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
