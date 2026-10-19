# RESITING Folder Handoff

Use this when sharing the whole workspace with a new user.

## Recommended Copy

Copy the project folder as one folder, preserving this layout:

```text
RESITING/
  START_RESITING.bat
  requirements.txt
  config/
  resiting/
  Data/
  Output/
  weightfactors/
```

`Data/` is required for rerunning the workflow. `Output/` is optional if the
recipient only needs to rerun from source data, but include it when they need
the already generated NetCDF, HTML, CSV, or Excel products.

Do not rely on a copied `.env/` virtual environment. It may work on the original
machine only. The launcher can detect a broken `.env/`, rename it to
`.env.broken-YYYYMMDD-HHMMSS`, and create a fresh environment.

## First Steps On The New Machine

1. Open the copied folder.
2. Double-click `START_RESITING.bat`.
3. Choose `Check copied folder`.
4. Choose `Install or refresh dependencies`.
5. Choose `Validate replacement data files`.
6. Choose `Validate scenario config`.

The equivalent command-line checks are:

```powershell
python -m resiting portable-check
python -m resiting validate-data
python -m resiting validate-config base
```

After validation, users can run scenario-aware downstream stages from the
launcher or the command line:

```powershell
python -m resiting run-stage all --scenario base
```

Use `--dry-run` first if they only want to preview what will run.

## Replacing Updated Data

New users can paste updated files over the older files in `Data/` as long as the
paths and schemas stay compatible. After replacing files, run:

```powershell
python -m resiting validate-data
```

The expected replacement-file contract lives in `config/data_manifest.yaml`.

## Changing Assumptions

Create a copied scenario file:

```powershell
python -m resiting new-scenario updated_2027 --from base
python -m resiting validate-config updated_2027
```

Then edit `config/scenarios/updated_2027.yaml`.

## Credentials

Files such as `Data/cds_api.txt` can contain personal credentials. Share them
only when appropriate. A recipient can create their own credentials locally.
