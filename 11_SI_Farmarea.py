import xarray as xr
import numpy as np
from pathlib import Path

def process_farm_area_suitability():
    print("Starting Farm Area Suitability Processing...")

    # Paths
    output_dir = Path("Output")
    final_output_path = output_dir / "xr_final_SI_all.nc"

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
    weights = {
        'Wind':    [0.0909, 0.0909, 0.0909, 0.0909, 0.0909, 0.0909, 0.0909, 0.0909, 0.0909, 0.0909, 0.0909],
        'Solar':   [0.0909, 0.0909, 0.0909, 0.0909, 0.0909, 0.0909, 0.0909, 0.0909, 0.0909, 0.0909, 0.0909],
        'Biomass': [0.125,  0.125,  0.125,  0.125,  0.125,  0.0,    0.125,  0.125,  0.0,    0.125,  0.0],
        'BGEC':    [0.125,  0.125,  0.125,  0.125,  0.125,  0.0,    0.125,  0.125,  0.0,    0.125,  0.0],
        'BGWW':    [0.125,  0.125,  0.125,  0.125,  0.125,  0.0,    0.125,  0.125,  0.0,    0.125,  0.0],
        'MSW':     [0.125,  0.125,  0.125,  0.125,  0.125,  0.0,    0.125,  0.125,  0.0,    0.125,  0.0],
        'IEW':     [0.125,  0.125,  0.125,  0.125,  0.125,  0.0,    0.125,  0.125,  0.0,    0.125,  0.0],
    }

    # --- STEP 0: Initialization & Landcover ---
    print("Processing Step 0: Landcover & Template Setup...")
    xr_landcover = xr.open_dataset(output_dir / 'xr_SI_Landcover.nc')
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
    suitablearea_bio = 150 # km2
    rolgrid_bio = int(np.ceil(np.sqrt(suitablearea_bio / areapergrid)))

    for t in bio_techs:
        cf = (convert_ktoe_to_mbtu / heatrates[t]) / (plantfactors[t] * 8760)
        xr_final_SI[f'A_{t}'] = xr_final_SI[f'A_{t}'] * cf

        # Mask available area based on A_{t} > 0
        aa_bio = xr.where(xr_final_SI[f'A_{t}'] > 0, areapergrid, 0)
        cal_si_bio = aa_bio.rolling(lon=rolgrid_bio, lat=rolgrid_bio, min_periods=1, center=True).sum()
        cal_si_bio = xr.where(aa_bio == 0, 0, cal_si_bio)

        # Assign suitability index tier based on area thresholds
        fra_si_bio = xr.where(cal_si_bio >= suitablearea_bio, 3, 0)
        fra_si_bio = xr.where((cal_si_bio >= 100) & (cal_si_bio < suitablearea_bio), 2, fra_si_bio)
        fra_si_bio = xr.where(cal_si_bio < 100, 0, fra_si_bio)

        xr_farmarea[f'SI_{t}'] = fra_si_bio.astype(np.float32)
        xr_final_SI[f'SI_{t}'] += fra_si_bio * weights[t][10]
        xr_final_SI[f'SI_{t}'] = xr.where(xr_final_SI[f'AVA_{t}'] == 0, 0, xr_final_SI[f'SI_{t}'])

    farmarea_output_path = output_dir / "xr_SI_Farmarea.nc"
    print(f"Saving Farm Area SI to {farmarea_output_path}...")
    xr_farmarea.to_netcdf(path=farmarea_output_path)
    xr_farmarea.close()

    # Print Output Summary
    print("\n--- Processing Summary ---")
    for t in all_techs:
        print(f"{t:7s} -> Max SI: {float(xr_final_SI[f'SI_{t}'].max()):.4f} | Sum AVA: {float(xr_final_SI[f'AVA_{t}'].sum()):.2f}")

    print(f"\nSaving final processed dataset to {final_output_path}...")
    try:
        xr_final_SI.to_netcdf(path=final_output_path)
        print("Successfully saved final dataset.")
    except PermissionError as e:
        print(f"Permission Error: {e}. Ensure the file is not open in another program.")
        
    xr_final_SI.close()

if __name__ == "__main__":
    process_farm_area_suitability()