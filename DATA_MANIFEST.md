# Data Manifest

This repository is set up so code and documentation can be shared separately
from large geospatial data products.

## Local Folders

| Path | Purpose | Default release zip |
| --- | --- | --- |
| `Data/` | Input datasets, shapefiles, NetCDF climate/resource files, regional tables, and local credentials. | Excluded |
| `Output/` | Generated suitability layers, final NetCDF products, HTML maps, CSVs, and Excel exports. | Excluded |
| `.env/` | Local Python virtual environment. | Excluded |
| `weightfactors/` | Empirical weight-factor code and JSON outputs used by downstream scripts. | Included |

## Large Files Observed

The workspace contains multi-GB NetCDF files in `Data/` and `Output/`. These are
not practical to send through ordinary source-control or email workflows. Use a
shared drive, object storage, or an external hard drive for a full reproducible
handoff.

Important examples:

- `Data/dataset-satellite-land-cover/C3S-LC-L4-LCCS-Map-300m-P1Y-2022-v2.1.1.nc`
- `Data/CDS_Data/*.nc`
- `Output/xr_final_SI_all.nc`
- `Output/xr_final_SI_all_existing_committed_cutoff.nc`
- `Output/SSI_*/xr_output_all.nc`

## Credential Handling

`Data/cds_api.txt` and similar CDS API configuration files can contain personal
credentials. Do not include them in shared release zips. Each recipient should
create their own CDS API credential file locally.

## Reproducing Outputs

1. Restore or download the required inputs into `Data/`.
2. Install dependencies from `requirements.txt`.
3. Run the ordered workflow in `WORKFLOW.md`.
4. Check generated products under `Output/`.
