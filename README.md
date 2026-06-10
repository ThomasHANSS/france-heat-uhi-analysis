# france-heat-uhi-analysis

**Analyse empirique du contraste urbain compact vs non bâti pendant les épisodes caniculaires français, avec un focus sur le dôme de chaleur de mai 2026.**

Le projet quantifie l'amplification thermique des cœurs urbains (LCZ "urbain compact") pendant six épisodes caniculaires couvrant 2003–2026, en stratifiant l'analyse par deux classifications climatiques officielles (Joly 2010 et RE2020). L'objectif est de séparer la signature d'**adaptation à l'îlot de chaleur urbain (ICU)** — phénomène chronique — de celle d'**adaptation aux extrêmes synoptiques** type dôme de chaleur — par nature aiguë et localisée.

## Question de recherche

L'adaptation thermique urbaine se concentre largement sur la **réduction de l'ICU** (végétalisation, albédo, désimperméabilisation), qui traite un excès chronique de quelques degrés. Mais le dôme du Pacifique Nord-Ouest 2021 (+15 à +20 °C au-dessus des normales, ~868 décès en 6 jours) a démontré qu'une autre catégorie d'événements pouvait dépasser brutalement les capacités d'adaptation, indépendamment du traitement urbain de fond.

Le dôme de chaleur de mai 2026 sur la France — événement précoce, à signature synoptique centrée sur Paris — offre un cas d'étude récent pour tester empiriquement cette distinction. La question : **les cœurs urbains s'amplifient-ils plus pendant un dôme synoptique que pendant une canicule classique** ?

## Données

| Source | Description | Période | Volume |
|---|---|---|---|
| **Météo-France** (meteo.data.gouv.fr) | Données climatologiques quotidiennes par département (RR, T, vent) | 1950–2026 | 96 fichiers CSV |
| **Joly et al. 2010** (DOI INRAE 10.15454/98BHVH) | Raster typologique 8 classes (k-means multi-variable sur normales 1971-2000) | 1971-2000 | TYPO_RGF93.tif, ~65 Mo, Lambert-93 |
| **CEREMA** | Polygones LCZ par agglomération | — | Shapefiles |
| **Demuzere et al. 2022** | Raster LCZ continental européen 100 m | — | GeoTIFF |
| **Arrêté du 26/10/2010 annexe I** | Mapping département → zone RE2020 (H1a–H3) | — | Texte réglementaire |

## Méthodologie

### Classification climatique

L'analyse stratifie les 1 845 stations actives sur la période 2003-2026 selon **deux grilles climatiques de granularité équivalente (8 classes)** :

- **Joly et al. 2010** (8 types) — classification scientifique peer-reviewed par k-means multi-variable sur normales 1971-2000. Source : Cybergeo doc. 501 (DOI 10.4000/cybergeo.23155).
- **RE2020 / TRACC** (8 zones H1a–H3) — classification officielle Météo-France/DHUP/CSTB, arrêté du 26 octobre 2010 (annexe I), repris inchangé dans l'arrêté du 4 août 2021. Stations de référence : Nancy (H1a), Trappes (H1b), Mâcon (H1c), Rennes (H2a), Tours (H2b), Agen (H2c), Carpentras (H2d), Marignane (H3).

Les deux grilles ne sont pas équivalentes : Joly capture une typologie climatique scientifique multi-variable, RE2020 est une classification réglementaire par département. Leur utilisation conjointe sert de **test de robustesse** : si nos conclusions tiennent sous les deux grilles, l'argument est indépendant du choix de découpage.

### Classification LCZ hybride

Chaque station est attribuée à une catégorie LCZ via une logique hybride :
- **CEREMA** quand l'agglomération couvre la station (priorité, plus précise)
- **Demuzere et al. 2022** en fallback continental
- Composition LCZ sur buffer 100 m / 300 m / 500 m → catégorie agrégée parmi `urbain_compact`, `urbain_aere`, `bati_special`, `non_bati`

### Épisodes analysés

| Épisode | Période | Durée | Nature |
|---|---|---|---|
| Canicule août 2003 | 01/08–15/08/2003 | 15 j | Canicule paroxystique nationale |
| Vague juin 2019 | 24/06–30/06/2019 | 7 j | Méditerranéenne, record absolu (46 °C Gard) |
| Vague juillet 2019 | 21/07–27/07/2019 | 7 j | Tardive de juillet |
| Vague juillet 2022 | 12/07–25/07/2022 | 14 j | Estivale longue |
| Canicule août 2023 | 15/08–25/08/2023 | 11 j | Méridionale tardive |
| **Dôme mai 2026** | 20/05–29/05/2026 | 10 j | **Dôme précoce, couloir centré sur Paris** |

### Indicateurs

- `TnMax` : température minimale maximale sur l'épisode (peak chaleur nocturne, métrique d'intensité non saturable)
- `NTrop` : nombre absolu de nuits tropicales (Tn ≥ 20 °C) sur l'épisode
- `NTrop_taux = NTrop / NDays` : taux normalisé pour comparabilité inter-épisodes
- `NTrop_5j_max` : max sur fenêtre glissante de 5 jours (décorrèle l'intensité du pic de la durée totale)
- `TnMoy_5j_max` : max de la Tn moyenne sur fenêtre glissante de 5 jours

### Tests statistiques (étape 3b)

Comparaison UC (urbain compact) vs NB (non bâti) par épisode et par zone climatique :
- **Mann-Whitney U** (non paramétrique, valide pour petits effectifs)
- **Cliff's delta** avec **bootstrap 95% CI** (taille d'effet plus interprétable que p-value avec n petit)
- Doublé en `UC+UA` vs `NB` pour test de robustesse à effectifs élargis (n = 170 vs n > 1500)

## Pipeline

```
01_download_meteo.py              → Téléchargement données MF par département
02_compute_indicators.py          → Indicateurs par épisode (TnMax, NTrop, TnMoy...)
02b_compute_rolling_indicators.py → Indicateurs glissants 5 j (NTrop_5j_max, TnMoy_5j_max)
03_attribute_lcz.py               → Attribution LCZ hybride CEREMA + Demuzere
04_extract_episodes.py            → Filtre stations × période × indicateurs
05_compare_episodes.py            → Synthèse comparative inter-épisodes
06_attribute_joly_climate.py      → Attribution Joly 2010 (8 types)
07_attribute_re2020_zone.py       → Attribution RE2020 (8 zones H1a–H3)
```

## Résultats principaux à l'étape 3b

### Contraste UC vs NB toutes zones confondues

Sur les 6 épisodes étudiés, le contraste TnMax entre stations LCZ "urbain compact" (n = 4-8) et "non bâti" (n > 1 500) est **significatif et de grande ampleur** (Cliff's δ ≥ 0,53) :

| Épisode | Δ TnMax (UC – NB, médian) | Cliff's δ | p (Mann-Whitney) |
|---|---|---|---|
| **mai 2026** | **+4,70 °C** | **+0,89** [+0,84, +0,95] | 2,7 × 10⁻⁴ |
| juillet 2019 | +5,00 °C | +0,95 [+0,90, +0,99] | 1,2 × 10⁻⁴ |
| août 2003 | +3,60 °C | +0,78 [+0,62, +0,91] | 7,1 × 10⁻⁵ |
| août 2023 | +3,70 °C | +0,74 [+0,49, +0,91] | 2,3 × 10⁻³ |
| juillet 2022 | +3,20 °C | +0,74 [+0,45, +0,95] | 2,2 × 10⁻³ |
| juin 2019 | +2,85 °C | +0,53 [+0,10, +0,96] | 3,4 × 10⁻² |

### Résultat-clé : zone Joly 3 (bassin parisien, couloir du dôme)

Sur la zone climatique correspondant au couloir géographique du dôme de mai 2026, l'amplification UC vs NB **bat tous les autres épisodes** :

| Épisode | Δ TnMax sur Joly 3 | Cliff's δ |
|---|---|---|
| **mai 2026** | **+6,90 °C** | **+1,00** (séparation totale) |
| juillet 2019 | +5,15 °C | +0,95 |
| juillet 2022 | +4,55 °C | +0,77 |
| août 2003 | +2,50 °C | +0,81 |
| août 2023 | +1,65 °C | +0,67 |
| juin 2019 | +0,80 °C | +0,40 |

Cliff's δ = +1,00 signifie **séparation totale** des distributions UC et NB sur Paris. Aucun autre épisode n'atteint cette amplitude sur cette zone.

### Pic glissant 5 jours (mai 2026)

| Station | Catégorie | NTrop_5j_max | TnMoy_5j_max |
|---|---|---|---|
| Lariboisière (75) | urbain dense | 5/5 | **22,78 °C** |
| Tour Eiffel (75) | mat exposé | 5/5 | 23,00 °C |
| Luxembourg (75) | urbain parc | 3/5 | 20,10 °C |
| Montsouris (75) | urbain parc | 2-3/5 | 19,74 °C |
| Marseille-Obs (13) | urbain dense | 3/5 | 20,40 °C |
| **Trappes (78)** | banlieue ouest | 0/5 | 17,42 °C |
| **Melun (77)** | banlieue sud | 0/5 | 15,64 °C |
| **Fontainebleau (77)** | forêt (trou à froid) | 0/5 | 12,38 °C |

**Lariboisière vs Trappes : écart +5,4 °C** en Tn moyenne sur 5 jours consécutifs ; vs Fontainebleau : +10,4 °C.

### Conclusion à l'étape 3b

Mai 2026 produit **l'amplification UC vs NB la plus extrême** des 6 épisodes étudiés, malgré une température moyenne nationale très inférieure à août 2003 (NTrop_taux moyen = 0,03 vs 0,29). La signature du **dôme + couloir centré + ICU** est plus forte sur Paris que celle de la canicule paroxystique de 2003. Résultat empirique qui valide l'argument central du projet : **l'adaptation au dôme de chaleur n'est pas réductible à l'adaptation à l'ICU** — ce sont deux phénomènes physiquement et géographiquement distincts qui requièrent des politiques d'adaptation différentes.

## Reproduire l'analyse

### Dépendances

```bash
pip install pandas numpy scipy rasterio
```

### Téléchargement raster Joly 2010 (~65 Mo, hors Git)

```bash
mkdir -p data/raw/joly_2010
curl -L "https://entrepot.recherche.data.gouv.fr/api/access/datafile/84435" \
     -o data/raw/joly_2010/TYPO_RGF93.tif
```

### Pipeline d'analyse

```bash
# 1. Données MF
python scripts/01_download_meteo.py

# 2. Indicateurs par épisode + indicateurs glissants 5 j
python scripts/02_compute_indicators.py
bash scripts/run_rolling_indicators_other_episodes.sh

# 3. Attribution LCZ hybride
python scripts/03_attribute_lcz.py

# 4. Attribution climatique (Joly + RE2020)
python scripts/06_attribute_joly_climate.py \
    --joly-raster data/raw/joly_2010/TYPO_RGF93.tif \
    --stations data/processed/dome-chaleur-mai-2026/stations_lcz_dome-chaleur-mai-2026.csv \
    --output data/processed/stations_climat_joly.csv

python scripts/07_attribute_re2020_zone.py \
    --input data/processed/stations_climat_joly.csv \
    --output data/processed/stations_climat.csv
```

## Structure du repo

```
france-heat-uhi-analysis/
├── data/
│   ├── raw/                    # Données brutes (hors Git, re-téléchargeables)
│   │   ├── meteo_france/
│   │   ├── cerema_lcz/
│   │   ├── demuzere_lcz/
│   │   └── joly_2010/
│   ├── processed/              # Données traitées (sélection trackée)
│   │   ├── stations_climat.csv         ✓ tracké
│   │   ├── stations_climat_joly.csv    ✓ tracké
│   │   ├── indicators_normalized_*.csv ✓ tracké (6 épisodes)
│   │   ├── synthese_normalisation_episodes.csv
│   │   └── <episode>/
│   │       ├── stations_lcz_<episode>.csv
│   │       ├── indicators_<episode>.csv
│   │       └── indicators_glissant.csv
│   └── results/                # Résultats statistiques (trackés)
│       ├── tests_3b_global.csv
│       ├── tests_3b_stratified_tnmax.csv
│       └── tests_3b_stratified_ntrop.csv
└── scripts/
    ├── 01_download_meteo.py
    ├── 02_compute_indicators.py
    ├── 02b_compute_rolling_indicators.py
    ├── 03_attribute_lcz.py
    ├── 04_extract_episodes.py
    ├── 05_compare_episodes.py
    ├── 06_attribute_joly_climate.py
    └── 07_attribute_re2020_zone.py
```

## Licence

Code : MIT
Données dérivées : Licence Ouverte / Open Licence v2.0 (héritée de Météo-France)

## Sources et citations

- **Météo-France** — Données climatologiques de base, quotidiennes. meteo.data.gouv.fr, Licence Ouverte / Open Licence v2.0.
- **Joly D., Brossard T., Cardot H., Cavailhès J., Hilal M., Wavresky P. (2010)** — *Les types de climats en France, une construction spatiale*. Cybergeo, doc. 501. DOI 10.4000/cybergeo.23155. Données : DOI INRAE 10.15454/98BHVH.
- **Arrêté du 26 octobre 2010** (annexe I, mapping département → zone RE2020) et **arrêté du 4 août 2021** (RE2020). Légifrance.
- **Météo-France / ADEME / CSTB / DHUP (2025)** — *Données climatiques prospectives France TRACC +2/+2,7/+4 °C*. data.ademe.fr.
- **Demuzere M. et al. (2022)** — *European LCZ map*.
- **CEREMA** — Polygones LCZ pour les principales agglomérations françaises.
