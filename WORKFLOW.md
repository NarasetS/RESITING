# RESITING Workflow

Run the workflow vertically by filename. The empirical weight-factor step belongs
after the criterion layers are generated and before the final SI composer.

## Replace-Data Flow

When updated data is provided, replace the old file in the same `Data/` path and
run validation before rerunning workflow stages:

```powershell
python -m resiting validate-data
```

If only assumptions changed, create or edit a scenario YAML file under
`config/scenarios/` and validate it:

```powershell
python -m resiting new-scenario updated_2027 --from base
python -m resiting validate-config updated_2027
```

Use `config/data_manifest.yaml` for the expected replacement-file schema and
`config/default.yaml` for the default modeling assumptions.

For a copied folder on a new machine, run this first:

```powershell
python -m resiting portable-check
```

The same check is available from `START_RESITING.bat` as `Check copied folder`.

## Scenario-Aware Commands

The downstream production stages can be run through the helper:

```powershell
python -m resiting run-stage weights --scenario base
python -m resiting run-stage farm-area --scenario base
python -m resiting run-stage apply-exclusions --scenario base
python -m resiting run-stage visualize-si --scenario base
python -m resiting run-stage investment-map --scenario base
```

To preview commands without running them:

```powershell
python -m resiting run-stage all --scenario base --dry-run
```

Scenario files can control downstream assumptions including weights, farm-area
thresholds, exclusion buffer, SI threshold, coarsening scale, capacity density,
plant sizes, solver gaps, quota enforcement, output folder, and quotas.

The `base` scenario keeps legacy downstream filenames directly under `Output/`.
Other scenarios write SI products under `Output/scenarios/<scenario_name>/`, and
investment-map products under an identifying folder such as
`Output/SSI_0_CS_3_PDP2026_PH_Case4H/`. Metadata JSON files are written beside
the outputs so the producing scenario is visible later.

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
13. `python 11_SI_Farmarea.py --scenario base`
14. `python 11a_SI_ApplyPlantExclusions.py --scenario base`
15. `python 11b_Visualize_SI.py`
16. `python 12_SI_InvestmentMap.py --scenario base`

## Weight-Factor Rule

Rerun `10a_SI_WeightFactors.py` when any upstream criterion layer changes:
landcover/feedstock, slope, elevation, distance layers, resource potential, or
land cost.

You do not need to rerun weight factors when only downstream investment settings
change, such as `scenario_SI`, `coarsenscale`, quotas, solver gaps, map styling,
or export formatting.

The default output is `weightfactors/empirical_weights.json`, which
`11_SI_Farmarea.py` reads when `--weight-source empirical` is used.
