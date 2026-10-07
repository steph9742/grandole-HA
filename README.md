# Grandole Mobilités : intégration Home Assistant

> Intégration personnalisée pour suivre en temps réel les bus du réseau **Grandole Mobilités** (Grand Dole, Jura) depuis Home Assistant. 16 lignes, 412 arrêts, sans clé API : tout vient des données ouvertes publiées sur transport.data.gouv.fr.

---

## Sommaire

1. [Description](#description)
2. [Prérequis](#prérequis)
3. [Installation](#installation)
4. [Configuration des modes](#configuration-des-modes)
   - [Mode 1 : Arrêt par nom](#mode-1--arrêt-par-nom)
   - [Mode 2 : Arrêt par ligne et direction](#mode-2--arrêt-par-ligne-et-direction)
   - [Mode 3 : Arrêts proches d'une personne](#mode-3--arrêts-proches-dune-personne)
   - [Mode 4 : État d'une ligne](#mode-4--état-dune-ligne)
   - [Mode 5 : Positions des véhicules](#mode-5--positions-des-véhicules)
5. [Capteurs globaux](#capteurs-globaux)
6. [Cartes Lovelace](#cartes-lovelace)
7. [Services](#services)
8. [Référence des attributs des capteurs](#référence-des-attributs-des-capteurs)
9. [Options après installation](#options-après-installation)
10. [Dépannage](#dépannage)

---

## Description

Cette intégration connecte Home Assistant aux données ouvertes du réseau de bus **Grandole Mobilités** du Grand Dole. Elle vous permet de surveiller :

- Les **prochains passages** à n'importe quel arrêt, avec les retards en temps réel
- L'**infotrafic** publié par le réseau (travaux, déviations, perturbations à venir), le même que sur grandole-mobilites.fr
- L'**état des lignes** (en service, hors service, information, perturbation, courses annulées, retards importants)
- La **position GPS** des bus en circulation sur une ligne
- Les **arrêts les plus proches** d'une personne suivie par Home Assistant

Les horaires théoriques viennent du fichier GTFS du réseau (valable jusqu'en septembre 2027, rechargé automatiquement quand une nouvelle version est publiée). Les retards et les positions des bus viennent des flux GTFS-RT, lus toutes les 10 secondes. L'infotrafic est relu toutes les 5 minutes depuis le widget du site officiel. Aucune clé, aucune inscription.

> 🚆 **Dole Gare** est l'arrêt de correspondance avec les trains TER et TGV. Six lignes le desservent (1, 2, 3, 11, 17 et 18). C'est l'arrêt à configurer en premier si vous prenez le train : le capteur vous dira en combien de minutes part le prochain bus vers votre quartier, et les cartes signalent la correspondance par un pictogramme « Trains ».

---

## Prérequis

| Élément | Détail |
|---|---|
| **Home Assistant** | Version 2024.6.0 ou plus récente ; la dépendance `gtfs-realtime-bindings` 2.2.0 est installée automatiquement, compatible avec le protobuf fourni par Home Assistant |
| **Accès Internet** | Vers transport.data.gouv.fr, data.gouv.fr et sim.133.prod.instant-system.com (infotrafic du site officiel) |
| **Accès aux fichiers HA** | Via SSH, Samba, l'add-on File Editor ou HACS |

Aucune clé API n'est nécessaire.

---

## Installation

### Méthode 1 : HACS (recommandée)

1. Dans HACS, ouvrez le menu **⋮** (en haut à droite) puis **Dépôts personnalisés**
2. Ajoutez l'URL du dépôt : `https://github.com/steph9742/grandole-ha`
   avec la catégorie **Integration**
3. Recherchez **« Grandole Mobilités »** dans HACS et cliquez sur **Télécharger**
4. Redémarrez Home Assistant depuis **Paramètres → Système → Redémarrer**

> Les mises à jour apparaîtront ensuite automatiquement dans HACS à chaque nouvelle version.

### Méthode 2 : Manuelle

Copiez le dossier `custom_components/grandole/` dans le répertoire `config/custom_components/` de votre installation Home Assistant :

```
config/
└── custom_components/
    └── grandole/
        ├── __init__.py
        ├── manifest.json
        ├── config_flow.py
        ├── sensor.py
        └── ...
```

Puis redémarrez Home Assistant.

### Ajouter l'intégration

1. Allez dans **Paramètres → Appareils et services → Intégrations**
2. Cliquez sur **+ Ajouter une intégration**
3. Recherchez **« Grandole »** et sélectionnez-la
4. Choisissez le **mode** qui correspond à votre usage (voir ci-dessous)

Au premier ajout, l'intégration télécharge le fichier GTFS (400 Ko) : la première page du formulaire peut mettre quelques secondes à s'afficher.

---

## Configuration des modes

L'intégration propose cinq modes. Vous pouvez créer autant d'entrées que nécessaire (plusieurs arrêts, plusieurs lignes). Toutes les entrées partagent un seul lecteur des flux temps réel : ajouter des entrées n'augmente pas le trafic réseau.

---

### Mode 1 : Arrêt par nom

**Usage :** afficher tous les prochains passages à un arrêt, toutes lignes et directions confondues.

| Champ | Description |
|---|---|
| Nom de l'arrêt | Liste déroulante des 256 noms d'arrêts (un nom partiel est accepté : « gare » trouve Dole Gare) |
| Passages par ligne et direction | De 1 à 5 (défaut : 3) |

**Capteur créé :** `sensor.grandole_<nom_arret>`
- **État :** nombre de passages dans les 3 prochaines heures
- **Attributs :** `passages` (liste), `nom_arret`, `temps_reel`, `temps_reel_age`

---

### Mode 2 : Arrêt par ligne et direction

**Usage :** suivre le prochain bus d'une ligne et d'un sens précis, par exemple pour une automatisation « préviens-moi 5 minutes avant mon bus ».

Pour chaque combinaison, vous choisissez successivement :
1. L'**arrêt**
2. La **ligne** (seules les lignes desservant l'arrêt sont proposées)
3. La **direction** (terminus)
4. Optionnel : ajouter une autre combinaison dans la même entrée

**Capteurs créés :** un par combinaison, `sensor.grandole_<nom>_<ligne>_aller` ou `_retour`
- **État :** minutes avant le prochain bus (entier)
- **Attributs :** voir [la référence](#référence-des-attributs-des-capteurs)

---

### Mode 3 : Arrêts proches d'une personne

**Usage :** trouver automatiquement les arrêts les plus proches d'une personne géolocalisée par Home Assistant.

| Champ | Description |
|---|---|
| Entité personne | Sélecteur d'entité `person.*` avec position GPS |
| Passages par ligne et direction | De 1 à 5 |
| Nombre d'arrêts maximum | De 1 à 10 (défaut : 5), dans un rayon de 1 km |

**Capteur créé :** `sensor.grandole_proximite_<personne>`
- **État :** nombre d'arrêts trouvés
- **Attributs :** `arrets` (nom, distance en mètres, passages), `person_state`

---

### Mode 4 : État d'une ligne

**Usage :** surveiller la circulation d'une ligne. L'état combine l'**infotrafic** publié sur grandole-mobilites.fr (travaux, déviations, arrêts supprimés, perturbations à venir) et les anomalies constatées en **temps réel**.

| État | Signification |
|---|---|
| Normal | Des courses circulent, aucune anomalie, aucune info trafic |
| Information | Une info trafic de niveau information concerne la ligne (déviation, arrêt reporté) |
| Hors service | Aucune course en cours (avant le premier départ, après le dernier, dimanche, jours fériés) |
| Perturbation prévue | Une info trafic annonce une perturbation à une date à venir |
| Perturbation en cours | Info trafic de niveau alerte, course annulée, arrêt non desservi ou retard d'au moins 10 minutes |
| Circulation interrompue | Toutes les courses restantes de la journée sont annulées |

**Capteurs créés (2 par ligne) :**

| Capteur | État | Description |
|---|---|---|
| `sensor.grandole_ligne_<N>_etat` | Libellé d'état | Circulation de la ligne, avec retard max, courses en cours, bus localisés |
| `sensor.grandole_ligne_<N>_messages` | Nombre de messages | Infos trafic de la ligne et messages générés à partir des annulations, retards et arrêts non desservis |

---

### Mode 5 : Positions des véhicules

**Usage :** suivre la position de tous les bus en circulation sur une ligne.

| Champ | Description |
|---|---|
| Ligne | Liste déroulante des 16 lignes |

**Capteur créé :** `sensor.grandole_bus_ligne_<N>`
- **État :** nombre de bus suivis
- **Attributs :** `num_ligne`, `buses` (liste détaillée avec position GPS, prochain arrêt, retard)

> ℹ️ Les positions GPS de plus de 5 minutes sont ignorées (le flux conserve parfois des bus de la veille). Un bus sans position GPS mais dont la course a une mise à jour temps réel récente est positionné d'après ses horaires, avec la mention « ~ ».

---

## Capteurs globaux

Ces deux capteurs sont créés **automatiquement** avec la première entrée configurée :

| Capteur | État | Attributs |
|---|---|---|
| `sensor.grandole_etat_lignes` | Nombre de lignes perturbées | `lignes` (les 16 lignes avec état, couleurs, courses, bus localisés, retard max), `lignes_perturbees`, `lignes_en_service`, `vehicules_localises` |
| `sensor.grandole_messages` | Nombre de messages | `messages` : infos trafic du site officiel (titre, corps, lignes, période, causes, gravité), puis annulations, retards d'au moins 5 minutes et arrêts non desservis constatés en temps réel ; `infotrafic` et `temps_reel_anomalies` donnent le détail du compte |

---

## Cartes Lovelace

L'intégration inclut quatre cartes personnalisées, enregistrées automatiquement au démarrage de Home Assistant. Elles s'adaptent aux thèmes clair et sombre.

> 💡 Les ressources JS sont versionnées (`?v=<version>`) : après une mise à jour de l'intégration, un simple rechargement de la page suffit.

---

### Carte 1 : `grandole-card`

**Pour :** les modes Arrêt par nom, Arrêt par ligne et direction, Arrêts proches.

Affiche la liste des prochains passages avec :
- Badge coloré aux couleurs officielles de la ligne
- Temps en minutes et heure de passage prévue
- Wifi = mise à jour temps réel · ~ = horaire théorique
- Badge de retard (`+3 min`) ou d'avance
- Pictogramme « Trains » sur Dole Gare
- Point de position : vert = à quai, bleu = en circulation (avec un capteur de positions)
- Bandeau infotrafic (bleu pour une simple information, ambre pour une perturbation) et anomalies temps réel sur les lignes affichées

```yaml
type: custom:grandole-card
entity: sensor.grandole_dole_gare
messages_entity: sensor.grandole_messages
suivi_entities:
  - sensor.grandole_bus_ligne_1
  - sensor.grandole_bus_ligne_2
```

| Option | Obligatoire | Description |
|---|---|---|
| `entity` | ✅ Oui | Capteur d'un arrêt (mode lieu, liste ou proximité) |
| `mode` | Non | `lieu` (défaut), `liste` ou `proximity` |
| `messages_entity` | Non | `sensor.grandole_messages` pour le bandeau |
| `suivi_entities` | Non | Capteurs de positions pour afficher où sont les bus |
| `max_passages` | Non | Passages affichés par direction, 1 à 5 (défaut : 3) |
| `max_stops` | Non | Arrêts affichés en mode proximité, 1 à 10 (défaut : 5) |
| `lignes_filtre` | Non | Liste de numéros de lignes à afficher |
| `show_traffic` | Non | `if_disrupted` (défaut), `always` ou `never` |
| `show_hour` | Non | `false` pour masquer l'heure de passage |

---

### Carte 2 : `grandole-etat-card`

**Pour :** l'état du réseau.

Affiche :
- Bannière verte « Tout est normal » avec le nombre de lignes en service et de bus localisés
- Filtres : Perturbées / Toutes / En service / Infos / Prévues / par ligne
- Infos trafic du site officiel (causes, période d'application, date de mise à jour, corps dépliable) et messages temps réel (annulations, retards, arrêts non desservis)
- Pour chaque ligne : infos trafic, courses en cours, bus localisés, retard max, prochain départ

```yaml
type: custom:grandole-etat-card
entity: sensor.grandole_etat_lignes
messages_entity: sensor.grandole_messages
```

| Option | Obligatoire | Description |
|---|---|---|
| `entity` | ✅ Oui | `sensor.grandole_etat_lignes` |
| `messages_entity` | Non | `sensor.grandole_messages` |
| `hide_inactive` | Non | `true` pour masquer les lignes hors service dans la vue « Toutes » |

---

### Carte 3 : `grandole-suivi-card`

**Pour :** les positions des bus (mode 5).

Affiche :
- Filtres de direction : Tous / → Aller / ← Retour
- Pour chaque bus : numéro, terminus, position (arrêt précédent → prochain arrêt, « À quai » ou « Au départ de »), retard, minutes avant le prochain arrêt
- Pictogramme GPS vert (position réelle) ou « ~ » (position estimée d'après les horaires)

```yaml
type: custom:grandole-suivi-card
entity: sensor.grandole_bus_ligne_1
```

---

### Carte 4 : `grandole-recherche-card`

**Pour :** consulter les horaires de **n'importe quel arrêt** du réseau, suivi ou non, comme dans une application de transports.

Affiche :
- Un champ de recherche avec autocomplétion (accents et casse ignorés, navigation clavier ↑ ↓ Entrée), avec les lignes desservant chaque arrêt proposé
- Les prochains passages de l'arrêt choisi, avec le même rendu que `grandole-card`
- Rafraîchissement automatique tant qu'un arrêt est affiché ; le dernier arrêt consulté est mémorisé dans le navigateur

Cette carte **ne crée aucun capteur** : elle appelle les [services de l'intégration](#services).

```yaml
type: custom:grandole-recherche-card
messages_entity: sensor.grandole_messages
nb_passages: 3
refresh: 30
```

| Option | Obligatoire | Description |
|---|---|---|
| `arret` | Non | Arrêt prédéfini (la recherche reste possible) |
| `nb_passages` | Non | Passages par ligne et direction, 1 à 5 (défaut : 3) |
| `refresh` | Non | Intervalle de rafraîchissement en secondes, 10 à 300 (défaut : 30) |
| `show_traffic` | Non | `if_disrupted` (défaut), `always` ou `never` |
| `messages_entity` | Non | `sensor.grandole_messages` pour le bandeau |
| `remember` | Non | `false` pour ne pas mémoriser le dernier arrêt (défaut : `true`) |

---

## Services

L'intégration expose deux services **avec réponse**, utilisables depuis les automatisations, les scripts, les templates, la carte de recherche ou une autre intégration. Les calculs sont locaux : aucun appel réseau supplémentaire.

### `grandole.chercher_arret`

Recherche des arrêts par nom (accents et casse ignorés ; les noms commençant par la recherche sont classés en premier, puis les mots commençant par la recherche).

| Champ | Obligatoire | Description |
|---|---|---|
| `recherche` | ✅ Oui | Texte à chercher (ex. `gare`) |
| `limite` | Non | Nombre maximum de résultats, 1 à 50 (défaut : 10) |

Réponse : `{ arrets: [ { nom, latitude, longitude, accessible, quais, lignes } ] }`

### `grandole.get_horaires`

Prochains passages d'un arrêt, qu'il soit suivi par un capteur ou non.

| Champ | Obligatoire | Description |
|---|---|---|
| `nom` | ✅ Oui | Nom de l'arrêt (correspondance approximative acceptée) |
| `nb` | Non | Passages par ligne et direction, 1 à 5 (défaut : 3) |

Réponse : `{ nom, nb_passages, passages: [ … ], temps_reel }`. Chaque passage a la même structure que l'attribut `passages` des capteurs.

**Exemple dans un script :**

```yaml
sequence:
  - action: grandole.get_horaires
    data:
      nom: "Dole Gare"
      nb: 2
    response_variable: horaires
  - action: notify.mobile_app
    data:
      message: >
        Prochain {{ horaires.passages[0].numLignePublic }} vers
        {{ horaires.passages[0].destination }} dans {{ horaires.passages[0].temps }}
```

**Exemple depuis une autre intégration (Python) :**

```python
resp = await hass.services.async_call(
    "grandole", "get_horaires",
    {"nom": "Dole Gare", "nb": 3},
    blocking=True, return_response=True,
)
passages = resp["passages"]
```

---

## Référence des attributs des capteurs

### Objet passage (attribut `passages`)

Structure identique à celle de l'intégration Ginko (Besançon) : les cartes et automatisations écrites pour Ginko fonctionnent sans modification.

| Attribut | Type | Description |
|---|---|---|
| `idLigne` | string | Identifiant de la ligne (`1`, `2`, `LZ`…) |
| `numLignePublic` | string | Numéro affiché de la ligne |
| `nomLigne` | string | Nom long de la ligne |
| `couleurFond` / `couleurTexte` | string | Couleurs officielles (hex `#RRGGBB`) |
| `destination` | string | Terminus de la course |
| `temps` | string | Temps lisible en minutes (`3 min`, `< 1 min`) |
| `tempsEnSeconde` | int | Secondes avant le passage |
| `typeDeTemps` | int | Toujours `0` (temps relatif) |
| `fiable` | bool | `true` si une mise à jour temps réel valide existe pour cette course |
| `retard` | int ou null | Retard en secondes (négatif = avance), `null` sans temps réel |
| `heure` | string | Heure de passage prévue (`HH:MM`) |
| `heureTheorique` | string | Heure théorique du GTFS |
| `numVehicule` | string ou null | Numéro du bus si connu |
| `modeTransport` | int | Toujours `0` (bus) |
| `accessibiliteVehicule` | int | `1` si le véhicule est déclaré accessible |
| `accessibiliteArret` | int | `1` si le quai est accessible PMR |
| `idArret` / `nomExact` | string | Quai physique et nom de l'arrêt |
| `latitude` / `longitude` | float | Position du quai |
| `sensAller` | bool | `true` pour la direction 0 du GTFS |
| `idCourse` | string | Identifiant de la course GTFS |

### Mode Liste (`sensor.grandole_<nom>_<ligne>_aller/retour`)

En plus de `passages`, les attributs du premier passage sont remontés à plat : `temps`, `tempsEnSeconde`, `heure`, `retard`, `destination`, `fiable`, `numLignePublic`, `couleurFond`, `couleurTexte`, `typeDeTemps`, `modeTransport`, `numVehicule`, ainsi que `deviation` (toujours `false`).

### Mode Personne (`sensor.grandole_proximite_<personne>`)

| Attribut | Type | Description |
|---|---|---|
| `person_state` | string | État de l'entité personne |
| `arrets` | liste | `{nom, distance, passages}` triés par distance |

### Mode Ligne (`sensor.grandole_ligne_<N>_etat`)

| Attribut | Type | Description |
|---|---|---|
| `etat` | int | `1` normal, `2` information, `3` hors service, `4` perturbation prévue, `5` perturbation en cours, `6` interrompue |
| `etat_label`, `etat_description`, `couleur_etat` | string | Libellés et couleur conseillée |
| `perturbation_active` | bool | Vrai pour les états 5 et 6 |
| `courses_jour`, `courses_en_cours`, `courses_a_venir`, `courses_annulees` | int | Compteurs de la journée |
| `arrets_non_desservis` | int | Arrêts sautés signalés en temps réel |
| `vehicules_localises` | int | Bus avec position GPS récente |
| `retard_max` | int ou null | Retard maximal en secondes sur les courses en cours |
| `prochain_depart` | string ou null | Heure du prochain départ |
| `infotrafic_en_cours`, `infotrafic_a_venir` | int | Nombre d'infos trafic concernant la ligne |

### Objet message (attribut `messages`)

| Attribut | Type | Description |
|---|---|---|
| `id` | string | Identifiant stable (`infotrafic-…`, `annulation-…`, `retard-…`, `saut-…`) |
| `type` | string | `infotrafic`, `annulation`, `retard` ou `arret_non_desservi` |
| `titre`, `corps` | string | Titre et corps (HTML simple pour l'infotrafic, texte sinon) |
| `lignes` | liste | Numéros des lignes concernées |
| `etat` | string | `en_cours` ou `a_venir` (infotrafic) |
| `gravite` | string | `WARN` (perturbation) ou `INFO` (information), infotrafic uniquement |
| `causes`, `effet`, `sens` | liste, string, string | Causes affichées par le réseau (`Travaux`…), effet (`modified_service`…), sens concernés |
| `debut`, `fin` | string ou null | Période d'application (ISO 8601) |
| `mise_a_jour` | string | Date de mise à jour affichée par le réseau |

### Mode Suivi (`sensor.grandole_bus_ligne_<N>`)

Chaque objet de la liste `buses` :

| Champ | Type | Description |
|---|---|---|
| `id` | string | Numéro du bus (ou `course-<id>` si inconnu) |
| `sens` | string | `aller` ou `retour` |
| `terminus` | string | Destination |
| `prochain_arret`, `arret_precedent` | string | Position sur la ligne |
| `statut` | string | `a_quai`, `depart` ou `en_route` |
| `dans_sec` | int | Secondes avant le prochain arrêt |
| `latitude`, `longitude`, `cap` | float ou null | Position GPS et cap |
| `gps` | bool | `true` si position GPS réelle, `false` si estimée d'après les horaires |
| `age` | int | Âge de la donnée en secondes |
| `retard` | int ou null | Retard en secondes |

---

## Options après installation

1. Allez dans **Paramètres → Appareils et services → Intégrations**
2. Trouvez votre entrée Grandole et cliquez sur **Configurer**

| Option | Modes concernés |
|---|---|
| Passages par ligne et direction | Arrêt par nom, Arrêt par ligne, Personne |
| Nombre d'arrêts maximum | Personne |
| Ajouter une combinaison arrêt / ligne / direction | Arrêt par ligne |

---

## Dépannage

### « Impossible de charger les horaires GTFS »

L'intégration télécharge le fichier GTFS depuis `transport.data.gouv.fr` au premier lancement, puis le conserve dans `.storage/grandole_gtfs.zip`. Ce téléchargement est redirigé vers data.gouv.fr ; si data.gouv.fr est en panne (constaté le 7 octobre 2026), l'intégration se replie sur l'URL d'origine du fichier fournie par l'API de transport.data.gouv.fr. Vérifiez l'accès Internet de Home Assistant et réessayez. Une fois le fichier en cache, l'intégration démarre même sans réseau.

### Tous les passages sont marqués « ~ » (théoriques)

Le flux GTFS-RT est injoignable ou ne contient pas encore la course. C'est normal :
- La nuit et le dimanche (aucun bus en circulation)
- Quelques minutes avant le départ d'une course, tant que le bus n'a pas émis sa première mise à jour
- Pour les lignes scolaires ou peu fréquentes

Il arrive aussi que le flux soit **figé côté réseau** : le 18 septembre 2026 à 19h18, les deux flux étaient régénérés toutes les 10 s mais leur contenu datait de 07h26 (29 bus, 42 courses), alors que 6 courses circulaient encore. L'intégration ignore ces données périmées et affiche les horaires théoriques.

L'attribut `temps_reel` des capteurs vaut `true` seulement si le flux a été lu **et** contient une donnée de moins de 15 minutes ; `temps_reel_age` donne l'âge en secondes de la donnée la plus récente.

### Aucun bus n'apparaît en mode « Positions des véhicules »

- Les positions de plus de 5 minutes sont ignorées
- En heures creuses, peu de bus circulent
- Vérifiez d'abord le capteur `sensor.grandole_etat_lignes` : `vehicules_localises` donne le nombre de bus visibles sur tout le réseau

### La carte Lovelace n'est pas trouvée

**Symptôme :** « Custom element doesn't exist: grandole-card ».

1. Les fichiers JS sont enregistrés automatiquement au démarrage : **redémarrez Home Assistant**
2. Rechargez la page du navigateur
3. Vérifiez dans **Paramètres → Tableaux de bord → Ressources** que `/grandole_card/grandole-card.js?v=<version>` est présent

### L'infotrafic n'apparaît pas

L'intégration lit toutes les 5 minutes la page `sim.133.prod.instant-system.com/fr/traffic-infos`, celle que le site officiel affiche dans son bloc « Info trafic ». Si cette page est injoignable, les capteurs conservent la dernière liste connue et `infotrafic_horodatage` du capteur `sensor.grandole_messages` indique la dernière lecture réussie. Le flux RSS du site (`/rss.xml`) et son bandeau d'alerte ne sont pas utilisés : ils ne sont remplis qu'à la reconstruction du site et étaient vides alors que trois lignes étaient perturbées.

### Les horaires ne changent pas après une modification d'offre

L'intégration vérifie toutes les 6 heures sur data.gouv.fr si une nouvelle version du GTFS a été publiée et la recharge automatiquement. Pour forcer la vérification, rechargez l'intégration ou redémarrez Home Assistant. L'attribut `gtfs_version` des capteurs indique la date du fichier en cours.

---

## Publication HACS

Le dépôt est prêt pour une installation en dépôt personnalisé HACS et contient ce qu'exige une future inclusion dans le catalogue par défaut :

- `hacs.json` à la racine, `manifest.json` avec `domain`, `name`, `version`, `documentation`, `issue_tracker`, `codeowners`
- Workflow `Validation` (hassfest et action HACS) à chaque push, chaque pull request et chaque lundi ; workflow `Tests` (pytest, syntaxe des cartes et des JSON)
- README et TECHNICAL en français, icônes de marque dans `custom_components/grandole/brand/`

Restent à faire côté GitHub avant de soumettre au catalogue : une description et des sujets (`home-assistant`, `hacs`, `custom-integration`, `gtfs`, `gtfs-realtime`, `dole`), une première release portant le même numéro que `manifest.json`, et une contribution de l'icône au dépôt `home-assistant/brands` (le workflow ignore cette vérification tant que ce n'est pas fait).

## Tests

Le dossier `tests/` contient une suite pytest fondée sur `pytest-homeassistant-custom-component`, avec des captures réelles dans `tests/fixtures/` : le GTFS du 2 septembre 2026, les deux flux GTFS-RT du 7 octobre 2026 à 14h54 (8 bus localisés) et la page infotrafic du site officiel. Elle couvre le config flow des cinq modes, les options, les capteurs, les services, le cache et le rechargement du GTFS, le repli de téléchargement, les flux injoignables et les flux figés.

```bash
python3 -m venv .venv && .venv/bin/pip install homeassistant pytest-homeassistant-custom-component home-assistant-frontend gtfs-realtime-bindings
.venv/bin/python -m pytest tests -q
```

## Licence

Ce projet est une intégration communautaire non officielle, sans lien avec Grandole Mobilités ni la Communauté d'agglomération du Grand Dole. Les données proviennent du jeu ouvert « Réseau de transport du Grand Dole » publié sous licence ouverte sur data.gouv.fr. Utilisez cette intégration à vos propres risques.

---

*Fait avec ❤️ pour la communauté Home Assistant du Grand Dole.*
