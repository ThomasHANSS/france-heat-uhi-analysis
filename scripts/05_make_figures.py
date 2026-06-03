#!/usr/bin/env python3
"""
05_make_figures.py — Génération des figures publiables pour un épisode.

Produit dans data/results/<episode>/figures/ :

  - boxplot_ntrop_by_lcz.svg      : distribution NTrop par catégorie LCZ
  - bar_ntrop_top_stations.svg    : top 20 stations par NTrop, colorées par LCZ
  - scatter_tnmax_tx_max.svg      : nuage Tn vs Tx, coloré par LCZ
  - map_stations_5plus.svg        : carte des stations ≥5 NTrop (cartopy optionnel)

USAGE
-----
    python scripts/05_make_figures.py --episode dome-chaleur-mai-2026
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    Episode,
    get_logger,
    load_episodes,
    load_lcz_config,
    results_dir,
)

logger = get_logger("05_make_figures")


CATEGORY_ORDER = ["urbain_compact", "urbain_aere", "bati_special", "non_bati"]


def _setup_figures_dir(ep: Episode) -> Path:
    d = results_dir(ep.id) / "figures"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_full_table(ep: Episode) -> pd.DataFrame:
    csv = results_dir(ep.id) / f"full_table_{ep.id}.csv"
    if not csv.exists():
        raise FileNotFoundError(
            f"{csv} introuvable. Exécuter d'abord 04_compute_stats.py."
        )
    return pd.read_csv(csv, dtype={"NUM_POSTE": str})


def _category_colors(lcz_config: dict) -> dict[str, str]:
    return {
        cat_id: cat["color"]
        for cat_id, cat in lcz_config["categories"].items()
    }


def fig_boxplot_ntrop_by_lcz(
    df: pd.DataFrame, lcz_config: dict, out_dir: Path, episode: Episode,
) -> Path:
    """Boxplot du nombre de nuits tropicales par catégorie LCZ."""
    colors = _category_colors(lcz_config)
    cats = [c for c in CATEGORY_ORDER if c in df["lcz_category"].unique()]
    data = [df.loc[df["lcz_category"] == c, "NTrop"].dropna().values for c in cats]
    labels = [
        lcz_config["categories"][c]["label"].replace(" (", "\n(")
        for c in cats
    ]

    fig, ax = plt.subplots(figsize=(9, 5))
    bp = ax.boxplot(
        data, patch_artist=True, showfliers=True,
        medianprops={"color": "black", "linewidth": 1.5},
        flierprops={"marker": "o", "markersize": 3, "alpha": 0.5},
    )
    for patch, cat in zip(bp["boxes"], cats):
        patch.set_facecolor(colors.get(cat, "#888888"))
        patch.set_alpha(0.7)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("Nuits tropicales (Tn ≥ 20 °C)")
    ax.set_title(f"Distribution des nuits tropicales par classe LCZ\n{episode.name}",
                 fontsize=11)
    ax.grid(True, axis="y", linestyle=":", alpha=0.5)
    fig.tight_layout()
    out = out_dir / "boxplot_ntrop_by_lcz.svg"
    fig.savefig(out, format="svg")
    plt.close(fig)
    logger.info("Figure : %s", out)
    return out


def fig_top_stations_ntrop(
    df: pd.DataFrame, lcz_config: dict, out_dir: Path, episode: Episode,
    n: int = 20,
) -> Path:
    """Barres horizontales : top N stations par NTrop, colorées par LCZ."""
    colors = _category_colors(lcz_config)
    top = df.sort_values(["NTrop", "TnMax"], ascending=[False, False]).head(n)
    bar_colors = [
        colors.get(c, "#888888") for c in top["lcz_category"].fillna("non_classifie")
    ]
    labels = [
        f"{row['NOM_USUEL'][:35]} ({row['NUM_POSTE'][:2]})"
        for _, row in top.iterrows()
    ]

    fig, ax = plt.subplots(figsize=(10, max(5, n * 0.35)))
    ax.barh(range(len(top)), top["NTrop"].values, color=bar_colors, edgecolor="black",
            linewidth=0.4)
    ax.set_yticks(range(len(top)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("Nuits tropicales (Tn ≥ 20 °C)")
    ax.set_title(f"Top {n} stations par nombre de nuits tropicales\n{episode.name}",
                 fontsize=11)
    ax.grid(True, axis="x", linestyle=":", alpha=0.5)

    # Légende des catégories
    from matplotlib.patches import Patch
    handles = [
        Patch(facecolor=colors[c], edgecolor="black",
              label=lcz_config["categories"][c]["label"])
        for c in CATEGORY_ORDER if c in df["lcz_category"].unique()
    ]
    ax.legend(handles=handles, loc="lower right", fontsize=8, framealpha=0.9)
    fig.tight_layout()
    out = out_dir / "bar_ntrop_top_stations.svg"
    fig.savefig(out, format="svg")
    plt.close(fig)
    logger.info("Figure : %s", out)
    return out


def fig_scatter_tn_tx(
    df: pd.DataFrame, lcz_config: dict, out_dir: Path, episode: Episode,
) -> Path:
    """Nuage de points TnMax vs TxMax, coloré par LCZ."""
    colors = _category_colors(lcz_config)
    fig, ax = plt.subplots(figsize=(8, 6))
    for cat in CATEGORY_ORDER:
        sub = df[df["lcz_category"] == cat]
        if sub.empty:
            continue
        ax.scatter(sub["TxMax"], sub["TnMax"], s=14,
                   color=colors[cat], alpha=0.55,
                   label=lcz_config["categories"][cat]["label"],
                   edgecolors="none")
    ax.axhline(20, color="red", linestyle="--", linewidth=0.8, alpha=0.5)
    ax.text(ax.get_xlim()[0], 20.2, "  seuil nuit tropicale (Tn=20 °C)",
            fontsize=8, color="red", alpha=0.7)
    ax.set_xlabel("TxMax sur l'épisode (°C)")
    ax.set_ylabel("TnMax sur l'épisode (°C)")
    ax.set_title(f"Nuage TnMax vs TxMax par classe LCZ\n{episode.name}", fontsize=11)
    ax.grid(True, linestyle=":", alpha=0.5)
    ax.legend(loc="lower right", fontsize=8, framealpha=0.9)
    fig.tight_layout()
    out = out_dir / "scatter_tnmax_txmax.svg"
    fig.savefig(out, format="svg")
    plt.close(fig)
    logger.info("Figure : %s", out)
    return out


def fig_map_stations(
    df: pd.DataFrame, lcz_config: dict, out_dir: Path, episode: Episode,
    min_ntrop: int = 5,
) -> Path:
    """Carte simplifiée des stations ≥min_ntrop nuits tropicales."""
    colors = _category_colors(lcz_config)
    sub = df[df["NTrop"] >= min_ntrop].copy()

    fig, ax = plt.subplots(figsize=(8, 9))

    # Tracé sobre des contours France (utilise les bornes des points si pas de
    # carte fournie). Pour une carte plus belle, ajouter contextily ou cartopy.
    ax.set_xlim(-5.5, 10)
    ax.set_ylim(41, 51.5)

    # Tracer toutes les stations en arrière-plan en gris clair
    ax.scatter(df["LON"], df["LAT"], s=4, color="#cccccc", alpha=0.4, edgecolors="none",
               label="Toutes stations")

    # Tracer les stations ≥min_ntrop colorées par catégorie
    for cat in CATEGORY_ORDER:
        s = sub[sub["lcz_category"] == cat]
        if s.empty:
            continue
        ax.scatter(s["LON"], s["LAT"], s=80, color=colors[cat],
                   edgecolor="black", linewidth=0.7, alpha=0.9,
                   label=lcz_config["categories"][cat]["label"])

    # Étiquettes des stations les plus marquantes
    for _, r in sub.iterrows():
        ax.annotate(
            r["NOM_USUEL"][:25],
            xy=(r["LON"], r["LAT"]),
            xytext=(4, 2), textcoords="offset points",
            fontsize=7, alpha=0.8,
        )

    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title(
        f"Stations Météo-France à ≥{min_ntrop} nuits tropicales — {episode.name}",
        fontsize=11,
    )
    ax.legend(loc="lower left", fontsize=8, framealpha=0.9)
    ax.set_aspect(1.4)
    ax.grid(True, linestyle=":", alpha=0.4)
    fig.tight_layout()
    out = out_dir / f"map_stations_{min_ntrop}plus.svg"
    fig.savefig(out, format="svg")
    plt.close(fig)
    logger.info("Figure : %s", out)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Génération des figures publiables pour un épisode",
    )
    parser.add_argument(
        "--episode", required=True,
        help="Identifiant d'un épisode défini dans config/episodes.yaml",
    )
    args = parser.parse_args()

    episodes = load_episodes()
    if args.episode not in episodes:
        logger.error("Épisode inconnu : %s", args.episode)
        return 2
    ep = episodes[args.episode]
    lcz_config = load_lcz_config()
    df = load_full_table(ep)
    out_dir = _setup_figures_dir(ep)

    fig_boxplot_ntrop_by_lcz(df, lcz_config, out_dir, ep)
    fig_top_stations_ntrop(df, lcz_config, out_dir, ep, n=20)
    fig_scatter_tn_tx(df, lcz_config, out_dir, ep)
    fig_map_stations(df, lcz_config, out_dir, ep, min_ntrop=5)
    logger.info("Toutes figures écrites dans %s", out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
