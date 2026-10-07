from __future__ import annotations

DOMAIN = "grandole"

GTFS_URL = "https://transport.data.gouv.fr/resources/81254/download"
DATAGOUV_DATASET_URL = "https://www.data.gouv.fr/api/1/datasets/reseau-de-transport-du-grand-dole/"
TRANSPORT_DATASET_URL = "https://transport.data.gouv.fr/api/datasets/5e2087978b4c41738e555328"
TRIP_UPDATES_URL = "https://proxy.transport.data.gouv.fr/resource/tgd-dole-gtfs-rt-trip-update"
VEHICLE_POSITIONS_URL = "https://proxy.transport.data.gouv.fr/resource/tgd-dole-gtfs-rt-vehicle-position"

INFOTRAFIC_URL = "https://sim.133.prod.instant-system.com/fr/traffic-infos"
INFOTRAFIC_SITE = "https://www.grandole-mobilites.fr/"
INFOTRAFIC_INTERVAL = 300

SCAN_INTERVAL_TEMPS_REEL = 10
GTFS_CHECK_INTERVAL = 6 * 3600
GTFS_CACHE_FILE = "grandole_gtfs.zip"
GTFS_META_STORE = "grandole_gtfs_meta"

AGE_MAX_POSITION = 300
AGE_MAX_FLUX = 900
AGE_MAX_MISE_A_JOUR = 300
TOLERANCE_HEURE_PREVUE = 3 * 3600
MARGE_AVANT_COURSE = 3 * 3600
MARGE_APRES_COURSE = 2 * 3600
GRACE_PASSAGE = 30
HORIZON_PASSAGES = 3 * 3600
RAYON_PROXIMITE = 1000
RAYON_A_QUAI = 40
RETARD_MESSAGE = 300
RETARD_PERTURBATION = 600

CONF_MODE = "mode"
CONF_NOM = "nom"
CONF_NB_PASSAGES = "nb_passages"
CONF_ITEMS = "items"
CONF_ID_LIGNE = "id_ligne"
CONF_NUM_LIGNE = "num_ligne"
CONF_NOM_LIGNE = "nom_ligne"
CONF_SENS_ALLER = "sens_aller"
CONF_PERSON_ENTITY = "person_entity_id"
CONF_MAX_STOPS = "max_stops"

DEFAULT_NB_PASSAGES = 3
DEFAULT_MAX_STOPS = 5

MODE_LIEU = "lieu"
MODE_LISTE = "liste"
MODE_PERSON = "person_proximity"
MODE_LIGNE = "ligne"
MODE_SUIVI_LIGNE = "suivi_ligne"

ETAT_META = {
    0: {
        "label": "Pas d'information",
        "description": "Aucune information sur l'état de la ligne.",
        "couleur": None,
        "icon": "mdi:bus",
        "perturbation_active": False,
        "perturbation_prevue": False,
    },
    1: {
        "label": "Normal",
        "description": "La ligne circule normalement.",
        "couleur": "#2E7D32",
        "icon": "mdi:check-circle",
        "perturbation_active": False,
        "perturbation_prevue": False,
    },
    2: {
        "label": "Information",
        "description": "Une information trafic concerne la ligne (travaux, déviation sans gravité).",
        "couleur": "#1976D2",
        "icon": "mdi:information",
        "perturbation_active": False,
        "perturbation_prevue": False,
    },
    3: {
        "label": "Hors service",
        "description": "La ligne ne circule pas en ce moment, selon sa période de fonctionnement.",
        "couleur": "#9E9E9E",
        "icon": "mdi:close-circle",
        "perturbation_active": False,
        "perturbation_prevue": False,
    },
    4: {
        "label": "Perturbation prévue",
        "description": "Une perturbation est annoncée pour une date à venir.",
        "couleur": "#9E9E9E",
        "icon": "mdi:alert",
        "perturbation_active": False,
        "perturbation_prevue": True,
    },
    5: {
        "label": "Perturbation en cours",
        "description": "Perturbation annoncée par le réseau, course annulée, arrêt non desservi ou retard important.",
        "couleur": "#F57C00",
        "icon": "mdi:alert",
        "perturbation_active": True,
        "perturbation_prevue": False,
    },
    6: {
        "label": "Circulation interrompue",
        "description": "Toutes les courses restantes de la journée sont annulées.",
        "couleur": "#D32F2F",
        "icon": "mdi:close-octagon",
        "perturbation_active": True,
        "perturbation_prevue": False,
    },
}


def etat_meta(etat: int | None) -> dict:
    if etat in ETAT_META:
        return ETAT_META[etat]
    return {
        "label": "Inconnu",
        "description": "État non reconnu.",
        "couleur": None,
        "icon": "mdi:help-circle",
        "perturbation_active": False,
        "perturbation_prevue": False,
    }
