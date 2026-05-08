import argparse
from pathlib import Path
import runpy

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr


TECHS = ["Wind", "Solar", "Biomass", "BGEC", "BGWW", "MSW", "IEW"]


def _buffer_points_meters(gdf, buffer_m):
    """Buffer point geometries in meters, then return to WGS84."""
    return gdf.to_crs("EPSG:32647").buffer(buffer_m).to_crs("EPSG:4326")


def load_restricted_sites(data_dir=Path("Data"), buffer_m=2900):
    print("Loading existing power plants and committed RE sites...")

    existing_path = data_dir / "ExistingPlants_wPosition.csv"
    existing = pd.read_csv(existing_path)
    existing = gpd.GeoDataFrame(
        existing,
        geometry=gpd.points_from_xy(existing["longitude"], existing["latitude"]),
        crs="EPSG:4326",
    )
    existing["geometry"] = _buffer_points_meters(existing, buffer_m)
    existing = existing[["geometry"]].assign(type="existing_plant")
    print(f"Existing power plants: {len(existing)}")

    committed_path = data_dir / "NewVRE.xlsx"
    committed = pd.read_excel(committed_path, sheet_name="สรุปผู้ที่ได้รับการคัดเลือก")
    committed = gpd.GeoDataFrame(
        committed,
        geometry=gpd.points_from_xy(committed["lon"], committed["lat"]),
        crs="EPSG:4326",
    )
    committed["geometry"] = _buffer_points_meters(committed, buffer_m)
    committed = committed[["geometry"]].assign(type="committed_re_site")
    print(f"Committed RE sites: {len(committed)}")

    restricted_sites = pd.concat([existing, committed], ignore_index=True)
    restricted_sites = gpd.GeoDataFrame(restricted_sites, geometry="geometry", crs="EPSG:4326")
    print(f"Total restricted sites: {len(restricted_sites)}")
    return restricted_sites


def build_restricted_mask(ds, restricted_sites):
    lon_grid, lat_grid = np.meshgrid(ds.lon.values, ds.lat.values)
    grid_points = gpd.GeoDataFrame(
        {
            "lat": lat_grid.ravel(),
            "lon": lon_grid.ravel(),
            "grid_index": np.arange(lat_grid.size),
        },
        geometry=gpd.points_from_xy(lon_grid.ravel(), lat_grid.ravel()),
        crs="EPSG:4326",
    )

    print("Checking final SI grid cells against restricted sites...")
    joined = gpd.sjoin(grid_points[["grid_index", "geometry"]], restricted_sites[["geometry"]], how="left")
    restricted_index = joined.loc[joined["index_right"].notna(), "grid_index"].unique()

    mask = np.zeros(lat_grid.size, dtype=bool)
    mask[restricted_index] = True
    mask = mask.reshape((len(ds.lat), len(ds.lon)))

    return xr.DataArray(mask, coords={"lat": ds.lat, "lon": ds.lon}, dims=("lat", "lon"))


def apply_landcover_exclusion(ds, restricted_mask):
    vars_to_zero = [
        var
        for var in ds.data_vars
        if var == "lccs_class" or var.startswith("SI_")
    ]

    print(f"Masking {int(restricted_mask.sum())} pre-feedstock grid cells across {len(vars_to_zero)} variables...")
    out = ds.copy()
    for var in vars_to_zero:
        out[var] = xr.where(restricted_mask, 0, out[var])
    return out


def build_existing_committed_cutoff_si(
    template_path=Path("Output") / "xr_SI_Landcover_beforefeedstock.nc",
    cutoff_prefeedstock_path=Path("Output") / "xr_SI_Landcover_beforefeedstock_existing_committed_cutoff.nc",
    cutoff_landcover_path=Path("Output") / "xr_SI_Landcover_existing_committed_cutoff.nc",
    output_path=Path("Output") / "xr_final_SI_all_existing_committed_cutoff.nc",
    farmarea_output_path=Path("Output") / "xr_SI_Farmarea_existing_committed_cutoff.nc",
    buffer_m=2900,
    weight_source="empirical",
    weights_path=None,
):
    """Build the optimization input without running weight-factor evaluation."""
    print("Building investment-ready SI with existing/committed sites excluded before feedstock integration...")
    restricted_sites = load_restricted_sites(buffer_m=buffer_m)

    with xr.open_dataset(template_path) as ds:
        template = ds.load()

    restricted_mask = build_restricted_mask(template, restricted_sites)
    cutoff_prefeedstock = apply_landcover_exclusion(template, restricted_mask)
    print(f"Saving pre-feedstock cutoff landcover SI to {cutoff_prefeedstock_path}...")
    cutoff_prefeedstock.to_netcdf(cutoff_prefeedstock_path)
    template.close()
    cutoff_prefeedstock.close()

    feedstock_module = runpy.run_path("1_1_SI_Landcover_feedstock.py")
    process_landcover_feedstock = feedstock_module["process_landcover_feedstock"]
    process_landcover_feedstock(
        input_path=cutoff_prefeedstock_path,
        output_path=cutoff_landcover_path,
    )

    farmarea_module = runpy.run_path("11_SI_Farmarea.py")
    process_farm_area_suitability = farmarea_module["process_farm_area_suitability"]
    process_farm_area_suitability(
        landcover_path=cutoff_landcover_path,
        final_output_path=output_path,
        farmarea_output_path=farmarea_output_path,
        bio_capacity_source="landcover",
        weight_source=weight_source,
        weights_path=weights_path,
        run_label="existing/committed cutoff",
    )
    print("Investment-ready existing/committed cutoff SI completed.")


if __name__ == "__main__":
    # Production/optimization build only. This reruns the SI composer once with
    # the cutoff landcover input; it does not generate relative-importance weights.
    parser = argparse.ArgumentParser(description="Build the investment-ready cutoff final SI dataset.")
    parser.add_argument(
        "--weight-source",
        choices=["default", "empirical"],
        default="empirical",
        help="Weight source for the optimization SI build.",
    )
    parser.add_argument(
        "--weights-file",
        default=None,
        help="Optional custom JSON empirical weight file.",
    )
    args = parser.parse_args()
    build_existing_committed_cutoff_si(weight_source=args.weight_source, weights_path=args.weights_file)
