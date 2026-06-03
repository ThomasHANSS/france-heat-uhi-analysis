# Épisodes étudiés

Le dépôt inclut six épisodes caniculaires configurés par défaut dans `config/episodes.yaml`. Cette section documente le contexte de chacun.

Pour ajouter un nouvel épisode, éditer `config/episodes.yaml` et compléter cette page.

## 1. Dôme de chaleur de fin mai 2026 (`dome-chaleur-mai-2026`)

**Période** : 20 au 29 mai 2026 (10 jours).

**Type** : dôme de chaleur (heat dome) — phénomène synoptique d'échelle continentale.

**Contexte synoptique** : anticyclone puissant bloqué en altitude, configuration en oméga sur l'Europe de l'Ouest. Subsidence et compression adiabatique de la masse d'air, advection persistante d'air saharien sur le sud et l'ouest du pays. Sols préalablement secs aggravant le réchauffement diurne par réduction de l'évapotranspiration.

**Particularité** : épisode très précoce dans l'année (fin mai), ce qui rend le contraste avec les normales saisonnières particulièrement marqué. Touche prioritairement la façade atlantique, l'intérieur vendéen, le sud-ouest et la Méditerranée occidentale. Le quart nord-est est moins exposé.

**Étude principale du projet** — voir `articles/dome-mai-2026/`.

## 2. Canicule historique d'août 2003 (`canicule-aout-2003`)

**Période** : 1ᵉʳ au 15 août 2003 (15 jours).

**Type** : canicule prolongée (prolonged heatwave).

**Contexte synoptique** : blocage anticyclonique subtropical durablement installé sur l'Europe de l'Ouest. Quinze jours consécutifs de températures exceptionnelles, en particulier des minima nocturnes très élevés. Sécheresse des sols préalable amplifiant l'effet.

**Particularité** : événement de référence historique en France, associé à un excès de mortalité estimé à environ 15 000 décès. Cas d'étude majeur pour comprendre la conjonction entre forçage synoptique extrême et vulnérabilité sociale aux extrêmes thermiques.

## 3. Vague de chaleur précoce de juin 2019 (`vague-chaleur-juin-2019`)

**Période** : 24 au 30 juin 2019 (7 jours).

**Type** : vague de chaleur courte et intense.

**Contexte synoptique** : plume saharienne advectée sur la France, configuration anticyclonique de blocage temporaire. Le 28 juin 2019, le record absolu national est battu à Gallargues-le-Montueux (Gard) avec 46,0 °C.

**Particularité** : événement court mais d'intensité diurne record. Permet de tester la signature d'un événement où le forçage est très focalisé géographiquement (sud-est).

## 4. Vague de chaleur de juillet 2019 (`vague-chaleur-juillet-2019`)

**Période** : 21 au 27 juillet 2019 (7 jours).

**Type** : vague de chaleur.

**Contexte synoptique** : seconde vague de chaleur de l'été 2019, plus intense sur le quart nord-est qu'en juin. Le 25 juillet 2019, Paris-Montsouris atteint son record absolu (42,6 °C).

**Particularité** : événement intéressant pour comparer la signature urbaine du dôme entre épisodes : sur juillet 2019, Paris-Montsouris a battu son record absolu, alors qu'en mai 2026 elle a fait beaucoup moins.

## 5. Vague de chaleur de juillet 2022 (`vague-chaleur-juillet-2022`)

**Période** : 12 au 25 juillet 2022 (14 jours).

**Type** : vague de chaleur d'ampleur exceptionnelle.

**Contexte synoptique** : succession de pulsations chaudes liées à un blocage atmosphérique en oméga, advection régulière d'air saharien. Sols très secs sur la majorité du pays.

**Particularité** : épisode marqué par des records absolus sur la façade atlantique (Biarritz, La Rochelle, Brest) — zones habituellement tempérées. Cas d'étude pour la question « le dôme peut-il toucher en priorité des régions atypiques ? ».

## 6. Canicule d'août 2023 (`canicule-aout-2023`)

**Période** : 15 au 25 août 2023 (11 jours).

**Type** : canicule tardive.

**Contexte synoptique** : canicule tardive et intense, particulièrement marquée dans la vallée du Rhône et le sud-est. Multiples nuits tropicales soutenues en Méditerranée et Provence, conséquence de la chaleur stockée par la mer et restituée la nuit.

**Particularité** : intéressant pour observer le rôle de la Méditerranée comme « radiateur nocturne » et la signature thermique côtière de fin d'été.

---

## Analyse comparative attendue

L'intérêt d'avoir six épisodes plutôt qu'un seul est de vérifier la **stabilité de la conclusion** : la signature géographique d'un dôme suit-elle toujours la même logique, ou varie-t-elle selon le contexte synoptique ?

Hypothèses à tester :

1. **Mai 2026** — façade atlantique + Vendée + Méditerranée occidentale ; cœur urbain parisien fortement touché ; reste des grandes villes peu touché.
2. **Août 2003** — touche large, dôme installé sur tout le pays ; signature urbaine et rurale forte.
3. **Juin 2019** — focalisée sur le sud-est ; quart nord-ouest épargné.
4. **Juillet 2019** — au contraire, signal fort sur le quart nord-est (Paris-Montsouris record).
5. **Juillet 2022** — façade atlantique (atypique) ; nord-ouest fortement touché.
6. **Août 2023** — sud-est + Méditerranée.

Si l'ICU était le facteur dominant, on s'attendrait à ce que les **mêmes grandes villes** soient en tête à chaque épisode. Si c'est le facteur synoptique qui domine, on s'attend à des **patterns géographiques différents** d'un épisode à l'autre, suivant la trajectoire du blocage. L'analyse multi-épisodes permet de trancher empiriquement.
