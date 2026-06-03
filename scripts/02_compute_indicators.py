#!/usr/bin/env python3
"""
02_compute_indicators.py — Calcul des indicateurs canicule par station.

Pour chaque station Météo-France et pour un épisode donné, calcule :

  - NTrop  : nombre de nuits tropicales (Tn ≥ 20 °C)
  - TnMax  : Tn maximale sur la période
  - TnMoy  : Tn moyenne sur la période
  - TxMax  : Tx maximale sur la période
  - TxMoy  : Tx moyenne sur la période
  - TmMoy  : Tm moyenne sur la période
  - NDays  : nombre de jours avec donnée Tn

Le seuil "nuit tropicale" est Tn ≥ 20 °C (recommandation OMM /
Météo-France). Une station est gardée si elle dispose d'au moins
``--min-days`` jours de données sur la période (par défaut 7).

USAGE
-----
    python scripts/02_compute_indicators.py --episode dome-chaleur-mai-2026

SORTIE
------
    data/processed/<episode-id>/indicators_<episode-id>.csv
    data/stations/stations_metadata.csv  (fusionné/mis à jour si absent)
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    DATA_STATIONS,
    Episode,
    get_logger,
    load_episodes,
    meteo_period_dir,
    processed_dir,
)

logger = get_logger("02_compute_indicators")

NUIT_TROPICALE_SEUIL_C = 20.0  # seuil nuit tropicale, en °C


def find_csv_files(period: str) -> list[Path]:
    """Liste les CSV Météo-France disponibles pour la période donnée."""
    d = meteo_period_dir(period)
    files = sorted(list(d.glob("Q_*.csv")) + list(d.glob("Q_*.csv.gz")))
    if not files:
        logger.warning(
            "Aucun fichier CSV trouvé dans %s. "
            "Exécuter d'abord 01_download_meteo.py ou placer les fichiers manuellement.",
            d,
        )
    return files


def load_station_data(csv_path: Path, dates_yyyymmdd: set[str]) -> pd.DataFrame:
    """
    Charge un CSV Météo-France par chunks pour limiter la consommation RAM,
    et filtre immédiatement sur l'ensemble des dates demandées.

    Crucial pour les fichiers historiques 1950-2024 qui pèsent plusieurs Go
    décompressés. Sans chunking, pandas charge des centaines de millions de
    lignes en mémoire avant de filtrer.

    Les colonnes clés utilisées :
        NUM_POSTE, NOM_USUEL, LAT, LON, ALTI, AAAAMMJJ, TN, TX, TM
    """
    chunks = []
    try:
        reader = pd.read_csv(
            csv_path,
            sep=";",
            encoding="utf-8",
            dtype={
                "NUM_POSTE": str,
                "AAAAMMJJ": str,
            },
            usecols=lambda c: c in {
                "NUM_POSTE", "NOM_USUEL", "LAT", "LON", "ALTI",
                "AAAAMMJJ", "TN", "TX", "TM",
            },
            chunksize=500_000,
            low_memory=False,
        )
        for chunk in reader:
            filtered = chunk[chunk["AAAAMMJJ"].isin(dates_yyyymmdd)]
            if not filtered.empty:
                chunks.append(filtered.copy())
    except (UnicodeDecodeError, FileNotFoundError) as e:
        logger.warning("Lecture %s impossible : %s", csv_path.name, e)
        return pd.DataFrame()
    if not chunks:
        return pd.DataFrame()
    df = pd.concat(chunks, ignore_index=True)
    for col in ("TN", "TX", "TM", "LAT", "LON", "ALTI"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def aggregate_station_indicators(
    df: pd.DataFrame, min_days: int,
) -> pd.DataFrame:
    """Calcule par NUM_POSTE les indicateurs canicule sur la période."""
    if df.empty:
        return pd.DataFrame()

    grouped = df.groupby("NUM_POSTE", as_index=False)
    rows = []
    for num_poste, gdf in grouped:
        tns = gdf["TN"].dropna()
        txs = gdf["TX"].dropna()
        tms = gdf["TM"].dropna() if "TM" in gdf.columns else pd.Series(dtype=float)
        if len(tns) < min_days:
            continue
        ntrop = int((tns >= NUIT_TROPICALE_SEUIL_C).sum())
        first = gdf.iloc[0]
        rows.append({
            "NUM_POSTE": num_poste,
            "NOM_USUEL": first["NOM_USUEL"],
            "LAT": first["LAT"],
            "LON": first["LON"],
            "ALTI": first["ALTI"],
            "NDays": int(len(tns)),
            "NTrop": ntrop,
            "TnMax": float(tns.max()),
            "TnMoy": float(tns.mean()),
            "TxMax": float(txs.max()) if not txs.empty else None,
            "TxMoy": float(txs.mean()) if not txs.empty else None,
            "TmMoy": float(tms.mean()) if not tms.empty else None,
        })
    return pd.DataFrame(rows)


def run(episode: Episode, min_days: int = 7) -> Path:
    """Calcule les indicateurs et écrit le CSV résultat."""
    period = episode.meteo_data_period or (
        f"{episode.start.year}-{episode.end.year}"
        if episode.start.year != episode.end.year
        else f"{episode.start.year}-{episode.start.year}"
    )
    csv_files = find_csv_files(period)
    if not csv_files:
        raise FileNotFoundError(
            f"Aucun CSV Météo-France pour la période {period}. "
            "Exécuter d'abord 01_download_meteo.py."
        )

    dates = episode.dates_yyyymmdd
    logger.info("Période d'analyse : %s → %s (%d jours, période MF : %s)",
                episode.start, episode.end, len(dates), period)
    logger.info("Lecture de %d fichiers CSV départementaux", len(csv_files))

    all_indicators = []
    for fp in csv_files:
        df = load_station_data(fp, dates)
        if df.empty:
            continue
        ind = aggregate_station_indicators(df, min_days=min_days)
        if not ind.empty:
            all_indicators.append(ind)

    if not all_indicators:
        raise RuntimeError("Aucune donnée exploitable sur la période.")

    out = pd.concat(all_indicators, ignore_index=True)
    out = out.drop_duplicates(subset=["NUM_POSTE"]).reset_index(drop=True)
    logger.info(
        "Indicateurs calculés pour %d stations (NTrop≥5: %d, NTrop≥3: %d)",
        len(out),
        int((out["NTrop"] >= 5).sum()),
        int((out["NTrop"] >= 3).sum()),
    )

    out_path = processed_dir(episode.id) / f"indicators_{episode.id}.csv"
    out.to_csv(out_path, index=False, encoding="utf-8")
    logger.info("Écrit : %s", out_path)

    # Mise à jour des métadonnées stations (LAT/LON/ALTI uniquement,
    # pour éviter d'avoir à les redériver à chaque épisode)
    update_stations_metadata(out)
    return out_path


def update_stations_metadata(indicators: pd.DataFrame) -> None:
    """
    Met à jour data/stations/stations_metadata.csv en y ajoutant les
    stations rencontrées dans cet épisode (sans écraser).
    """
    DATA_STATIONS.mkdir(parents=True, exist_ok=True)
    meta_path = DATA_STATIONS / "stations_metadata.csv"
    cols = ["NUM_POSTE", "NOM_USUEL", "LAT", "LON", "ALTI"]
    new_meta = indicators[cols].drop_duplicates(subset=["NUM_POSTE"])
    if meta_path.exists():
        existing = pd.read_csv(meta_path, dtype={"NUM_POSTE": str})
        combined = pd.concat([existing, new_meta], ignore_index=True)
        combined = combined.drop_duplicates(subset=["NUM_POSTE"], keep="first")
    else:
        combined = new_meta
    combined.to_csv(meta_path, index=False, encoding="utf-8")
    logger.info("Métadonnées stations à jour : %s (%d entrées)",
                meta_path, len(combined))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Calcul des indicateurs canicule par station Météo-France",
    )
    parser.add_argument(
        "--episode", required=True,
        help="Identifiant d'un épisode défini dans config/episodes.yaml",
    )
    parser.add_argument(
        "--min-days", type=int, default=7,
        help="Nombre minimum de jours de données pour conserver une station",
    )
    args = parser.parse_args()

    episodes = load_episodes()
    if args.episode not in episodes:
        logger.error("Épisode inconnu : %s", args.episode)
        return 2
    ep = episodes[args.episode]
    run(ep, min_days=args.min_days)
    return 0


if __name__ == "__main__":
    sys.exit(main())
