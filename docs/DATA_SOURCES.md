# Sources de données

Ce document liste toutes les sources de données utilisées par le pipeline, leurs licences, leurs limites et leurs citations.

## 1. Données climatologiques Météo-France

**Nom du dataset** : Données climatologiques de base — quotidiennes.

**Producteur** : Météo-France.

**Portail de diffusion** : [meteo.data.gouv.fr](https://meteo.data.gouv.fr/datasets/donnees-climatologiques-de-base-quotidiennes).

**Licence** : Licence Ouverte / Open Licence v2.0 (Etalab). Réutilisation libre, attribution requise.

**Description** : températures minimale (Tn), maximale (Tx), moyenne (Tm) quotidiennes, par station du réseau Météo-France, depuis 1959 à aujourd'hui. Plusieurs milliers de stations sont disponibles, sur l'ensemble du territoire métropolitain et ultramarin.

**Fréquence de mise à jour** : mensuelle pour les données historiques, en quasi-temps réel pour les données récentes.

**Acquisition automatisée par le pipeline** : le script `01_download_meteo.py` interroge l'API publique data.gouv.fr et télécharge les ressources correspondant à la période de l'épisode étudié. Les fichiers sont stockés dans `data/raw/meteo_france/<période>/`.

**Citation conseillée** :
> Météo-France. Données climatologiques de base — quotidiennes. Diffusion via meteo.data.gouv.fr, Licence Ouverte 2.0.

## 2. Classification LCZ Cerema — France

**Nom du dataset** : Cartographie des Zones Climatiques Locales (LCZ) des 88 aires urbaines de plus de 50 000 habitants de France métropolitaine (LCZ_SPOT_2022_Fr).

**Producteur** : Cerema, Pôle satellite.

**Portail de diffusion** : [data.gouv.fr](https://www.data.gouv.fr/datasets/cartographie-des-zones-climatiques-locales-lcz-des-88-aires-urbaines-de-plus-de-50-000-habitants-de-france-metropolitaine).

**Licence** : Licence Ouverte / Open Licence v2.0 (Etalab).

**Description** : classification LCZ à 1,5 m de résolution, produite à partir d'imagerie SPOT 2022 (DINAMIS) et de la BD TOPO IGN v3.3. Couvre 88 aires urbaines françaises de plus de 50 000 habitants, définies à partir de l'Urban Atlas 2018 (Copernicus). Format livré : ZIP par aire urbaine contenant shapefile (`.shp`), raster (`.tif` à 1,5 m), métadonnées XML, symbologie QGIS et descriptif PDF.

**Usage validé par le producteur** : « Cette donnée LCZ peut être utilisée comme diagnostic à grande échelle du phénomène d'Îlot de Chaleur Urbain (ICU) sur votre territoire. Elle constitue un pré-diagnostic climatique tenant compte de la morphologie urbaine et de l'occupation du sol. » (page du dataset).

**Acquisition** : automatisable via l'API data.gouv.fr (le script `03_classify_stations_lcz.py` peut télécharger automatiquement avec `--download-cerema`, mais la taille totale est d'environ 10 Go, donc on télécharge uniquement les aires nécessaires pour les stations étudiées). Les ZIP doivent être extraits avant utilisation.

**Limite à connaître** : couverture limitée aux 88 aires urbaines de plus de 50 000 habitants. Pour les stations en dehors, le pipeline utilise la source 3 (Demuzere) en complément.

**Citation conseillée** :
> Cerema (2024). Cartographie des Zones Climatiques Locales (LCZ) des 88 aires urbaines de plus de 50 000 habitants de France métropolitaine — LCZ_SPOT_2022_Fr. Données publiées sur data.gouv.fr, Licence Ouverte 2.0.

## 3. Classification LCZ globale — Demuzere et al. 2022

**Nom du dataset** : Global map of Local Climate Zones.

**Producteur** : Demuzere, Kittner, Martilli, Mills, Moede, Stewart, van Vliet, Bechtel (consortium académique).

**Portail de diffusion** : [Zenodo](https://doi.org/10.5281/zenodo.6364594).

**Licence** : Creative Commons Attribution 4.0 International (CC-BY 4.0). Citation obligatoire.

**Description** : cartographie LCZ globale à 100 m de résolution, année de référence 2018, produite à partir d'images Landsat 8 et de zones d'entraînement WUDAPT. 17 classes Stewart & Oke 2012. Format : GeoTIFF 8 bits, EPSG:4326.

**Acquisition** : téléchargement direct depuis Zenodo. Le fichier France peut être découpé à partir du raster global pour limiter le volume. À placer dans `data/raw/demuzere_lcz/`.

**Citation obligatoire** :
> Demuzere, M., Kittner, J., Martilli, A., Mills, G., Moede, C., Stewart, I. D., van Vliet, J., and Bechtel, B. (2022). A global map of local climate zones to support earth system modelling and urban-scale environmental science. *Earth System Science Data*, 14(8), 3835-3873. https://doi.org/10.5194/essd-14-3835-2022

## 4. Référence méthodologique LCZ

**Article fondateur** :
> Stewart, I. D., & Oke, T. R. (2012). Local Climate Zones for Urban Temperature Studies. *Bulletin of the American Meteorological Society*, 93(12), 1879-1900. https://doi.org/10.1175/BAMS-D-11-00019.1

## 5. Autres références méthodologiques mobilisées

- Martilli, A., Krayenhoff, E. S., & Nazarian, N. (2020). Is the Urban Heat Island intensity relevant for heat mitigation studies? *Urban Climate*, 31, 100541. https://doi.org/10.1016/j.uclim.2019.100541
- Bercos-Hickey, E., et al. (2022). Anthropogenic Contributions to the 2021 Pacific Northwest Heatwave. *Geophysical Research Letters*, 49, e2022GL099396.
- White, R. H., et al. (2023). The unprecedented Pacific Northwest heatwave of June 2021. *Nature Communications*, 14, 727.
- Matthews, T., et al. (2025). Mortality impacts of the most extreme heat events. *Nature Reviews Earth & Environment*.
- IPCC AR6 Working Group I (2021). *Climate Change 2021: The Physical Science Basis*. Chapter 11 (Weather and Climate Extreme Events in a Changing Climate).
- Météo-France (2025). Cartographie ICU MApUCE pour 47 agglomérations françaises (novembre 2025).
