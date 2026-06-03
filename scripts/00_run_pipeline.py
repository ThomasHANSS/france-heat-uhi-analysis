#!/usr/bin/env python3
"""
00_run_pipeline.py — Exécute le pipeline complet pour un épisode.

Exécute en séquence :
  1. 01_download_meteo.py
  2. 02_compute_indicators.py
  3. 03_classify_stations_lcz.py
  4. 04_compute_stats.py
  5. 05_make_figures.py

Toute étape qui rencontre une erreur fatale interrompt le pipeline. Les
étapes intermédiaires écrivent leurs résultats dans data/processed et
data/results.

USAGE
-----
    python scripts/00_run_pipeline.py --episode dome-chaleur-mai-2026

    # Toutes les étapes :
    python scripts/00_run_pipeline.py --episode dome-chaleur-mai-2026 --all

    # Ne refait pas les téléchargements :
    python scripts/00_run_pipeline.py --episode dome-chaleur-mai-2026 --skip 1
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import get_logger, load_episodes  # noqa: E402

logger = get_logger("00_run_pipeline")

# Définition des étapes du pipeline. Chaque étape est un module Python à
# importer dynamiquement (les noms commençant par un chiffre rendent
# l'import direct impossible).
STEPS = [
    ("01_download_meteo", "Téléchargement données Météo-France"),
    ("02_compute_indicators", "Calcul des indicateurs canicule"),
    ("03_classify_stations_lcz", "Classification LCZ des stations"),
    ("04_compute_stats", "Statistiques croisées canicule × LCZ"),
    ("05_make_figures", "Génération des figures publiables"),
]


def import_step_module(name: str):
    """Importe dynamiquement un script numéroté du dossier scripts/."""
    scripts_dir = Path(__file__).resolve().parent
    fp = scripts_dir / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, fp)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Impossible d'importer {fp}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pipeline complet d'analyse d'un épisode caniculaire",
    )
    parser.add_argument(
        "--episode", required=True,
        help="Identifiant d'un épisode défini dans config/episodes.yaml",
    )
    parser.add_argument(
        "--skip", type=int, action="append", default=[],
        help="Numéros d'étapes à sauter (peut être répété, ex: --skip 1 --skip 3)",
    )
    parser.add_argument(
        "--only", type=int, default=None,
        help="N'exécute que l'étape numérotée",
    )
    parser.add_argument(
        "--download-cerema", action="store_true",
        help="Tente le téléchargement automatique des couches Cerema LCZ",
    )
    args = parser.parse_args()

    episodes = load_episodes()
    if args.episode not in episodes:
        logger.error("Épisode inconnu : %s", args.episode)
        logger.info("Épisodes disponibles :")
        for ep_id in sorted(episodes):
            logger.info("  - %s", ep_id)
        return 2

    logger.info("===========================================================")
    logger.info("Pipeline pour l'épisode : %s", args.episode)
    logger.info("===========================================================")

    for i, (step_name, label) in enumerate(STEPS, start=1):
        if args.only is not None and i != args.only:
            continue
        if i in args.skip:
            logger.info("[%d] %-50s SKIP", i, label)
            continue

        logger.info("[%d/5] %s ...", i, label)
        try:
            mod = import_step_module(step_name)
        except Exception as e:
            logger.error("Import de l'étape %d échoué : %s", i, e)
            return 1

        # Adapter les arguments pour appeler le module.main()
        original_argv = sys.argv[:]
        sub_argv = [step_name + ".py", "--episode", args.episode]
        if step_name == "03_classify_stations_lcz" and args.download_cerema:
            sub_argv.append("--download-cerema")
        sys.argv = sub_argv
        try:
            rc = mod.main()
        except SystemExit as e:
            rc = int(e.code) if e.code is not None else 0
        except Exception as e:
            logger.exception("Erreur dans l'étape %d : %s", i, e)
            sys.argv = original_argv
            return 1
        sys.argv = original_argv
        if rc != 0:
            logger.error("Étape %d (%s) a renvoyé code %d. Pipeline interrompu.",
                         i, step_name, rc)
            return rc

    logger.info("===========================================================")
    logger.info("Pipeline terminé avec succès pour %s", args.episode)
    logger.info("Résultats : data/results/%s/", args.episode)
    logger.info("===========================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
