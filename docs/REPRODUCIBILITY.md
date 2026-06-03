# Reproductibilité

Ce document décrit comment refaire l'analyse complète à partir de zéro, sur n'importe quelle machine. Le pipeline est conçu pour être entièrement reproductible : toutes les figures et tables publiées dans `articles/` sont régénérables par exécution des scripts.

## Pré-requis

- **Python 3.10 ou supérieur**
- Environ **15 Go d'espace disque libre** (CSV Météo-France + couches LCZ Cerema + Demuzere)
- Une connexion Internet (le premier `run` télécharge les données sources)
- Compte gratuit sur Zenodo pour télécharger la carte LCZ Demuzere (alternativement, certaines mirroirs académiques sont accessibles sans compte)

## Installation

```bash
# Cloner le dépôt
git clone https://github.com/ThomasHANSS/france-heat-uhi-analysis.git
cd france-heat-uhi-analysis

# Créer un environnement virtuel
python -m venv venv
source venv/bin/activate   # Windows : venv\Scripts\activate

# Installer les dépendances
pip install --upgrade pip
pip install -r requirements.txt
```

### Astuce installation rasterio / geopandas

Sur Windows et certaines distributions Linux, l'installation de `rasterio`, `geopandas` et `fiona` via pip peut échouer faute de bibliothèque GDAL système. La solution la plus simple est d'utiliser conda :

```bash
conda install -c conda-forge rasterio geopandas fiona pyproj shapely
pip install -r requirements.txt  # pour les autres dépendances
```

## Acquisition des données

### Étape 1 — Données Météo-France

Pour chaque épisode à analyser, télécharger les CSV correspondants. Pour l'épisode principal mai 2026 :

```bash
python scripts/01_download_meteo.py --episode dome-chaleur-mai-2026
```

Les CSV sont placés dans `data/raw/meteo_france/2025-2026/`. Si l'API data.gouv.fr est inaccessible (filtrage réseau, hors-ligne), le script affiche le lien pour téléchargement manuel.

### Étape 2 — Couches LCZ Cerema

Deux options :

**a) Téléchargement automatique** (~10 Go) :

```bash
python scripts/03_classify_stations_lcz.py --episode dome-chaleur-mai-2026 --download-cerema
```

Note : le téléchargement automatique récupère les **88 archives ZIP** des aires urbaines. Il faut ensuite les **extraire manuellement** dans `data/raw/cerema_lcz/` pour que le pipeline puisse lire les rasters. Sous Linux/Mac :

```bash
cd data/raw/cerema_lcz/
for f in *.zip; do unzip -o "$f"; done
```

**b) Téléchargement ciblé** : se rendre sur le portail [data.gouv.fr](https://www.data.gouv.fr/datasets/cartographie-des-zones-climatiques-locales-lcz-des-88-aires-urbaines-de-plus-de-50-000-habitants-de-france-metropolitaine) et télécharger uniquement les aires urbaines pertinentes (par exemple, pour mai 2026, les aires comprenant Paris, Marseille, Lyon, Nice, Bordeaux, Strasbourg, Nantes…). Extraire les ZIP dans `data/raw/cerema_lcz/`.

### Étape 3 — Carte LCZ globale Demuzere

Se rendre sur [Zenodo, DOI 10.5281/zenodo.6364594](https://doi.org/10.5281/zenodo.6364594) et télécharger le fichier GeoTIFF principal (~150 Mo). Le placer dans `data/raw/demuzere_lcz/`.

**Alternative : pré-découper le raster sur la France** pour gagner du temps et de la place. Avec `gdalwarp` (paquet GDAL en ligne de commande) :

```bash
gdalwarp -te -5.5 41 10 51.5 \
  data/raw/demuzere_lcz/lcz_global.tif \
  data/raw/demuzere_lcz/lcz_france.tif
rm data/raw/demuzere_lcz/lcz_global.tif
```

Le raster découpé ne pèse que quelques Mo.

## Exécution du pipeline

### Pipeline complet pour un épisode

```bash
python scripts/00_run_pipeline.py --episode dome-chaleur-mai-2026
```

Cela exécute les 5 étapes (`01_` à `05_`) en séquence. Durée typique sur un portable correct : 5 à 15 minutes, principalement pour la classification LCZ (étape 3) qui ouvre chaque raster Cerema pour chaque station.

### Exécution étape par étape

```bash
python scripts/01_download_meteo.py        --episode dome-chaleur-mai-2026
python scripts/02_compute_indicators.py    --episode dome-chaleur-mai-2026
python scripts/03_classify_stations_lcz.py --episode dome-chaleur-mai-2026
python scripts/04_compute_stats.py         --episode dome-chaleur-mai-2026
python scripts/05_make_figures.py          --episode dome-chaleur-mai-2026
```

### Sauter une étape déjà exécutée

```bash
python scripts/00_run_pipeline.py --episode dome-chaleur-mai-2026 --skip 1 --skip 3
```

### Analyser tous les épisodes du catalogue

```bash
for ep in dome-chaleur-mai-2026 canicule-aout-2003 vague-chaleur-juin-2019 \
          vague-chaleur-juillet-2019 vague-chaleur-juillet-2022 canicule-aout-2023; do
    python scripts/00_run_pipeline.py --episode "$ep"
done
```

## Sorties

Pour chaque épisode, le pipeline produit :

**Fichiers intermédiaires** dans `data/processed/<episode>/` :
- `indicators_<episode>.csv` — indicateurs canicule par station
- `stations_lcz_<episode>.csv` — classification LCZ par station

**Résultats** dans `data/results/<episode>/` :
- `full_table_<episode>.csv` — table jointe complète
- `stats_by_lcz_<episode>.csv` — stats par catégorie LCZ
- `top_stations_by_ntrop_<episode>.csv` — top 30 stations par NTrop
- `top_stations_by_tnmax_<episode>.csv` — top 30 par TnMax
- `summary_<episode>.json` — résumé chiffré utilisable dans les articles
- `figures/` — figures SVG publiables

## Vérification de cohérence

Pour s'assurer que les résultats du dépôt sont reproductibles, on peut comparer un résumé connu :

```bash
cat data/results/dome-chaleur-mai-2026/summary_dome-chaleur-mai-2026.json
```

Le champ `n_stations_5plus_ntrop` doit retourner 14 (à 1 près selon classification LCZ d'éventuelles stations en limite d'aire urbaine). Le champ `pic_nocturne_station` doit retourner « CAP BEAR ».

## Reproductibilité longue durée

Les sources de données utilisées sont toutes des datasets pérennes publiés via DOI ou via data.gouv.fr (qui garantit l'archivage). Les versions exactes utilisées sont :

- **Météo-France** : observations quotidiennes, dataset de référence sur meteo.data.gouv.fr (mises à jour mensuelles, données antérieures inchangées).
- **Cerema LCZ_SPOT_2022_Fr** : version juin 2025 (mise à jour 30 juin 2025 selon le portail).
- **Demuzere et al. 2022** : version Zenodo, archivée sous DOI.

Si l'un des datasets sources évolue, le pipeline reste fonctionnel — seuls les chiffres précis peuvent évoluer marginalement.
