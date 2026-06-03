# Méthodologie

Ce document décrit la méthodologie complète mise en œuvre par le pipeline pour analyser un épisode caniculaire et croiser le signal thermique observé avec le contexte urbain de chaque station de mesure.

## 1. Données sources

### 1.1 Observations climatologiques

Les températures quotidiennes proviennent des **Données climatologiques de base — quotidiennes** publiées par Météo-France sur [meteo.data.gouv.fr](https://meteo.data.gouv.fr). Les fichiers CSV utilisés contiennent, pour chaque station du réseau et chaque jour :

- `NUM_POSTE` — identifiant unique de la station ;
- `NOM_USUEL`, `LAT`, `LON`, `ALTI` — métadonnées de la station (coordonnées en WGS84, altitude en m) ;
- `AAAAMMJJ` — date au format `YYYYMMDD` ;
- `TN` — température minimale de la nuit, en °C ;
- `TX` — température maximale de la journée, en °C ;
- `TM` — température moyenne du jour, en °C.

Les données sont produites sous le contrôle qualité standard de Météo-France et sont diffusées sous Licence Ouverte 2.0 (Etalab).

### 1.2 Classification du contexte des stations

Le contexte urbain de chaque capteur est qualifié à l'aide du système des **Local Climate Zones (LCZ)** introduit par Stewart & Oke (2012), Bulletin of the American Meteorological Society, qui est aujourd'hui la référence internationale pour la qualification thermo-physique de l'environnement d'une station de température dans les études d'îlot de chaleur urbain.

Le pipeline utilise deux sources LCZ en complémentarité :

1. **LCZ_SPOT_2022_Fr du Cerema** — cartographie LCZ à 1,5 m de résolution couvrant les 88 aires urbaines françaises de plus de 50 000 habitants, produite à partir d'images SPOT 2022 et de la BD TOPO IGN v3.3 (Licence Ouverte 2.0). Cette source est utilisée en priorité pour toute station dont les coordonnées tombent dans l'emprise d'une aire urbaine couverte.
2. **Global LCZ map de Demuzere et al. (2022)** — cartographie LCZ globale à 100 m de résolution, publiée dans Earth System Science Data (CC-BY 4.0). Cette source est utilisée en complément pour toutes les stations hors aires urbaines Cerema, garantissant qu'aucune station n'est non-classifiée.

Les deux sources utilisent le même système typologique à 17 classes (10 bâties LCZ 1-10, 7 non-bâties LCZ A-G), ce qui rend les classifications agrégeables sans incohérence.

## 2. Indicateurs calculés

Pour chaque station et chaque épisode, le pipeline calcule :

| Indicateur | Définition |
|---|---|
| `NTrop` | Nombre de jours dans la période où Tn ≥ 20,0 °C (seuil OMM/Météo-France pour « nuit tropicale ») |
| `TnMax` | Température minimale nocturne la plus élevée sur la période |
| `TnMoy` | Moyenne arithmétique des Tn sur la période |
| `TxMax` | Température maximale diurne la plus élevée sur la période |
| `TxMoy` | Moyenne arithmétique des Tx sur la période |
| `TmMoy` | Moyenne arithmétique des Tm sur la période |
| `NDays` | Nombre de jours avec donnée Tn valide |

Une station est considérée comme exploitable si elle dispose d'au moins 7 jours de données Tn valides sur la période (option `--min-days` du script 02).

## 3. Classification LCZ des stations

Pour chaque station, la classe LCZ dominante est déterminée à partir des pixels du raster LCZ tombant dans un buffer circulaire centré sur les coordonnées WGS84 de la station.

### 3.1 Choix du rayon

Stewart & Oke (2012) définissent les LCZ comme « des régions de couverture de surface, structure, matériaux et activité humaine uniformes, à l'échelle horizontale de plusieurs centaines de mètres à plusieurs kilomètres ». Il n'existe pas de rayon unique faisant consensus.

Le pipeline calcule deux rayons en parallèle :

- **300 m** — footprint immédiat du capteur, échelle micrométéorologique ;
- **500 m** — rayon de référence WUDAPT pour la classification LCZ.

Le rayon de 500 m est le « rayon primaire » utilisé pour la catégorisation finale ; le rayon de 300 m sert au contrôle de cohérence. Une divergence importante (>20 % de pixels en désaccord) entre les deux est signalée dans le champ `lcz_divergence` de la sortie.

### 3.2 Catégorisation

Les 17 classes LCZ sont agrégées en 4 catégories pour l'analyse :

| Catégorie | Classes LCZ | Description |
|---|---|---|
| `urbain_compact` | LCZ 1, 2, 3 | Cœur urbain dense (compact high/mid/lowrise) — contexte ICU le plus marqué |
| `urbain_aere` | LCZ 4, 5, 6 | Tissu résidentiel ouvert (open high/mid/lowrise) — ICU modéré |
| `bati_special` | LCZ 7, 8, 9, 10 | Bâti léger, large lowrise (commercial/aéroports), bâti dispersé, industrie lourde |
| `non_bati` | LCZ A-G | Forêt, broussaille, prairies, sol nu, eau — contextes ruraux ou naturels |

Voir `config/lcz_categories.yaml` pour le détail des codes et le mapping.

### 3.3 Source LCZ retenue

Pour chaque station, le pipeline tente l'extraction Cerema en premier. Si la station est dans l'emprise d'au moins un raster Cerema, c'est cette source qui est utilisée (résolution 1,5 m). Sinon, le pipeline utilise le raster Demuzere (100 m). La source effective est tracée dans le champ `lcz_source` de la sortie.

## 4. Statistiques et figures

Le script 04 produit les statistiques agrégées par catégorie LCZ : nombre de stations, médiane et moyenne des NTrop, proportion de stations à ≥3 et ≥5 nuits tropicales, médiane des TnMax et TxMax.

Le script 05 produit les figures publiables :

- distribution boxplot des NTrop par catégorie LCZ ;
- barres horizontales des 20 stations top NTrop, colorées par LCZ ;
- nuage TnMax vs TxMax par catégorie LCZ ;
- carte simplifiée des stations à ≥5 nuits tropicales.

## 5. Limites assumées

- **Couverture LCZ Cerema** : limitée aux 88 aires urbaines françaises >50 000 habitants. Pour les stations hors de ces aires, le pipeline utilise Demuzere 100 m, dont la résolution est moindre. Cela ne pose pas de problème conceptuel : par définition, l'ICU se développe à partir d'une masse urbaine critique, et les stations en zone rurale ou en petites communes ne sont pas concernées par un ICU significatif.
- **Année de référence LCZ** : 2022 pour Cerema (SPOT), 2018 pour Demuzere. L'urbanisation française évolue lentement à l'échelle des classes LCZ ; les classifications restent pertinentes pour la période d'étude.
- **Coordonnées des stations** : les LAT/LON publiées par Météo-France ont une précision d'environ 10⁻⁴ degré (~10 m). Cette précision est compatible avec une analyse en buffer de 300-500 m.
- **Représentativité spatiale du capteur** : aucune analyse n'est faite ici sur le footprint micrométéorologique réel du capteur (qui dépend de la hauteur d'installation, du régime de vent, etc.). On approxime par un buffer circulaire homogène.

## 6. Références

- Stewart, I. D., & Oke, T. R. (2012). Local Climate Zones for Urban Temperature Studies. *Bulletin of the American Meteorological Society*, 93(12), 1879-1900. [doi:10.1175/BAMS-D-11-00019.1](https://doi.org/10.1175/BAMS-D-11-00019.1)
- Demuzere, M., et al. (2022). A global map of local climate zones to support earth system modelling and urban-scale environmental science. *Earth System Science Data*, 14(8), 3835-3873. [doi:10.5194/essd-14-3835-2022](https://doi.org/10.5194/essd-14-3835-2022)
- Cerema (2024). Cartographie des Zones Climatiques Locales (LCZ) des 88 aires urbaines de plus de 50 000 habitants de France métropolitaine — LCZ_SPOT_2022_Fr. [data.gouv.fr](https://www.data.gouv.fr/datasets/cartographie-des-zones-climatiques-locales-lcz-des-88-aires-urbaines-de-plus-de-50-000-habitants-de-france-metropolitaine)
- Martilli, A., Krayenhoff, E. S., & Nazarian, N. (2020). Is the Urban Heat Island intensity relevant for heat mitigation studies? *Urban Climate*, 31, 100541.
- Matthews, T., et al. (2025). Mortality impacts of the most extreme heat events. *Nature Reviews Earth & Environment*.
