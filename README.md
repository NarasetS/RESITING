# RESITING

Geospatial workflow for renewable-energy site suitability and investment mapping.
The numbered notebooks and scripts build suitability-index layers, estimate
empirical weights, apply exclusions, visualize results, and generate investment
site maps.

## What to Send

For a lightweight handoff, send a release zip created with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/make_release.ps1
```

The default zip excludes `.git`, `.env`, caches, `Data/`, and `Output/`.
Those folders are large and machine-local. Share them separately only when the
recipient needs to reproduce or inspect the full data products.

To include source data or generated outputs in the zip:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/make_release.ps1 -IncludeData
powershell -ExecutionPolicy Bypass -File scripts/make_release.ps1 -IncludeOutput
powershell -ExecutionPolicy Bypass -File scripts/make_release.ps1 -IncludeData -IncludeOutput
```

See `DATA_MANIFEST.md` for the expected data/output layout.

## Setup

Use Python 3.11 on Windows. A fresh virtual environment is recommended instead
of sending the existing `.env/` folder.

For the easiest setup, double-click:

```text
START_RESITING.bat
```

Then choose `Install or refresh dependencies`. The launcher creates `.env/`,
installs `requirements.txt`, and registers a `RESITING (.env)` Jupyter kernel.

Manual setup is also supported:

```powershell
py -3.11 -m venv .env
.\.env\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Some geospatial packages depend on native libraries. If installation fails,
install the packages through conda-forge instead:

```powershell
conda create -n resiting python=3.11 --file requirements.txt
conda activate resiting
```

## Run Order

Run the project vertically by filename. The detailed workflow is maintained in
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
12. `python 10a_SI_WeightFactors.py`
13. `python 11_SI_Farmarea.py`
14. `python 11a_SI_ApplyPlantExclusions.py`
15. `python 11b_Visualize_SI.py`
16. `python 12_SI_InvestmentMap.py`

## Notes for Recipients

- Put input data under `Data/`.
- Generated intermediate and final products are written under `Output/`.
- Do not commit or share local CDS API credentials. Keep credentials outside the
  release zip and configure them locally before downloading climate data.
- If upstream criterion layers change, rerun `10a_SI_WeightFactors.py` before
  running downstream farm-area and investment-map steps.
