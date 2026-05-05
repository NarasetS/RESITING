import linopy
import pandas as pd
import xarray as xr
import geopandas as gpd
import numpy as np
import folium
from pathlib import Path
 
# ======================================================================================================================
# 1. Configuration
# ----------------------------------------------------------------------------------------------------------------------
# Grid resolution, technology density assumptions, plant footprint size, and rolling-window sizes.
# The rolling window represents the area around a candidate plant center that is considered part of the plant footprint.
# ======================================================================================================================
coarsenscale = 10
lccs_resolution = 300 * coarsenscale #m
areapergrid = (lccs_resolution/1000) ** 2 ## km2
scenario_SI = 0  ## Include area where SI >= scenario_SI

mwperkm2_wind = 4.5 ## originally 9 MW/km2 but deduct by 50% of the technically available from IEA's Thailand CET
mwperkm2_solar = 15 ## originally 30 MW/km2 but deduct by 50% of the technically available from IEA's Thailand CET

mwpergrid_wind = np.round(areapergrid * mwperkm2_wind,2)
mwpergrid_solar =  np.round(areapergrid * mwperkm2_solar,2)

target_capacity_mw = 90
suitablearea_wind = target_capacity_mw / mwperkm2_wind
suitablearea_solar = target_capacity_mw / mwperkm2_solar

run_name = f'SSI_{scenario_SI}_CS_{coarsenscale}_TC_{target_capacity_mw}MW'
output_dir = Path('Output') / run_name
output_dir.mkdir(parents=True, exist_ok=True)

rollingwindow_wind = int(np.ceil(np.sqrt(suitablearea_wind/areapergrid)))
rollingwindow_solar = int(np.ceil(np.sqrt(suitablearea_solar/areapergrid)))

suitablearea_biomass = 100 ## km2 
suitablearea_bgec = 100 ## km2
suitablearea_msw = 100 ## km2

rollingwindow_biomass = int(np.ceil(np.sqrt(suitablearea_biomass/areapergrid)))
rollingwindow_bgec = int(np.ceil(np.sqrt(suitablearea_bgec/areapergrid)))
rollingwindow_msw = int(np.ceil(np.sqrt(suitablearea_msw/areapergrid)))

print('areapergrid = ',areapergrid)
print('mwpergrid_wind = ',mwpergrid_wind)
print('mwpergrid_solar = ',mwpergrid_solar)
print('rollingwindow_wind = ',rollingwindow_wind,' * ',rollingwindow_wind)
print('rollingwindow_solar = ',rollingwindow_solar,' * ',rollingwindow_solar)
print('rollingwindow_biomass = ',rollingwindow_biomass,' * ',rollingwindow_biomass)
print('rollingwindow_bgec = ',rollingwindow_bgec,' * ',rollingwindow_bgec)
print('rollingwindow_msw = ',rollingwindow_msw,' * ',rollingwindow_msw)

# Shared rolling helpers. Keeping these centralized avoids repeated long rolling expressions later in the model.
def rolling_sum(da, window):
    return da.rolling(lon=window, lat=window, min_periods=1, center=True).sum()

def rolling_mean_positive(da, window):
    return da.where(da > 0).rolling(lon=window, lat=window, min_periods=1, center=True).mean().fillna(0)

# ======================================================================================================================
# 2. Load and Preprocess Suitability Data
# ----------------------------------------------------------------------------------------------------------------------
# Apply the SI threshold, remove availability where SI is zero, coarsen the raster grid, and preserve selected min/max
# SI diagnostics from the original resolution.
# ======================================================================================================================
xr_final_SI_raw = xr.open_dataset('Output\\xr_final_SI_all.nc')
xr_final_SI_raw = xr_final_SI_raw.drop_vars('ADM1_EN')
# xr_final_SI_raw = xr_final_SI_raw.drop_vars('SI_BGEC')
# xr_final_SI_raw = xr_final_SI_raw.drop_vars('SI_BGWW')
# xr_final_SI_raw = xr_final_SI_raw.drop_vars('SI_MSW')
# xr_final_SI_raw = xr_final_SI_raw.drop_vars('SI_IEW')
# xr_final_SI_raw = xr_final_SI_raw.drop_vars('A_BGEC')
# xr_final_SI_raw = xr_final_SI_raw.drop_vars('A_BGWW')
# xr_final_SI_raw = xr_final_SI_raw.drop_vars('A_MSW')
# xr_final_SI_raw = xr_final_SI_raw.drop_vars('A_IEW')
# xr_final_SI_raw = xr_final_SI_raw.drop_vars('AVA_BGEC')
# xr_final_SI_raw = xr_final_SI_raw.drop_vars('AVA_BGWW')
# xr_final_SI_raw = xr_final_SI_raw.drop_vars('AVA_MSW')
# xr_final_SI_raw = xr_final_SI_raw.drop_vars('AVA_IEW')

xr_final_SI_raw['SI_Wind'] = xr.where(xr_final_SI_raw['SI_Wind'] >= scenario_SI ,xr_final_SI_raw['SI_Wind'],0)
xr_final_SI_raw['AVA_Wind'] = xr.where(xr_final_SI_raw['SI_Wind'] == 0 , 0 , xr_final_SI_raw['AVA_Wind'])

xr_final_SI_raw['SI_Solar'] = xr.where(xr_final_SI_raw['SI_Solar'] >= scenario_SI ,xr_final_SI_raw['SI_Solar'],0)
xr_final_SI_raw['AVA_Solar'] = xr.where(xr_final_SI_raw['SI_Solar'] == 0 , 0 , xr_final_SI_raw['AVA_Solar'])

xr_final_SI_raw['SI_Biomass'] = xr.where(xr_final_SI_raw['SI_Biomass'] >= scenario_SI ,xr_final_SI_raw['SI_Biomass'],0)
xr_final_SI_raw['AVA_Biomass'] = xr.where(xr_final_SI_raw['SI_Biomass'] == 0 , 0 , xr_final_SI_raw['AVA_Biomass'])

xr_final_SI_raw['SI_BGEC'] = xr.where(xr_final_SI_raw['SI_BGEC'] >= scenario_SI ,xr_final_SI_raw['SI_BGEC'],0)
xr_final_SI_raw['AVA_BGEC'] = xr.where(xr_final_SI_raw['SI_BGEC'] == 0 , 0 , xr_final_SI_raw['AVA_BGEC'])

xr_final_SI_raw['SI_MSW'] = xr.where(xr_final_SI_raw['SI_MSW'] >= scenario_SI ,xr_final_SI_raw['SI_MSW'],0)
xr_final_SI_raw['AVA_MSW'] = xr.where(xr_final_SI_raw['SI_MSW'] == 0 , 0 , xr_final_SI_raw['AVA_MSW'])

xr_final_SI = xr_final_SI_raw.coarsen(lat = coarsenscale, lon= coarsenscale, boundary='trim').sum()

# Average all SI variables dynamically (including individual sub-criteria SIs)
for var in xr_final_SI.data_vars:
    if var.startswith('SI_'):
        xr_final_SI[var] = xr_final_SI[var] / (coarsenscale**2)

# Preserve within-cell SI spread after coarsening for wind and solar diagnostics.
xr_final_SI['SI_Wind_max'] = xr_final_SI_raw['SI_Wind'].coarsen(lat = coarsenscale, lon= coarsenscale, boundary='trim').max()
xr_final_SI['SI_Wind_min'] = xr_final_SI_raw['SI_Wind'].coarsen(lat = coarsenscale, lon= coarsenscale, boundary='trim').min()
xr_final_SI['SI_Solar_max'] = xr_final_SI_raw['SI_Solar'].coarsen(lat = coarsenscale, lon= coarsenscale, boundary='trim').max()
xr_final_SI['SI_Solar_min'] = xr_final_SI_raw['SI_Solar'].coarsen(lat = coarsenscale, lon= coarsenscale, boundary='trim').min()

# ======================================================================================================================
# 3. Cache Rolling Footprint Metrics
# ----------------------------------------------------------------------------------------------------------------------
# These arrays are reused in max-capacity checks, constraints, objective scoring, CSV export, and mapping.
# rolling_cap_* is in MW for wind/solar and in the native capacity units for biomass/BGEC/MSW.
# rolling_avg_SI_* averages only cells with SI > 0 inside the footprint.
# ======================================================================================================================
tech_settings = {
    'wind': {'label': 'Wind', 'si': 'SI_Wind', 'ava': 'AVA_Wind', 'cap_source': 'AVA_Wind', 'density': mwperkm2_wind, 'window': rollingwindow_wind},
    'solar': {'label': 'Solar', 'si': 'SI_Solar', 'ava': 'AVA_Solar', 'cap_source': 'AVA_Solar', 'density': mwperkm2_solar, 'window': rollingwindow_solar},
    'biomass': {'label': 'Biomass', 'si': 'SI_Biomass', 'ava': 'AVA_Biomass', 'cap_source': 'A_Biomass', 'window': rollingwindow_biomass},
    'bgec': {'label': 'BGEC', 'si': 'SI_BGEC', 'ava': 'AVA_BGEC', 'cap_source': 'A_BGEC', 'window': rollingwindow_bgec},
    'msw': {'label': 'MSW', 'si': 'SI_MSW', 'ava': 'AVA_MSW', 'cap_source': 'A_MSW', 'window': rollingwindow_msw},
}

for settings in tech_settings.values():
    label = settings['label']
    window = settings['window']
    si = xr_final_SI[settings['si']]
    rolling_cap = rolling_sum(xr_final_SI[settings['cap_source']], window)
    if 'density' in settings:
        rolling_cap = rolling_cap * settings['density']
    xr_final_SI[f'rolling_AVA_{label}'] = rolling_sum(xr_final_SI[settings['ava']], window)
    xr_final_SI[f'rolling_cap_{label}'] = rolling_cap
    xr_final_SI[f'rolling_avg_SI_{label}'] = rolling_mean_positive(si, window)

xr_final_SI['rolling_sum_SI_Wind'] = rolling_sum(xr_final_SI['SI_Wind'], rollingwindow_wind)
xr_final_SI['rolling_sum_SI_Solar'] = rolling_sum(xr_final_SI['SI_Solar'], rollingwindow_solar)

# Maximum candidate footprint capacity by technology. These are used mainly for diagnostics and visualization scaling.
maxcap_wind = xr_final_SI['rolling_cap_Wind'].where(xr_final_SI['SI_Wind']>0).max()
maxcap_solar = xr_final_SI['rolling_cap_Solar'].where(xr_final_SI['SI_Solar']>0).max()
maxcap_biomass = xr_final_SI['rolling_cap_Biomass'].where(xr_final_SI['SI_Biomass']>0).max()
maxcap_bgec = xr_final_SI['rolling_cap_BGEC'].where(xr_final_SI['SI_BGEC']>0).max()
maxcap_msw = xr_final_SI['rolling_cap_MSW'].where(xr_final_SI['SI_MSW']>0).max()
print('maxcap_wind = ',maxcap_wind)
print('maxcap_solar = ',maxcap_solar)
print('maxcap_biomass = ',maxcap_biomass)
print('maxcap_bgec = ',maxcap_bgec)
print('maxcap_msw = ',maxcap_msw)


xr_final_SI_raw.close()
print(xr_final_SI.data_vars)
print("AVA Wind = ",xr_final_SI['AVA_Wind'].sum())
print("AVA Solar = ",xr_final_SI['AVA_Solar'].sum())
print("A_Biomass = ",xr_final_SI['A_Biomass'].sum())
print("A_BGEC = ",xr_final_SI['A_BGEC'].sum())
print("A_MSW = ",xr_final_SI['A_MSW'].sum())
print('Max SI_Wind = ',xr_final_SI['SI_Wind'].max())
print('Max SI_Solar = ',xr_final_SI['SI_Solar'].max())
print('Max SI_Biomass = ',xr_final_SI['SI_Biomass'].max())
print('Max SI_BGEC = ',xr_final_SI['SI_BGEC'].max())
print('Max SI_MSW = ',xr_final_SI['SI_MSW'].max())

# ======================================================================================================================
# 4. Assign Planning Regions to Grid Cells
# ----------------------------------------------------------------------------------------------------------------------
# Spatially join each coarsened grid-cell centroid to the provincial boundary layer, then attach the region label.
# ======================================================================================================================
region = pd.read_csv('Data\\Region.csv')
thailandmap = gpd.read_file('Data\\tha_admbnda_adm1_rtsd_20220121\\tha_admbnda_adm1_rtsd_20220121.shp')
thailandmap.crs = "EPSG:4326"
region_lookup = region.set_index('province')['region']
thailandmap['region'] = thailandmap['ADM1_TH'].map(region_lookup).fillna('xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx')
for missing_province in thailandmap.loc[thailandmap['region'] == 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx', 'ADM1_TH']:
    print(missing_province,'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx')
# thailandmap['center'] = thailandmap['geometry'].centroid
# thailandmap = thailandmap.set_geometry('center')
thailandmap = thailandmap.set_geometry('geometry')
thailandmap = thailandmap.drop(columns=['Shape_Leng',
                                        'Shape_Area',
                                        'ADM1_PCODE',
                                        'ADM1_REF',
                                        'ADM1ALT1EN',
                                        'ADM1ALT2EN',
                                        'ADM1ALT1TH',
                                        'ADM1ALT2TH',
                                        'ADM0_EN',
                                        'ADM0_TH',
                                        'ADM0_PCODE',
                                        'date',
                                        'validOn',
                                        'validTo'
                                        # ,'geometry'
                                        ])
df_final_SI = xr_final_SI.to_dataframe()
df_final_SI.reset_index(inplace=True)
df_final_SI = gpd.GeoDataFrame(df_final_SI, geometry =gpd.points_from_xy(df_final_SI['lon'],df_final_SI['lat']))
df_final_SI.crs = "EPSG:4326"
df_final_SI.reset_index(inplace= True, drop = False)
# df_final_SI_2 = gpd.sjoin_nearest(df_final_SI,thailandmap,how = 'left')
df_final_SI_2 = gpd.sjoin(predicate='within',left_df= df_final_SI, right_df= thailandmap,how = 'left')
df_final_SI_2 = df_final_SI_2.drop(columns=['ADM1_TH','geometry','index_right'])
df_final_SI_2 = df_final_SI_2.drop_duplicates('index')
df_final_SI_2 = df_final_SI_2.drop(columns=['index'])
df_final_SI_2.reset_index(inplace= True, drop = True)
df_final_SI_2 = df_final_SI_2.set_index(['lat', 'lon'])
xr_final_SI = xr.Dataset.from_dataframe(df_final_SI_2)

# ======================================================================================================================
# 5. Dataset Summary
# ----------------------------------------------------------------------------------------------------------------------
# Print sanity checks before building the optimization model.
# ======================================================================================================================
xr_ref = xr_final_SI
print("AVA Wind = ",xr_ref['AVA_Wind'].sum())
print("AVA Solar = ",xr_ref['AVA_Solar'].sum()) 
print("A_Biomass = ",xr_ref['A_Biomass'].sum())
print("A_BGEC = ",xr_ref['A_BGEC'].sum())
print("A_MSW = ",xr_ref['A_MSW'].sum())
print('Mean SI Wind = ',xr_ref['SI_Wind'].where(xr_ref['SI_Wind']>0).mean())
print('Mean SI Solar = ',xr_ref['SI_Solar'].where(xr_ref['SI_Solar']>0).mean())
print('Mean SI_Biomass = ',xr_ref['SI_Biomass'].where(xr_ref['SI_Biomass']>0).mean())
print('Mean SI_BGEC = ',xr_ref['SI_BGEC'].where(xr_ref['SI_BGEC']>0).mean())
print('Mean SI_MSW = ',xr_ref['SI_MSW'].where(xr_ref['SI_MSW']>0).mean())
print('Max SI Wind = ',xr_ref['SI_Wind'].max())
print('Max SI Solar = ',xr_ref['SI_Solar'].max())
print('Max SI Biomass = ',xr_ref['SI_Biomass'].max())
print('Max SI BGEC = ',xr_ref['SI_BGEC'].max())
print('Max SI MSW = ',xr_ref['SI_MSW'].max())
print('coarsenscale = ',coarsenscale)
print('areapergrid = ',areapergrid)
print('mwpergrid_wind = ',mwpergrid_wind)
print('mwpergrid_solar = ',mwpergrid_solar)

# ======================================================================================================================
# 6. PDP Capacity Quotas
# ----------------------------------------------------------------------------------------------------------------------
# These quotas drive the capacity that must be allocated by technology and region.
# ======================================================================================================================
enforce_total_quota = True
enforce_regional_quota = True

quotas = {
    'wind': {'R0': 0, 'R10': 3000, 'R11': 1840, 'R12': 1220, 'R2': 10940, 'R3': 800, 'R4': 2200},
    'solar': {'R0': 300, 'R10': 4000, 'R11': 4600, 'R12': 4600, 'R2': 25000, 'R3': 10000, 'R4': 15000},
    'biomass': {'R0': 0, 'R10': 110, 'R11': 75, 'R12': 80, 'R2': 420, 'R3': 220, 'R4': 280},
    'bgec': {'R0': 3, 'R10': 50, 'R11': 114, 'R12': 57, 'R2': 174, 'R3': 70, 'R4': 44},
    'msw': {'R0': 133, 'R10': 68, 'R11': 100, 'R12': 39, 'R2': 227, 'R3': 97, 'R4': 96}
}

quota_totals = {tech: sum(reg_quotas.values()) for tech, reg_quotas in quotas.items()}

for tech, total in quota_totals.items():
    print(f"quota_{tech}_total = {total}")

# ======================================================================================================================
# 7. Pre-Optimization Feasibility Check
# ----------------------------------------------------------------------------------------------------------------------
# Check whether requested quotas exceed physically available capacity by region or in total.
# This does not prove the MIP is feasible, but it catches obvious quota problems early.
# ======================================================================================================================
print("\n--- Pre-Optimization Quota Feasibility Check ---")
infeasible_precheck = False

avail_sources = {
    'wind': ('AVA_Wind', mwperkm2_wind),
    'solar': ('AVA_Solar', mwperkm2_solar),
    'biomass': ('A_Biomass', 1),
    'bgec': ('A_BGEC', 1),
    'msw': ('A_MSW', 1),
}
region_available = {}
for tech, (source_var, multiplier) in avail_sources.items():
    region_available[tech] = {}
    for region_name in quotas[tech].keys():
        mask = xr_ref['region'] == region_name
        region_available[tech][region_name] = float(xr_ref[source_var].where(mask, drop=True).sum() * multiplier)

def get_avail_cap(t, r):
    return region_available.get(t, {}).get(r, 0.0)

if enforce_regional_quota:
    for tech, reg_quotas in quotas.items():
        for reg, q_val in reg_quotas.items():
            if q_val > 0:
                avail = get_avail_cap(tech, reg)
                if q_val > avail:
                    print(f"  [!] WARNING: {tech.upper()} in {reg} requests {q_val} MW but only ~{avail:.2f} MW is physically available!")
                    infeasible_precheck = True
                else:
                    print(f"  [OK] {tech.upper()} in {reg} requests {q_val} MW (Max Available: ~{avail:.2f} MW)")

if enforce_total_quota:
    for tech, total_q in quota_totals.items():
        if total_q > 0:
            avail_total = sum(get_avail_cap(tech, r) for r in quotas[tech].keys())
            if total_q > avail_total:
                print(f"  [!] WARNING: {tech.upper()} TOTAL requests {total_q} MW but only ~{avail_total:.2f} MW is physically available!")
                infeasible_precheck = True

if infeasible_precheck:
    print(">>> SOME QUOTAS EXCEED AVAILABLE CAPACITY. The model is structurally infeasible and will use slack variables or fail. <<<")
else:
    print(">>> All requested quotas are within theoretical maximum available limits. <<<")
print("------------------------------------------------\n")

# ======================================================================================================================
# 8. Build Optimization Model
# ----------------------------------------------------------------------------------------------------------------------
# built_* is a binary decision: whether a plant center is selected at a grid cell.
# cap_* is a continuous decision: how much capacity is assigned to that selected cell.
# Variables are only created for technologies with positive total quota.
# ======================================================================================================================
m = linopy.Model()

built_wind = m.add_variables(binary=True, coords=xr_ref.coords, name='built_wind') if quota_totals['wind'] > 0 else None
cap_wind = m.add_variables(lower=0.00, coords=xr_ref.coords, name='cap_wind') if quota_totals['wind'] > 0 else None

built_solar = m.add_variables(binary=True, coords=xr_ref.coords, name='built_solar') if quota_totals['solar'] > 0 else None
cap_solar = m.add_variables(lower=0.00, coords=xr_ref.coords, name='cap_solar') if quota_totals['solar'] > 0 else None

built_biomass = m.add_variables(binary=True, coords=xr_ref.coords, name='built_biomass') if quota_totals['biomass'] > 0 else None
cap_biomass = m.add_variables(lower=0.00, coords=xr_ref.coords, name='cap_biomass') if quota_totals['biomass'] > 0 else None

built_bgec = m.add_variables(binary=True, coords=xr_ref.coords, name='built_bgec') if quota_totals['bgec'] > 0 else None
cap_bgec = m.add_variables(lower=0.00, coords=xr_ref.coords, name='cap_bgec') if quota_totals['bgec'] > 0 else None

built_msw = m.add_variables(binary=True, coords=xr_ref.coords, name='built_msw') if quota_totals['msw'] > 0 else None
cap_msw = m.add_variables(lower=0.00, coords=xr_ref.coords, name='cap_msw') if quota_totals['msw'] > 0 else None

# ----------------------------------------------------------------------------------------------------------------------
# 8a. Location Exclusion Constraint
# One selected plant footprint can occupy a rolling window. The combined rolling sum across technologies must stay <= 1,
# which prevents overlapping/too-close plant centers across all active technologies.
# ----------------------------------------------------------------------------------------------------------------------
built_terms = []
if built_wind is not None:
    built_terms.append(built_wind.rolling(lat = rollingwindow_wind,min_periods=1,center=True).sum().rolling(lon = rollingwindow_wind,min_periods=1,center=True).sum())
if built_solar is not None:
    built_terms.append(built_solar.rolling(lat = rollingwindow_solar,min_periods=1,center=True).sum().rolling(lon = rollingwindow_solar,min_periods=1,center=True).sum())
if built_biomass is not None:
    built_terms.append(built_biomass.rolling(lat = rollingwindow_biomass,min_periods=1,center=True).sum().rolling(lon = rollingwindow_biomass,min_periods=1,center=True).sum())
if built_bgec is not None:
    built_terms.append(built_bgec.rolling(lat = rollingwindow_bgec,min_periods=1,center=True).sum().rolling(lon = rollingwindow_bgec,min_periods=1,center=True).sum())
if built_msw is not None:
    built_terms.append(built_msw.rolling(lat = rollingwindow_msw,min_periods=1,center=True).sum().rolling(lon = rollingwindow_msw,min_periods=1,center=True).sum())

if built_terms:
    constr_built_logic = m.add_constraints(sum(built_terms) <= 1, name='constr_built_logic')

# ----------------------------------------------------------------------------------------------------------------------
# 8b. Capacity Upper Bounds
# Capacity can only be assigned where built_* = 1, and it cannot exceed the rolling footprint capacity at that location.
# The builtarea constraints also force plant centers onto cells with available area/feedstock.
# ----------------------------------------------------------------------------------------------------------------------
if built_wind is not None:
    constr_maxcap_wind = m.add_constraints(
        cap_wind <= (built_wind * xr_ref['rolling_cap_Wind'])
        ,name = 'constr_maxcap_wind'
    )
    constr_builtarea_wind = m.add_constraints(
        built_wind <= (xr_ref['AVA_Wind'] * 10000)
        ,name = 'constr_builtarea_wind'
    )

if built_solar is not None:
    constr_maxcap_solar = m.add_constraints(
        cap_solar <= (built_solar * xr_ref['rolling_cap_Solar'])
        ,name = 'constr_maxcap_solar'
    )
    constr_builtarea_solar = m.add_constraints(
        built_solar <= (xr_ref['AVA_Solar'] * 10000)
        ,name = 'constr_builtarea_solar'
    )

if built_biomass is not None:
    constr_maxcap_biomass = m.add_constraints(
        cap_biomass <= (built_biomass * xr_ref['rolling_cap_Biomass'])
        ,name = 'constr_maxcap_biomass'
    )
    constr_builtarea_biomass = m.add_constraints(
        built_biomass <= (xr_ref['AVA_Biomass'] * 10000)
        ,name = 'constr_builtarea_biomass'
    )

if built_bgec is not None:
    constr_maxcap_bgec = m.add_constraints(
        cap_bgec <= (built_bgec * xr_ref['rolling_cap_BGEC'])
        ,name = 'constr_maxcap_bgec'
    )
    constr_builtarea_bgec = m.add_constraints(
        built_bgec <= (xr_ref['AVA_BGEC'] * 10000)
        ,name = 'constr_builtarea_bgec'
    )

if built_msw is not None:
    constr_maxcap_msw = m.add_constraints(
        cap_msw <= (built_msw * xr_ref['rolling_cap_MSW'])
        ,name = 'constr_maxcap_msw'
    )
    constr_builtarea_msw = m.add_constraints(
        built_msw <= (xr_ref['AVA_MSW'] * 10000)
        ,name = 'constr_builtarea_msw'
    )

# ----------------------------------------------------------------------------------------------------------------------
# 8c. Quota Constraints
# Total quotas require each technology to hit its target. Regional quotas distribute that target across planning regions.
# With total equality active, the regional >= constraints behave like exact regional allocations when region quotas sum
# to the total quota.
# ----------------------------------------------------------------------------------------------------------------------
cap_vars = {}
if cap_wind is not None: cap_vars['wind'] = cap_wind
if cap_solar is not None: cap_vars['solar'] = cap_solar
if cap_biomass is not None: cap_vars['biomass'] = cap_biomass
if cap_bgec is not None: cap_vars['bgec'] = cap_bgec
if cap_msw is not None: cap_vars['msw'] = cap_msw

if enforce_total_quota:
    for tech, cap_var in cap_vars.items():
        m.add_constraints(cap_var.sum() == quota_totals[tech], name=f'constr_quota_{tech}_total')

if enforce_regional_quota:
    for tech, cap_var in cap_vars.items():
        for region_name, quota_val in quotas[tech].items():
            # Using '>=' for regional limits. Since the total quota is capped by the equality 
            # constraint above, this effectively acts as an exact distribution if the sum matches.
            m.add_constraints(
                lhs = cap_var.where(xr_ref['region'] == region_name, drop=True).sum(),
                sign = '>=', 
                rhs = quota_val, 
                name=f'constr_quota_{tech}_{region_name}'
            )

# ----------------------------------------------------------------------------------------------------------------------
# 8d. Objective Function
# Minimize the negative score, which is equivalent to maximizing capacity-weighted average SI.
# rolling_avg_SI_* excludes zero-SI cells inside the rolling footprint and returns 0 for all-zero windows.
# ----------------------------------------------------------------------------------------------------------------------
obj_terms = []
if quota_totals['wind'] > 0:
    obj_terms.append(xr_ref['rolling_avg_SI_Wind'] * cap_wind)
if quota_totals['solar'] > 0:
    obj_terms.append(xr_ref['rolling_avg_SI_Solar'] * cap_solar)
if quota_totals['biomass'] > 0:
    obj_terms.append(xr_ref['rolling_avg_SI_Biomass'] * cap_biomass)
if quota_totals['bgec'] > 0:
    obj_terms.append(xr_ref['rolling_avg_SI_BGEC'] * cap_bgec)
if quota_totals['msw'] > 0:
    obj_terms.append(xr_ref['rolling_avg_SI_MSW'] * cap_msw)

if obj_terms:
    obj = (-10000) * sum(obj_terms)
    m.add_objective(obj)

# ======================================================================================================================
# 9. Solve Model and Run Basic Diagnostics
# ======================================================================================================================
print("presolve = ",m)
m.solve(solver_name='highs',
        mip_abs_gap = 0.1,
        mip_rel_gap = 0.1,
        )

print('Solver status =', m.status)
solution = m.solution

print("\n--- Quota Feasibility Diagnostics ---")
infeasible_quotas_found = False
if solution is not None:
    for var_name in solution.data_vars:
        if var_name.startswith('slack_'):
            val = float(solution[var_name].item())
            if val > 0.01:  # Allow for tiny float precision noise
                print(f"INFEASIBILITY DETECTED: '{var_name}' is short by {val:.2f} MW")
                infeasible_quotas_found = True
    if not infeasible_quotas_found:
        print("All quotas were met successfully! The model is fully feasible.")
else:
    print("No solution returned. Infeasibility may stem from other non-quota constraints.")
print("-------------------------------------\n")

print('aftersolve = ',m)
solution = solution.fillna(0)
print(solution)

# ======================================================================================================================
# 10. Attach Solution Back to the xarray Dataset
# ----------------------------------------------------------------------------------------------------------------------
# Multiplying cap_* by built_* removes capacity from any non-selected cells and gives clean output layers for export.
# ======================================================================================================================
xr_ref['cap_wind'] = np.round(solution['cap_wind'] * solution['built_wind'],4) if 'cap_wind' in solution else 0
xr_ref['cap_solar'] = np.round(solution['cap_solar'] * solution['built_solar'],4) if 'cap_solar' in solution else 0
xr_ref['cap_biomass'] = np.round(solution['cap_biomass'] * solution['built_biomass'],4) if 'cap_biomass' in solution else 0
xr_ref['cap_bgec'] = np.round(solution['cap_bgec'] * solution['built_bgec'],4) if 'cap_bgec' in solution else 0
xr_ref['cap_msw'] = np.round(solution['cap_msw'] * solution['built_msw'],4) if 'cap_msw' in solution else 0

# Capture boolean built locations
xr_ref['built_wind'] = solution['built_wind'] if 'built_wind' in solution else 0
xr_ref['built_solar'] = solution['built_solar'] if 'built_solar' in solution else 0
xr_ref['built_biomass'] = solution['built_biomass'] if 'built_biomass' in solution else 0
xr_ref['built_bgec'] = solution['built_bgec'] if 'built_bgec' in solution else 0
xr_ref['built_msw'] = solution['built_msw'] if 'built_msw' in solution else 0

# ======================================================================================================================
# 11. Print Capacity Summary
# ----------------------------------------------------------------------------------------------------------------------
# Report total installed capacity and regional totals by technology for a quick check against quotas.
# ======================================================================================================================
print("cap_wind = ",xr_ref['cap_wind'].sum())
print("  R0 cap_wind = ",xr_ref['cap_wind'].where(xr_ref['region'] == 'R0').sum())
print("  R10 cap_wind = ",xr_ref['cap_wind'].where(xr_ref['region'] == 'R10').sum())
print("  R11 cap_wind = ",xr_ref['cap_wind'].where(xr_ref['region'] == 'R11').sum())
print("  R12 cap_wind = ",xr_ref['cap_wind'].where(xr_ref['region'] == 'R12').sum())
print("  R2 cap_wind = ",xr_ref['cap_wind'].where(xr_ref['region'] == 'R2').sum())
print("  R3 cap_wind = ",xr_ref['cap_wind'].where(xr_ref['region'] == 'R3').sum())
print("  R4 cap_wind = ",xr_ref['cap_wind'].where(xr_ref['region'] == 'R4').sum())

print("cap_solar = ",xr_ref['cap_solar'].sum())
print("  R0 cap_solar = ",xr_ref['cap_solar'].where(xr_ref['region'] == 'R0').sum())
print("  R10 cap_solar = ",xr_ref['cap_solar'].where(xr_ref['region'] == 'R10').sum())
print("  R11 cap_solar = ",xr_ref['cap_solar'].where(xr_ref['region'] == 'R11').sum())
print("  R12 cap_solar = ",xr_ref['cap_solar'].where(xr_ref['region'] == 'R12').sum())
print("  R2 cap_solar = ",xr_ref['cap_solar'].where(xr_ref['region'] == 'R2').sum())
print("  R3 cap_solar = ",xr_ref['cap_solar'].where(xr_ref['region'] == 'R3').sum())
print("  R4 cap_solar = ",xr_ref['cap_solar'].where(xr_ref['region'] == 'R4').sum())

print("cap_biomass = ",xr_ref['cap_biomass'].sum())
print("  R0 cap_biomass = ",xr_ref['cap_biomass'].where(xr_ref['region'] == 'R0').sum())
print("  R10 cap_biomass = ",xr_ref['cap_biomass'].where(xr_ref['region'] == 'R10').sum())
print("  R11 cap_biomass = ",xr_ref['cap_biomass'].where(xr_ref['region'] == 'R11').sum())
print("  R12 cap_biomass = ",xr_ref['cap_biomass'].where(xr_ref['region'] == 'R12').sum())
print("  R2 cap_biomass = ",xr_ref['cap_biomass'].where(xr_ref['region'] == 'R2').sum())
print("  R3 cap_biomass = ",xr_ref['cap_biomass'].where(xr_ref['region'] == 'R3').sum())
print("  R4 cap_biomass = ",xr_ref['cap_biomass'].where(xr_ref['region'] == 'R4').sum())

print("cap_bgec = ",xr_ref['cap_bgec'].sum())
print("  R0 cap_bgec = ",xr_ref['cap_bgec'].where(xr_ref['region'] == 'R0').sum())
print("  R10 cap_bgec = ",xr_ref['cap_bgec'].where(xr_ref['region'] == 'R10').sum())
print("  R11 cap_bgec = ",xr_ref['cap_bgec'].where(xr_ref['region'] == 'R11').sum())
print("  R12 cap_bgec = ",xr_ref['cap_bgec'].where(xr_ref['region'] == 'R12').sum())
print("  R2 cap_bgec = ",xr_ref['cap_bgec'].where(xr_ref['region'] == 'R2').sum())
print("  R3 cap_bgec = ",xr_ref['cap_bgec'].where(xr_ref['region'] == 'R3').sum())
print("  R4 cap_bgec = ",xr_ref['cap_bgec'].where(xr_ref['region'] == 'R4').sum())

print("cap_msw = ",xr_ref['cap_msw'].sum())
print("  R0 cap_msw = ",xr_ref['cap_msw'].where(xr_ref['region'] == 'R0').sum())
print("  R10 cap_msw = ",xr_ref['cap_msw'].where(xr_ref['region'] == 'R10').sum())
print("  R11 cap_msw = ",xr_ref['cap_msw'].where(xr_ref['region'] == 'R11').sum())
print("  R12 cap_msw = ",xr_ref['cap_msw'].where(xr_ref['region'] == 'R12').sum())
print("  R2 cap_msw = ",xr_ref['cap_msw'].where(xr_ref['region'] == 'R2').sum())
print("  R3 cap_msw = ",xr_ref['cap_msw'].where(xr_ref['region'] == 'R3').sum())
print("  R4 cap_msw = ",xr_ref['cap_msw'].where(xr_ref['region'] == 'R4').sum())

print(xr_ref.data_vars)
netcdf_out_path = output_dir / 'xr_output_all.nc'
xr_ref.to_netcdf(path=netcdf_out_path)
print(f"NetCDF results exported successfully to: {netcdf_out_path}")

# ======================================================================================================================
# 12. Export Selected Sites
# ----------------------------------------------------------------------------------------------------------------------
# Keep only grid cells where at least one technology has positive installed capacity.
# ======================================================================================================================
csv_cols = [
    'cap_wind', 'rolling_AVA_Wind', 'rolling_avg_SI_Wind', 
    'cap_solar', 'rolling_AVA_Solar', 'rolling_avg_SI_Solar', 
    'cap_biomass', 'rolling_AVA_Biomass', 'rolling_avg_SI_Biomass', 
    'cap_bgec', 'rolling_AVA_BGEC', 'rolling_avg_SI_BGEC', 
    'cap_msw', 'rolling_AVA_MSW', 'rolling_avg_SI_MSW', 
    'region'
]
df_results = xr_ref[csv_cols].to_dataframe().reset_index()

# Filter to keep only the grid cells where capacity was built
df_results = df_results[(df_results['cap_wind'] > 0) | (df_results['cap_solar'] > 0) | (df_results['cap_biomass'] > 0) | (df_results['cap_bgec'] > 0) | (df_results['cap_msw'] > 0)]

# Export to CSV
csv_out_path = output_dir / 'Investment_Sites.csv'
df_results.round(2).to_csv(csv_out_path, index=False)
print(f"Tabular results exported successfully to: {csv_out_path}")

# ======================================================================================================================
# 13. Interactive Map
# ----------------------------------------------------------------------------------------------------------------------
# Draw selected sites as capacity-scaled square buffers and write an HTML map with one layer per technology.
# ======================================================================================================================
print("Generating interactive map visualization...")

# We already have thailandmap loaded from earlier in the script
thailandmap = thailandmap.to_crs("EPSG:4326")

# Create an interactive base map with the Thailand boundaries
m = thailandmap.explore(
    color="black", 
    style_kwds={"fillOpacity": 0.0, "weight": 1.5}, 
    name="Thailand Boundary",
    tooltip=False,
    tiles="OpenStreetMap"
)

# Configuration for each technology map layer
tech_configs = [
    ('wind', 'Wind', 'Blues', rollingwindow_wind, [('rolling_avg_SI_Solar', 'Average SI Solar')]),
    ('solar', 'Solar', 'Oranges', rollingwindow_solar, [('rolling_avg_SI_Wind', 'Average SI Wind')]),
    ('biomass', 'Biomass', 'Greens', rollingwindow_biomass, []),
    ('bgec', 'BGEC', 'Purples', rollingwindow_bgec, []),
    ('msw', 'MSW', 'Reds', rollingwindow_msw, [])
]

for tech, tech_label, cmap, window, extra_tips in tech_configs:
    cap_col = f'cap_{tech}'
    ava_col = f'rolling_AVA_{tech_label}'
    si_col = f'rolling_avg_SI_{tech_label}'

    cols = [cap_col, ava_col, si_col] + [tip[0] for tip in extra_tips]

    # Reuse selected-site rows instead of rebuilding full xarray dataframes for every technology.
    df = df_results[['lat', 'lon'] + cols].copy()
    df = df[df[cap_col] > 0].dropna(subset=[cap_col])

    if df.empty:
        continue

    rename_dict = {
        cap_col: 'Capacity (MW)',
        ava_col: 'Total Area',
        si_col: f'Average SI {tech_label}',
        'lat': 'Latitude',
        'lon': 'Longitude'
    }
    for tip_col, tip_label in extra_tips:
        rename_dict[tip_col] = tip_label

    df = df.rename(columns=rename_dict).round(2)

    # Convert to GeoDataFrame
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df['Longitude'], df['Latitude']))
    gdf = gdf.set_crs("EPSG:4326")

    gdf = gdf.to_crs("EPSG:32647")
    
    # Convert capacity into an approximate footprint area for visual scaling.
    if tech == 'wind':
        area_km2 = gdf['Capacity (MW)'] / mwperkm2_wind
    elif tech == 'solar':
        area_km2 = gdf['Capacity (MW)'] / mwperkm2_solar
    elif tech == 'biomass':
        area_km2 = (gdf['Capacity (MW)'] / float(maxcap_biomass)) * suitablearea_biomass
    elif tech == 'bgec':
        area_km2 = (gdf['Capacity (MW)'] / float(maxcap_bgec)) * suitablearea_bgec
    elif tech == 'msw':
        area_km2 = (gdf['Capacity (MW)'] / float(maxcap_msw)) * suitablearea_msw
        
    buffer_m = (np.sqrt(area_km2) * 1000) / 2
    gdf.geometry = gdf.geometry.buffer(buffer_m, cap_style=3)
    gdf = gdf.to_crs("EPSG:4326")

    # Add to map
    tooltip_cols = ["Latitude", "Longitude", "Total Area", "Capacity (MW)", f"Average SI {tech_label}"] + [tip[1] for tip in extra_tips]
    gdf.explore(
        m=m, column="Capacity (MW)", cmap=cmap, style_kwds={"fillOpacity": 0.6, "weight": 1},
        name=f"{tech_label} Capacity (MW)", legend_kwds={"caption": f"{tech_label} Capacity (MW)"},
        tooltip=tooltip_cols
    )

# Add a layer control panel to toggle technologies and boundaries.
folium.LayerControl().add_to(m)

# Save interactive map
out_file = output_dir / 'InvestmentMap_Interactive.html'
m.save(out_file)
print(f"Interactive map saved successfully! Open '{out_file}' in your web browser to explore.")
