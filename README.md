# france-heat-uhi-analysis

**Pipeline reproductible d'analyse des vagues de chaleur françaises et de leur relation à l'îlot de chaleur urbain (ICU).**

Ce dépôt fournit un cadre d'analyse documenté et reproductible pour étudier les épisodes caniculaires en France métropolitaine et distinguer, dans le signal thermique observé, ce qui relève du forçage synoptique (dôme de chaleur, advection, blocage anticyclonique) de ce qui relève du contexte urbain local (îlot de chaleur urbain).

L'analyse croise :

* les **données climatologiques quotidiennes de Météo-France** (températures minimale, maximale, moyenne par station, sur la période d'épisode étudiée),
* la **cartographie LCZ Cerema 2022** (Zones Climatiques Locales à 1,5 m, 88 aires urbaines de plus de 50 000 habitants en France métropolitaine),
* la **carte LCZ globale Demuzere et al. 2022** (100 m, mêmes 17 classes Stewart & Oke 2012, en complément hors aires Cerema).

Six épisodes sont configurés par défaut : août 2003, juin 2019, juillet 2019, juillet 2022, août 2023, mai 2026.

---

## Résultat principal — Dôme de chaleur de mai 2026

L'analyse appliquée à l'épisode du 20 au 29 mai 2026 produit le constat suivant (voir `articles/dome-mai-2026/` pour le texte complet) :

* le pic de température nocturne français sur l'épisode a été relevé à **Cap Béar (Pyrénées-Orientales), un phare maritime rural, à 26,2 °C** ;
* parmi les **14 stations françaises qui ont enregistré au moins 5 nuits tropicales** (Tn ≥ 20 °C) sur l'épisode, **12 sont en contexte non-urbain** (rural, littoral, communes <50 000 hab) selon la classification LCZ Cerema + Demuzere ;
* parmi les **25 stations Météo-France en cœur d'agglomération de plus de 100 000 habitants**, **une seule a enregistré ≥5 nuits tropicales** (Paris-Lariboisière), la **médiane des grandes villes étant à 1 nuit tropicale**.

L'ICU joue localement et est documenté par les cartographies Cerema et MApUCE (Météo-France), mais il ne suffit pas à expliquer le signal observé en mai 2026 : la signature de cet épisode est avant tout synoptique et géographique, pas urbaine.

---

## Architecture du dépôt

```text
france-heat-uhi-analysis/
├── README.md                # ce fichier
├── LICENSE                  # MIT (code) + CC-BY 4.0 (données dérivées et texte)
├── CITATION.cff             # citation auto du dépôt
├── requirements.txt         # dépendances Python
│
├── config/
│   ├── episodes.yaml        # catalogue des épisodes étudiables
│   └── lcz_categories.yaml  # mapping classes LCZ → catégories ICU
│
├── data/
│   ├── raw/                 # données sources (non versionnées, voir .gitignore)
│   │   ├── meteo_france/    # CSV Météo-France
│   │   ├── cerema_lcz/      # rasters et shapefiles LCZ Cerema
│   │   └── demuzere_lcz/    # raster LCZ global Demuzere
│   ├── stations/            # métadonnées stations
│   ├── processed/           # indicateurs calculés par épisode
│   └── results/             # statistiques finales par épisode
│
├── scripts/
│   ├── 00_run_pipeline.py            # pipeline complet pour un épisode
│   ├── 01_download_meteo.py          # acquisition données Météo-France
│   ├── 02_compute_indicators.py      # calcul NTrop, TnMax, TxMax par station
│   ├── 03_classify_stations_lcz.py   # classification LCZ Cerema + Demuzere
│   ├── 04_compute_stats.py           # statistiques par classe LCZ
│   └── 05_make_figures.py            # figures publiables
│
├── articles/
│   └── dome-mai-2026/                # articles produits sur l'épisode
│       ├── post_x.md
│       └── post_linkedin.md
│
└── docs/
    ├── METHODOLOGY.md       # méthodologie détaillée
    ├── EPISODES.md          # description des épisodes étudiés
    ├── DATA_SOURCES.md      # sources de données, licences, citations
    └── REPRODUCIBILITY.md   # comment refaire l'analyse de zéro
```

---

## Installation

Prérequis : Python 3.10 ou supérieur.

```bash
# Cloner le dépôt
git clone https://github.com/ThomasHANSS/france-heat-uhi-analysis.git
cd france-heat-uhi-analysis

# Créer un environnement virtuel et installer les dépendances
python -m venv venv
source venv/bin/activate    # sous Windows : venv\Scripts\activate
pip install -r requirements.txt
```

Les paquets `rasterio`, `geopandas` et `fiona` reposent sur GDAL. Si l'installation pip échoue (cas Windows fréquent), utiliser conda :

```bash
conda install -c conda-forge rasterio geopandas fiona pyproj shapely
```

---

## Utilisation

### Analyser un épisode (exemple : mai 2026)

```bash
python scripts/00_run_pipeline.py --episode dome-chaleur-mai-2026
```

Le pipeline exécute en séquence :

1. **Téléchargement** des données Météo-France pour la période, si absentes localement (`01_download_meteo.py`).
2. **Téléchargement** des couches LCZ Cerema des aires urbaines pertinentes, si absentes (`03_classify_stations_lcz.py`).
3. **Calcul des indicateurs** (NTrop = nombre de nuits tropicales avec Tn ≥ 20 °C, TnMax, TxMax) pour chaque station sur la période (`02_compute_indicators.py`).
4. **Classification LCZ** de chaque station (`03_classify_stations_lcz.py`) : Cerema 1,5 m si la station est dans une aire urbaine couverte, sinon Demuzere 100 m.
5. **Statistiques par classe LCZ** (`04_compute_stats.py`).
6. **Génération des figures** publiables (`05_make_figures.py`).

Les sorties sont écrites dans :

* `data/processed/<episode-id>/` — fichiers intermédiaires
* `data/results/<episode-id>/` — fichier `stats_<episode-id>.csv` et figures

### Analyser tous les épisodes configurés

```bash
for ep in dome-chaleur-mai-2026 canicule-aout-2003 vague-chaleur-juin-2019 \
          vague-chaleur-juillet-2019 vague-chaleur-juillet-2022 canicule-aout-2023; do
    python scripts/00_run_pipeline.py --episode "$ep"
done
```

### Ajouter un nouvel épisode

Éditer `config/episodes.yaml` et ajouter une nouvelle entrée avec ses dates. Le pipeline le prendra en compte sans modification du code.

---

## Sources de données et licences

| Source | Producteur | Licence | Référence |
|---|---|---|---|
| Données climatologiques quotidiennes | Météo-France | Licence Ouverte 2.0 (Etalab) | [meteo.data.gouv.fr](https://meteo.data.gouv.fr) |
| LCZ_SPOT_2022_Fr (88 aires urbaines, 1,5 m) | Cerema | Licence Ouverte 2.0 (Etalab) | [data.gouv.fr](https://www.data.gouv.fr/datasets/cartographie-des-zones-climatiques-locales-lcz-des-88-aires-urbaines-de-plus-de-50-000-habitants-de-france-metropolitaine) |
| Global LCZ map (100 m) | Demuzere et al. 2022 | CC-BY 4.0 | [doi:10.5281/zenodo.6364594](https://doi.org/10.5281/zenodo.6364594) |

Voir `docs/DATA_SOURCES.md` pour le détail.

---

## Méthodologie

Voir `docs/METHODOLOGY.md` pour la méthodologie détaillée. En résumé :

1. **Définition** : nuit tropicale = température minimale Tn ≥ 20 °C (seuil OMM/Météo-France).
2. **Classification LCZ** : système Stewart & Oke 2012 (10 classes bâties + 7 non-bâties). Application sur buffers de 300 m et 500 m autour des coordonnées WGS84 de chaque station Météo-France.
3. **Hybridation des sources LCZ** :
   - Cerema 1,5 m utilisé en priorité quand la station est dans une des 88 aires urbaines françaises >50 000 habitants ;
   - Demuzere 100 m utilisé pour toutes les autres stations.
4. **Catégorisation finale** : `urbain_compact` (LCZ 1-3), `urbain_aere` (LCZ 4-6), `bati_special` (LCZ 7-10), `non_bati` (LCZ A-G).

---

## Reproductibilité

Voir `docs/REPRODUCIBILITY.md` pour refaire l'analyse complète à partir de zéro.

Toutes les figures et tables publiées dans les articles `articles/<episode>/` sont régénérables par exécution du pipeline. Aucune valeur n'est saisie manuellement ailleurs.

---

## Citation

Si vous utilisez ce dépôt ou ses sorties, merci de citer comme indiqué dans `CITATION.cff`, ainsi que les sources de données primaires (Météo-France, Cerema, Demuzere et al.).

---

## Contact

Issues GitHub : [ThomasHANSS/france-heat-uhi-analysis/issues](https://github.com/ThomasHANSS/france-heat-uhi-analysis/issues)
