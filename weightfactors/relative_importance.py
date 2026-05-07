import pandas as pd
import xarray as xr
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import json
from pathlib import Path

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

def load_existing_plants(csv_path, xlsx_path):
    """
    Load and standardize existing power plant coordinates.
    Adjust the column names based on your actual data structure.
    """
    print("Loading existing plant data...")
    plants = []
    
    lat_opts = ['latitude', 'lat', 'y']
    lon_opts = ['longitude', 'lon', 'long', 'x']
    # Ordered by highest priority first. "type" is generic and should be checked last.
    tech_opts = ['fuel', 'fuel type', 'fueltypename', 'technology', 'tech', 'energy_source', 'plant_type', 'planttype', 'type']
    
    def extract_relevant_data(df, source_name):
        df_cols_lower = [str(c).strip().lower() for c in df.columns]
        
        # Find columns based on priority list
        lat_col = next((df.columns[df_cols_lower.index(opt)] for opt in lat_opts if opt in df_cols_lower), None)
        lon_col = next((df.columns[df_cols_lower.index(opt)] for opt in lon_opts if opt in df_cols_lower), None)
        tech_col = next((df.columns[df_cols_lower.index(opt)] for opt in tech_opts if opt in df_cols_lower), None)
        
        if lat_col and lon_col and tech_col:
            print(f"  [{source_name}] Using columns: Lat='{lat_col}', Lon='{lon_col}', Tech='{tech_col}'")
            df_sub = df[[lat_col, lon_col, tech_col]].copy()
            df_sub.columns = ['Latitude', 'Longitude', 'Technology']
            return df_sub
        else:
            print(f"Warning: {source_name} is missing required columns.")
            print(f"Found columns: {list(df.columns)}")
            return None

    if Path(csv_path).exists():
        df_csv = pd.read_csv(csv_path)
        df_sub = extract_relevant_data(df_csv, "CSV")
        if df_sub is not None:
            plants.append(df_sub)
            
    if Path(xlsx_path).exists():
        df_xlsx = pd.read_excel(xlsx_path)
        df_sub = extract_relevant_data(df_xlsx, "Excel")
        if df_sub is not None:
            plants.append(df_sub)
            
    if not plants:
        raise ValueError("Could not find required columns in plant data files. Check the printed columns above.")
        
    df_all = pd.concat(plants, ignore_index=True).dropna(subset=['Latitude', 'Longitude'])
    df_all['Latitude'] = pd.to_numeric(df_all['Latitude'], errors='coerce')
    df_all['Longitude'] = pd.to_numeric(df_all['Longitude'], errors='coerce')
    invalid_coords = df_all['Latitude'].isna() | df_all['Longitude'].isna()
    if invalid_coords.any():
        print(f"Warning: Dropping {int(invalid_coords.sum())} rows with non-numeric coordinates.")
        df_all = df_all.loc[~invalid_coords].copy()
    
    def standardize_tech(t):
        t_upper = str(t).strip().upper()
        if 'WIND' in t_upper: return 'Wind'
        if 'SOLAR' in t_upper: return 'Solar'
        if 'BIOMASS' in t_upper: return 'Biomass'
        if 'BGWW' in t_upper or 'WASTEWATER' in t_upper: return 'BGWW'
        if 'BIOGAS' in t_upper or 'BGEC' in t_upper: return 'BGEC'
        if 'IEW' in t_upper or 'INDUSTRIAL' in t_upper: return 'IEW'
        if 'MSW' in t_upper or 'MUNICIPAL' in t_upper or 'WASTE' in t_upper: return 'MSW'
        return None
        
    # Find and print unmapped values so you can debug what strings are failing
    unmapped_raw = df_all[df_all['Technology'].apply(standardize_tech).isna()]['Technology'].dropna().unique()
    if len(unmapped_raw) > 0:
        print(f"\nWarning: Could not map these raw values from your files: {unmapped_raw}")
        
    df_all['Tech_Standard'] = df_all['Technology'].apply(standardize_tech)
    df_all = df_all.dropna(subset=['Tech_Standard'])
    
    # Print out the counts so you can see exactly how many plants matched
    print("\nTotal existing plants mapped by technology:")
    print(df_all['Tech_Standard'].value_counts().to_string())
    
    return df_all

def get_local_sample_value(data_array, lat, lon, window_size=11, method="median"):
    """
    Retrieves an SI value around a coordinate.
    Median neighborhood sampling is less optimistic than the previous max-nearby
    approach while still reducing the impact of masked plant footprint cells.
    """
    try:
        if not (
            float(data_array.lat.min()) <= lat <= float(data_array.lat.max())
            and float(data_array.lon.min()) <= lon <= float(data_array.lon.max())
        ):
            return np.nan

        # Find the integer index of the nearest cell
        center = data_array.sel(lat=lat, lon=lon, method='nearest')
        lat_idx = int(np.abs(data_array.lat.values - center.lat.values).argmin())
        lon_idx = int(np.abs(data_array.lon.values - center.lon.values).argmin())

        center_value = float(center.values)
        if method == "nearest":
            return center_value if np.isfinite(center_value) else np.nan
        
        # Calculate the bounds of the window
        half_win = window_size // 2
        lat_start = max(0, lat_idx - half_win)
        lat_end = min(len(data_array.lat), lat_idx + half_win + 1)
        lon_start = max(0, lon_idx - half_win)
        lon_end = min(len(data_array.lon), lon_idx + half_win + 1)
        
        # Extract the window using integer slicing
        window = data_array.isel(lat=slice(lat_start, lat_end), lon=slice(lon_start, lon_end))
        
        window_values = window.values
        valid_vals = window_values[np.isfinite(window_values) & (window_values > 0)]
        if len(valid_vals) == 0:
            return 0.0
        if method == "median":
            return float(np.median(valid_vals))
        if method == "mean":
            return float(np.mean(valid_vals))
        if method == "max":
            return float(np.max(valid_vals))
        raise ValueError(f"Unsupported sampling method: {method}")
    except Exception:
        return np.nan
    
    return 0.0

def extract_si_features(df_tech, output_dir, tech_name, sample_method="median"):
    """
    Extracts the independent SI criteria values at point coordinates.
    The default median neighborhood sampler is a compromise between exact-cell
    sampling and the old max-neighborhood approach.
    """
    features = []
    for criteria_name, fname, var_template in TRAINING_CRITERIA_FILES:
        var_name = var_template.format(tech=tech_name)
        fpath = Path(output_dir) / fname
        if not fpath.exists():
            print(f"Warning: {criteria_name} file not found at {fpath}. Filling with 0.")
            features.append(np.zeros(len(df_tech)))
            continue
            
        with xr.open_dataset(fpath) as ds:
            if var_name in ds.data_vars:
                data = ds[var_name]
                sampled_vals = []
                for lat, lon in zip(df_tech['Latitude'].values, df_tech['Longitude'].values):
                    # Median sampling avoids overvaluing a point because of one high nearby cell.
                    val = get_local_sample_value(data, lat, lon, window_size=11, method=sample_method)
                    sampled_vals.append(val)
                sampled_vals = np.array(sampled_vals, dtype=float)
                failed_samples = np.isnan(sampled_vals)
                if failed_samples.any():
                    print(
                        f"Warning: {criteria_name} sampling failed for "
                        f"{int(failed_samples.sum())}/{len(sampled_vals)} {tech_name} points. Filling with 0."
                    )
                    sampled_vals = np.nan_to_num(sampled_vals, nan=0.0)
                features.append(sampled_vals)
            else:
                print(f"Warning: {var_name} not found in {fpath}. Filling {criteria_name} with 0.")
                features.append(np.zeros(len(df_tech)))
                
    # Shape: (num_plants, 10 criteria). Farm/feedstock area is appended after modeling
    # to avoid training weights on a layer generated by the weights themselves.
    return np.column_stack(features)

def generate_background_absence(num_points, output_dir, tech_name, rng):
    """
    Generates random background points for presence-vs-background training.
    These are pseudo-absence points, not confirmed rejected or unsuitable sites.
    """
    # Open one file to get the grid bounds and valid coordinates
    with xr.open_dataset(Path(output_dir) / 'xr_SI_Slope.nc') as ds:
        valid_mask = ds[f'SI_{tech_name}'].values > 0
        lats = ds.lat.values
        lons = ds.lon.values
        
    # Find all valid (lat, lon) indices
    valid_indices = np.argwhere(valid_mask)
    if len(valid_indices) == 0:
        raise ValueError(f"No valid slope cells found for {tech_name}; cannot generate background points.")
    
    # Randomly sample background points
    replace = num_points > len(valid_indices)
    if replace:
        print(
            f"Warning: Requested {num_points} background points for {tech_name}, "
            f"but only {len(valid_indices)} valid cells are available. Sampling with replacement."
        )
    sampled_idx = valid_indices[rng.choice(len(valid_indices), num_points, replace=replace)]
    
    df_bg = pd.DataFrame({
        'Latitude': lats[sampled_idx[:, 0]],
        'Longitude': lons[sampled_idx[:, 1]],
        'Tech_Standard': tech_name
    })
    return df_bg

def calculate_relative_importance():
    print("Starting Relative Importance Analysis...")
    print("Training mode: presence-vs-random-background pseudo-absence.")
    print("Sampling mode: median neighborhood.")
    
    # Configuration
    data_dir = Path("Data")
    output_dir = Path("Output") # Natively handles masks using neighborhood search
    out_weights_file = Path("weightfactors/empirical_weights.json")
    
    csv_path = data_dir / "ExistingPlants_wPosition.csv"
    xlsx_path = data_dir / "NewVRE.xlsx"
    
    # Load real plants
    df_plants = load_existing_plants(csv_path, xlsx_path)
    
    tech_groups = {
        'Wind': ['Wind'],
        'Solar': ['Solar'],
        'Biomass': ['Biomass'],
        'Biogas': ['BGEC', 'BGWW'],
        'Waste': ['MSW', 'IEW']
    }
    
    rng = np.random.default_rng(42)
    empirical_weights = {}
    
    for group_name, techs in tech_groups.items():
        print(f"\nAnalyzing Group: {group_name} ({', '.join(techs)})...")
        
        X_presence_list = []
        X_absence_list = []
        total_plants = 0
        
        for tech in techs:
            df_tech = df_plants[df_plants['Tech_Standard'] == tech]
            total_plants += len(df_tech)
            
            if len(df_tech) > 0:
                # 1. Get features for existing plants (Class 1)
                X_presence_list.append(extract_si_features(df_tech, output_dir, tech))
                
                # 2. Get pseudo-absence features (Class 0)
                df_bg = generate_background_absence(len(df_tech) * 3, output_dir, tech, rng)
                X_absence_list.append(extract_si_features(df_bg, output_dir, tech))
        
        if total_plants < 5:
            print(f"Not enough data for {group_name} (Found {total_plants}). Will fallback to defaults later.")
            continue
            
        X_presence = np.vstack(X_presence_list)
        X_absence = np.vstack(X_absence_list)
        
        # Combine
        X = np.vstack([X_presence, X_absence])
        y = np.concatenate([np.ones(len(X_presence)), np.zeros(len(X_absence))])
        
        # 3. Train Model to get Feature Importances
        rf = RandomForestClassifier(n_estimators=200, random_state=42, class_weight='balanced')
        rf.fit(X, y)
        
        # 4. Extract and normalize weights.
        # Farm/feedstock area is assigned 0 here because it is generated downstream
        # by 11_SI_Farmarea.py, which consumes these empirical weights.
        model_importances = rf.feature_importances_
        importances = np.append(model_importances, 0.0)
        
        # Distribute the group's weights to all individual technologies within it
        for tech in techs:
            empirical_weights[tech] = {
                criteria_name: float(importance)
                for criteria_name, importance in zip(CRITERIA_NAMES, importances)
            }
        
        print(f"Calculated Weights for {group_name}:")
        for criteria_name, importance in zip(CRITERIA_NAMES, importances):
            print(f"  {criteria_name:25s}: {importance:.4f}")
        
    # Save weights
    with open(out_weights_file, 'w') as f:
        json.dump(empirical_weights, f, indent=4)
    print(f"\nEmpirical weights saved to {out_weights_file}")

if __name__ == "__main__":
    calculate_relative_importance()
