| Day | Residential cohort | `upper_only` shifted heat [MWh] | `1 K` shifted heat [MWh] | `upper_only` shifted heat [kWh/m²] | `1 K` shifted heat [kWh/m²] | `1 K / upper_only` ratio [-] |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 2023-11-04 | residential_pre1975 | 1159.6 | 2959.5 | 0.0682 | 0.1524 | 2.23 |
| 2023-11-04 | residential_1975_1990 | 495.9 | 1427.6 | 0.0656 | 0.1654 | 2.52 |
| 2023-11-04 | residential_1990_2000 | 79.9 | 122.0 | 0.0634 | 0.0848 | 1.34 |
| 2023-11-04 | residential_2000_2014 | 12.6 | 153.1 | 0.0024 | 0.0250 | 10.62 |
| 2023-03-04 | residential_pre1975 | 785.3 | 2334.0 | 0.0462 | 0.1202 | 2.60 |
| 2023-03-04 | residential_1975_1990 | 69.2 | 1017.0 | 0.0092 | 0.1178 | 12.86 |
| 2023-03-04 | residential_1990_2000 | 8.4 | 112.7 | 0.0067 | 0.0784 | 11.67 |
| 2023-03-04 | residential_2000_2014 | 22.5 | 26.8 | 0.0042 | 0.0044 | 1.04 |
| 2023-03-18 | residential_pre1975 | 734.7 | 1968.4 | 0.0432 | 0.1013 | 2.34 |
| 2023-03-18 | residential_1975_1990 | 65.2 | 1832.3 | 0.0086 | 0.2123 | 24.59 |
| 2023-03-18 | residential_1990_2000 | 8.0 | 103.1 | 0.0064 | 0.0716 | 11.27 |
| 2023-03-18 | residential_2000_2014 | 21.0 | 56.1 | 0.0039 | 0.0092 | 2.33 |
| 2023-02-21 | residential_pre1975 | 698.9 | 4181.4 | 0.0411 | 0.2153 | 5.23 |
| 2023-02-21 | residential_1975_1990 | 81.9 | 1000.8 | 0.0108 | 0.1159 | 10.70 |
| 2023-02-21 | residential_1990_2000 | 7.4 | 104.6 | 0.0059 | 0.0727 | 12.43 |
| 2023-02-21 | residential_2000_2014 | 19.0 | 343.7 | 0.0036 | 0.0562 | 15.81 |

Notes:
- These are the top-savings days from the current heating-season screen.
- Shifted heat is computed from the cohort-aggregated `q_heat - q_heat_ref` series as `sum(abs(diff)) / 2`.
- The table shows that the `1 K` case amplifies residential cohort shifts strongly, but not uniformly.
- In particular, some newer cohorts respond disproportionately more in relative terms, even when their absolute `MWh` remain smaller than old-stock cohorts.
