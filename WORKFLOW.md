# RESITING Workflow

Run the workflow vertically by filename. The empirical weight-factor step belongs
after the criterion layers are generated and before the final SI composer.

## Ordered Run

1. `1_SI_Landcover.ipynb`
2. `1.1_SI_Landcover_feedstock.ipynb` or `python 1_1_SI_Landcover_feedstock.py`
3. `2_SI_Slope.ipynb`
4. `3_SI_Elevation.ipynb`
5. `4_SI_Distancetosettlement.ipynb`
6. `5_SI_Distancetowetland.ipynb`
7. `6_SI_Distancetoforest.ipynb`
8. `7_SI_Distancetoroad.ipynb`
9. `8_SI_Distancetosubstation.ipynb`
10. `9_SI_RP_SolarWind_newdata.ipynb`
11. `10_SI_RP_LandCost.ipynb`
12. `python 10a_SI_WeightFactors.py`
13. `python 11_SI_Farmarea.py`
14. `python 11a_SI_ApplyPlantExclusions.py`
15. `python 11b_Visualize_SI.py`
16. `python 12_SI_InvestmentMap.py`

## Weight-Factor Rule

Rerun `10a_SI_WeightFactors.py` when any upstream criterion layer changes:
landcover/feedstock, slope, elevation, distance layers, resource potential, or
land cost.

You do not need to rerun weight factors when only downstream investment settings
change, such as `scenario_SI`, `coarsenscale`, quotas, solver gaps, map styling,
or export formatting.

The default output is `weightfactors/empirical_weights.json`, which
`11_SI_Farmarea.py` reads when `--weight-source empirical` is used.
