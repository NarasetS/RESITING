from pathlib import Path
import time

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr
from scipy.spatial import cKDTree


FEEDSTOCK_MAPPING = {
    "A_BGEC": [10, 11, 12, 20, 30, 40],
    "A_Biomass": [110, 130, 120, 121, 122, 200, 201, 202, 140, 150, 151, 152, 153, 10, 11, 12, 20, 30, 40, 180],
    "A_BGWW": [10, 11, 12, 20, 30, 40],
    "A_MSW": [190],
    "A_IEW": [190],
}

FEEDSTOCK_TYPE = {
    "A_Biomass": "ชีวมวล",
    "A_BGEC": "ก๊าซชีวภาพ",
    "A_BGWW": "ก๊าซชีวภาพ",
    "A_MSW": "ขยะ",
    "A_IEW": "ขยะ",
}


def process_landcover_feedstock(
    input_path=Path("Output") / "xr_SI_Landcover_beforefeedstock.nc",
    output_path=Path("Output") / "xr_SI_Landcover.nc",
    data_dir=Path("Data"),
):
    print(f"Loading pre-feedstock landcover SI from {input_path}...")
    with xr.open_dataset(input_path) as ds:
        xr_final_si = ds.load()

    df = xr_final_si.to_dataframe().reset_index()
    df = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs="EPSG:4326")

    print("Loading Thailand provincial boundaries...")
    thailandmap = gpd.read_file(data_dir / "tha_admbnda_adm1_rtsd_20220121" / "tha_admbnda_adm1_rtsd_20220121.shp")
    thailandmap = thailandmap.to_crs("EPSG:4326")
    print(f"Loaded {len(thailandmap)} provinces")

    print("Assigning grid points to provinces...")
    t0 = time.time()
    thailandmap["prov_id"] = range(len(thailandmap))
    prov_id_to_th = dict(zip(range(len(thailandmap)), thailandmap["ADM1_TH"]))
    prov_id_to_en = dict(zip(range(len(thailandmap)), thailandmap["ADM1_EN"]))

    prov_centroids = np.column_stack((thailandmap.geometry.centroid.x, thailandmap.geometry.centroid.y))
    prov_tree = cKDTree(prov_centroids)
    grid_coords = np.column_stack((df["lon"].values, df["lat"].values))
    _, nearest_prov_idx = prov_tree.query(grid_coords, k=1)

    df2 = df.copy()
    df2["prov_id"] = nearest_prov_idx
    df2["ADM1_TH"] = df2["prov_id"].map(prov_id_to_th)
    df2["ADM1_EN"] = df2["prov_id"].map(prov_id_to_en)

    keep_cols = [
        "lat",
        "lon",
        "lccs_class",
        "SI_Solar",
        "SI_Wind",
        "SI_BGEC",
        "SI_Biomass",
        "SI_BGWW",
        "SI_MSW",
        "SI_IEW",
        "ADM1_EN",
        "ADM1_TH",
    ]
    df2 = df2[keep_cols]
    print(f"Assigned {len(df2)} points in {time.time() - t0:.2f}s")

    lccs_resolution = 300
    areapergrid = (lccs_resolution / 1000) ** 2
    lccs = df2["lccs_class"].values
    for col, classes in FEEDSTOCK_MAPPING.items():
        df2[col] = np.where(np.isin(lccs, classes), areapergrid, 0.0).astype("float64")

    feedstock_path = data_dir / "สรุปข้อมูลพลังงาน -  ฐานข้อมูลพลังงานประเทศไทย.csv"
    feedstock = pd.read_csv(feedstock_path, header=0)
    feedstock = feedstock.loc[feedstock["แหล่งพลังงานหลัก"].isin(["ชีวมวล", "ก๊าซชีวภาพ", "ขยะ"])].copy()
    feedstock["ศักยภาพพลังงานทดแทน (ktoe)"] = pd.to_numeric(
        feedstock["ศักยภาพพลังงานทดแทน (ktoe)"],
        errors="coerce",
    )
    feedstock = feedstock.dropna(subset=["ศักยภาพพลังงานทดแทน (ktoe)"])
    print(f"Loaded feedstock: {len(feedstock)} records | {len(feedstock['จังหวัด'].unique())} provinces")

    print("Distributing feedstock potential...")
    for col, thai_type in FEEDSTOCK_TYPE.items():
        mask = df2[col] > 0
        if not mask.any():
            print(f"  {col}: No suitable cells")
            continue

        areas = df2[mask].groupby("ADM1_TH")[col].sum() / areapergrid
        potentials = feedstock[feedstock["แหล่งพลังงานหลัก"] == thai_type].set_index("จังหวัด")[
            "ศักยภาพพลังงานทดแทน (ktoe)"
        ]

        matches = 0
        for prov in areas.index:
            if prov not in potentials.index:
                continue

            area_val = float(areas[prov])
            pot_val = float(potentials[prov])
            if area_val > 0 and pot_val > 0:
                df2.loc[mask & (df2["ADM1_TH"] == prov), col] = pot_val / area_val
                matches += 1

        print(f"  {col}: Distributed to {matches} provinces")

    for col in FEEDSTOCK_MAPPING:
        print(f"  {col}: {df2[col].sum():.2f} ktoe")

    df2 = df2.drop(columns="ADM1_TH").set_index(["lat", "lon"])
    xr_areafeedstock = xr.Dataset.from_dataframe(df2)

    print(f"Saving feedstock-integrated landcover SI to {output_path}...")
    xr_areafeedstock.to_netcdf(path=output_path)
    xr_areafeedstock.close()
    xr_final_si.close()
    print("Feedstock integration completed.")


if __name__ == "__main__":
    process_landcover_feedstock()
