import linopy
import pandas as pd
import xarray as xr
import geopandas as gpd
import matplotlib.pyplot as plt
from pathlib import Path
from shapely import wkt
import numpy as np
import folium

###################### Config ################################################################################################
coarsenscale = 5
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

rollingwindow_wind = int(np.ceil(np.sqrt(suitablearea_wind/areapergrid)))
rollingwindow_solar = int(np.ceil(np.sqrt(suitablearea_solar/areapergrid)))

suitablearea_biomass = 2500 ## km2 
suitablearea_bgec = 2500 ## km2
suitablearea_msw = 2500 ## km2

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

######## Find min/max SI within cell #############
xr_final_SI['SI_Wind_max'] = xr_final_SI_raw['SI_Wind'].coarsen(lat = coarsenscale, lon= coarsenscale, boundary='trim').max()
xr_final_SI['SI_Wind_min'] = xr_final_SI_raw['SI_Wind'].coarsen(lat = coarsenscale, lon= coarsenscale, boundary='trim').min()
xr_final_SI['SI_Solar_max'] = xr_final_SI_raw['SI_Solar'].coarsen(lat = coarsenscale, lon= coarsenscale, boundary='trim').max()
xr_final_SI['SI_Solar_min'] = xr_final_SI_raw['SI_Solar'].coarsen(lat = coarsenscale, lon= coarsenscale, boundary='trim').min()

maxcap_wind = xr_final_SI['AVA_Wind'].rolling(lon = rollingwindow_wind, lat = rollingwindow_wind, min_periods=1,center=True).sum().where(xr_final_SI['SI_Wind']>0).max()
maxcap_solar = xr_final_SI['AVA_Solar'].rolling(lon = rollingwindow_solar, lat = rollingwindow_solar, min_periods=1,center=True).sum().where(xr_final_SI['SI_Solar']>0).max()
maxcap_biomass = xr_final_SI['A_Biomass'].rolling(lon = rollingwindow_biomass, lat = rollingwindow_biomass, min_periods=1,center=True).sum().where(xr_final_SI['SI_Biomass']>0).max()
maxcap_bgec = xr_final_SI['A_BGEC'].rolling(lon = rollingwindow_bgec, lat = rollingwindow_bgec, min_periods=1,center=True).sum().where(xr_final_SI['SI_BGEC']>0).max()
maxcap_msw = xr_final_SI['A_MSW'].rolling(lon = rollingwindow_msw, lat = rollingwindow_msw, min_periods=1,center=True).sum().where(xr_final_SI['SI_MSW']>0).max()
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
###################### Config ################################################################################################

######### Next I assign Region to xarray ################################################################################
region = pd.read_csv('Data\\Region.csv')
thailandmap = gpd.read_file('Data\\tha_admbnda_adm1_rtsd_20220121\\tha_admbnda_adm1_rtsd_20220121.shp')
thailandmap.crs = "EPSG:4326"
list_region = []
count = 0
for i in thailandmap['ADM1_TH']:
    r = region['region'].loc[region['province'] == i]
    try : 
        # print(i,r.values[0])
        list_region.append(r.values[0])
    except :
        print(i,'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx')
        list_region.append('xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx')
thailandmap['region'] = list_region
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
#########################################################################################

###################### Summary ################################################################################################
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
###################### Summary ################################################################################################

####### PDP Quotas ############################################################
# Toggles to enable or disable quotas
enforce_total_quota = True
enforce_regional_quota = True

quotas = {
    'wind': {'R0': 0, 'R1': 6582, 'R2': 16540, 'R3': 1678, 'R4': 2320},
    'solar': {'R0': 0, 'R1': 0, 'R2': 0, 'R3': 0, 'R4': 0},
    'biomass': {'R0': 0, 'R1': 0, 'R2': 0, 'R3': 0, 'R4': 0},
    'bgec': {'R0': 0, 'R1': 0, 'R2': 0, 'R3': 0, 'R4': 0},
    'msw': {'R0': 0, 'R1': 0, 'R2': 0, 'R3': 0, 'R4': 0}
}

quota_totals = {tech: sum(reg_quotas.values()) for tech, reg_quotas in quotas.items()}

for tech, total in quota_totals.items():
    print(f"quota_{tech}_total = {total}")

####### PDP ############################################################

######################## model #####################################################
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

############################################ Constraint Building Location Logic ##############################################################################
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
############################################ Constraint Building Location Logic ##############################################################################

############################################ Constraint Capacity ##############################################################################
if built_wind is not None:
    constr_maxcap_wind = m.add_constraints(
        cap_wind <= (built_wind * (xr_ref['AVA_Wind'].rolling(lon = rollingwindow_wind, lat = rollingwindow_wind, min_periods=1,center=True).sum() * mwperkm2_wind))
        ,name = 'constr_maxcap_wind'
    )
    constr_builtarea_wind = m.add_constraints(
        built_wind <= (xr_ref['AVA_Wind'] * 10000)
        ,name = 'constr_builtarea_wind'
    )

if built_solar is not None:
    constr_maxcap_solar = m.add_constraints(
        cap_solar <= (built_solar * (xr_ref['AVA_Solar'].rolling(lon = rollingwindow_solar, lat = rollingwindow_solar, min_periods=1,center=True).sum() * mwperkm2_solar))
        ,name = 'constr_maxcap_solar'
    )
    constr_builtarea_solar = m.add_constraints(
        built_solar <= (xr_ref['AVA_Solar'] * 10000)
        ,name = 'constr_builtarea_solar'
    )

if built_biomass is not None:
    constr_maxcap_biomass = m.add_constraints(
        cap_biomass <= (built_biomass * (xr_ref['A_Biomass'].rolling(lon = rollingwindow_biomass, lat = rollingwindow_biomass, min_periods=1,center=True).sum()))
        ,name = 'constr_maxcap_biomass'
    )
    constr_builtarea_biomass = m.add_constraints(
        built_biomass <= (xr_ref['AVA_Biomass'] * 10000)
        ,name = 'constr_builtarea_biomass'
    )

if built_bgec is not None:
    constr_maxcap_bgec = m.add_constraints(
        cap_bgec <= (built_bgec * (xr_ref['A_BGEC'].rolling(lon = rollingwindow_bgec, lat = rollingwindow_bgec, min_periods=1,center=True).sum()))
        ,name = 'constr_maxcap_bgec'
    )
    constr_builtarea_bgec = m.add_constraints(
        built_bgec <= (xr_ref['AVA_BGEC'] * 10000)
        ,name = 'constr_builtarea_bgec'
    )

if built_msw is not None:
    constr_maxcap_msw = m.add_constraints(
        cap_msw <= ((built_msw) * (xr_ref['A_MSW'].rolling(lon = rollingwindow_msw, lat = rollingwindow_msw, min_periods=1,center=True).sum()))
        ,name = 'constr_maxcap_msw'
    )
    constr_builtarea_msw = m.add_constraints(
        built_msw <= (xr_ref['AVA_MSW'] * 10000)
        ,name = 'constr_builtarea_msw'
    )
############################################ Constraint Capacity ##############################################################################

###########################################################################################################################################################

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

##########################################################################################################################################################

###################### Objective function ################################################################################################
obj_terms = []
if quota_totals['wind'] > 0:
    obj_terms.append(xr_ref['SI_Wind'].rolling(lon=rollingwindow_wind, lat=rollingwindow_wind, min_periods=1, center=True).sum() * (cap_wind / maxcap_wind))
if quota_totals['solar'] > 0:
    obj_terms.append(xr_ref['SI_Solar'].rolling(lon=rollingwindow_solar, lat=rollingwindow_solar, min_periods=1, center=True).sum() * (cap_solar / maxcap_solar))
if quota_totals['biomass'] > 0:
    obj_terms.append(xr_ref['SI_Biomass'].rolling(lon=rollingwindow_biomass, lat=rollingwindow_biomass, min_periods=1, center=True).sum() * (cap_biomass / maxcap_biomass))
if quota_totals['bgec'] > 0:
    obj_terms.append(xr_ref['SI_BGEC'].rolling(lon=rollingwindow_bgec, lat=rollingwindow_bgec, min_periods=1, center=True).sum() * (cap_bgec / maxcap_bgec))
if quota_totals['msw'] > 0:
    obj_terms.append(xr_ref['SI_MSW'].rolling(lon=rollingwindow_msw, lat=rollingwindow_msw, min_periods=1, center=True).sum() * (cap_msw / maxcap_msw))

if obj_terms:
    obj = (-10000) * sum(obj_terms)
    m.add_objective(obj)
###################### Objective function ################################################################################################

###################### Solver ################################################################################################
print("presolve = ",m)
m.solve(solver_name='highs',
        mip_abs_gap = 0.1,
        mip_rel_gap = 0.1,
        )

print('aftersolve = ',m)
solution = m.solution
solution = solution.fillna(0)
print(solution)

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

# Capture rolling/footprint information (Available area, Sum of SI, Average SI)
xr_ref['rolling_AVA_Wind'] = xr_ref['AVA_Wind'].rolling(lon=rollingwindow_wind, lat=rollingwindow_wind, min_periods=1, center=True).sum()
xr_ref['rolling_AVA_Solar'] = xr_ref['AVA_Solar'].rolling(lon=rollingwindow_solar, lat=rollingwindow_solar, min_periods=1, center=True).sum()
xr_ref['rolling_AVA_Biomass'] = xr_ref['AVA_Biomass'].rolling(lon=rollingwindow_biomass, lat=rollingwindow_biomass, min_periods=1, center=True).sum()
xr_ref['rolling_AVA_BGEC'] = xr_ref['AVA_BGEC'].rolling(lon=rollingwindow_bgec, lat=rollingwindow_bgec, min_periods=1, center=True).sum()
xr_ref['rolling_AVA_MSW'] = xr_ref['AVA_MSW'].rolling(lon=rollingwindow_msw, lat=rollingwindow_msw, min_periods=1, center=True).sum()

xr_ref['rolling_sum_SI_Wind'] = xr_ref['SI_Wind'].rolling(lon=rollingwindow_wind, lat=rollingwindow_wind, min_periods=1, center=True).sum()
xr_ref['rolling_sum_SI_Solar'] = xr_ref['SI_Solar'].rolling(lon=rollingwindow_solar, lat=rollingwindow_solar, min_periods=1, center=True).sum()
xr_ref['rolling_avg_SI_Wind'] = xr_ref['SI_Wind'].rolling(lon=rollingwindow_wind, lat=rollingwindow_wind, min_periods=1, center=True).mean()
xr_ref['rolling_avg_SI_Solar'] = xr_ref['SI_Solar'].rolling(lon=rollingwindow_solar, lat=rollingwindow_solar, min_periods=1, center=True).mean()
xr_ref['rolling_avg_SI_Biomass'] = xr_ref['SI_Biomass'].rolling(lon=rollingwindow_biomass, lat=rollingwindow_biomass, min_periods=1, center=True).mean()
xr_ref['rolling_avg_SI_BGEC'] = xr_ref['SI_BGEC'].rolling(lon=rollingwindow_bgec, lat=rollingwindow_bgec, min_periods=1, center=True).mean()
xr_ref['rolling_avg_SI_MSW'] = xr_ref['SI_MSW'].rolling(lon=rollingwindow_msw, lat=rollingwindow_msw, min_periods=1, center=True).mean()

print("cap_wind = ",xr_ref['cap_wind'].sum())
print("  R0 cap_wind = ",xr_ref['cap_wind'].where(xr_ref['region'] == 'R0').sum())
print("  R1 cap_wind = ",xr_ref['cap_wind'].where(xr_ref['region'] == 'R1').sum())
print("  R2 cap_wind = ",xr_ref['cap_wind'].where(xr_ref['region'] == 'R2').sum())
print("  R3 cap_wind = ",xr_ref['cap_wind'].where(xr_ref['region'] == 'R3').sum())
print("  R4 cap_wind = ",xr_ref['cap_wind'].where(xr_ref['region'] == 'R4').sum())

print("cap_solar = ",xr_ref['cap_solar'].sum())
print("  R0 cap_solar = ",xr_ref['cap_solar'].where(xr_ref['region'] == 'R0').sum())
print("  R1 cap_solar = ",xr_ref['cap_solar'].where(xr_ref['region'] == 'R1').sum())
print("  R2 cap_solar = ",xr_ref['cap_solar'].where(xr_ref['region'] == 'R2').sum())
print("  R3 cap_solar = ",xr_ref['cap_solar'].where(xr_ref['region'] == 'R3').sum())
print("  R4 cap_solar = ",xr_ref['cap_solar'].where(xr_ref['region'] == 'R4').sum())

print("cap_biomass = ",xr_ref['cap_biomass'].sum())
print("  R0 cap_biomass = ",xr_ref['cap_biomass'].where(xr_ref['region'] == 'R0').sum())
print("  R1 cap_biomass = ",xr_ref['cap_biomass'].where(xr_ref['region'] == 'R1').sum())
print("  R2 cap_biomass = ",xr_ref['cap_biomass'].where(xr_ref['region'] == 'R2').sum())
print("  R3 cap_biomass = ",xr_ref['cap_biomass'].where(xr_ref['region'] == 'R3').sum())
print("  R4 cap_biomass = ",xr_ref['cap_biomass'].where(xr_ref['region'] == 'R4').sum())

print("cap_bgec = ",xr_ref['cap_bgec'].sum())
print("  R0 cap_bgec = ",xr_ref['cap_bgec'].where(xr_ref['region'] == 'R0').sum())
print("  R1 cap_bgec = ",xr_ref['cap_bgec'].where(xr_ref['region'] == 'R1').sum())
print("  R2 cap_bgec = ",xr_ref['cap_bgec'].where(xr_ref['region'] == 'R2').sum())
print("  R3 cap_bgec = ",xr_ref['cap_bgec'].where(xr_ref['region'] == 'R3').sum())
print("  R4 cap_bgec = ",xr_ref['cap_bgec'].where(xr_ref['region'] == 'R4').sum())

print("cap_msw = ",xr_ref['cap_msw'].sum())
print("  R0 cap_msw = ",xr_ref['cap_msw'].where(xr_ref['region'] == 'R0').sum())
print("  R1 cap_msw = ",xr_ref['cap_msw'].where(xr_ref['region'] == 'R1').sum())
print("  R2 cap_msw = ",xr_ref['cap_msw'].where(xr_ref['region'] == 'R2').sum())
print("  R3 cap_msw = ",xr_ref['cap_msw'].where(xr_ref['region'] == 'R3').sum())
print("  R4 cap_msw = ",xr_ref['cap_msw'].where(xr_ref['region'] == 'R4').sum())

print(xr_ref.data_vars)
xr_ref.to_netcdf(path='Output\\xr_output_all_SSI_' + str(scenario_SI) + "_CS_"+str(coarsenscale)+ '_.nc')

# Identify any additional individual SI sub-criteria variables dynamically
extra_si_vars = [v for v in xr_ref.data_vars if v.startswith('SI_') and v not in [
    'SI_Wind', 'SI_Solar', 'SI_Biomass', 'SI_BGEC', 'SI_MSW',
    'SI_Wind_max', 'SI_Wind_min', 'SI_Solar_max', 'SI_Solar_min'
]]

# Calculate footprint rolling averages for the sub-criteria SIs
wind_extra_si_vars = []
solar_extra_si_vars = []

for var in extra_si_vars:
    wind_var_name = f'rolling_avg_{var}_Wind'
    solar_var_name = f'rolling_avg_{var}_Solar'
    
    xr_ref[wind_var_name] = xr_ref[var].rolling(lon=rollingwindow_wind, lat=rollingwindow_wind, min_periods=1, center=True).mean()
    xr_ref[solar_var_name] = xr_ref[var].rolling(lon=rollingwindow_solar, lat=rollingwindow_solar, min_periods=1, center=True).mean()
    
    wind_extra_si_vars.append(wind_var_name)
    solar_extra_si_vars.append(solar_var_name)

# Export selected sites to CSV
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
df_results = df_results.round(2) # Clean up CSV float values

# Export to CSV
csv_out_path = f'Output\\Investment_Sites_SSI_{scenario_SI}_CS_{coarsenscale}.csv'
df_results.to_csv(csv_out_path, index=False)
print(f"Tabular results exported successfully to: {csv_out_path}")

###################### Visualization #########################################################################################
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

    # Extract DataFrame, filter, and clean up
    df = xr_ref[cols].to_dataframe().reset_index()
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

    # Project, buffer to squares, and project back
    buffer_m = (window * lccs_resolution) / 2
    gdf = gdf.to_crs("EPSG:32647")
    gdf.geometry = gdf.geometry.buffer(buffer_m, cap_style=3)
    gdf = gdf.to_crs("EPSG:4326")

    # Add to map
    tooltip_cols = ["Latitude", "Longitude", "Total Area", "Capacity (MW)", f"Average SI {tech_label}"] + [tip[1] for tip in extra_tips]
    gdf.explore(
        m=m, column="Capacity (MW)", cmap=cmap, style_kwds={"fillOpacity": 0.6, "weight": 1},
        name=f"{tech_label} Capacity (MW)", legend_kwds={"caption": f"{tech_label} Capacity (MW)"},
        tooltip=tooltip_cols
    )

# Add a layer control panel to easily toggle Wind/Solar/Boundaries on and off
folium.LayerControl().add_to(m)

# Save interactive map
out_file = f'Output\\InvestmentMap_SSI_{scenario_SI}_CS_{coarsenscale}_Interactive.html'
m.save(out_file)
print(f"Interactive map saved successfully! Open '{out_file}' in your web browser to explore.")
