"""
common.py — utilitaires partagés par les scripts du pipeline.

Centralise :
  - chargement de la configuration (episodes.yaml, lcz_categories.yaml)
  - constantes (codes département français, chemins standards)
  - helpers logging et chemins

Ce module est importé par les scripts 01 à 05.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Chemins du projet
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
DATA_RAW = DATA_DIR / "raw"
DATA_PROCESSED = DATA_DIR / "processed"
DATA_RESULTS = DATA_DIR / "results"
DATA_STATIONS = DATA_DIR / "stations"

METEO_DIR = DATA_RAW / "meteo_france"
CEREMA_DIR = DATA_RAW / "cerema_lcz"
DEMUZERE_DIR = DATA_RAW / "demuzere_lcz"

# ---------------------------------------------------------------------------
# Liste des départements métropolitains (codes Météo-France)
# ---------------------------------------------------------------------------
# Codes département : 01-95, sauf 20 remplacé par 2A et 2B en Corse.
# Météo-France utilise le code "20" pour les deux départements corses dans
# les noms de fichiers (Q_20_*), avec le département "20" dans NUM_POSTE
# distinguant 2A / 2B par l'INSEE.
DEPARTEMENTS_METRO = [f"{i:02d}" for i in range(1, 96) if i != 20]
# Ajout de la Corse : on traite Q_20 (qui contient 2A et 2B regroupés)
DEPARTEMENTS_METRO.append("20")
# Et le département 75 pour Paris est inclus dans la liste 01-95.


# ---------------------------------------------------------------------------
# Configuration de logging
# ---------------------------------------------------------------------------
def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Renvoie un logger configuré uniformément pour le projet."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(fmt)
        logger.addHandler(handler)
        logger.setLevel(level)
    return logger


# ---------------------------------------------------------------------------
# Représentation d'un épisode
# ---------------------------------------------------------------------------
@dataclass
class Episode:
    """Représentation typée d'un épisode caniculaire."""
    id: str
    name: str
    start: date
    end: date
    type: str
    context: str = ""
    meteo_data_period: str = ""

    @property
    def years(self) -> list[int]:
        """Liste des années couvertes par l'épisode."""
        return list(range(self.start.year, self.end.year + 1))

    @property
    def dates_yyyymmdd(self) -> set[str]:
        """Ensemble des dates couvertes au format AAAAMMJJ."""
        from datetime import timedelta
        out = set()
        d = self.start
        while d <= self.end:
            out.add(d.strftime("%Y%m%d"))
            d += timedelta(days=1)
        return out


def load_episodes(path: Path | None = None) -> dict[str, Episode]:
    """Charge le catalogue des épisodes depuis config/episodes.yaml."""
    if path is None:
        path = CONFIG_DIR / "episodes.yaml"
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    episodes: dict[str, Episode] = {}
    for ep_id, fields in raw.items():
        episodes[ep_id] = Episode(
            id=ep_id,
            name=fields["name"],
            start=fields["start"] if isinstance(fields["start"], date)
                  else date.fromisoformat(str(fields["start"])),
            end=fields["end"] if isinstance(fields["end"], date)
                  else date.fromisoformat(str(fields["end"])),
            type=fields.get("type", "heatwave"),
            context=fields.get("context", "").strip(),
            meteo_data_period=fields.get("meteo_data_period", ""),
        )
    return episodes


def load_lcz_config(path: Path | None = None) -> dict:
    """Charge la configuration des catégories LCZ."""
    if path is None:
        path = CONFIG_DIR / "lcz_categories.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Chemins par épisode
# ---------------------------------------------------------------------------
def processed_dir(episode_id: str) -> Path:
    """Renvoie le répertoire des fichiers intermédiaires d'un épisode."""
    p = DATA_PROCESSED / episode_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def results_dir(episode_id: str) -> Path:
    """Renvoie le répertoire des résultats d'un épisode."""
    p = DATA_RESULTS / episode_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def meteo_period_dir(period: str) -> Path:
    """Renvoie le répertoire des CSV Météo-France pour une période donnée."""
    p = METEO_DIR / period
    p.mkdir(parents=True, exist_ok=True)
    return p
