#!/usr/bin/env python3
"""
02b_compute_rolling_indicators.py

Calcule les indicateurs glissants sur fenêtre de N jours pour un épisode :
  - NTrop_5j_max : nombre max de nuits tropicales (Tn ≥ 20°C)
                   sur fenêtre glissante de N jours consécutifs
  - TnMoy_5j_max : max de la Tn moyenne sur fenêtre glissante de N jours

Ces métriques décorrèlent l'intensité du pic d'une part, de la durée
totale d'épisode d'autre part. Utiles pour comparer des épisodes de
durées inégales (mai 2026 = 10 j vs août 2003 = 15 j).

Usage typique :
    python 02b_compute_rolling_indicators.py \\
        --episode dome-chaleur-mai-2026 \\
        --start 20260520 --end 20260529 \\
        --raw-dir data/raw/meteo_france \\
        --output data/processed/dome-chaleur-mai-2026/indicators_glissant.csv

Pour les épisodes anciens (1950-2024) dont les CSV sont en gzip côté
serveur Météo-France et stockés tels quels par le script 01, le code
gère l'auto-détection gzip/plain.
"""

import argparse
import gzip
from glob import glob
from pathlib import Path

import numpy as np
import pandas as pd


def open_meteo_csv(path: Path) -> "pd.DataFrame":
    """
    Lit un CSV Météo-France, gérant le cas gzip masqué par extension .csv.
    """
    with open(path, "rb") as f:
        magic = f.read(2)
    if magic == b"\x1f\x8b":
        return pd.read_csv(gzip.open(path), sep=";",
                           usecols=["NUM_POSTE", "NOM_USUEL", "LAT", "LON", "ALTI",
                                    "AAAAMMJJ", "TN"])
    return pd.read_csv(path, sep=";",
                       usecols=["NUM_POSTE", "NOM_USUEL", "LAT", "LON", "ALTI",
                                "AAAAMMJJ", "TN"])


def rolling_ntrop_max(row_vals: np.ndarray, window: int, threshold: float) -> float:
    """Max nb de Tn>=threshold sur fenêtre glissante de `window` jours."""
    is_trop = (row_vals >= threshold).astype(int)
    valid_mask = ~np.isnan(row_vals)
    n = len(row_vals)
    if n < window:
        if valid_mask.sum() >= 0.8 * n:
            return float(is_trop[valid_mask].sum())
        return np.nan
    sums = []
    for i in range(n - window + 1):
        chunk_valid = valid_mask[i:i + window]
        if chunk_valid.sum() >= 0.8 * window:
            sums.append(is_trop[i:i + window].sum())
    return float(max(sums)) if sums else np.nan


def rolling_tnmoy_max(row_vals: np.ndarray, window: int) -> float:
    """Max de la Tn moyenne sur fenêtre glissante de `window` jours."""
    valid_mask = ~np.isnan(row_vals)
    n = len(row_vals)
    if n < window:
        if valid_mask.sum() >= 0.8 * n:
            return float(np.nanmean(row_vals))
        return np.nan
    moys = []
    for i in range(n - window + 1):
        chunk = row_vals[i:i + window]
        if (~np.isnan(chunk)).sum() >= 0.8 * window:
            moys.append(np.nanmean(chunk))
    return float(max(moys)) if moys else np.nan


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--episode", required=True, type=str,
                    help="Slug de l'épisode (ex: dome-chaleur-mai-2026)")
    ap.add_argument("--start", required=True, type=int,
                    help="Date début AAAAMMJJ (ex: 20260520)")
    ap.add_argument("--end", required=True, type=int,
                    help="Date fin AAAAMMJJ (ex: 20260529)")
    ap.add_argument("--raw-dir", required=True, type=Path,
                    help="Dossier des CSV bruts Météo-France")
    ap.add_argument("--pattern", default="Q_*.csv",
                    help="Pattern de glob des CSV (def: Q_*.csv)")
    ap.add_argument("--window", type=int, default=5,
                    help="Taille fenêtre glissante (def: 5 jours)")
    ap.add_argument("--threshold", type=float, default=20.0,
                    help="Seuil nuit tropicale (def: 20.0 °C)")
    ap.add_argument("--output", required=True, type=Path,
                    help="Chemin du CSV de sortie")
    args = ap.parse_args()

    csv_files = sorted(glob(str(args.raw_dir / args.pattern)))
    print(f"Fichiers trouvés : {len(csv_files)}")
    if not csv_files:
        raise SystemExit(f"Aucun CSV trouvé dans {args.raw_dir} avec pattern {args.pattern}")

    records = []
    for f in csv_files:
        try:
            df = open_meteo_csv(Path(f))
        except Exception as e:
            print(f"  ✗ Erreur sur {f}: {e}")
            continue
        df = df[(df["AAAAMMJJ"] >= args.start) & (df["AAAAMMJJ"] <= args.end)]
        df = df.dropna(subset=["TN"])
        if len(df) > 0:
            records.append(df)

    if not records:
        raise SystemExit(f"Aucune donnée trouvée pour la période {args.start}-{args.end}")

    big = pd.concat(records, ignore_index=True)
    print(f"Lignes (station × jour) : {len(big)}  |  Stations distinctes : {big['NUM_POSTE'].nunique()}")

    # Pivot station × jour
    big["AAAAMMJJ"] = big["AAAAMMJJ"].astype(int)
    piv = big.pivot_table(index="NUM_POSTE", columns="AAAAMMJJ", values="TN", aggfunc="first")
    piv = piv.sort_index(axis=1)
    print(f"Matrice pivotée : {piv.shape[0]} stations × {piv.shape[1]} jours")

    # Calcul indicateurs glissants
    print(f"Calcul fenêtre glissante {args.window} j (seuil Tn ≥ {args.threshold}°C)...")
    result = pd.DataFrame(index=piv.index)
    result["NTrop_glissant_max"] = piv.apply(
        lambda row: rolling_ntrop_max(row.values, args.window, args.threshold), axis=1)
    result["TnMoy_glissant_max"] = piv.apply(
        lambda row: rolling_tnmoy_max(row.values, args.window), axis=1)
    result["window_days"] = args.window
    result["episode"] = args.episode
    result = result.reset_index()

    # Merge metadonnées stations
    meta = big.drop_duplicates(subset="NUM_POSTE")[["NUM_POSTE", "NOM_USUEL", "LAT", "LON", "ALTI"]]
    result = meta.merge(result, on="NUM_POSTE", how="right")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False)
    print(f"\nÉcrit : {args.output}")

    print(f"\n=== Distribution NTrop_glissant_max ===")
    print(result["NTrop_glissant_max"].describe())
    print(f"\n=== Top 10 stations par TnMoy_glissant_max ===")
    top = result.nlargest(10, "TnMoy_glissant_max")
    print(top[["NUM_POSTE", "NOM_USUEL", "LAT", "LON", "ALTI",
               "NTrop_glissant_max", "TnMoy_glissant_max"]].to_string(index=False))


if __name__ == "__main__":
    main()
