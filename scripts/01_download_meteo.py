#!/usr/bin/env python3
"""
01_download_meteo.py — Acquisition des données climatologiques Météo-France.

Télécharge les CSV quotidiens de Météo-France pour la période d'un épisode
depuis l'API publique data.gouv.fr.

Source : « Données climatologiques de base — quotidiennes » publiées par
Météo-France sur meteo.data.gouv.fr. Licence Ouverte 2.0 (Etalab).

Convention de nommage Météo-France (juin 2026) :
    QUOT_departement_{DEPT}_periode_{PERIODE}_RR-T-Vent

Trois périodes par département :
    - avant-1949   : historique antérieur (mise à jour annuelle)
    - 1950-2024    : long terme (mise à jour mensuelle)
    - 2025-2026    : récent (mise à jour quotidienne)

Le script sélectionne la ressource qui contient l'année cible de l'épisode.

USAGE
-----
    python scripts/01_download_meteo.py --episode dome-chaleur-mai-2026
    python scripts/01_download_meteo.py --target-year 2003
    python scripts/01_download_meteo.py --list-episodes
"""

from __future__ import annotations

import argparse
import gzip
import re
import shutil
import sys
from pathlib import Path

import requests
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    get_logger,
    load_episodes,
    meteo_period_dir,
)

logger = get_logger("01_download_meteo")

DATAGOUV_DATASET_QUOTIDIENNES = "donnees-climatologiques-de-base-quotidiennes"
DATAGOUV_API_DATASET = (
    "https://www.data.gouv.fr/api/1/datasets/{slug}/"
)

# Pattern attendu pour les ressources de données quotidiennes Météo-France.
# Ex : "QUOT_departement_75_periode_2025-2026_RR-T-Vent"
#      "QUOT_departement_2A_periode_1950-2024_RR-T-Vent"
#      "QUOT_departement_01_periode_avant-1949_RR-T-Vent"
QUOT_PATTERN = re.compile(
    r"QUOT_departement_(?P<dept>2A|2B|\d{2})_periode_(?P<period>(?:avant-)?\d{4}(?:-\d{4})?)_RR-T-Vent",
    re.IGNORECASE,
)


def fetch_dataset_resources(slug: str) -> list[dict]:
    """Interroge l'API data.gouv.fr et retourne la liste des ressources."""
    url = DATAGOUV_API_DATASET.format(slug=slug)
    logger.info("Interrogation de l'API data.gouv.fr : %s", url)
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        logger.error("Impossible d'interroger l'API : %s", e)
        return []
    resources = data.get("resources", [])
    logger.info("  %d ressources trouvées dans le dataset", len(resources))
    return resources


def _parse_period_bounds(period: str) -> tuple[int, int]:
    """Convertit une chaîne de période en (start_year, end_year)."""
    if period.startswith("avant-"):
        return (1850, int(period.split("-", 1)[1]))
    parts = period.split("-")
    if len(parts) == 1:
        y = int(parts[0])
        return (y, y)
    return (int(parts[0]), int(parts[1]))


def select_resources_for_year(
    resources: list[dict], target_year: int,
) -> list[tuple[str, str, str, str]]:
    """
    Sélectionne les ressources Météo-France contenant ``target_year``.

    Retourne une liste de (titre, url_telechargement, dept, période).
    """
    selected = []
    for res in resources:
        title = res.get("title", "") or ""
        match = QUOT_PATTERN.search(title)
        if not match:
            continue
        dept = match.group("dept")
        period = match.group("period")
        r_start, r_end = _parse_period_bounds(period)
        if r_start <= target_year <= r_end:
            url = res.get("latest") or res.get("url")
            if url:
                selected.append((title, url, dept, period))
    return selected


def download_file(url: str, dest: Path, chunk_size: int = 1 << 14) -> bool:
    """Télécharge un fichier en streaming, et décompresse à la volée si gzip."""
    try:
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            tmp = dest.with_suffix(dest.suffix + ".tmp")
            with open(tmp, "wb") as f, tqdm(
                total=total, unit="B", unit_scale=True,
                desc=dest.name, leave=False,
            ) as bar:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        bar.update(len(chunk))
        # Détection gzip via magic bytes, et décompression si besoin
        with open(tmp, "rb") as fh:
            magic = fh.read(2)
        if magic == b"\x1f\x8b":
            with gzip.open(tmp, "rb") as fin, open(dest, "wb") as fout:
                shutil.copyfileobj(fin, fout)
            tmp.unlink(missing_ok=True)
        else:
            tmp.replace(dest)
        return True
    except requests.RequestException as e:
        logger.error("  Échec téléchargement %s : %s", url, e)
        if dest.exists():
            dest.unlink(missing_ok=True)
        return False


def download_for_target_year(target_year: int, dest_subdir: str) -> None:
    """Télécharge les fichiers Météo-France contenant l'année cible."""
    dest_dir = meteo_period_dir(dest_subdir)
    logger.info("Année cible : %d", target_year)
    logger.info("Répertoire de destination : %s", dest_dir)

    resources = fetch_dataset_resources(DATAGOUV_DATASET_QUOTIDIENNES)
    if not resources:
        logger.warning(
            "Aucune ressource récupérée via l'API. "
            "Téléchargez manuellement depuis : "
            "https://www.data.gouv.fr/datasets/%s/",
            DATAGOUV_DATASET_QUOTIDIENNES,
        )
        return

    matches = select_resources_for_year(resources, target_year)
    if not matches:
        logger.warning(
            "Aucune ressource ne couvre l'année %d. Vérifier le dataset.",
            target_year,
        )
        return

    # Une seule ressource par département (devrait être unique pour une année donnée)
    by_dept: dict[str, tuple[str, str, str]] = {}
    for title, url, dept, period in matches:
        if dept not in by_dept:
            by_dept[dept] = (title, url, period)

    logger.info(
        "%d département(s) à traiter pour l'année %d",
        len(by_dept), target_year,
    )

    n_ok = 0
    n_skip = 0
    n_fail = 0
    for dept in sorted(by_dept):
        title, url, period = by_dept[dept]
        # Détecter l'extension (CSV brut ou CSV gzippé)
        ext = ".csv.gz" if url.lower().endswith(".gz") else ".csv"
        dest = dest_dir / f"Q_{dept}_{period}{ext}"
        if dest.exists() and dest.stat().st_size > 0:
            logger.info("[%s] déjà présent (%s)", dept, dest.name)
            n_skip += 1
            continue
        logger.info("[%s] téléchargement %s …", dept, title)
        ok = download_file(url, dest)
        if ok:
            n_ok += 1
        else:
            n_fail += 1

    logger.info(
        "Bilan : %d téléchargés, %d déjà présents, %d échecs",
        n_ok, n_skip, n_fail,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Téléchargement des données Météo-France quotidiennes",
    )
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument(
        "--episode",
        help="Identifiant d'un épisode défini dans config/episodes.yaml",
    )
    grp.add_argument(
        "--target-year", type=int,
        help="Année cible à couvrir (ex: 2003, 2026)",
    )
    grp.add_argument(
        "--list-episodes",
        action="store_true",
        help="Liste les épisodes définis et sort",
    )
    args = parser.parse_args()

    episodes = load_episodes()

    if args.list_episodes:
        print("Épisodes définis dans config/episodes.yaml :")
        for ep_id, ep in episodes.items():
            print(f"  {ep_id:<35} {ep.name}")
        return 0

    if args.target_year:
        subdir = str(args.target_year)
        download_for_target_year(args.target_year, subdir)
        return 0

    if args.episode:
        if args.episode not in episodes:
            logger.error("Épisode inconnu : %s", args.episode)
            logger.info(
                "Épisodes disponibles : %s",
                ", ".join(sorted(episodes.keys())),
            )
            return 2
        ep = episodes[args.episode]
        target_year = ep.end.year
        subdir = ep.meteo_data_period or str(target_year)
        logger.info("Épisode : %s (%s → %s, année cible : %d, sous-dossier : %s)",
                    ep.id, ep.start, ep.end, target_year, subdir)
        download_for_target_year(target_year, subdir)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
