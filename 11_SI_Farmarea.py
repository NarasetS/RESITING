import argparse
import xarray as xr
import numpy as np
from pathlib import Path
import json

def _apply_exclusion_mask(ds, exclusion_mask, label):
    if exclusion_mask is None:
        return ds

    mask = exclusion_mask.reindex_like(ds, method=None).fillna(False)
    vars_to_zero = [
        var
        for var in ds.data_vars
        if var == "lccs_class" or var.startswith("SI_") or var.startswith("AVA_") or var.startswith("A_")
    ]

    print(f"Applying {label} exclusion mask to {len(vars_to_zero)} variables...")
    for var in vars_to_zero:
        ds[var] = xr.where(mask, 0, ds[var])
    return ds


def process_farm_area_suitability(
    landcover_path=None,
    final_output_path=None,
    farmarea_output_path=None,
    exclusion_mask=None,
    bio_capacity_source="resourcepotential",
    weight_source="empirical",
    weights_path=None,
    weights_override=None,
    write_outputs=True,
    return_dataset=False,
    run_label="full-area",
):
    """Build one final SI dataset.

    This function does not run weight-factor evaluation. Sensitivity/evaluation
    scripts may call it with weights_override, but normal reruns of this file
    build only one final SI using the current selected/default weights.
    """
    print(f"Starting Farm Area Suitability Processing ({run_label})...")

    # Paths
    output_dir = Path("Output")
    landcover_path = Path(landcover_path) if landcover_path else output_dir / "xr_SI_Landcover.nc"
    final_output_path = Path(final_output_path) if final_output_path else output_dir / "xr_final_SI_all.nc"
    farmarea_output_path = Path(farmarea_output_path) if farmarea_output_path else output_dir / "xr_SI_Farmarea.nc"

    # Constants
    lccs_resolution = 300  # meters
    areapergrid = (lccs_resolution / 1000) ** 2  # km2

    all_techs = ['Wind', 'Solar', 'Biomass', 'BGEC', 'BGWW', 'MSW', 'IEW']
    bio_techs = ['Biomass', 'BGEC', 'BGWW', 'MSW', 'IEW']
    ws_techs = ['Wind', 'Solar']

    # Weights Configuration
    # Each list contains 11 weights corresponding to the following criteria (steps 0 to 10):
    # [0: Landcover, 1: Slope, 2: Elevation, 3: Dist to settlement, 4: Dist to wetland, 
    #  5: Dist to forest, 6: Dist to road, 7: Dist to substation, 8: Resource potential, 
    #  9: Land Cost, 10: Farm/Feedstock Area]
    criteria_names = [
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

    default_weights = {
        'Wind':    [0.0909, 0.0909, 0.0909, 0.0909, 0.0909, 0.0909, 0.0909, 0.0909, 0.0909, 0.0909, 0.0909],
        'Solar':   [0.0909, 0.0909, 0.0909, 0.0909, 0.0909, 0.0909, 0.0909, 0.0909, 0.0909, 0.0909, 0.0909],
        'Biomass': [0.125,  0.125,  0.125,  0.125,  0.125,  0.0,    0.125,  0.125,  0.0,    0.125,  0.0],
        'BGEC':    [0.125,  0.125,  0.125,  0.125,  0.125,  0.0,    0.125,  0.125,  0.0,    0.125,  0.0],
        'BGWW':    [0.125,  0.125,  0.125,  0.125,  0.125,  0.0,    0.125,  0.125,  0.0,    0.125,  0.0],
        'MSW':     [0.125,  0.125,  0.125,  0.125,  0.125,  0.0,    0.125,  0.125,  0.0,    0.125,  0.0],
        'IEW':     [0.125,  0.125,  0.125,  0.125,  0.125,  0.0,    0.125,  0.125,  0.0,    0.125,  0.0],
    }

    def normalize_weight_values(raw_weights):
        """Accept either the old list format or the readable title:value format."""
        if isinstance(raw_weights, list):
            return raw_weights
        if isinstance(raw_weights, dict):
            return [raw_weights.get(criteria_name, 0.0) for criteria_name in criteria_names]
        return []

    def print_weight_summary(tech, weight_values):
        readable_weights = ", ".join(
            f"{criteria}: {value:.4f}"
            for criteria, value in zip(criteria_names, weight_values)
        )
        print(f"  -> {tech}: {readable_weights}")

    weight_files = {
        "empirical": Path("weightfactors") / "empirical_weights.json",
    }

    def load_weight_file(path):
        with open(path, "r") as f:
            raw_weights = json.load(f)

        loaded = {}
        for tech in all_techs:
            loaded[tech] = normalize_weight_values(raw_weights.get(tech))
        return loaded

    if weights_override is not None:
        print("Using supplied scenario weights.")
        weights = {
            tech: normalize_weight_values(weights_override.get(tech))
            for tech in all_techs
        }
    elif weight_source == "default":
        print("Using default heuristic weights.")
        weights = default_weights.copy()
    else:
        weights = default_weights.copy()
        selected_weights_path = Path(weights_path) if weights_path else weight_files[weight_source]

    if weights_override is None and weight_source in weight_files:
        print(f"Loading {weight_source} weights from {selected_weights_path}...")
        try:
            loaded_weights = load_weight_file(selected_weights_path)
            for tech in all_techs:
                if len(loaded_weights[tech]) == len(criteria_names):
                    weights[tech] = loaded_weights[tech]
                    print(f"  -> Applied {weight_source} weights for {tech}")
                    print_weight_summary(tech, weights[tech])
        except Exception as e:
            print(f"  -> Failed to load {weight_source} weights ({e}). Falling back to defaults.")

    for tech in all_techs:
        if len(weights.get(tech, [])) != len(criteria_names):
            weights[tech] = default_weights[tech]
            print(f"  -> Invalid weights for {tech}; falling back to defaults.")

    # --- STEP 0: Initialization & Landcover ---
    print("Processing Step 0: Landcover & Template Setup...")
    xr_landcover = xr.open_dataset(landcover_path)
    xr_final_SI = xr_landcover.copy(deep=True)

    for t in all_techs:
        # Initialize AVA arrays: grid area if landcover SI > 0, else 0
        xr_final_SI[f'AVA_{t}'] = xr.where(xr_landcover[f'SI_{t}'] > 0, np.float32(areapergrid), np.float32(0.0))
        # Initialize SI arrays applying the first weight
        xr_final_SI[f'SI_{t}'] = (xr_landcover[f'SI_{t}'] * weights[t][0]).astype(np.float32)

    xr_landcover.close()

    # Define sequence for steps 1 through 9
    # Format: (Step ID, Filename, Variable Template, Update AVA Mask?, Applicable Techs)
    steps = [
        (1, 'xr_SI_Slope.nc', 'SI_{t}', True, all_techs),
        (2, 'xr_SI_Elevation.nc', 'SI_{t}', False, all_techs),
        (3, 'xr_SI_Distancetosettlementarea.nc', 'SI_{t}', True, all_techs),
        (4, 'xr_SI_Distancetowetland.nc', 'SI_{t}', False, all_techs),
        (5, 'xr_SI_Distancetoforest.nc', 'SI_{t}', True, ws_techs),
        (6, 'xr_SI_Distancetoroad.nc', 'SI_{t}', True, all_techs),
        (7, 'xr_SI_Distancetosubstation.nc', 'SI_DtoSubs', False, all_techs),
        (8, 'xr_SI_resourcepotential.nc', 'SI_{t}', True, ws_techs),
        (9, 'xr_SI_LandCost.nc', 'land_cost_avg_price_norm', False, all_techs),
    ]

    # --- STEPS 1-9: Iteratively apply criteria ---
    for step_idx, fname, var_tpl, update_ava, affected_techs in steps:
        print(f"Processing Step {step_idx}: {fname}...")
        ds = xr.open_dataset(output_dir / fname)

        for t in affected_techs:
            var_name = var_tpl.format(t=t)
            
            # Add weighted score
            xr_final_SI[f'SI_{t}'] += (ds[var_name] * weights[t][step_idx]).astype(np.float32)

            # Cutout unavailable areas (AVA = 0)
            if update_ava:
                xr_final_SI[f'AVA_{t}'] = xr.where(ds[var_name] == 0, 0, xr_final_SI[f'AVA_{t}'])

            # Apply AVA mask to the SI score
            xr_final_SI[f'SI_{t}'] = xr.where(xr_final_SI[f'AVA_{t}'] == 0, 0, xr_final_SI[f'SI_{t}'])

        ds.close()

    # Apply optional site exclusions before farm/feedstock calculations so rolling
    # area checks and available capacity are recomputed on the investment-ready area.
    xr_final_SI = _apply_exclusion_mask(xr_final_SI, exclusion_mask, run_label)

    # --- STEP 10: Farm Area calculations ---
    print("Processing Step 10: Farm Area for Wind and Solar...")
    suitablearea_wind = 4.0  # km2
    suitablearea_solar = 0.4 # km2

    rolgrid_wind = int(np.ceil(np.sqrt(suitablearea_wind / areapergrid)))
    rolgrid_solar = int(np.ceil(np.sqrt(suitablearea_solar / areapergrid)))

    # Initialize Dataset to store the separated Farm Area SIs
    xr_farmarea = xr.Dataset(coords=xr_final_SI.coords)

    # Wind Farm Area
    fra_wind = xr_final_SI['AVA_Wind'].rolling(lon=rolgrid_wind, lat=rolgrid_wind, min_periods=1, center=True).sum()
    fra_wind = xr.where(xr_final_SI['AVA_Wind'] == 0, 0, fra_wind)
    fra_wind = xr.where(fra_wind >= suitablearea_wind, 3, 0)
    xr_farmarea['SI_Wind'] = fra_wind.astype(np.float32)
    xr_final_SI['SI_Wind'] += fra_wind * weights['Wind'][10]

    # Solar Farm Area
    fra_solar = xr_final_SI['AVA_Solar'].rolling(lon=rolgrid_solar, lat=rolgrid_solar, min_periods=1, center=True).sum()
    fra_solar = xr.where(xr_final_SI['AVA_Solar'] == 0, 0, fra_solar)
    fra_solar = xr.where(fra_solar >= suitablearea_solar, 3, 0)
    xr_farmarea['SI_Solar'] = fra_solar.astype(np.float32)
    xr_final_SI['SI_Solar'] += fra_solar * weights['Solar'][10]

    # --- Feedstock Area for fuel-based plant ---
    print("Processing Step 10: Feedstock Area for Bio/Waste plants...")
    heatrates = {
        'Biomass': 17.064, 'BGEC': 9.950, 'BGWW': 9.950, 'MSW': 14.838, 'IEW': 14.838
    }
    plantfactors = {
        'Biomass': 0.7, 'BGEC': 0.7, 'BGWW': 0.7, 'MSW': 0.44, 'IEW': 0.7
    }
    convert_ktoe_to_mbtu = 39652.608749183

    # Load the resource potential dataset to get the raw ktoe values for bio techs
    ds_res = xr.open_dataset(output_dir / 'xr_SI_resourcepotential.nc')

    for t in bio_techs:
        cf = (convert_ktoe_to_mbtu / heatrates[t]) / (plantfactors[t] * 8760)
        
        # Extract the raw resource potential (ktoe) and convert to Available Capacity (MW)
        if bio_capacity_source == "landcover" and f'A_{t}' in xr_final_SI.data_vars:
            raw_potential = xr_final_SI[f'A_{t}']
            xr_final_SI[f'A_{t}'] = (raw_potential * cf).astype(np.float32)
        elif f'A_{t}' in ds_res.data_vars:
            raw_potential = ds_res[f'A_{t}']
            xr_final_SI[f'A_{t}'] = (raw_potential * cf).astype(np.float32)
        else:
            print(f"Warning: A_{t} not found in xr_SI_resourcepotential.nc. Checking existing final_SI...")
            if f'A_{t}' in xr_final_SI.data_vars:
                xr_final_SI[f'A_{t}'] = (xr_final_SI[f'A_{t}'] * cf).astype(np.float32)
            else:
                xr_final_SI[f'A_{t}'] = xr.zeros_like(xr_final_SI[f'AVA_{t}'])

    ds_res.close()

    xr_final_SI = _apply_exclusion_mask(xr_final_SI, exclusion_mask, run_label)

    if write_outputs:
        print(f"Saving Farm Area SI to {farmarea_output_path}...")
        xr_farmarea.to_netcdf(path=farmarea_output_path)
    xr_farmarea.close()

    # Print Output Summary
    print("\n--- Processing Summary ---")
    for t in all_techs:
        sum_cap = f" | Sum Cap: {float(xr_final_SI[f'A_{t}'].sum()):.2f} MW" if t in bio_techs else ""
        print(f"{t:7s} -> Max SI: {float(xr_final_SI[f'SI_{t}'].max()):.4f} | Sum AVA: {float(xr_final_SI[f'AVA_{t}'].sum()):.2f}{sum_cap}")

    if write_outputs:
        print(f"\nSaving final processed dataset to {final_output_path}...")
        try:
            xr_final_SI.to_netcdf(path=final_output_path)
            print("Successfully saved final dataset.")
        except PermissionError as e:
            print(f"Permission Error: {e}. Ensure the file is not open in another program.")

    if return_dataset:
        return xr_final_SI

    xr_final_SI.close()
    return None

if __name__ == "__main__":
    # Production/full-area build only. Relative-importance weight generation
    # lives in weightfactors/evaluate_weight_factors.py and is never triggered here.
    parser = argparse.ArgumentParser(description="Build the full-area final SI dataset.")
    parser.add_argument(
        "--weight-source",
        choices=["default", "empirical"],
        default="empirical",
        help="Weight source for the production SI build.",
    )
    parser.add_argument(
        "--weights-file",
        default=None,
        help="Optional custom JSON empirical weight file.",
    )
    args = parser.parse_args()
    process_farm_area_suitability(weight_source=args.weight_source, weights_path=args.weights_file)
