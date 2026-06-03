#!/usr/bin/env python3
"""
03_classify_stations_lcz.py — Classification LCZ des stations Météo-France.

Pour chaque station, détermine sa classe LCZ dominante (Stewart & Oke 2012)
dans un buffer de 300 m et de 500 m, en utilisant :

  - Cerema LCZ_SPOT_2022_Fr (raster 1,5 m) si la station est dans une des
    88 aires urbaines couvertes ;
  - Demuzere et al. 2022 LCZ global (raster 100 m) en complément pour les
    stations hors aires urbaines Cerema.

USAGE
-----
    python scripts/03_classify_stations_lcz.py --episode dome-chaleur-mai-2026

ENTRÉES
-------
    data/processed/<episode>/indicators_<episode>.csv  (issu du script 02)
    data/raw/cerema_lcz/  (rasters .tif Cerema, à télécharger)
    data/raw/demuzere_lcz/lcz_filter_v3.tif (à télécharger depuis Zenodo)

SORTIE
------
    data/processed/<episode>/stations_lcz_<episode>.csv

PRÉREQUIS DE DONNÉES
--------------------
Avant d'exécuter ce script, télécharger les couches LCZ :

1. Cerema (88 aires urbaines) :
   https://www.data.gouv.fr/datasets/cartographie-des-zones-climatiques-locales-lcz-des-88-aires-urbaines-de-plus-de-50-000-habitants-de-france-metropolitaine
   Extraire les .tif dans data/raw/cerema_lcz/
   (le script peut télécharger automatiquement avec l'option --download-cerema)

2. Demuzere global (recommandé) :
   https://doi.org/10.5281/zenodo.6364594
   Placer le .tif dans data/raw/demuzere_lcz/
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import requests
from tqdm import tqdm

# Imports géospatiaux dans try pour message clair si absents
try:
    import rasterio
    from rasterio.mask import mask as rio_mask
    from rasterio.warp import transform_bounds
    from shapely.geometry import Point, mapping
    from pyproj import Transformer
except ImportError as e:
    sys.stderr.write(
        f"\n[FATAL] dépendance géospatiale manquante : {e}\n"
        "Installer : pip install -r requirements.txt\n"
        "Ou via conda : conda install -c conda-forge rasterio pyproj shapely\n"
    )
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    CEREMA_DIR,
    DEMUZERE_DIR,
    Episode,
    get_logger,
    load_episodes,
    load_lcz_config,
    processed_dir,
)

logger = get_logger("03_classify_lcz")

# Codes LCZ de référence (mêmes valeurs pour Cerema et Demuzere)
# Voir config/lcz_categories.yaml pour le mapping vers les catégories.
LCZ_VALID_CODES = set(range(1, 18))  # 1 à 17

# Endpoint data.gouv.fr pour le dataset Cerema LCZ
DATAGOUV_DATASET_CEREMA_LCZ = (
    "cartographie-des-zones-climatiques-locales-lcz-des-88-aires-urbaines"
    "-de-plus-de-50-000-habitants-de-france-metropolitaine"
)

# Endpoint Zenodo pour Demuzere LCZ global
ZENODO_DEMUZERE_RECORD = "6364594"


# ---------------------------------------------------------------------------
# Téléchargement optionnel des couches LCZ
# ---------------------------------------------------------------------------
def download_cerema_aires_for_stations(stations: pd.DataFrame) -> int:
    """
    Télécharge depuis data.gouv.fr les couches Cerema des aires urbaines
    susceptibles de contenir des stations. Stratégie : on télécharge toutes
    les aires (couverture exhaustive France >50k hab).

    Retourne le nombre de fichiers téléchargés.
    """
    api_url = (
        f"https://www.data.gouv.fr/api/1/datasets/"
        f"{DATAGOUV_DATASET_CEREMA_LCZ}/"
    )
    logger.info("Interrogation API data.gouv.fr Cerema LCZ : %s", api_url)
    try:
        r = requests.get(api_url, timeout=30)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        logger.error("Impossible d'interroger l'API : %s", e)
        return 0

    resources = data.get("resources", [])
    zips = [
        res for res in resources
        if (res.get("format") or "").lower() == "zip"
        or (res.get("title") or "").lower().endswith(".zip")
    ]
    logger.info("  %d ressources ZIP trouvées", len(zips))

    n_downloaded = 0
    for res in zips:
        title = res.get("title", "ressource")
        url = res.get("url")
        if not url:
            continue
        dest = CEREMA_DIR / title
        if dest.exists() and dest.stat().st_size > 0:
            continue
        logger.info("  Téléchargement : %s", title)
        try:
            with requests.get(url, stream=True, timeout=120) as rr:
                rr.raise_for_status()
                total = int(rr.headers.get("content-length", 0))
                with open(dest, "wb") as f, tqdm(
                    total=total, unit="B", unit_scale=True,
                    desc=title[:40], leave=False,
                ) as bar:
                    for chunk in rr.iter_content(chunk_size=1 << 14):
                        if chunk:
                            f.write(chunk)
                            bar.update(len(chunk))
            n_downloaded += 1
        except requests.RequestException as e:
            logger.error("  Échec : %s", e)
            dest.unlink(missing_ok=True)
    return n_downloaded


# ---------------------------------------------------------------------------
# Indexation des rasters disponibles
# ---------------------------------------------------------------------------
def list_cerema_rasters() -> list[Path]:
    """Liste les .tif Cerema présents localement (après extraction des ZIP)."""
    return sorted(CEREMA_DIR.rglob("*.tif"))


def list_demuzere_raster() -> Optional[Path]:
    """Renvoie le raster LCZ global de Demuzere si présent."""
    candidates = list(DEMUZERE_DIR.rglob("*.tif"))
    if not candidates:
        return None
    # Préférer un fichier qui contient 'lcz' dans son nom
    for c in candidates:
        if "lcz" in c.name.lower():
            return c
    return candidates[0]


def build_cerema_index(rasters: list[Path]) -> list[dict]:
    """
    Pour chaque raster Cerema, mémorise son emprise (bbox en EPSG:4326)
    pour pouvoir tester rapidement si une station tombe dedans.
    """
    index = []
    for path in rasters:
        try:
            with rasterio.open(path) as src:
                left, bottom, right, top = transform_bounds(
                    src.crs, "EPSG:4326", *src.bounds, densify_pts=21,
                )
                index.append({
                    "path": path,
                    "crs": src.crs.to_string(),
                    "bounds_wgs84": (left, bottom, right, top),
                })
        except (rasterio.RasterioIOError, OSError) as e:
            logger.warning("Raster Cerema illisible : %s (%s)", path.name, e)
    logger.info("Index Cerema : %d rasters indexés", len(index))
    return index


def find_cerema_raster_for_point(
    lat: float, lon: float, cerema_index: list[dict],
) -> Optional[dict]:
    """Trouve un raster Cerema dont l'emprise contient le point (lat, lon)."""
    for entry in cerema_index:
        left, bottom, right, top = entry["bounds_wgs84"]
        if left <= lon <= right and bottom <= lat <= top:
            return entry
    return None


# ---------------------------------------------------------------------------
# Extraction LCZ dans un buffer
# ---------------------------------------------------------------------------
def extract_lcz_in_buffer(
    raster_path: Path,
    raster_crs: str,
    lat: float,
    lon: float,
    buffer_m: float,
) -> Optional[Counter]:
    """
    Ouvre le raster, projette le point, applique un buffer de ``buffer_m``
    mètres, et compte les pixels par classe LCZ dans le buffer.

    Retourne un Counter {classe_lcz: nb_pixels} ou None en cas d'échec.
    """
    try:
        with rasterio.open(raster_path) as src:
            # Reprojeter le point WGS84 vers le CRS du raster
            tf = Transformer.from_crs(
                "EPSG:4326", src.crs, always_xy=True,
            )
            x, y = tf.transform(lon, lat)
            point = Point(x, y).buffer(buffer_m)
            # mask : extrait les pixels dans le buffer
            data, _ = rio_mask(src, [mapping(point)], crop=True, filled=False)
            arr = data[0]
            # Filtrer les valeurs valides
            valid = arr[~arr.mask] if hasattr(arr, "mask") else arr.flatten()
            valid = valid[np.isin(valid, list(LCZ_VALID_CODES))]
            if valid.size == 0:
                return None
            return Counter(valid.tolist())
    except Exception as e:  # rasterio + numpy, attraper large
        logger.debug("Extraction LCZ échouée pour %s : %s",
                     raster_path.name, e)
        return None


def dominant_class(counter: Counter) -> Optional[int]:
    """Renvoie la classe LCZ la plus représentée."""
    if not counter:
        return None
    return int(counter.most_common(1)[0][0])


def category_for_lcz(lcz_code: Optional[int], lcz_config: dict) -> Optional[str]:
    """Renvoie la catégorie (urbain_compact, urbain_aere, ...) d'une classe LCZ."""
    if lcz_code is None:
        return None
    for cat_id, cat in lcz_config["categories"].items():
        if lcz_code in cat["lcz_codes"]:
            return cat_id
    return None


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------
def classify_stations(
    indicators_csv: Path,
    cerema_index: list[dict],
    demuzere_raster: Optional[Path],
    lcz_config: dict,
    buffer_radii: list[int],
) -> pd.DataFrame:
    """Classifie toutes les stations du fichier indicators."""
    stations = pd.read_csv(indicators_csv, dtype={"NUM_POSTE": str})
    logger.info("Classification LCZ de %d stations", len(stations))

    out_rows = []
    n_cerema = 0
    n_demuzere = 0
    n_none = 0

    for _, row in tqdm(stations.iterrows(), total=len(stations),
                       desc="Stations"):
        lat = row["LAT"]
        lon = row["LON"]
        if pd.isna(lat) or pd.isna(lon):
            continue

        # Tenter Cerema en priorité
        cerema = find_cerema_raster_for_point(lat, lon, cerema_index)
        source = None
        lcz_per_radius: dict[int, Optional[int]] = {}
        composition_per_radius: dict[int, dict] = {}

        if cerema is not None:
            source = "cerema"
            for radius in buffer_radii:
                counter = extract_lcz_in_buffer(
                    cerema["path"], cerema["crs"], lat, lon, radius,
                )
                lcz_per_radius[radius] = dominant_class(counter) if counter else None
                composition_per_radius[radius] = dict(counter) if counter else {}

        # Fallback Demuzere si Cerema absent ou pas de pixels
        if (source is None or
            lcz_per_radius.get(buffer_radii[0]) is None) and demuzere_raster:
            source = "demuzere"
            for radius in buffer_radii:
                counter = extract_lcz_in_buffer(
                    demuzere_raster, None, lat, lon, radius,
                )
                lcz_per_radius[radius] = dominant_class(counter) if counter else None
                composition_per_radius[radius] = dict(counter) if counter else {}

        if source == "cerema":
            n_cerema += 1
        elif source == "demuzere":
            n_demuzere += 1
        else:
            n_none += 1

        primary_radius = lcz_config["classification"]["primary_radius_m"]
        primary_lcz = lcz_per_radius.get(primary_radius)
        category = category_for_lcz(primary_lcz, lcz_config)

        out_rows.append({
            "NUM_POSTE": row["NUM_POSTE"],
            "NOM_USUEL": row["NOM_USUEL"],
            "LAT": lat,
            "LON": lon,
            "ALTI": row.get("ALTI"),
            "lcz_source": source,
            **{
                f"lcz_dom_{r}m": lcz_per_radius.get(r)
                for r in buffer_radii
            },
            **{
                f"lcz_comp_{r}m": json.dumps(composition_per_radius.get(r, {}))
                for r in buffer_radii
            },
            "lcz_category": category,
        })

    logger.info(
        "Sources utilisées : Cerema=%d, Demuzere=%d, aucune=%d",
        n_cerema, n_demuzere, n_none,
    )
    return pd.DataFrame(out_rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Classification LCZ hybride (Cerema + Demuzere) des stations Météo-France",
    )
    parser.add_argument(
        "--episode", required=True,
        help="Identifiant d'un épisode défini dans config/episodes.yaml",
    )
    parser.add_argument(
        "--download-cerema", action="store_true",
        help="Tente de télécharger automatiquement les couches Cerema "
             "depuis data.gouv.fr (~10 Go au total).",
    )
    args = parser.parse_args()

    episodes = load_episodes()
    if args.episode not in episodes:
        logger.error("Épisode inconnu : %s", args.episode)
        return 2
    ep = episodes[args.episode]
    lcz_config = load_lcz_config()

    indicators_csv = processed_dir(ep.id) / f"indicators_{ep.id}.csv"
    if not indicators_csv.exists():
        logger.error("Fichier indicators manquant : %s", indicators_csv)
        logger.error("Exécuter d'abord : python scripts/02_compute_indicators.py --episode %s",
                     ep.id)
        return 2

    if args.download_cerema:
        download_cerema_aires_for_stations(pd.read_csv(indicators_csv))
        logger.info(
            "Penser à extraire les ZIP dans %s avant la classification.",
            CEREMA_DIR,
        )

    cerema_rasters = list_cerema_rasters()
    if not cerema_rasters:
        logger.warning(
            "Aucun raster Cerema trouvé dans %s. "
            "Télécharger depuis https://www.data.gouv.fr/datasets/%s",
            CEREMA_DIR, DATAGOUV_DATASET_CEREMA_LCZ,
        )
    cerema_index = build_cerema_index(cerema_rasters)

    demuzere_raster = list_demuzere_raster()
    if demuzere_raster is None:
        logger.warning(
            "Aucun raster Demuzere trouvé dans %s. "
            "Télécharger depuis https://doi.org/10.5281/zenodo.6364594. "
            "Les stations hors aires Cerema seront non classifiées.",
            DEMUZERE_DIR,
        )

    buffer_radii = lcz_config["classification"]["buffer_radii_m"]
    out_df = classify_stations(
        indicators_csv, cerema_index, demuzere_raster,
        lcz_config, buffer_radii,
    )

    out_path = processed_dir(ep.id) / f"stations_lcz_{ep.id}.csv"
    out_df.to_csv(out_path, index=False, encoding="utf-8")
    logger.info("Écrit : %s", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
