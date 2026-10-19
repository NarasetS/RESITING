# RESITING

RESITING is a Windows/Python geospatial workflow for renewable-energy site
suitability and investment mapping. The workflow builds suitability-index layers,
applies empirical weights and exclusions, then produces investment site outputs
as NetCDF, CSV/XLSX, and HTML maps.

The project is designed so a new user can copy the folder, refresh the local
Python environment, validate replacement data, choose a scenario, and run the
downstream workflow without editing Python code.

## Quick Start

For a copied folder on a new machine:

1. Open the copied `RESITING/` folder.
2. Double-click `START_RESITING.bat`.
3. Choose `Check copied folder`.
4. Choose `Install or refresh dependencies`.
5. Choose `Validate replacement data files`.
6. Choose `Validate scenario config`.
7. Run the needed workflow stage from the launcher, or use the command line.

Equivalent command-line checks:

```powershell
python -m resiting portable-check
python -m resiting validate-data
python -m resiting validate-config base
```

For a named scenario:

```powershell
python -m resiting validate-config PDP2026_PH_Case4H
python -m resiting run-stage all --scenario PDP2026_PH_Case4H --dry-run
python -m resiting run-stage all --scenario PDP2026_PH_Case4H
```

Use `--dry-run` first to preview commands without launching heavy geospatial
processing.

## Folder Handoff

For whole-folder transfer, see `HANDOFF.md`.

The folder can be copied as-is, but do not rely on a copied `.env/` virtual
environment. If the copied `.env/` is broken on the recipient machine,
`START_RESITING.bat` renames it to `.env.broken-YYYYMMDD-HHMMSS` and creates a
fresh one.

Large local folders are intentionally separate from source control:

| Path | Purpose |
| --- | --- |
| `Data/` | Input datasets and replacement files |
| `Output/` | Generated NetCDF, HTML, CSV, and Excel outputs |
| `.env/` | Local Python virtual environment |
| `config/scenarios/` | Scenario assumptions and quotas |

## Setup

Use Python 3.11 on Windows. Python 3.10 and 3.12 are also accepted by the
launcher, but Python 3.11 is the recommended baseline.

Easiest setup:

```text
START_RESITING.bat
```

Then choose `Install or refresh dependencies`. The launcher creates `.env/`,
installs `requirements.txt`, and registers a `RESITING (.env)` Jupyter kernel.

Manual setup:

```powershell
py -3.11 -m venv .env
.\.env\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Some geospatial packages depend on native libraries. If normal `pip` setup
fails, install through conda-forge instead:

```powershell
conda create -n resiting python=3.11 --file requirements.txt
conda activate resiting
```

## Data Updates

New users usually update data by replacing files in the same `Data/` paths.
After replacing files, run:

```powershell
python -m resiting validate-data
```

The validator checks the replace-in-place contract in
`config/data_manifest.yaml`, including required files, columns, Excel sheets,
shapefile readability, CRS, and geometry types.

If validation fails, fix the replacement file before rerunning downstream
workflow stages.

## Scenarios

Scenario YAML files live under:

```text
config/scenarios/
```

Create a new scenario from `base`:

```powershell
python -m resiting new-scenario updated_2027 --from base
python -m resiting validate-config updated_2027
```

Then edit:

```text
config/scenarios/updated_2027.yaml
```

Scenario files control downstream assumptions such as:

- SI threshold
- coarsening scale
- capacity density
- plant size
- farm-area thresholds
- existing/committed plant exclusion buffer
- solver gaps and quota enforcement
- empirical/default weight source
- regional quotas
- optional output names

Do not edit Python scripts for ordinary assumption changes.

## Running The Workflow

The notebooks still build the upstream criterion layers. The scenario-aware
helper runs the downstream production stages.

Recommended downstream command:

```powershell
python -m resiting run-stage all --scenario base
```

Run one stage at a time:

```powershell
python -m resiting run-stage weights --scenario base
python -m resiting run-stage farm-area --scenario base
python -m resiting run-stage apply-exclusions --scenario base
python -m resiting run-stage visualize-si --scenario base
python -m resiting run-stage investment-map --scenario base
```

For PDP2026 public hearing case 4H:

```powershell
python -m resiting run-stage all --scenario PDP2026_PH_Case4H
```

The original numbered scripts still work directly for advanced users.

## Ordered Run

Run the project vertically by filename. Detailed workflow notes live in
`WORKFLOW.md`.

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
12. `python -m resiting run-stage weights --scenario base`
13. `python -m resiting run-stage farm-area --scenario base`
14. `python -m resiting run-stage apply-exclusions --scenario base`
15. `python -m resiting run-stage visualize-si --scenario base`
16. `python -m resiting run-stage investment-map --scenario base`

The removed notebook `11a_SI_ApplyPlantExclusions.ipynb` is no longer part of
the official workflow. Use `11a_SI_ApplyPlantExclusions.py` or
`python -m resiting run-stage apply-exclusions --scenario ...`.

## Outputs

The `base` scenario keeps legacy downstream files directly under `Output/`.
Other scenarios write scenario-specific SI products under:

```text
Output/scenarios/<scenario_name>/
```

Example for `PDP2026_PH_Case4H`:

```text
Output/scenarios/PDP2026_PH_Case4H/xr_final_SI_all.nc
Output/scenarios/PDP2026_PH_Case4H/xr_SI_Farmarea.nc
Output/scenarios/PDP2026_PH_Case4H/xr_final_SI_all_existing_committed_cutoff.nc
Output/scenarios/PDP2026_PH_Case4H/xr_SI_Farmarea_existing_committed_cutoff.nc
Output/SSI_0_CS_3_PDP2026_PH_Case4H/
```

Metadata files record which scenario produced each downstream output:

```text
farm_area_metadata.json
apply_exclusions_metadata.json
run_metadata.json
```

## Sharing A Lightweight Zip

For a source-only handoff, create a release zip:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/make_release.ps1
```

The default zip excludes `.git`, `.env`, caches, `Data/`, and `Output/`.

To include source data or generated outputs:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/make_release.ps1 -IncludeData
powershell -ExecutionPolicy Bypass -File scripts/make_release.ps1 -IncludeOutput
powershell -ExecutionPolicy Bypass -File scripts/make_release.ps1 -IncludeData -IncludeOutput
```

See `DATA_MANIFEST.md` for the expected data/output layout.

## Notes

- Keep local CDS API credentials out of shared zips unless intentionally shared.
- If upstream criterion layers change, rerun the empirical weights before
  downstream farm-area and investment-map stages.
- `11b_Visualize_SI.py` currently uses fixed visualization inputs; the core
  scenario-specific investment outputs are handled by `12_SI_InvestmentMap.py`.
