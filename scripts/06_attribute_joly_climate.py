#!/usr/bin/env python3
"""
06_attribute_joly_climate.py
Attribue à chaque station MF un type de climat Joly et al. 2010 (8 classes)
par échantillonnage du raster TYPO_RGF93.tif au point (LAT, LON).
"""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import transform as warp_transform

JOLY_LABELS = {
    1: "Climat montagnard",
    2: "Climat semi-continental / marges montagnardes",
    3: "Climat océanique dégradé (Centre/Nord, bassin parisien)",
    4: "Climat océanique altéré",
    5: "Climat océanique franc (façade atlantique)",
    6: "Climat méditerranéen altéré",
    7: "Climat méditerranéen franc",
    8: "Climat du bassin du Sud-Ouest",
}


def sample_raster_at_points(raster_path, lats, lons):
    with rasterio.open(raster_path) as src:
        print(f"Raster CRS    : {src.crs}")
        print(f"Raster shape  : {src.shape}")
        print(f"Raster bounds : {src.bounds}")
        print(f"NoData        : {src.nodata}")
        target_crs = src.crs if src.crs else "EPSG:2154"
        if str(target_crs) != "EPSG:4326":
            xs, ys = warp_transform("EPSG:4326", target_crs, lons.tolist(), lats.tolist())
        else:
            xs, ys = lons.tolist(), lats.tolist()
        coords = list(zip(xs, ys))
        values = []
        for val in src.sample(coords):
            v = val[0]
            if src.nodata is not None and v == src.nodata:
                values.append(np.nan)
            else:
                values.append(v)
        return np.array(values, dtype=float)


def fill_nearest_neighbor(df, type_col, lat_col, lon_col):
    from scipy.spatial import cKDTree
    df = df.copy()
    known = df[df[type_col].notna()].copy()
    unknown = df[df[type_col].isna()].copy()
    if len(unknown) == 0:
        df["source_attribution"] = "raster"
        return df
    if len(known) == 0:
        raise RuntimeError("Aucune station avec attribution valide.")
    tree = cKDTree(known[[lat_col, lon_col]].values)
    dists, idxs = tree.query(unknown[[lat_col, lon_col]].values, k=1)
    df.loc[unknown.index, type_col] = known.iloc[idxs][type_col].values
    df["source_attribution"] = "raster"
    df.loc[unknown.index, "source_attribution"] = "nearest_neighbor"
    print(f"Fallback voisin: {len(unknown)} stations  (distance médiane {np.median(dists):.3f}°)")
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--joly-raster", required=True, type=Path)
    ap.add_argument("--stations", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--no-nn-fallback", action="store_true")
    args = ap.parse_args()

    print(f"Stations : {args.stations}")
    df = pd.read_csv(args.stations)
    print(f"  {len(df)} stations")

    lat_col = "LAT" if "LAT" in df.columns else "lat"
    lon_col = "LON" if "LON" in df.columns else "lon"

    print(f"\nRaster : {args.joly_raster}")
    values = sample_raster_at_points(args.joly_raster, df[lat_col].values, df[lon_col].values)
    df["type_joly"] = pd.Series(values).where(~pd.isna(values), np.nan)
    n_valid = df["type_joly"].notna().sum()
    print(f"\nAttribution directe : {n_valid}/{len(df)}")

    if n_valid < len(df) and not args.no_nn_fallback:
        df = fill_nearest_neighbor(df, "type_joly", lat_col, lon_col)
    else:
        df["source_attribution"] = "raster"
        df.loc[df["type_joly"].isna(), "source_attribution"] = "missing"

    df["type_joly"] = df["type_joly"].astype("Int64")
    df["type_joly_label"] = df["type_joly"].map(JOLY_LABELS)

    out_cols = ["NUM_POSTE", "NOM_USUEL", lat_col, lon_col, "ALTI",
                "type_joly", "type_joly_label", "source_attribution"]
    out_cols = [c for c in out_cols if c in df.columns]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    df[out_cols].to_csv(args.output, index=False)
    print(f"\nÉcrit : {args.output}")
    print(f"\n=== Distribution des types Joly ===")
    print(df["type_joly_label"].value_counts(dropna=False))

    print(f"\n=== Stations témoins (vérification du mapping) ===")
    temoins = ["BREST", "MARSEILLE-OBS", "CHAMONIX", "LONS", "STRASBOURG",
               "BORDEAUX-PAULIN", "CAP BEAR", "LARIBOISIERE", "MONTSOURIS"]
    for t in temoins:
        m = df[df["NOM_USUEL"].str.contains(t, case=False, na=False)]
        for _, r in m.iterrows():
            label = r["type_joly_label"] if pd.notna(r["type_joly_label"]) else "—"
            print(f"  {r['NUM_POSTE']:>10}  {r['NOM_USUEL']:<35}  type={r['type_joly']}  {label}")


if __name__ == "__main__":
    main()
