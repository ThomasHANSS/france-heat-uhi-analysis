#!/usr/bin/env python3
"""
04_compute_stats.py — Statistiques croisées indicateurs canicule × LCZ.

Croise indicators_<episode>.csv (script 02) et stations_lcz_<episode>.csv
(script 03) pour produire :

  - un tableau station → indicateurs + LCZ
  - des statistiques par catégorie LCZ (médiane NTrop, % stations ≥5 NTrop, etc.)
  - le top des stations par NTrop et par TnMax
  - le décompte décisif "stations urbaines compactes au sol vs reste"

USAGE
-----
    python scripts/04_compute_stats.py --episode dome-chaleur-mai-2026

SORTIES
-------
    data/results/<episode>/full_table_<episode>.csv
    data/results/<episode>/stats_by_lcz_<episode>.csv
    data/results/<episode>/top_stations_<episode>.csv
    data/results/<episode>/summary_<episode>.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    Episode,
    get_logger,
    load_episodes,
    load_lcz_config,
    processed_dir,
    results_dir,
)

logger = get_logger("04_compute_stats")


def merge_indicators_lcz(indicators_csv: Path, lcz_csv: Path) -> pd.DataFrame:
    """Joint indicateurs et classification LCZ par NUM_POSTE."""
    df_ind = pd.read_csv(indicators_csv, dtype={"NUM_POSTE": str})
    df_lcz = pd.read_csv(lcz_csv, dtype={"NUM_POSTE": str})
    # Conserver seulement les colonnes LCZ utiles dans la jointure
    lcz_cols = [
        "NUM_POSTE", "lcz_source", "lcz_category",
    ] + [c for c in df_lcz.columns if c.startswith("lcz_dom_")]
    df = df_ind.merge(df_lcz[lcz_cols], on="NUM_POSTE", how="left")
    return df


def stats_by_category(df: pd.DataFrame) -> pd.DataFrame:
    """Statistiques par catégorie LCZ."""
    rows = []
    grouped = df.groupby("lcz_category", dropna=False)
    for cat, gdf in grouped:
        rows.append({
            "category": cat if pd.notna(cat) else "non_classifie",
            "n_stations": int(len(gdf)),
            "ntrop_median": float(gdf["NTrop"].median()),
            "ntrop_mean": float(gdf["NTrop"].mean()),
            "ntrop_max": int(gdf["NTrop"].max()),
            "n_ntrop_ge_5": int((gdf["NTrop"] >= 5).sum()),
            "n_ntrop_ge_3": int((gdf["NTrop"] >= 3).sum()),
            "pct_ntrop_ge_5": round(float((gdf["NTrop"] >= 5).mean() * 100), 2),
            "tnmax_median": float(gdf["TnMax"].median()),
            "tnmax_p95": float(gdf["TnMax"].quantile(0.95)),
            "txmax_median": float(gdf["TxMax"].median()),
        })
    out = pd.DataFrame(rows).sort_values("n_stations", ascending=False)
    return out


def top_stations(df: pd.DataFrame, n: int = 30) -> dict[str, pd.DataFrame]:
    """Top stations par NTrop et par TnMax."""
    cols = [
        "NUM_POSTE", "NOM_USUEL", "LAT", "LON", "ALTI",
        "NTrop", "TnMax", "TxMax", "lcz_source", "lcz_category",
    ]
    cols = [c for c in cols if c in df.columns]
    return {
        "by_ntrop": df.sort_values(
            ["NTrop", "TnMax"], ascending=[False, False]
        ).head(n)[cols].copy(),
        "by_tnmax": df.sort_values(
            "TnMax", ascending=False
        ).head(n)[cols].copy(),
    }


def summary_for_episode(df: pd.DataFrame, episode: Episode) -> dict:
    """Résumé chiffré central pour insertion dans articles."""
    urban_compact = df[df["lcz_category"] == "urbain_compact"]
    non_bati = df[df["lcz_category"] == "non_bati"]

    # Stations ≥5 nuits tropicales, par catégorie
    top5 = df[df["NTrop"] >= 5].copy()

    pic_nocturne = df.loc[df["TnMax"].idxmax()] if not df.empty else None

    return {
        "episode_id": episode.id,
        "episode_name": episode.name,
        "period": f"{episode.start} → {episode.end}",
        "n_stations_total": int(len(df)),
        "n_stations_urbain_compact": int(len(urban_compact)),
        "n_stations_non_bati": int(len(non_bati)),
        "n_stations_5plus_ntrop": int(len(top5)),
        "n_stations_5plus_urbain_compact": int(
            (top5["lcz_category"] == "urbain_compact").sum()
        ),
        "n_stations_5plus_non_bati": int(
            (top5["lcz_category"] == "non_bati").sum()
        ),
        "median_ntrop_urbain_compact": (
            float(urban_compact["NTrop"].median())
            if not urban_compact.empty else None
        ),
        "pic_nocturne_station": (
            str(pic_nocturne["NOM_USUEL"]) if pic_nocturne is not None else None
        ),
        "pic_nocturne_value": (
            float(pic_nocturne["TnMax"]) if pic_nocturne is not None else None
        ),
        "pic_nocturne_lcz_source": (
            str(pic_nocturne.get("lcz_source", "")) if pic_nocturne is not None else None
        ),
        "pic_nocturne_lcz_category": (
            str(pic_nocturne.get("lcz_category", "")) if pic_nocturne is not None else None
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Statistiques canicule × LCZ pour un épisode",
    )
    parser.add_argument(
        "--episode", required=True,
        help="Identifiant d'un épisode défini dans config/episodes.yaml",
    )
    parser.add_argument(
        "--top-n", type=int, default=30,
        help="Nombre de stations à conserver dans les tops",
    )
    args = parser.parse_args()

    episodes = load_episodes()
    if args.episode not in episodes:
        logger.error("Épisode inconnu : %s", args.episode)
        return 2
    ep = episodes[args.episode]

    ind_csv = processed_dir(ep.id) / f"indicators_{ep.id}.csv"
    lcz_csv = processed_dir(ep.id) / f"stations_lcz_{ep.id}.csv"
    for f in (ind_csv, lcz_csv):
        if not f.exists():
            logger.error("Fichier manquant : %s", f)
            logger.error("Exécuter d'abord 02_ puis 03_ pour cet épisode.")
            return 2

    df = merge_indicators_lcz(ind_csv, lcz_csv)
    out_dir = results_dir(ep.id)

    full = out_dir / f"full_table_{ep.id}.csv"
    df.to_csv(full, index=False, encoding="utf-8")
    logger.info("Table jointe : %s (%d lignes)", full, len(df))

    by_cat = stats_by_category(df)
    by_cat_path = out_dir / f"stats_by_lcz_{ep.id}.csv"
    by_cat.to_csv(by_cat_path, index=False, encoding="utf-8")
    logger.info("Stats par catégorie LCZ : %s", by_cat_path)
    logger.info("\n%s", by_cat.to_string(index=False))

    tops = top_stations(df, n=args.top_n)
    top_ntrop_path = out_dir / f"top_stations_by_ntrop_{ep.id}.csv"
    top_tnmax_path = out_dir / f"top_stations_by_tnmax_{ep.id}.csv"
    tops["by_ntrop"].to_csv(top_ntrop_path, index=False, encoding="utf-8")
    tops["by_tnmax"].to_csv(top_tnmax_path, index=False, encoding="utf-8")
    logger.info("Top NTrop : %s", top_ntrop_path)
    logger.info("Top TnMax : %s", top_tnmax_path)

    summary = summary_for_episode(df, ep)
    summary_path = out_dir / f"summary_{ep.id}.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
    logger.info("Résumé : %s", summary_path)
    logger.info("\n%s", json.dumps(summary, ensure_ascii=False, indent=2, default=str))

    return 0


if __name__ == "__main__":
    sys.exit(main())
