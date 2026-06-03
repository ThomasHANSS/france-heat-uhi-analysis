#!/usr/bin/env python3
"""
03_classify_stations_lcz.py — Classification LCZ hybride.

Pour chaque station Météo-France, détermine sa composition LCZ dans des
buffers de 300 m et 500 m, à partir de :

  - Cerema LCZ_SPOT_2022_Fr : shapefiles vectoriels par aire urbaine
    (résolution équivalente 1.5 m). Utilisé en priorité quand la station
    tombe dans une des 88 aires urbaines françaises >50 000 habitants.
    Intersection géométrique exacte des polygones LCZ avec le buffer.

  - Demuzere et al. 2022 : raster global 100 m. Utilisé en fallback pour
    les stations hors aires Cerema. Comptage des pixels par classe LCZ
    dans le buffer.

Les deux sources utilisent le même codage entier (1-10 pour LCZ bâti,
11-17 pour A-G), permettant une agrégation homogène.

Buffer construit en projection azimuthale équidistante (AEQD) centrée sur
le point, garantissant l'exactitude métrique du rayon quel que soit le
CRS source.

USAGE
-----
    python scripts/03_classify_stations_lcz.py --episode <episode-id>
    python scripts/03_classify_stations_lcz.py --episode <episode-id> --download-cerema
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import requests
from tqdm import tqdm

try:
    import geopandas as gpd
    import rasterio
    from rasterio.mask import mask as rio_mask
    from shapely.geometry import Point, mapping
    from shapely.ops import transform as shapely_transform
    from pyproj import Transformer
except ImportError as e:
    sys.stderr.write(
        f"\n[FATAL] dépendance géospatiale manquante : {e}\n"
        "Installer : pip install -r requirements.txt\n"
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

LCZ_VALID_CODES = set(range(1, 18))

DATAGOUV_DATASET_CEREMA_LCZ = (
    "cartographie-des-zones-climatiques-locales-lcz-des-88-aires-urbaines"
    "-de-plus-de-50-000-habitants-de-france-metropolitaine"
)


# ---------------------------------------------------------------------------
# Téléchargement Cerema sélectif (n'extrait QUE le shapefile, pas le raster)
# ---------------------------------------------------------------------------
def list_cerema_resources() -> list[dict]:
    """Liste les ZIP Cerema disponibles via data.gouv.fr."""
    url = f"https://www.data.gouv.fr/api/1/datasets/{DATAGOUV_DATASET_CEREMA_LCZ}/"
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        logger.error("Impossible d'interroger l'API Cerema : %s", e)
        return []
    resources = []
    for res in data.get("resources", []):
        title = res.get("title", "")
        if title.lower().endswith(".zip"):
            resources.append({
                "title": title,
                "url": res.get("latest") or res.get("url"),
                "size_mb": (res.get("filesize") or 0) / 1e6,
            })
    return resources


def download_and_extract_cerema_zip(res_dict: dict) -> Optional[Path]:
    """Télécharge un ZIP Cerema et extrait UNIQUEMENT le shapefile.
    Saute le raster .tif (10 Go par aire) et la carte PDF."""
    title = res_dict["title"]
    # Le nom du dossier est dérivé du titre, e.g. lcz-spot-2022-paris.zip → paris
    name = title.replace(".zip", "").replace("lcz-spot-2022-", "").lower()
    extract_dir = CEREMA_DIR / name
    if list(extract_dir.glob("LCZ_SPOT_2022_*.shp")):
        return extract_dir

    zip_path = CEREMA_DIR / title
    if not zip_path.exists():
        logger.info("  Téléchargement %s (~%.0f MB)…", title, res_dict["size_mb"])
        try:
            with requests.get(res_dict["url"], stream=True, timeout=300) as r:
                r.raise_for_status()
                with open(zip_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1 << 16):
                        if chunk:
                            f.write(chunk)
        except requests.RequestException as e:
            logger.error("  Échec téléchargement : %s", e)
            zip_path.unlink(missing_ok=True)
            return None

    extract_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.namelist():
                # Skip raster .tif (10 Go) et carte PDF (≈100 Mo)
                lname = member.lower()
                if "_raster_" in lname or "_carte.pdf" in lname:
                    continue
                zf.extract(member, extract_dir)
    except zipfile.BadZipFile as e:
        logger.error("  ZIP corrompu : %s", e)
        return None

    # Nettoyer le ZIP source
    zip_path.unlink(missing_ok=True)
    return extract_dir


# ---------------------------------------------------------------------------
# Indexation des shapefiles Cerema disponibles localement
# ---------------------------------------------------------------------------
def list_cerema_shapefiles() -> list[Path]:
    """Liste tous les shapefiles LCZ Cerema disponibles localement."""
    return sorted(CEREMA_DIR.rglob("LCZ_SPOT_2022_*.shp"))


def list_demuzere_raster() -> Optional[Path]:
    """Renvoie le raster LCZ Demuzere France (priorité) ou global."""
    candidates = list(DEMUZERE_DIR.rglob("*.tif"))
    # Priorité : fichier "france" + "lcz"
    for c in candidates:
        n = c.name.lower()
        if "france" in n and "lcz" in n:
            return c
    # Sinon : n'importe quel "lcz"
    for c in candidates:
        if "lcz" in c.name.lower():
            return c
    return candidates[0] if candidates else None


def load_cerema_index(shapefiles: list[Path]) -> list[dict]:
    """Charge chaque shapefile en mémoire avec emprise WGS84 pour test rapide."""
    index = []
    for shp in shapefiles:
        try:
            gdf = gpd.read_file(shp)
            bbox_wgs84 = gdf.to_crs("EPSG:4326").total_bounds
            index.append({
                "path": shp,
                "name": shp.stem.replace("LCZ_SPOT_2022_", ""),
                "crs": gdf.crs,
                "bbox_wgs84": tuple(bbox_wgs84),
                "gdf": gdf,
            })
            logger.info("  Indexé : %s (%d polygones)", shp.name, len(gdf))
        except Exception as e:
            logger.warning("  Shapefile illisible : %s (%s)", shp.name, e)
    logger.info("Index Cerema : %d aire(s) urbaine(s) chargée(s)", len(index))
    return index


def find_cerema_for_point(
    lat: float, lon: float, cerema_index: list[dict],
) -> Optional[dict]:
    """Renvoie l'entrée Cerema dont l'emprise contient le point."""
    for entry in cerema_index:
        left, bottom, right, top = entry["bbox_wgs84"]
        if left <= lon <= right and bottom <= lat <= top:
            return entry
    return None


# ---------------------------------------------------------------------------
# Extraction LCZ — Cerema (vectoriel)
# ---------------------------------------------------------------------------
def extract_lcz_from_cerema(
    entry: dict, lat: float, lon: float, buffer_m: float,
) -> Optional[Counter]:
    """Composition LCZ dans le buffer via intersection vectorielle."""
    try:
        local_proj = (
            f"+proj=aeqd +lat_0={lat} +lon_0={lon} "
            "+x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
        )
        buffer_local = Point(0, 0).buffer(buffer_m)
        tf = Transformer.from_crs(local_proj, entry["crs"], always_xy=True)
        buffer_target = shapely_transform(tf.transform, buffer_local)

        gdf = entry["gdf"]
        # Pré-filtrage spatial via sindex (rapide)
        possible_idx = list(gdf.sindex.intersection(buffer_target.bounds))
        if not possible_idx:
            return None

        candidates = gdf.iloc[possible_idx]
        composition: Counter = Counter()
        for _, row in candidates.iterrows():
            inter = row.geometry.intersection(buffer_target)
            if inter.is_empty:
                continue
            lcz_int = int(row["lcz_int"])
            if lcz_int in LCZ_VALID_CODES:
                composition[lcz_int] += inter.area  # m² (CRS métrique)
        return composition if composition else None
    except Exception as e:
        logger.debug("Extraction Cerema échouée : %s", e)
        return None


# ---------------------------------------------------------------------------
# Extraction LCZ — Demuzere (raster)
# ---------------------------------------------------------------------------
def extract_lcz_from_demuzere(
    raster_path: Path, lat: float, lon: float, buffer_m: float,
) -> Optional[Counter]:
    """Composition LCZ dans le buffer via comptage de pixels."""
    try:
        with rasterio.open(raster_path) as src:
            local_proj = (
                f"+proj=aeqd +lat_0={lat} +lon_0={lon} "
                "+x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
            )
            buffer_local = Point(0, 0).buffer(buffer_m)
            tf = Transformer.from_crs(local_proj, src.crs, always_xy=True)
            buffer_target = shapely_transform(tf.transform, buffer_local)
            data, _ = rio_mask(src, [mapping(buffer_target)],
                               crop=True, filled=False)
            arr = data[0]
            valid = arr[~arr.mask] if hasattr(arr, "mask") else arr.flatten()
            valid = valid[np.isin(valid, list(LCZ_VALID_CODES))]
            if valid.size == 0:
                return None
            return Counter(valid.tolist())
    except Exception as e:
        logger.debug("Extraction Demuzere échouée : %s", e)
        return None


# ---------------------------------------------------------------------------
# Classification de toutes les stations d'un épisode
# ---------------------------------------------------------------------------
def dominant_class(counter: Optional[Counter]) -> Optional[int]:
    if not counter:
        return None
    return int(counter.most_common(1)[0][0])


def category_for_lcz(
    lcz_code: Optional[int], lcz_config: dict,
) -> Optional[str]:
    if lcz_code is None:
        return None
    for cat_id, cat in lcz_config["categories"].items():
        if lcz_code in cat["lcz_codes"]:
            return cat_id
    return None


def classify_stations(
    indicators_csv: Path,
    cerema_index: list[dict],
    demuzere_raster: Optional[Path],
    lcz_config: dict,
    buffer_radii: list[int],
) -> pd.DataFrame:
    stations = pd.read_csv(indicators_csv, dtype={"NUM_POSTE": str})
    logger.info("Classification LCZ de %d stations", len(stations))

    out_rows = []
    n_cerema = n_demuzere = n_none = 0

    for _, row in tqdm(stations.iterrows(), total=len(stations),
                       desc="Stations", unit="st"):
        lat = row["LAT"]
        lon = row["LON"]
        if pd.isna(lat) or pd.isna(lon):
            continue

        # Cerema en priorité si la station tombe dans une aire couverte
        cerema = find_cerema_for_point(lat, lon, cerema_index)
        source = None
        lcz_per_radius: dict[int, Optional[int]] = {}
        composition_per_radius: dict[int, dict] = {}

        if cerema is not None:
            source = "cerema"
            for radius in buffer_radii:
                counter = extract_lcz_from_cerema(cerema, lat, lon, radius)
                lcz_per_radius[radius] = dominant_class(counter)
                composition_per_radius[radius] = dict(counter) if counter else {}

        # Fallback Demuzere si pas couvert Cerema ou pas de polygone trouvé
        if ((source is None or lcz_per_radius.get(buffer_radii[0]) is None)
                and demuzere_raster):
            source = "demuzere"
            for radius in buffer_radii:
                counter = extract_lcz_from_demuzere(demuzere_raster, lat, lon, radius)
                lcz_per_radius[radius] = dominant_class(counter)
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
            **{f"lcz_dom_{r}m": lcz_per_radius.get(r) for r in buffer_radii},
            **{f"lcz_comp_{r}m": json.dumps(composition_per_radius.get(r, {}),
                                            default=float)
               for r in buffer_radii},
            "lcz_category": category,
        })

    logger.info("Sources : Cerema=%d, Demuzere=%d, aucune=%d",
                n_cerema, n_demuzere, n_none)
    return pd.DataFrame(out_rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Classification LCZ hybride (Cerema vecteur + Demuzere raster)",
    )
    parser.add_argument("--episode", required=True)
    parser.add_argument(
        "--download-cerema", action="store_true",
        help="Télécharge automatiquement TOUTES les aires Cerema manquantes",
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
        return 2

    if args.download_cerema:
        logger.info("Téléchargement de toutes les aires Cerema (≈30 GB total) …")
        for res in list_cerema_resources():
            try:
                download_and_extract_cerema_zip(res)
            except Exception as e:
                logger.error("Échec %s : %s", res["title"], e)

    cerema_shapefiles = list_cerema_shapefiles()
    if not cerema_shapefiles:
        logger.warning(
            "Aucun shapefile Cerema trouvé dans %s.",
            CEREMA_DIR,
        )
    cerema_index = load_cerema_index(cerema_shapefiles)

    demuzere_raster = list_demuzere_raster()
    if demuzere_raster is None:
        logger.warning(
            "Aucun raster Demuzere trouvé dans %s.", DEMUZERE_DIR,
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
