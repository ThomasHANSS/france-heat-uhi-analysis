#!/usr/bin/env python3
"""
01_download_meteo.py — Acquisition des données climatologiques Météo-France.

Télécharge les CSV quotidiens de Météo-France pour la période d'un épisode
depuis l'API publique data.gouv.fr.

Source : « Données climatologiques de base — quotidiennes » publiées par
Météo-France sur meteo.data.gouv.fr. Licence Ouverte 2.0 (Etalab).

Si les CSV sont déjà présents dans data/raw/meteo_france/<période>/, le script
les laisse en place.

USAGE
-----
    python scripts/01_download_meteo.py --episode dome-chaleur-mai-2026
    python scripts/01_download_meteo.py --period 2025-2026
    python scripts/01_download_meteo.py --list-episodes

NOTE
----
Météo-France publie les données par fenêtres temporelles glissantes (en
particulier les dernières années sont dans un fichier "previous" qui couvre
~50 ans, complété par un fichier "latest" pour l'année en cours). Le script
détecte automatiquement les bonnes ressources via l'API data.gouv.fr.

Si l'API n'est pas accessible (sandbox restreinte, hors-ligne), le script
imprime le lien de téléchargement manuel et termine sans erreur.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import requests
from tqdm import tqdm

# Permet l'exécution directe (`python scripts/01_*.py`) ET en module
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    DEPARTEMENTS_METRO,
    Episode,
    get_logger,
    load_episodes,
    meteo_period_dir,
)

logger = get_logger("01_download_meteo")

# UUID du dataset principal Météo-France sur data.gouv.fr.
# Mis à jour : voir https://www.data.gouv.fr/datasets/donnees-climatologiques-de-base-quotidiennes/
DATAGOUV_DATASET_QUOTIDIENNES = "donnees-climatologiques-de-base-quotidiennes"
DATAGOUV_API_DATASET = (
    "https://www.data.gouv.fr/api/1/datasets/{slug}/"
)

# Pattern attendu dans les noms de ressources Météo-France
# Ex : "Q_75_previous-1950-2023_RR-T-Vent.csv"
#      "Q_75_latest-2024-2025_RR-T-Vent.csv"
RESOURCE_PATTERN = re.compile(
    r"Q_(?P<dept>\d{2})_(?P<kind>previous|latest)-(?P<start>\d{4})-(?P<end>\d{4})_RR-T-Vent\.csv",
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


def select_resources_for_period(
    resources: list[dict],
    start_year: int,
    end_year: int,
) -> list[tuple[str, str]]:
    """
    Sélectionne les ressources qui couvrent la période demandée.

    Retourne une liste de (nom_fichier, url_telechargement).
    """
    selected = []
    for res in resources:
        title = res.get("title", "") or res.get("filename", "") or ""
        match = RESOURCE_PATTERN.search(title)
        if not match:
            continue
        dept = match.group("dept")
        kind = match.group("kind").lower()
        r_start = int(match.group("start"))
        r_end = int(match.group("end"))
        # garde si la période couverte par la ressource intersecte
        # la période demandée
        if r_end >= start_year and r_start <= end_year:
            url = res.get("url") or res.get("latest")
            if url:
                selected.append((title, url, dept, kind))
    return selected


def download_file(url: str, dest: Path, chunk_size: int = 1 << 14) -> bool:
    """Télécharge un fichier en streaming avec barre de progression."""
    try:
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            with open(dest, "wb") as f, tqdm(
                total=total, unit="B", unit_scale=True,
                desc=dest.name, leave=False,
            ) as bar:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        bar.update(len(chunk))
        return True
    except requests.RequestException as e:
        logger.error("  Échec téléchargement %s : %s", url, e)
        if dest.exists():
            dest.unlink(missing_ok=True)
        return False


def download_for_period(period: str, start_year: int, end_year: int) -> None:
    """Télécharge les fichiers Météo-France pour la période demandée."""
    dest_dir = meteo_period_dir(period)
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

    matches = select_resources_for_period(resources, start_year, end_year)
    if not matches:
        logger.warning(
            "Aucune ressource ne couvre %d-%d. Vérifier le dataset.",
            start_year, end_year,
        )
        return

    # Garder une seule ressource par département : préférer "latest" si
    # disponible pour les années récentes, sinon "previous".
    by_dept: dict[str, tuple[str, str, str]] = {}
    for title, url, dept, kind in matches:
        if dept not in by_dept or kind == "latest":
            by_dept[dept] = (title, url, kind)

    logger.info(
        "%d département(s) à traiter pour la période %d-%d",
        len(by_dept), start_year, end_year,
    )

    n_ok = 0
    n_skip = 0
    n_fail = 0
    for dept in sorted(by_dept):
        title, url, kind = by_dept[dept]
        dest = dest_dir / f"Q_{dept}_{period}.csv"
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
        "--period",
        help="Période Météo-France au format AAAA-AAAA (ex: 2025-2026)",
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

    if args.period:
        # Période donnée explicitement
        if "-" not in args.period:
            logger.error("--period doit être de la forme AAAA-AAAA")
            return 2
        s_year, e_year = args.period.split("-", 1)
        download_for_period(args.period, int(s_year), int(e_year))
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
        period = ep.meteo_data_period or (
            f"{ep.start.year}-{ep.end.year}"
            if ep.start.year != ep.end.year else f"{ep.start.year}-{ep.start.year}"
        )
        logger.info("Épisode : %s (%s → %s, période MF : %s)",
                    ep.id, ep.start, ep.end, period)
        s_y, e_y = period.split("-", 1)
        download_for_period(period, int(s_y), int(e_y))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
