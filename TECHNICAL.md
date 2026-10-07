# Documentation technique : intégration Home Assistant Grandole Mobilités

> Version : 1.0.0 · Domaine HA : `grandole` · Classe IoT : `cloud_polling`

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Architecture](#2-architecture)
3. [Sources de données](#3-sources-de-données)
4. [Modèle GTFS en mémoire (`gtfs.py`)](#4-modèle-gtfs-en-mémoire-gtfspy)
5. [Lecture des flux GTFS-RT (`realtime.py`)](#5-lecture-des-flux-gtfs-rt-realtimepy)
6. [Calcul des passages](#6-calcul-des-passages)
7. [État des lignes et messages](#7-état-des-lignes-et-messages)
8. [Positions des véhicules](#8-positions-des-véhicules)
9. [Coordinateur et cache GTFS (`coordinator.py`)](#9-coordinateur-et-cache-gtfs-coordinatorpy)
10. [Entités sensor (`sensor.py`)](#10-entités-sensor-sensorpy)
11. [Flux de configuration (`config_flow.py`)](#11-flux-de-configuration-config_flowpy)
12. [Schéma des données de configuration](#12-schéma-des-données-de-configuration)
13. [Services (`services.py`)](#13-services-servicespy)
14. [Cartes Lovelace](#14-cartes-lovelace)
15. [Cycle de vie](#15-cycle-de-vie)
16. [Différences avec l'intégration Ginko](#16-différences-avec-lintégration-ginko)
17. [Limitations connues](#17-limitations-connues)

---

## 1. Vue d'ensemble

L'intégration **Grandole** expose dans Home Assistant les données du réseau de bus Grandole Mobilités (Grand Dole, 16 lignes, 412 quais, 256 noms d'arrêts, 654 courses). Elle est construite sur le modèle de l'intégration Ginko (Besançon) : mêmes modes, mêmes noms de capteurs, même structure d'attributs de passage, mêmes cartes Lovelace. La différence fondamentale est l'absence d'API REST : **tout est calculé localement** à partir de trois fichiers ouverts, sans clé.

| Besoin | Ginko | Grandole |
|---|---|---|
| Horaires théoriques | API `getTempsLieu` | GTFS statique en mémoire |
| Retards | Champ `fiable` de l'API | GTFS-RT trip-updates (`delay` par arrêt) |
| Positions des bus | Déduites de `getListeTemps` | GTFS-RT vehicle-positions (GPS réel) |
| État des lignes | API `getEtatLignes` | Déduit des horaires et du temps réel |
| Infotrafic | API `getMessages` | Page HTML du widget Instant System utilisée par grandole-mobilites.fr |
| Messages temps réel | (inclus dans l'infotrafic) | Synthétisés (annulations, retards, arrêts sautés) |
| Arrêts proches | API `getArretsProches` | Distance haversine sur `stops.txt` |

---

## 2. Architecture

### 2.1 Arborescence des fichiers

```
custom_components/grandole/
├── __init__.py            Setup global, fichiers JS Lovelace, cycle de vie du coordinateur
├── const.py               Constantes (URLs, intervalles, seuils, modes, états)
├── gtfs.py                Modèle GTFS en mémoire et tous les calculs (aucune dépendance HA)
├── realtime.py            Décodage protobuf des deux flux GTFS-RT
├── infotrafic.py          Analyse HTML de l'infotrafic du site officiel (aucune dépendance HA)
├── coordinator.py         GrandoleStore (GTFS, cache disque, mise à jour) et GrandoleCoordinator (10 s)
├── sensor.py              9 classes d'entités sensor
├── config_flow.py         Config flow multi-étapes et options flow
├── services.py            Services chercher_arret et get_horaires
├── services.yaml          Sélecteurs des services
├── strings.json           Textes (français)
├── translations/fr.json, en.json
├── manifest.json          requirements: gtfs-realtime-bindings
├── brand/icon.png, icon@2x.png
└── lovelace/
    ├── grandole-card.js         4 custom elements
    └── grandole-card-editor.js  4 éditeurs
```

### 2.2 Diagramme général

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           Home Assistant                                 │
│                                                                          │
│  __init__.py                                                             │
│   • async_setup : store GTFS, services, /grandole_card, ressources JS    │
│   • async_setup_entry : un GrandoleCoordinator partagé pour toutes       │
│     les entrées (compteur d'entrées), plateformes sensor                 │
│                │                                                         │
│                ▼                                                         │
│  coordinator.py                                                          │
│   ┌─────────────────────────┐   ┌──────────────────────────────────┐    │
│   │ GrandoleStore           │   │ GrandoleCoordinator (10 s)       │    │
│   │ • Reseau (gtfs.py)      │◀──│ • GET trip-updates + positions   │    │
│   │ • cache .storage/*.zip  │   │ • construire_temps_reel()        │    │
│   │ • data.gouv toutes 6 h  │   │ • data = TempsReel               │    │
│   │                         │   │ • infotrafic toutes les 5 min    │    │
│   └─────────────────────────┘   └──────────────────────────────────┘    │
│                │                                 │                       │
│                ▼                                 ▼                       │
│  sensor.py : chaque entité appelle reseau.passages() / etat_lignes() /   │
│  positions_ligne() avec coordinator.data à chaque cycle                  │
│                                                                          │
│  Lovelace : /grandole_card/grandole-card.js?v=1.0.0                      │
└──────────────────────────────────────────────────────────────────────────┘
                │                          │
                ▼ HTTPS (au démarrage,     ▼ HTTPS toutes les 10 s
                  puis si modifié)
   transport.data.gouv.fr/resources/81254/download      proxy.transport.data.gouv.fr/resource/
   www.data.gouv.fr/api/1/datasets/reseau-de-…            tgd-dole-gtfs-rt-trip-update
                                                           tgd-dole-gtfs-rt-vehicle-position
                ▼ HTTPS toutes les 5 min
   sim.133.prod.instant-system.com/fr/traffic-infos (infotrafic du site officiel)
```

### 2.3 Modes, coordinateur et capteurs

Tous les modes partagent **le même coordinateur**. Le tableau donne les capteurs créés par mode.

```
Mode             │ Capteurs créés
─────────────────┼──────────────────────────────────────────────────────────
lieu             │ GrandoleLieuSensor
liste            │ GrandoleListeSensor × N combinaisons
person_proximity │ GrandolePersonProximitySensor
ligne            │ GrandoleLigneEtatSensor + GrandoleLigneMessagesSensor
suivi_ligne      │ GrandoleSuiviLigneSensor
(première entrée)│ GrandoleEtatLignesSensor + GrandoleMessagesSensor (globaux)
```

---

## 3. Sources de données

| Source | URL | Format | Fréquence |
|---|---|---|---|
| GTFS statique | `https://transport.data.gouv.fr/resources/81254/download` | zip (400 Ko) | Au démarrage si absent du cache, puis quand `last_modified` change |
| Métadonnées | `https://www.data.gouv.fr/api/1/datasets/reseau-de-transport-du-grand-dole/` | JSON | Toutes les 6 h (`GTFS_CHECK_INTERVAL`) |
| Métadonnées de repli | `https://transport.data.gouv.fr/api/datasets/5e2087978b4c41738e555328` | JSON | Si data.gouv.fr ne répond pas : `updated` et `original_url` de la ressource GTFS |
| Trip-updates | `https://proxy.transport.data.gouv.fr/resource/tgd-dole-gtfs-rt-trip-update` | protobuf | 10 s |
| Vehicle-positions | `https://proxy.transport.data.gouv.fr/resource/tgd-dole-gtfs-rt-vehicle-position` | protobuf | 10 s |
| Infotrafic | `https://sim.133.prod.instant-system.com/fr/traffic-infos` | HTML | 5 min (`INFOTRAFIC_INTERVAL`) |

### 3.1 Contenu du GTFS (version du 2 septembre 2026)

| Fichier | Lignes | Remarques |
|---|---|---|
| `agency.txt` | 1 | `Europe/Paris`, utilisé comme fuseau de référence |
| `routes.txt` | 16 | `route_color` et `route_text_color` renseignés, `route_sort_order` fiable |
| `stops.txt` | 412 | 256 noms uniques ; suffixe `1`/`2` de `stop_id` = quai par sens ; `wheelchair_boarding` renseigné ; pas de `parent_station` |
| `trips.txt` | 654 | `direction_id` 0/1, `trip_headsign` toujours présent, `wheelchair_accessible` toujours 0 |
| `stop_times.txt` | 15 186 | `arrival_time` = `departure_time`, `stop_headsign` = `trip_headsign`, dernier départ 20:52 |
| `calendar.txt` | 14 | Services jusqu'au 10 septembre 2027 |
| `calendar_dates.txt` | 673 | Surtout des suppressions (vacances, fériés) |

### 3.2 Infotrafic du site officiel

Le site grandole-mobilites.fr est une plateforme Keolis Web Passengers (Gatsby + DatoCMS). Trois sources d'infotrafic y coexistent, dont deux inutilisables :

| Source | Contenu observé le 18 septembre 2026 | Verdict |
|---|---|---|
| `/rss.xml` (« Info Traffic RSS feed ») | 0 élément, `lastBuildDate` du 16 septembre | Rempli seulement à la reconstruction du site |
| DatoCMS `allInfoTraffics` (GraphQL, jeton public en lecture) | 0 enregistrement | Modèle non alimenté pour ce réseau |
| Widget Instant System `sim.133.prod.instant-system.com/fr/widget/traffic?token=GRANDOLE-MOBILITES` | 3 lignes perturbées (18, 2, 10) | C'est le bloc « Info trafic » affiché sur la page d'accueil |

Le widget charge son contenu par une requête GET sur `/fr/traffic-infos` (chemin `disruptionPath` de sa configuration), sans jeton ni cookie : la réponse est un fragment HTML de 20 Ko rendu côté serveur. Structure :

```
<ul class="is-Switch">                       onglets « en cours » / « à venir »
<div id="is-TrafficInfos-Disruption-List_Ongoing">
  <a data-target="#_HANOVER-18_currents" data-line-id="HANOVER:18" data-line-short-name="18" …>
     <i class="… is-Disruption-State_WARN">   gravité : WARN ou INFO
  <div class="is-Modal is-fade" id="_HANOVER-18_currents">
     <div class="is-Disruption-Item-Header-State">   un bloc par perturbation
        <i class="… is-Disruption-Effect-modified_service">
     <p class="is-Disruption-Item-Header-Title">Perturbation sur la ligne 18:</p>
     <p class="is-Disruptions-Details-Title">Période d'application</p>
     <p class="is-Disruptions-Details-Item">du 06/09/2026 à 06:15 au 26/03/2027 à 10:00</p>
     <div class="is-Disruptions-Details-Problems"><span …>Travaux</span><span …>Service modifié</span></div>
     <div class="is-Disruptions-Details-Lines"> … Ligne </span>18 … <span class="direction">Tous les sens</span>
     <p class="is-Disruptions-Details-Problems-Item"><p>corps HTML (avec styles Word)</p>…</p>
     <p class="is-Disruption-Item-Content-UpdateDate">Mise à jour le lundi 7 septembre 2026 à 13:09</p>
<div id="is-TrafficInfos-Disruption-List_ToCome">   « Aucune perturbation de ligne à venir » ou même structure
```

Une même perturbation touchant plusieurs lignes est répétée dans la fenêtre de chaque ligne (ici « Travaux rue de Damparis à Foucherans » pour les lignes 2 et 10).

### 3.3 Particularités observées sur les flux GTFS-RT

- **Trip-updates** : `incrementality FULL_DATASET`, une entité par course avec un `stop_time_update` par arrêt (`arrival` seulement, `delay` + `time` absolu + `uncertainty` 100). Pas de `start_date`, pas de `departure`. Le champ `vehicle.label` n'est présent que sur certaines courses. **Le flux conserve les courses de la veille** : à 01:19, il contenait 16 courses horodatées de la veille entre 07:21 et 09:41. D'où la validation d'instance décrite au §6.2.
- **Vehicle-positions** : `trip_id`, `route_id`, `position` (lat, lon, bearing), `timestamp`, `vehicle.label`. Pas de `stop_id` ni `current_status`. **Le flux conserve des positions périmées** : à 00:40, un bus daté de 07:46 était encore présent. Toute position de plus de `AGE_MAX_POSITION` (300 s) est ignorée au décodage.

- **Flux figé** : le 18 septembre 2026 à 19h18, l'en-tête des deux flux était à jour (régénération toutes les 10 s) mais toutes les entités dataient de 07h04 à 07h26 (29 positions, 42 courses), alors que 6 courses circulaient d'après le GTFS. L'en-tête ne prouve donc rien. `TempsReel.derniere_donnee` retient l'horodatage d'entité le plus récent (positions périmées comprises) ; `frais()` exige une donnée de moins de `AGE_MAX_FLUX` (900 s). Les capteurs exposent `temps_reel` (= `frais()`) et `temps_reel_age`. La nuit, faute de bus, `temps_reel` est donc faux aussi, ce qui est exact : aucun temps réel n'est disponible.

---

## 4. Modèle GTFS en mémoire (`gtfs.py`)

`instances_du_jour` ne retient de la veille que les courses dont la fin (marge comprise) déborde sur le jour courant, pour que `courses_jour` compte bien les courses d'une seule journée.

`gtfs.py` ne dépend pas de Home Assistant (uniquement `csv`, `zipfile`, `zoneinfo`) : il est testable seul et s'exécute dans l'executor.

### 4.1 Classes

```python
Arret(id, nom, latitude, longitude, accessible)
Ligne(id, num, nom, couleur_fond, couleur_texte, ordre)
Course(id, id_ligne, id_service, destination, sens_aller, accessible,
       arrets[], sequences[], arrivees[], departs[], destinations[])   # listes alignées par index
ArretMaj(sequence, id_arret, retard, heure, saute)                       # un stop_time_update
MiseAJourCourse(id_course, id_ligne, date_debut, horodatage, annulee, vehicule,
                retard_course, par_sequence{}, par_arret{})
PositionVehicule(id, label, id_course, id_ligne, latitude, longitude, cap, horodatage)
TempsReel(horodatage, courses{trip_id: MiseAJourCourse}, vehicules[], disponible)
Prediction(theorique, prevu, fiable, retard, annule, saute, vehicule)
```

### 4.2 `Reseau`

| Attribut | Contenu |
|---|---|
| `arrets` | `stop_id → Arret` |
| `arrets_par_nom` | `nom → [Arret]` (les quais d'un même nom) |
| `lignes` | `route_id → Ligne` |
| `courses` | `trip_id → Course` avec ses horaires triés par `stop_sequence` |
| `index_arret` | `stop_id → [(depart_s, trip_id, idx)]` trié par heure : c'est l'index utilisé pour les passages |
| `calendrier`, `exceptions` | `calendar.txt` et `calendar_dates.txt` |
| `fuseau` | `ZoneInfo` de `agency_timezone` |

Analyse du zip : 57 ms sur un Mac, environ 5 Mo de mémoire.

### 4.3 Jours de service

`services_actifs(jour)` applique `calendar.txt` (plage de dates + jour de semaine) puis `calendar_dates.txt` (type 1 ajoute, type 2 retire). Résultat mis en cache par date.

`base_jour(jour)` = midi local moins 12 h, conformément à la convention GTFS (les heures `stop_times` supérieures à 24:00:00 appartiennent au jour de service précédent). `jours_candidats(maintenant)` renvoie la veille et le jour courant : chaque calcul considère les deux instances possibles d'une course.

### 4.4 Recherche d'arrêts

- `normaliser()` : décomposition NFKD, suppression des accents, `casefold`.
- `resoudre_nom(nom)` : nom exact, puis égalité normalisée, puis préfixe, puis sous-chaîne. Utilisé par les capteurs, les services et le config flow (le sélecteur d'arrêt accepte une valeur libre).
- `chercher_arrets(texte, limite)` : préfixe du nom, puis préfixe d'un mot du nom, puis sous-chaîne. Chaque résultat contient `lignes` (numéros des lignes desservant l'arrêt).
- `arrets_proches(lat, lon, max_stops, rayon)` : haversine sur les 412 quais, regroupés par nom (distance minimale), triés, dans un rayon de `RAYON_PROXIMITE` (1000 m).

---

## 5. Lecture des flux GTFS-RT (`realtime.py`)

### 5.0 Analyse de l'infotrafic (`infotrafic.py`)

`analyser_infotrafic(html, fuseau)` travaille par expressions régulières sur le fragment décrit au §3.2, sans dépendance externe :

1. Découpage en deux volets (`en_cours`, `a_venir`) sur les identifiants des onglets.
2. Dans chaque volet, association `data-target` → (identifiant de ligne, numéro, gravité `WARN`/`INFO`) à partir des liens de badge.
3. Découpage de chaque fenêtre modale en blocs `is-Disruption-Item-Header-State`, puis extraction : titre (deux-points final retiré), effet, période (dates `JJ/MM/AAAA à HH:MM` converties en ISO 8601 dans le fuseau de l'agence ; « jusqu'au » donne seulement `fin`), causes, lignes des badges, sens, corps, date de mise à jour.
4. Nettoyage du corps : suppression des `<span>` et attributs `style`/`class`/`lang`, seules les balises `p`, `br`, `strong`, `b`, `em`, `i`, `ul`, `ol`, `li`, `a` sont conservées, paragraphes vides retirés.
5. Déduplication par empreinte SHA-1 de (titre, début, fin, texte du corps) : les lignes des fenêtres successives sont fusionnées dans `lignes`, la gravité `WARN` l'emporte.

Résultat : liste de messages `{id, type: "infotrafic", titre, corps, lignes, etat, gravite, effet, causes, sens, debut, fin, mise_a_jour, source}`. Si le HTML ne contient pas l'onglet « en cours », la fonction renvoie une liste vide (page vide ou structure changée) ; le coordinateur ne conserve la liste précédente qu'en cas d'erreur réseau.


`construire_temps_reel(mises_a_jour, positions, maintenant_ts)` décode les deux protobufs avec `gtfs-realtime-bindings` et renvoie un `TempsReel`.

- **Trip-updates** : une `MiseAJourCourse` par entité. `horodatage` = `trip_update.timestamp`, sinon l'horodatage de l'en-tête. `annulee` si `schedule_relationship == CANCELED`. Chaque `stop_time_update` devient un `ArretMaj` indexé par `stop_sequence` (et par `stop_id` en repli) ; `saute` si `SKIPPED` ; l'événement retenu est `arrival`, sinon `departure`.
- **Vehicle-positions** : les entités sans `position` sont ignorées, ainsi que celles dont `maintenant - timestamp > AGE_MAX_POSITION`. `disponible` passe à vrai dès qu'un des deux flux a été lu.

Si un flux est injoignable, le coordinateur passe `None` et le `TempsReel` est simplement vide pour ce flux : les capteurs restent disponibles avec les horaires théoriques (`fiable: false`).

---

## 6. Calcul des passages

### 6.1 `passages(ids_arrets, maintenant, temps_reel, nb, id_ligne, sens_aller, horizon)`

```
Pour chaque (jour, base) dans jours_candidats(maintenant)   # veille et jour courant
    actifs = services_actifs(jour)
    Pour chaque quai demandé
        Pour chaque (depart, trip_id, idx) de index_arret[quai]  (trié par heure)
            arrêt si base + depart dépasse l'horizon (+ tolérance)
            ignorer si service inactif, si dernier arrêt de la course (terminus d'arrivée),
                    si ligne ou sens ne correspond pas
            prediction = prediction(course, base, idx, temps_reel)
            ignorer si annulée ou arrêt sauté
            ignorer si prevu < maintenant - GRACE_PASSAGE (30 s) ou > maintenant + horizon (3 h)
            candidats += (prevu, passage)
Trier par heure prévue
Garder les nb premiers par (ligne, sens)
```

Coût mesuré : 0,4 ms pour Dole Gare.

### 6.2 `prediction(course, base, idx, temps_reel)` : validation d'une mise à jour

C'est le point délicat, à cause des mises à jour périmées conservées par le flux.

```
maj = temps_reel.courses[trip_id]
Si pas de maj                                        → théorique, fiable = false
Si maj.date_debut renseigné                          → valide ssi égal à la date de base
Sinon                                                → valide ssi
      base + premier_depart - MARGE_AVANT_COURSE (3 h) ≤ maj.horodatage
                                                     ≤ base + derniere_arrivee + MARGE_APRES_COURSE (2 h)
Si non valide                                        → théorique, fiable = false
Si maj.annulee                                       → annule = true
arret_maj = _arret_maj(maj, course, idx)             # voir ci-dessous
Si arret_maj.heure présent, même séquence, et |heure - theorique| ≤ 3 h
                                                     → prevu = heure absolue, retard = prevu - theorique
Sinon si arret_maj.retard présent                    → prevu = theorique + retard
Sinon si maj.retard_course présent                   → prevu = theorique + retard_course
Sinon                                                → retard = 0
```

`_arret_maj` applique la règle GTFS-RT de propagation : la mise à jour de l'arrêt lui-même, sinon celle de l'arrêt précédent le plus proche (son `delay` se propage), sinon le `delay` de la première mise à jour suivante.

Exemple concret : le 18 septembre à 07:19, la mise à jour de la course 1705 datée de la veille 07:21 est hors fenêtre pour l'instance du jour (07:08 à 07:46, marges comprises) : les passages sont théoriques. La même mise à jour horodatée du jour est acceptée et `retard` vaut 0.

### 6.3 Structure d'un passage

Voir le README, section « Objet passage ». Les clés sont celles de Ginko (`idLigne`, `numLignePublic`, `couleurFond`, `couleurTexte`, `destination`, `temps`, `tempsEnSeconde`, `typeDeTemps`, `fiable`, `numVehicule`, `modeTransport`, `accessibiliteVehicule`, `accessibiliteArret`, `idArret`, `nomExact`, `latitude`, `longitude`, `sensAller`, `precisionDestination`, `tempsHTML`) plus `nomLigne`, `retard`, `heure`, `heureTheorique`, `idCourse`.

`temps` est toujours en minutes (`typeDeTemps` = 0) : `< 1 min` sous 60 s, sinon `N min`. `numVehicule` vient de la position GPS de la course si elle existe, sinon du `vehicle.label` de la mise à jour.

---

## 7. État des lignes et messages

`etat_lignes(maintenant, temps_reel)` renvoie `(etats, messages)` pour les 16 lignes, dans l'ordre de `route_sort_order`. Pour chaque instance de course du jour :

| Compteur | Règle |
|---|---|
| `courses_en_cours` | `debut_prevu - 60 ≤ maintenant ≤ fin_prevu + 60`, course non annulée |
| `courses_a_venir` | `debut_prevu > maintenant` |
| `courses_annulees` | Mise à jour valide `CANCELED`, fin théorique il y a moins d'une heure |
| `arrets_non_desservis` | Arrêts `SKIPPED` non encore passés sur les courses en cours |
| `retard_max` | Maximum des `retard` au prochain arrêt des courses en cours avec temps réel |
| `vehicules_localises` | Positions GPS récentes dont `route_id` (ou la course) est la ligne |
| `prochain_depart` | Premier `debut_prevu` futur |

État résultant (codes identiques à Ginko pour la compatibilité des cartes) :

| Code | Condition |
|---|---|
| 3 Hors service | Aucune instance aujourd'hui, ou ni course en cours ni course à venir, ou aucune course en cours (avant le premier départ) |
| 6 Circulation interrompue | Toutes les courses restantes sont annulées |
| 5 Perturbation en cours | Au moins une annulation, un arrêt sauté ou `retard_max ≥ RETARD_PERTURBATION` (600 s) |
| 1 Normal | Sinon |

Le code 0 existe dans `ETAT_META` mais n'est jamais produit ; 2 et 4 viennent uniquement de l'infotrafic (§7.0).

### 7.0 Prise en compte de l'infotrafic

`etat_lignes(maintenant, temps_reel, infotrafic)` reçoit la liste des messages infotrafic du coordinateur. Pour chaque ligne, les messages dont `lignes` contient son numéro donnent des états candidats : `WARN` en cours → 5, `INFO` en cours → 2, à venir → 4. L'état final est le candidat de rang le plus élevé (`RANG_ETAT` : 1 et 3 valent 0, puis 2, 4, 5, 6), l'état calculé depuis le temps réel restant un candidat. Une ligne hors service avec une info trafic de niveau information passe donc en 2 ; une ligne normale avec une alerte `WARN` passe en 5. Les compteurs `infotrafic_en_cours` et `infotrafic_a_venir` et la liste `infotrafic` (identifiants) sont ajoutés à chaque ligne.

Les messages renvoyés par `etat_lignes` sont l'infotrafic (dans l'ordre de la page) suivi des messages synthétisés ci-dessous.

### 7.1 Messages synthétisés

Le réseau ne publie pas de service-alerts GTFS-RT. En complément de l'infotrafic, des messages sont générés à partir des anomalies temps réel :

| Type | Déclencheur | Identifiant stable |
|---|---|---|
| `annulation` | Course annulée dont la fin théorique est dans la dernière heure ou à venir | `annulation-<trip>-<date>` |
| `retard` | Course en cours avec `retard ≥ RETARD_MESSAGE` (300 s) | `retard-<trip>-<date>` |
| `arret_non_desservi` | Arrêt `SKIPPED` à venir | `saut-<trip>-<seq>-<date>` |

Chaque message a `titre`, `corps`, `lignes: [num]`, `type`, `idCourse`. Les cartes filtrent par `lignes` exactement comme avec Ginko.

Le coordinateur met ce calcul en cache 5 s (`etats_et_messages()`) car quatre capteurs peuvent le demander à chaque cycle.

---

## 8. Positions des véhicules

`positions_ligne(id_ligne, maintenant, temps_reel)` :

1. **Positions GPS** (`temps_reel.vehicules`, déjà filtrées sur l'âge) dont la ligne correspond. Si la course est connue :
   - `_instance_course` choisit l'instance (veille ou jour) dont la fenêtre contient l'instant courant.
   - `_projeter` cherche l'arrêt le plus proche ; s'il est à moins de `RAYON_A_QUAI` (40 m) le bus est `a_quai` à cet arrêt (ou `depart` s'il est au premier arrêt avant l'heure de départ). Sinon la position est projetée sur chaque segment entre arrêts consécutifs (projection plane locale) : le segment le plus proche donne `arret_precedent` et `prochain_arret`.
   - `dans_sec` et `retard` viennent de `prediction()` sur le prochain arrêt.
2. **Courses avec mise à jour temps réel récente mais sans GPS** (`horodatage` de moins de `AGE_MAX_MISE_A_JOUR`, en cours, non annulée) : position estimée d'après les horaires, comme Ginko (`_prochain_index` = premier arrêt dont l'heure prévue est future). `gps: false`, `id` = `vehicle.label` ou `course-<trip>`.

Résultat trié par `dans_sec`. Chaque bus : `id, sens, terminus, prochain_arret, arret_precedent, statut, dans_sec, latitude, longitude, cap, age, gps, retard, idCourse`.

---

## 9. Coordinateur et cache GTFS (`coordinator.py`)

### 9.1 `GrandoleStore`

Unique par instance HA, dans `hass.data["grandole"]["store"]`, créé par `async_get_store()` (donc disponible pour le config flow avant toute entrée).

```
async_get()
    si Reseau déjà chargé → le renvoyer
    verrou
    lire .storage/grandole_gtfs.zip (executor)
    si présent → Reseau.depuis_zip (executor), version = meta["last_modified"]
    sinon      → _telecharger(None)

async_verifier_si_necessaire()        # appelé à chaque cycle, agit toutes les 6 h
    derniere = _derniere_modification()    # data.gouv : ressource format zip → last_modified,
                                           # sinon API transport.data.gouv.fr : ressource GTFS → updated
    si derniere != version → _telecharger(derniere) sous verrou, échec journalisé sans effet

_telecharger(version)
    GET GTFS_URL (60 s) ; GTFS_URL redirige vers data.gouv.fr : en cas d'échec, GET de
    l'`original_url` (static.data.gouv.fr) lue dans l'API transport.data.gouv.fr
    Reseau.depuis_zip (executor), refus si vide
    écriture atomique du zip dans .storage (fichier .tmp puis os.replace)
    Store JSON grandole_gtfs_meta : {last_modified, telecharge_le}
```

Le premier `async_verifier_si_necessaire()` a lieu dès le premier cycle : au démarrage avec cache, HA vérifie immédiatement si une nouvelle offre a été publiée.

### 9.2 `GrandoleCoordinator`

`DataUpdateCoordinator[TempsReel]`, intervalle `SCAN_INTERVAL_TEMPS_REEL` = 10 s (les flux sont régénérés toutes les 10 à 12 s).

```
_async_update_data()
    store.async_get()                         → UpdateFailed si le GTFS est introuvable
    store.async_verifier_si_necessaire()
    gather(GET trip-updates, GET positions)   → None par flux en cas d'erreur (journal limité aux
                                                échecs n° 1, 10, 100…, puis « de nouveau joignable »)
    _rafraichir_infotrafic()                  → au plus toutes les 5 min : GET traffic-infos avec
                                                Referer grandole-mobilites.fr, analyse dans l'executor,
                                                liste conservée telle quelle si la page est injoignable
    construire_temps_reel(...) dans l'executor
```

`infotrafic` et `infotrafic_horodatage` sont des attributs du coordinateur (pas de `data`), lus par `etats_et_messages()`.

`entrees` compte les config entries qui utilisent le coordinateur ; il est arrêté quand la dernière est déchargée.

---

## 10. Entités sensor (`sensor.py`)

Toutes héritent de `GrandoleEntity` : `_unrecorded_attributes = frozenset({MATCH_ALL})` (aucun attribut dans le recorder), `available` = dernier cycle réussi et GTFS chargé, attributs communs `temps_reel` et `gtfs_version`.

| Classe | Mode | `unique_id` | État |
|---|---|---|---|
| `GrandoleLieuSensor` | lieu | `grandole_<entry>_lieu_<nom>` | Nombre de passages |
| `GrandoleListeSensor` | liste | `grandole_<entry>_<nom>_<ligne>_<sens>` | Minutes avant le prochain bus |
| `GrandolePersonProximitySensor` | person_proximity | `grandole_<entry>_person_proximity` | Nombre d'arrêts |
| `GrandoleLigneEtatSensor` | ligne | `grandole_ligne_<id>_etat` | Libellé d'état |
| `GrandoleLigneMessagesSensor` | ligne | `grandole_ligne_<id>_messages` | Nombre de messages |
| `GrandoleEtatLignesSensor` | global | `grandole_etat_lignes` | Lignes perturbées |
| `GrandoleMessagesSensor` | global | `grandole_messages` | Nombre de messages |
| `GrandoleSuiviLigneSensor` | suivi_ligne | `grandole_suivi_ligne_<entry>` | Nombre de bus |

Les capteurs ne stockent rien : `native_value` et `extra_state_attributes` recalculent leur vue à partir de `coordinator.reseau` et `coordinator.data` (quelques millisecondes par cycle). Le nom d'arrêt est résolu à chaque calcul par `resoudre_nom`, ce qui rend les entrées robustes à un renommage mineur dans une future version du GTFS.

Les capteurs globaux sont créés par l'entrée « propriétaire » (`hass.data["grandole"]["_info_sensors_owner"]`), libérée au déchargement pour qu'une autre entrée puisse les recréer.

---

## 11. Flux de configuration (`config_flow.py`)

Pas d'étape clé API ni de réauthentification. Le GTFS est chargé via `async_get_store(hass).async_get()` dès la première étape qui en a besoin ; en cas d'échec le formulaire affiche `gtfs_indisponible`.

```
user : mode + nom (optionnel)
  ├─ lieu        : nom (dropdown 256 noms, valeur libre acceptée) + nb_passages
  │                unique_id lieu:<nom>
  ├─ liste       : nom (+ nb_passages la première fois)
  │    └─ liste_ligne : lignes desservant l'arrêt (lignes_arret)
  │         └─ liste_sens : directions observées à cet arrêt (sens_ligne_arret) + add_another
  ├─ person      : entité person + nb_passages + max_stops     unique_id person:<entité>
  ├─ ligne       : dropdown des 16 lignes                       unique_id ligne:<id>
  └─ suivi_ligne : dropdown des 16 lignes                       unique_id suivi:<id>
```

`sens_ligne_arret` compte, pour chaque `direction_id`, les `stop_headsign` des courses de la ligne passant par l'arrêt (hors terminus d'arrivée) : le libellé proposé est la destination majoritaire, les autres entre parenthèses.

Options flow : `init` (nb_passages ; max_stops en mode personne ; case add_item en mode liste) puis `add_item → add_item_ligne → add_item_sens` avec les mêmes sélecteurs que le config flow. Les modes ligne et suivi_ligne n'ont pas d'option (`aucune_option`).

---

## 12. Schéma des données de configuration

```json
{ "entry": { "mode": "lieu", "nom": "Dole Gare", "nb_passages": 3 } }
{ "entry": { "mode": "liste", "nb_passages": 3,
             "items": [ { "nom": "Dole Gare", "id_ligne": "2", "sens_aller": false } ] } }
{ "entry": { "mode": "person_proximity", "person_entity_id": "person.steph",
             "nb_passages": 3, "max_stops": 5 } }
{ "entry": { "mode": "ligne", "id_ligne": "2", "num_ligne": "2",
             "nom_ligne": "Tavaux Collège <> Dole Gare" } }
{ "entry": { "mode": "suivi_ligne", "id_ligne": "2", "num_ligne": "2",
             "nom_ligne": "Tavaux Collège <> Dole Gare" } }
```

`entry.options` peut contenir `nb_passages` et `max_stops` ; les capteurs lisent d'abord les options puis les données.

### Constantes (`const.py`)

| Constante | Valeur | Rôle |
|---|---|---|
| `SCAN_INTERVAL_TEMPS_REEL` | 10 s | Lecture des flux |
| `INFOTRAFIC_INTERVAL` | 5 min | Lecture de l'infotrafic |
| `GTFS_CHECK_INTERVAL` | 6 h | Vérification data.gouv |
| `AGE_MAX_POSITION` | 300 s | Positions GPS ignorées au-delà |
| `AGE_MAX_FLUX` | 900 s | Au-delà, le temps réel est considéré figé (`temps_reel: false`) |
| `AGE_MAX_MISE_A_JOUR` | 300 s | Bus estimé sans GPS : fraîcheur requise |
| `MARGE_AVANT_COURSE` / `MARGE_APRES_COURSE` | 3 h / 2 h | Fenêtre de validité d'une mise à jour |
| `TOLERANCE_HEURE_PREVUE` | 3 h | Écart maximal entre `time` absolu et horaire théorique |
| `GRACE_PASSAGE` | 30 s | Passage encore affiché juste après son heure |
| `HORIZON_PASSAGES` | 3 h | Horizon des passages |
| `RAYON_PROXIMITE` | 1000 m | Mode personne |
| `RAYON_A_QUAI` | 40 m | Bus considéré à l'arrêt |
| `RETARD_MESSAGE` | 300 s | Seuil de message de retard |
| `RETARD_PERTURBATION` | 600 s | Seuil d'état perturbé |

---

## 13. Services (`services.py`)

Deux services avec réponse (`SupportsResponse.ONLY`), enregistrés dans `async_setup`.

| Service | Entrée | Sortie |
|---|---|---|
| `grandole.chercher_arret` | `recherche`, `limite` (1 à 50, défaut 10) | `{arrets: [{nom, latitude, longitude, accessible, quais, lignes}]}` |
| `grandole.get_horaires` | `nom`, `nb` (1 à 5, défaut 3) | `{nom, nb_passages, passages, temps_reel}` |

Les deux passent par `async_get_store(hass).async_get()` (donc fonctionnent même sans entrée chargée, avec un chargement du GTFS à la volée) ; le temps réel vient du coordinateur s'il existe, sinon les passages sont théoriques. Erreurs : GTFS indisponible → `HomeAssistantError`, arrêt inconnu ou nom vide → `ServiceValidationError`. Aucun cache : le calcul est local et plus rapide qu'un cache.

---

## 14. Cartes Lovelace

Servies depuis `/grandole_card/` (`StaticPathConfig`, en-têtes de cache) et injectées par `add_extra_js_url` avec `?v=<version du manifest>` ; l'entrée correspondante de `.storage/lovelace_resources` est créée ou mise à jour au démarrage.

| Élément | Source | Notes |
|---|---|---|
| `grandole-card` | `GrandoleCard` | Modes `lieu`, `liste`, `proximity` (capteur ou `person_entity`). Bannière = premier passage par direction, pilules pour les suivants, heure prévue, badge de retard, point de position via `suivi_entities` (correspondance `numVehicule` ↔ `buses[].id`), pictogramme « Trains » sur Dole Gare, mention « horaires théoriques » si `temps_reel` est faux |
| `grandole-recherche-card` | hérite de `GrandoleCard` | Coquille construite une fois (focus conservé), recherche debouncée 300 ms via `callWS call_service` + `return_response`, dernier arrêt en `localStorage` (`grandole-recherche-last`) |
| `grandole-etat-card` | `GrandoleEtatCard` | Filtres Perturbées / Toutes / En service / Infos / Prévues / par ligne, messages dépliables avec causes, période et date de mise à jour (teinte bleue pour une information, ambre pour une perturbation), sous-titre par ligne (infos trafic, courses en cours, bus localisés, retard max, prochain départ), lignes hors service estompées et en dernier |
| `grandole-suivi-card` | `GrandoleSuiviCard` | Badge de ligne coloré, filtre de sens, pictogramme GPS ou « ~ » (estimé), retard, « À quai » / « Au départ de » / « précédent → prochain » |

Les éditeurs (`grandole-card-editor.js`) filtrent les entités sur le préfixe `sensor.grandole_` et l'attribut `grandole_mode` (`lieu`, `liste`, `proximity`, `suivi`).

Les styles reposent sur les variables CSS de Home Assistant (`--primary-text-color`, `--divider-color`, `--ha-card-background`…) avec `color-mix` pour les teintes secondaires ; un fond `#0f1729` est forcé en thème sombre comme dans Ginko. Vérifié dans un navigateur en clair et en sombre avec des données simulées issues du GTFS réel.

---

## 15. Cycle de vie

```
HA démarre
  └─ async_setup : store, services, chemin statique, ressources JS
Première entrée
  └─ async_setup_entry : GrandoleCoordinator créé, async_config_entry_first_refresh
        (charge le GTFS : cache disque ou téléchargement ; ConfigEntryNotReady si impossible)
     entrees = {entry_id}, plateformes sensor, update listener → reload
Entrées suivantes
  └─ réutilisent le coordinateur, entrees += entry_id
Toutes les 10 s
  └─ flux GTFS-RT → TempsReel → tous les capteurs recalculent
Toutes les 6 h
  └─ data.gouv last_modified → rechargement du GTFS si changé (sans interruption)
Déchargement
  └─ entrees -= entry_id ; propriétaire des capteurs globaux libéré ;
     coordinateur arrêté quand entrees est vide
```

---

## 16. Différences avec l'intégration Ginko

| Sujet | Ginko | Grandole |
|---|---|---|
| Authentification | Clé API, étape `user`, `reauth` | Aucune ; l'étape `user` est le choix du mode |
| Intervalle | Options auto/manuel (10 à 300 s) | Fixe 10 s, un seul coordinateur pour toutes les entrées |
| Coordinateurs | 4 classes | 1 classe + un store GTFS |
| `typeDeTemps` | 0, 1 ou 2 | Toujours 0, temps en minutes |
| `numVehicule` | Toujours présent en temps réel | Présent si position GPS ou `vehicle.label` |
| État des lignes | Codes 0 à 6 fournis par l'API | Codes 1 à 6 déduits de l'infotrafic et du temps réel (0 jamais produit) |
| Messages | Infotrafic éditorial (HTML) | Infotrafic du site officiel (HTML nettoyé) plus messages synthétisés à partir du temps réel |
| Tram | Détection `T1`, `T2` | Réseau 100 % bus, pictogramme unique |
| Mode liste, état | Secondes | Minutes |
| Dépendance | Aucune | `gtfs-realtime-bindings` (protobuf) |

---

## 17. Limitations connues

- **Deux formats de version du GTFS** : `last_modified` de data.gouv.fr (`2026-09-02T11:39:50.120000+00:00`) et `updated` de transport.data.gouv.fr (`2026-09-02T11:39:50.120000Z`) désignent le même fichier avec deux écritures. Un basculement d'une source à l'autre provoque donc un rechargement inutile mais inoffensif du GTFS, au plus une fois par bascule.

- **Infotrafic par analyse HTML** : la page `traffic-infos` n'est pas une API documentée. Un changement de gabarit du widget Instant System rendrait la liste vide (aucune erreur levée) ; le test `test_analyser_infotrafic` s'appuie sur une copie de la page du 18 septembre 2026 pour détecter une régression du parseur, pas du site.
- **Gravité par ligne** : le widget associe la gravité (`WARN`/`INFO`) au badge de ligne, pas à la perturbation ; une perturbation partagée par plusieurs lignes prend la gravité la plus haute rencontrée.

- **Mises à jour sans `start_date`** : la validation d'instance repose sur la fenêtre horaire (§6.2). Une course dont la mise à jour serait publiée plus de 3 h avant le départ serait considérée comme périmée jusqu'à ce que la fenêtre s'ouvre.
- **Retard négatif au terminus** : le flux peut annoncer une avance ; les passages en avance sont masqués dès que l'heure prévue est dépassée de plus de 30 s, comme les autres.
- **`wheelchair_accessible` vaut 0 pour toutes les courses** : `accessibiliteVehicule` est donc toujours 0 ; `accessibiliteArret` reste utile (78 quais accessibles).
- **Lignes 14 et 18** : leur `route_long_name` décrit deux itinéraires ; les destinations proposées dans le config flow sont celles réellement observées dans `stop_times`.
- **Projection GPS** : la position est projetée sur la ligne brisée des arrêts, pas sur `shapes.txt`. Sur une boucle passant deux fois près du même point, le segment retenu peut être le mauvais pendant quelques dizaines de secondes.
- **Changement de GTFS pendant la nuit** : au rechargement, les `trip_id` peuvent changer ; les mises à jour temps réel du cycle en cours sont alors ignorées jusqu'au cycle suivant (10 s).
- **Fuseau horaire** : les calculs utilisent le fuseau de l'agence (`Europe/Paris`), indépendamment du fuseau configuré dans Home Assistant.
