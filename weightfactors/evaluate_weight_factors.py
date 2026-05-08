import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from sklearn.ensemble import RandomForestClassifier


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

TRAINING_CRITERIA_FILES = [
    ("Landcover", "xr_SI_Landcover.nc", "SI_{tech}"),
    ("Slope", "xr_SI_Slope.nc", "SI_{tech}"),
    ("Elevation", "xr_SI_Elevation.nc", "SI_{tech}"),
    ("Distance to settlement", "xr_SI_Distancetosettlementarea.nc", "SI_{tech}"),
    ("Distance to wetland", "xr_SI_Distancetowetland.nc", "SI_{tech}"),
    ("Distance to forest", "xr_SI_Distancetoforest.nc", "SI_{tech}"),
    ("Distance to road", "xr_SI_Distancetoroad.nc", "SI_{tech}"),
    ("Distance to substation", "xr_SI_Distancetosubstation.nc", "SI_DtoSubs"),
    ("Resource potential", "xr_SI_resourcepotential.nc", "SI_{tech}"),
    ("Land cost", "xr_SI_LandCost.nc", "land_cost_avg_price_norm"),
]

ALL_TECHS = ["Wind", "Solar", "Biomass", "BGEC", "BGWW", "MSW", "IEW"]


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


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
        raise ValueError("No usable existing or committed plant data was found.")

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
    df_all = df_all.dropna(subset=["Tech_Standard"]).copy()
    print("\nExisting/committed plants mapped by technology:")
    print(df_all["Tech_Standard"].value_counts().to_string())
    return df_all


def sample_local_positive(data_array, lat, lon, window_size=11, method="mean"):
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
    if method == "mean":
        return float(np.mean(positive_values))
    if method == "median":
        return float(np.median(positive_values))
    if method == "max":
        return float(np.max(positive_values))
    raise ValueError(f"Unsupported sampling method: {method}")


def extract_si_features(df_tech, output_dir, tech_name, sample_method="mean"):
    features = []
    for criteria_name, fname, var_template in TRAINING_CRITERIA_FILES:
        var_name = var_template.format(tech=tech_name)
        fpath = output_dir / fname
        if not fpath.exists():
            print(f"Warning: {criteria_name} file not found at {fpath}. Filling with 0.")
            features.append(np.zeros(len(df_tech)))
            continue

        with xr.open_dataset(fpath) as ds:
            if var_name not in ds.data_vars:
                print(f"Warning: {var_name} not found in {fpath}. Filling {criteria_name} with 0.")
                features.append(np.zeros(len(df_tech)))
                continue

            data = ds[var_name]
            sampled_vals = [
                sample_local_positive(data, lat, lon, window_size=11, method=sample_method)
                for lat, lon in zip(df_tech["Latitude"].values, df_tech["Longitude"].values)
            ]
            features.append(np.nan_to_num(np.array(sampled_vals, dtype=float), nan=0.0))

    return np.column_stack(features)


def generate_background_absence(num_points, output_dir, tech_name, rng):
    resource_path = output_dir / "xr_SI_resourcepotential.nc"
    fallback_path = output_dir / "xr_SI_Slope.nc"
    var_name = f"SI_{tech_name}"

    with xr.open_dataset(resource_path) as ds:
        if var_name in ds.data_vars:
            valid_mask = ds[var_name].values > 0
            lats = ds.lat.values
            lons = ds.lon.values
            source_label = resource_path.name
        else:
            print(f"Warning: {var_name} not found in {resource_path}; falling back to slope suitability.")
            with xr.open_dataset(fallback_path) as fallback_ds:
                valid_mask = fallback_ds[var_name].values > 0
                lats = fallback_ds.lat.values
                lons = fallback_ds.lon.values
            source_label = fallback_path.name

    valid_indices = np.argwhere(valid_mask)
    if len(valid_indices) == 0:
        raise ValueError(f"No valid background cells found for {tech_name}; cannot generate pseudo-absence points.")

    replace = num_points > len(valid_indices)
    if replace:
        print(
            f"Warning: requested {num_points} background points for {tech_name}, "
            f"but only {len(valid_indices)} valid cells are available. Sampling with replacement."
        )

    sampled_idx = valid_indices[rng.choice(len(valid_indices), num_points, replace=replace)]
    print(f"  {tech_name}: pseudo-absence source = {source_label}")
    return pd.DataFrame(
        {
            "Latitude": lats[sampled_idx[:, 0]],
            "Longitude": lons[sampled_idx[:, 1]],
            "Tech_Standard": tech_name,
        }
    )


def generate_empirical_weights(output_dir, data_dir, out_weights_file):
    print("Generating empirical relative-importance weights...")
    print("Feature sampling: mean of positive SI values in an 11x11 neighborhood.")
    print("Pseudo-absence sampling: random resource-potential-suitable grid cells, 3 per existing/committed plant.")

    plants = load_existing_plants(
        data_dir / "ExistingPlants_wPosition.csv",
        data_dir / "NewVRE.xlsx",
    )

    tech_groups = {
        "Wind": ["Wind"],
        "Solar": ["Solar"],
        "Biomass": ["Biomass"],
        "Biogas": ["BGEC", "BGWW"],
        "Waste": ["MSW", "IEW"],
    }

    rng = np.random.default_rng(42)
    empirical_weights = {}

    for group_name, techs in tech_groups.items():
        print(f"\nAnalyzing group: {group_name} ({', '.join(techs)})")
        x_presence_list = []
        x_absence_list = []
        total_plants = 0

        for tech in techs:
            df_tech = plants[plants["Tech_Standard"] == tech]
            total_plants += len(df_tech)
            if len(df_tech) == 0:
                continue

            x_presence_list.append(extract_si_features(df_tech, output_dir, tech))
            df_bg = generate_background_absence(len(df_tech) * 3, output_dir, tech, rng)
            print(f"  {tech}: {len(df_tech)} presence points, {len(df_bg)} pseudo-absence points")
            x_absence_list.append(extract_si_features(df_bg, output_dir, tech))

        if total_plants < 5:
            print(f"Not enough data for {group_name} ({total_plants}); fallback will use default weights.")
            continue

        x_presence = np.vstack(x_presence_list)
        x_absence = np.vstack(x_absence_list)
        x = np.vstack([x_presence, x_absence])
        y = np.concatenate([np.ones(len(x_presence)), np.zeros(len(x_absence))])

        rf = RandomForestClassifier(n_estimators=200, random_state=42, class_weight="balanced")
        rf.fit(x, y)
        importances = np.append(rf.feature_importances_, 0.0)

        for tech in techs:
            empirical_weights[tech] = {
                criteria: float(value)
                for criteria, value in zip(CRITERIA_NAMES, importances)
            }

        for criteria, value in zip(CRITERIA_NAMES, importances):
            print(f"  {criteria:25s}: {value:.4f}")

    write_json(out_weights_file, empirical_weights)
    print(f"\nEmpirical weights written to: {out_weights_file}")


def main():
    parser = argparse.ArgumentParser(description="Generate empirical relative-importance weights.")
    parser.add_argument("--output-dir", default="Output")
    parser.add_argument("--data-dir", default="Data")
    parser.add_argument("--weights-dir", default="weightfactors")
    parser.add_argument("--output-file", default=None)
    args = parser.parse_args()

    weights_dir = Path(args.weights_dir)
    output_file = Path(args.output_file) if args.output_file else weights_dir / "empirical_weights.json"
    generate_empirical_weights(
        output_dir=Path(args.output_dir),
        data_dir=Path(args.data_dir),
        out_weights_file=output_file,
    )


if __name__ == "__main__":
    main()
