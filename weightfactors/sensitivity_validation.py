import json
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


CRITERIA_NAMES = [
    "Landcover",
    "Slope",
    "Elevation",
    "Distance to settlement",
    "Distance to wetland",
    "Distance to forest",
    "Distance to road",
    "Distance to substation",
    "Resource potential",
    "Land cost",
    "Farm/feedstock area",
]

ALL_TECHS = ["Wind", "Solar", "Biomass", "BGEC", "BGWW", "MSW", "IEW"]
BIO_TECHS = ["Biomass", "BGEC", "BGWW", "MSW", "IEW"]
WS_TECHS = ["Wind", "Solar"]

DEFAULT_WEIGHTS = {
    "Wind": [0.0909] * 11,
    "Solar": [0.0909] * 11,
    "Biomass": [0.125, 0.125, 0.125, 0.125, 0.125, 0.0, 0.125, 0.125, 0.0, 0.125, 0.0],
    "BGEC": [0.125, 0.125, 0.125, 0.125, 0.125, 0.0, 0.125, 0.125, 0.0, 0.125, 0.0],
    "BGWW": [0.125, 0.125, 0.125, 0.125, 0.125, 0.0, 0.125, 0.125, 0.0, 0.125, 0.0],
    "MSW": [0.125, 0.125, 0.125, 0.125, 0.125, 0.0, 0.125, 0.125, 0.0, 0.125, 0.0],
    "IEW": [0.125, 0.125, 0.125, 0.125, 0.125, 0.0, 0.125, 0.125, 0.0, 0.125, 0.0],
}


def normalize(weights):
    total = float(np.sum(weights))
    if total <= 0:
        return list(weights)
    return [float(w / total) for w in weights]


def load_empirical_weights(path):
    if not path.exists():
        raise FileNotFoundError(f"Empirical weights file not found: {path}")

    with open(path, "r") as f:
        raw = json.load(f)

    weights = {}
    for tech in ALL_TECHS:
        tech_weights = raw.get(tech)
        if isinstance(tech_weights, dict):
            values = [float(tech_weights.get(name, 0.0)) for name in CRITERIA_NAMES]
        elif isinstance(tech_weights, list):
            values = [float(v) for v in tech_weights]
        else:
            values = DEFAULT_WEIGHTS[tech]
        weights[tech] = normalize(values)
    return weights


def make_equal_weights():
    weights = {}
    for tech in ALL_TECHS:
        active = np.array(DEFAULT_WEIGHTS[tech], dtype=float) > 0
        values = np.where(active, 1.0, 0.0)
        weights[tech] = normalize(values)
    return weights


def boost_criteria(base_weights, boosted_names, factor):
    boosted_idx = {CRITERIA_NAMES.index(name) for name in boosted_names}
    out = {}
    for tech, values in base_weights.items():
        adjusted = np.array(values, dtype=float)
        for idx in boosted_idx:
            adjusted[idx] *= factor
        out[tech] = normalize(adjusted)
    return out


def build_weight_scenarios():
    empirical = load_empirical_weights(Path("weightfactors/empirical_weights.json"))
    default = {tech: normalize(values) for tech, values in DEFAULT_WEIGHTS.items()}

    return {
        "empirical": empirical,
        "equal_active": make_equal_weights(),
        "default_heuristic": default,
        "resource_priority": boost_criteria(
            empirical,
            ["Resource potential", "Farm/feedstock area"],
            factor=1.5,
        ),
        "infrastructure_priority": boost_criteria(
            empirical,
            ["Distance to road", "Distance to substation"],
            factor=1.5,
        ),
        "environment_priority": boost_criteria(
            empirical,
            ["Distance to wetland", "Distance to forest"],
            factor=1.5,
        ),
    }


def load_existing_plants(csv_path, xlsx_path):
    plants = []
    lat_opts = ["latitude", "lat", "y"]
    lon_opts = ["longitude", "lon", "long", "x"]
    tech_opts = ["fuel", "fuel type", "fueltypename", "technology", "tech", "energy_source", "plant_type", "planttype", "type"]

    def extract(df, source):
        cols_lower = [str(c).strip().lower() for c in df.columns]
        lat_col = next((df.columns[cols_lower.index(opt)] for opt in lat_opts if opt in cols_lower), None)
        lon_col = next((df.columns[cols_lower.index(opt)] for opt in lon_opts if opt in cols_lower), None)
        tech_col = next((df.columns[cols_lower.index(opt)] for opt in tech_opts if opt in cols_lower), None)
        if not (lat_col and lon_col and tech_col):
            print(f"Warning: {source} is missing latitude, longitude, or technology columns.")
            return None
        out = df[[lat_col, lon_col, tech_col]].copy()
        out.columns = ["Latitude", "Longitude", "Technology"]
        return out

    if csv_path.exists():
        df = extract(pd.read_csv(csv_path), "CSV")
        if df is not None:
            plants.append(df)
    if xlsx_path.exists():
        df = extract(pd.read_excel(xlsx_path), "Excel")
        if df is not None:
            plants.append(df)

    if not plants:
        raise ValueError("No usable existing plant data was found.")

    df_all = pd.concat(plants, ignore_index=True)
    df_all["Latitude"] = pd.to_numeric(df_all["Latitude"], errors="coerce")
    df_all["Longitude"] = pd.to_numeric(df_all["Longitude"], errors="coerce")
    df_all = df_all.dropna(subset=["Latitude", "Longitude"])

    def standardize_tech(value):
        text = str(value).strip().upper()
        if "WIND" in text:
            return "Wind"
        if "SOLAR" in text:
            return "Solar"
        if "BIOMASS" in text:
            return "Biomass"
        if "BGWW" in text or "WASTEWATER" in text:
            return "BGWW"
        if "BIOGAS" in text or "BGEC" in text:
            return "BGEC"
        if "IEW" in text or "INDUSTRIAL" in text:
            return "IEW"
        if "MSW" in text or "MUNICIPAL" in text or "WASTE" in text:
            return "MSW"
        return None

    df_all["Tech_Standard"] = df_all["Technology"].apply(standardize_tech)
    return df_all.dropna(subset=["Tech_Standard"]).copy()


def compose_final_si(weights, output_dir):
    lccs_resolution = 300
    areapergrid = (lccs_resolution / 1000) ** 2

    xr_landcover = xr.open_dataset(output_dir / "xr_SI_Landcover.nc")
    xr_final = xr_landcover.copy(deep=True)

    for tech in ALL_TECHS:
        xr_final[f"AVA_{tech}"] = xr.where(xr_landcover[f"SI_{tech}"] > 0, np.float32(areapergrid), np.float32(0.0))
        xr_final[f"SI_{tech}"] = (xr_landcover[f"SI_{tech}"] * weights[tech][0]).astype(np.float32)
    xr_landcover.close()

    steps = [
        (1, "xr_SI_Slope.nc", "SI_{t}", True, ALL_TECHS),
        (2, "xr_SI_Elevation.nc", "SI_{t}", False, ALL_TECHS),
        (3, "xr_SI_Distancetosettlementarea.nc", "SI_{t}", True, ALL_TECHS),
        (4, "xr_SI_Distancetowetland.nc", "SI_{t}", False, ALL_TECHS),
        (5, "xr_SI_Distancetoforest.nc", "SI_{t}", True, WS_TECHS),
        (6, "xr_SI_Distancetoroad.nc", "SI_{t}", True, ALL_TECHS),
        (7, "xr_SI_Distancetosubstation.nc", "SI_DtoSubs", False, ALL_TECHS),
        (8, "xr_SI_resourcepotential.nc", "SI_{t}", True, WS_TECHS),
        (9, "xr_SI_LandCost.nc", "land_cost_avg_price_norm", False, ALL_TECHS),
    ]

    for step_idx, fname, var_template, update_ava, affected_techs in steps:
        ds = xr.open_dataset(output_dir / fname)
        for tech in affected_techs:
            var_name = var_template.format(t=tech)
            xr_final[f"SI_{tech}"] += (ds[var_name] * weights[tech][step_idx]).astype(np.float32)
            if update_ava:
                xr_final[f"AVA_{tech}"] = xr.where(ds[var_name] == 0, 0, xr_final[f"AVA_{tech}"])
            xr_final[f"SI_{tech}"] = xr.where(xr_final[f"AVA_{tech}"] == 0, 0, xr_final[f"SI_{tech}"])
        ds.close()

    suitablearea_wind = 4.0
    suitablearea_solar = 0.4
    rolgrid_wind = int(np.ceil(np.sqrt(suitablearea_wind / areapergrid)))
    rolgrid_solar = int(np.ceil(np.sqrt(suitablearea_solar / areapergrid)))

    fra_wind = xr_final["AVA_Wind"].rolling(lon=rolgrid_wind, lat=rolgrid_wind, min_periods=1, center=True).sum()
    fra_wind = xr.where(xr_final["AVA_Wind"] == 0, 0, fra_wind)
    xr_final["SI_Wind"] += xr.where(fra_wind >= suitablearea_wind, 3, 0) * weights["Wind"][10]

    fra_solar = xr_final["AVA_Solar"].rolling(lon=rolgrid_solar, lat=rolgrid_solar, min_periods=1, center=True).sum()
    fra_solar = xr.where(xr_final["AVA_Solar"] == 0, 0, fra_solar)
    xr_final["SI_Solar"] += xr.where(fra_solar >= suitablearea_solar, 3, 0) * weights["Solar"][10]

    heatrates = {"Biomass": 17.064, "BGEC": 9.950, "BGWW": 9.950, "MSW": 14.838, "IEW": 14.838}
    plantfactors = {"Biomass": 0.7, "BGEC": 0.7, "BGWW": 0.7, "MSW": 0.44, "IEW": 0.7}
    convert_ktoe_to_mbtu = 39652.608749183
    ds_res = xr.open_dataset(output_dir / "xr_SI_resourcepotential.nc")
    for tech in BIO_TECHS:
        cf = (convert_ktoe_to_mbtu / heatrates[tech]) / (plantfactors[tech] * 8760)
        if f"A_{tech}" in ds_res.data_vars:
            xr_final[f"A_{tech}"] = (ds_res[f"A_{tech}"] * cf).astype(np.float32)
        else:
            xr_final[f"A_{tech}"] = xr.zeros_like(xr_final[f"AVA_{tech}"])
    ds_res.close()

    return xr_final


def sample_local_positive(data_array, lat, lon, window_size=11, method="median"):
    if not (
        float(data_array.lat.min()) <= lat <= float(data_array.lat.max())
        and float(data_array.lon.min()) <= lon <= float(data_array.lon.max())
    ):
        return np.nan

    center = data_array.sel(lat=lat, lon=lon, method="nearest")
    lat_idx = int(np.abs(data_array.lat.values - center.lat.values).argmin())
    lon_idx = int(np.abs(data_array.lon.values - center.lon.values).argmin())
    half_window = window_size // 2

    window = data_array.isel(
        lat=slice(max(0, lat_idx - half_window), min(len(data_array.lat), lat_idx + half_window + 1)),
        lon=slice(max(0, lon_idx - half_window), min(len(data_array.lon), lon_idx + half_window + 1)),
    )
    values = window.values
    positive_values = values[np.isfinite(values) & (values > 0)]
    if len(positive_values) == 0:
        return 0.0
    if method == "median":
        return float(np.median(positive_values))
    if method == "mean":
        return float(np.mean(positive_values))
    if method == "max":
        return float(np.max(positive_values))
    raise ValueError(f"Unsupported sampling method: {method}")


def percentile_rank(value, population):
    population = population[np.isfinite(population)]
    if not np.isfinite(value) or len(population) == 0:
        return np.nan
    return float((population <= value).mean() * 100.0)


def validate_existing_plants(ds, plants, scenario_name, sample_window):
    rows = []
    for tech in ALL_TECHS:
        tech_plants = plants[plants["Tech_Standard"] == tech]
        if tech_plants.empty or f"SI_{tech}" not in ds:
            continue

        si = ds[f"SI_{tech}"]
        positive_si = si.values[np.isfinite(si.values) & (si.values > 0)]
        for _, plant in tech_plants.iterrows():
            value = sample_local_positive(si, plant["Latitude"], plant["Longitude"], window_size=sample_window)
            rows.append(
                {
                    "scenario": scenario_name,
                    "tech": tech,
                    "latitude": plant["Latitude"],
                    "longitude": plant["Longitude"],
                    "si_value": value,
                    "si_percentile": percentile_rank(value, positive_si),
                }
            )
    return pd.DataFrame(rows)


def summarize_scenario(ds, validation_df, scenario_name):
    rows = []
    for tech in ALL_TECHS:
        if f"SI_{tech}" not in ds:
            continue
        si_values = ds[f"SI_{tech}"].values
        positive_si = si_values[np.isfinite(si_values) & (si_values > 0)]
        tech_validation = validation_df[validation_df["tech"] == tech]
        rows.append(
            {
                "scenario": scenario_name,
                "tech": tech,
                "positive_cells": int(len(positive_si)),
                "mean_positive_si": float(np.mean(positive_si)) if len(positive_si) else np.nan,
                "p90_positive_si": float(np.percentile(positive_si, 90)) if len(positive_si) else np.nan,
                "existing_plant_count": int(len(tech_validation)),
                "mean_existing_plant_si": float(tech_validation["si_value"].mean()) if len(tech_validation) else np.nan,
                "median_existing_plant_percentile": float(tech_validation["si_percentile"].median()) if len(tech_validation) else np.nan,
                "share_existing_plants_top_30pct": float((tech_validation["si_percentile"] >= 70).mean()) if len(tech_validation) else np.nan,
                "share_existing_plants_top_20pct": float((tech_validation["si_percentile"] >= 80).mean()) if len(tech_validation) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def run_sensitivity_validation(write_rasters=False, sample_window=51):
    output_dir = Path("Output")
    sensitivity_dir = output_dir / "sensitivity"
    sensitivity_dir.mkdir(parents=True, exist_ok=True)

    plants = load_existing_plants(
        Path("Data") / "ExistingPlants_wPosition.csv",
        Path("Data") / "NewVRE.xlsx",
    )
    scenarios = build_weight_scenarios()

    all_validation = []
    all_summary = []

    for scenario_name, weights in scenarios.items():
        print(f"\nRunning scenario: {scenario_name}")
        scenario_dir = sensitivity_dir / scenario_name
        scenario_dir.mkdir(parents=True, exist_ok=True)

        ds = compose_final_si(weights, output_dir)
        validation = validate_existing_plants(ds, plants, scenario_name, sample_window)
        summary = summarize_scenario(ds, validation, scenario_name)

        validation.to_csv(scenario_dir / "existing_plant_validation.csv", index=False)
        summary.to_csv(scenario_dir / "scenario_summary.csv", index=False)
        if write_rasters:
            ds.to_netcdf(scenario_dir / "xr_final_SI_all.nc")

        all_validation.append(validation)
        all_summary.append(summary)
        ds.close()

    pd.concat(all_validation, ignore_index=True).to_csv(sensitivity_dir / "existing_plant_validation_all.csv", index=False)
    pd.concat(all_summary, ignore_index=True).to_csv(sensitivity_dir / "scenario_summary_all.csv", index=False)
    print(f"\nSensitivity outputs written to: {sensitivity_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run weight sensitivity scenarios and validate existing plants against each SI map."
    )
    parser.add_argument(
        "--write-rasters",
        action="store_true",
        help="Also write full NetCDF rasters for each scenario. This is slow and uses several GB.",
    )
    parser.add_argument(
        "--sample-window",
        type=int,
        default=51,
        help="Odd-sized local window, in raster cells, used to validate existing plants against final masked SI maps.",
    )
    args = parser.parse_args()
    run_sensitivity_validation(write_rasters=args.write_rasters, sample_window=args.sample_window)
