#!/bin/bash
# Lancement de 02b sur les 5 épisodes restants (mai 2026 est déjà fait par Claude).
# À exécuter dans la racine du repo france-heat-uhi-analysis.

set -e

RAW_DIR="data/raw/meteo_france/1950-2024"   # adapter si nécessaire

# ATTENTION : pour les épisodes anciens, il faut s'assurer que les CSV
# Météo-France de la bonne période sont présents dans $RAW_DIR.
# Le script 01_download_meteo.py télécharge les périodes 1950-2024 et 2025-2026.

python scripts/02b_compute_rolling_indicators.py \
    --episode canicule-aout-2003 \
    --start 20030801 --end 20030815 \
    --raw-dir "$RAW_DIR" \
    --pattern "Q_*_1950-2024.csv*" \
    --output data/processed/canicule-aout-2003/indicators_glissant.csv

python scripts/02b_compute_rolling_indicators.py \
    --episode vague-chaleur-juin-2019 \
    --start 20190624 --end 20190630 \
    --raw-dir "$RAW_DIR" \
    --pattern "Q_*_1950-2024.csv*" \
    --output data/processed/vague-chaleur-juin-2019/indicators_glissant.csv

python scripts/02b_compute_rolling_indicators.py \
    --episode vague-chaleur-juillet-2019 \
    --start 20190721 --end 20190727 \
    --raw-dir "$RAW_DIR" \
    --pattern "Q_*_1950-2024.csv*" \
    --output data/processed/vague-chaleur-juillet-2019/indicators_glissant.csv

python scripts/02b_compute_rolling_indicators.py \
    --episode vague-chaleur-juillet-2022 \
    --start 20220712 --end 20220725 \
    --raw-dir "$RAW_DIR" \
    --pattern "Q_*_1950-2024.csv*" \
    --output data/processed/vague-chaleur-juillet-2022/indicators_glissant.csv

python scripts/02b_compute_rolling_indicators.py \
    --episode canicule-aout-2023 \
    --start 20230815 --end 20230825 \
    --raw-dir "$RAW_DIR" \
    --pattern "Q_*_1950-2024.csv*" \
    --output data/processed/canicule-aout-2023/indicators_glissant.csv

echo "Tous les épisodes traités. Uploade les 5 fichiers indicators_glissant.csv générés."
