from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ID_LIGNE,
    CONF_ITEMS,
    CONF_MAX_STOPS,
    CONF_NB_PASSAGES,
    CONF_NOM,
    CONF_NUM_LIGNE,
    CONF_PERSON_ENTITY,
    CONF_SENS_ALLER,
    DEFAULT_MAX_STOPS,
    DEFAULT_NB_PASSAGES,
    DOMAIN,
    MODE_LIEU,
    MODE_LIGNE,
    MODE_LISTE,
    MODE_PERSON,
    MODE_SUIVI_LIGNE,
    etat_meta,
)
from .coordinator import GrandoleCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GrandoleCoordinator = hass.data[DOMAIN][entry.entry_id]
    entry_data = entry.data["entry"]
    mode = entry_data["mode"]
    entities: list[SensorEntity] = []

    if mode == MODE_LIEU:
        entities.append(GrandoleLieuSensor(coordinator, entry))
    elif mode == MODE_LISTE:
        for item in entry_data[CONF_ITEMS]:
            entities.append(GrandoleListeSensor(coordinator, entry, item))
    elif mode == MODE_PERSON:
        entities.append(GrandolePersonProximitySensor(coordinator, entry))
    elif mode == MODE_LIGNE:
        entities.append(GrandoleLigneEtatSensor(coordinator, entry))
        entities.append(GrandoleLigneMessagesSensor(coordinator, entry))
    elif mode == MODE_SUIVI_LIGNE:
        entities.append(GrandoleSuiviLigneSensor(coordinator, entry))

    owner_key = "_info_sensors_owner"
    owner = hass.data[DOMAIN].get(owner_key)
    if owner is None or owner == entry.entry_id:
        hass.data[DOMAIN][owner_key] = entry.entry_id
        entities.append(GrandoleEtatLignesSensor(coordinator))
        entities.append(GrandoleMessagesSensor(coordinator))

    async_add_entities(entities, True)


def _nb(entry: ConfigEntry, key: str, default: int) -> int:
    return int(entry.options.get(key, entry.data["entry"].get(key, default)))


class GrandoleEntity(CoordinatorEntity[GrandoleCoordinator], SensorEntity):
    _unrecorded_attributes = frozenset({MATCH_ALL})
    _attr_has_entity_name = False

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.coordinator.reseau is not None

    def _base_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        maintenant = self.coordinator.maintenant().timestamp()
        return {
            "temps_reel": bool(data and data.frais(maintenant)),
            "temps_reel_age": data.age(maintenant) if data else None,
            "gtfs_version": self.coordinator.store.version,
        }


class GrandoleLieuSensor(GrandoleEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "passages"
    _attr_icon = "mdi:bus-stop"

    def __init__(self, coordinator: GrandoleCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._nom: str = entry.data["entry"][CONF_NOM]
        self._attr_unique_id = f"grandole_{entry.entry_id}_lieu_{self._nom}"
        self._attr_name = f"Grandole {self._nom}"

    def _nom_exact(self) -> str | None:
        reseau = self.coordinator.reseau
        return reseau.resoudre_nom(self._nom) if reseau else None

    def _passages(self) -> list[dict]:
        reseau = self.coordinator.reseau
        nom = self._nom_exact()
        if reseau is None or nom is None:
            return []
        return reseau.passages(
            reseau.ids_arrets(nom), self.coordinator.maintenant(), self.coordinator.data,
            _nb(self._entry, CONF_NB_PASSAGES, DEFAULT_NB_PASSAGES),
        )

    @property
    def native_value(self) -> int:
        return len(self._passages())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "grandole_mode": "lieu",
            "passages": self._passages(),
            "nom_arret": self._nom_exact() or self._nom,
            **self._base_attributes(),
        }


class GrandoleListeSensor(GrandoleEntity):
    _attr_native_unit_of_measurement = "min"
    _attr_icon = "mdi:bus-clock"

    def __init__(self, coordinator: GrandoleCoordinator, entry: ConfigEntry, item: dict) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._nom: str = item[CONF_NOM]
        self._id_ligne: str = str(item[CONF_ID_LIGNE])
        self._sens_aller: bool = bool(item[CONF_SENS_ALLER])
        sens_label = "aller" if self._sens_aller else "retour"
        self._attr_unique_id = f"grandole_{entry.entry_id}_{self._nom}_{self._id_ligne}_{sens_label}"
        self._attr_name = f"Grandole {self._nom} {self._id_ligne} {sens_label}"

    def _passages(self) -> list[dict]:
        reseau = self.coordinator.reseau
        if reseau is None:
            return []
        nom = reseau.resoudre_nom(self._nom)
        if nom is None:
            return []
        return reseau.passages(
            reseau.ids_arrets(nom), self.coordinator.maintenant(), self.coordinator.data,
            _nb(self._entry, CONF_NB_PASSAGES, DEFAULT_NB_PASSAGES),
            id_ligne=self._id_ligne, sens_aller=self._sens_aller,
        )

    @property
    def native_value(self) -> int | None:
        passages = self._passages()
        if not passages:
            return None
        return passages[0]["tempsEnSeconde"] // 60

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        passages = self._passages()
        attributs: dict[str, Any] = {
            "grandole_mode": "liste",
            "passages": passages,
            "nom_arret": self._nom,
            "id_ligne": self._id_ligne,
            "sens_aller": self._sens_aller,
            **self._base_attributes(),
        }
        if not passages:
            return attributs
        premier = passages[0]
        attributs.update({
            "temps": premier.get("temps"),
            "tempsEnSeconde": premier.get("tempsEnSeconde"),
            "heure": premier.get("heure"),
            "retard": premier.get("retard"),
            "destination": premier.get("destination"),
            "fiable": premier.get("fiable"),
            "numLignePublic": premier.get("numLignePublic"),
            "couleurFond": premier.get("couleurFond"),
            "couleurTexte": premier.get("couleurTexte"),
            "typeDeTemps": premier.get("typeDeTemps"),
            "deviation": False,
            "modeTransport": premier.get("modeTransport"),
            "numVehicule": premier.get("numVehicule"),
        })
        return attributs


class GrandolePersonProximitySensor(GrandoleEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "arrêts"
    _attr_icon = "mdi:map-marker-radius"

    def __init__(self, coordinator: GrandoleCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._person_id: str = entry.data["entry"][CONF_PERSON_ENTITY]
        self._attr_unique_id = f"grandole_{entry.entry_id}_person_proximity"
        self._attr_name = f"Grandole proximité {self._person_id.split('.')[-1]}"

    def _calcul(self) -> dict[str, Any]:
        person = self.hass.states.get(self._person_id)
        if person is None:
            return {"arrets": [], "person_state": None}
        lat = person.attributes.get("latitude")
        lon = person.attributes.get("longitude")
        reseau = self.coordinator.reseau
        if lat is None or lon is None or reseau is None:
            return {"arrets": [], "person_state": person.state}
        maintenant = self.coordinator.maintenant()
        nb = _nb(self._entry, CONF_NB_PASSAGES, DEFAULT_NB_PASSAGES)
        max_stops = _nb(self._entry, CONF_MAX_STOPS, DEFAULT_MAX_STOPS)
        arrets = []
        for proche in reseau.arrets_proches(float(lat), float(lon), max_stops):
            arrets.append({
                "nom": proche["nom"],
                "distance": proche["distance"],
                "passages": reseau.passages(proche["ids"], maintenant, self.coordinator.data, nb),
            })
        return {"arrets": arrets, "person_state": person.state}

    @property
    def native_value(self) -> int:
        return len(self._calcul()["arrets"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._calcul()
        return {
            "grandole_mode": "proximity",
            "arrets": data["arrets"],
            "person_state": data["person_state"],
            **self._base_attributes(),
        }


def _ligne_detail(lg: dict) -> dict[str, Any]:
    meta = etat_meta(lg.get("etat"))
    return {
        "id": lg.get("idLigne"),
        "num": lg.get("numLignePublic"),
        "nom": lg.get("nomLigne"),
        "etat": lg.get("etat"),
        "etat_label": meta["label"],
        "perturbation_active": meta["perturbation_active"],
        "perturbation_prevue": meta["perturbation_prevue"],
        "couleur_fond": lg.get("couleurFond"),
        "couleur_texte": lg.get("couleurTexte"),
        "courses_jour": lg.get("courses_jour"),
        "courses_en_cours": lg.get("courses_en_cours"),
        "courses_a_venir": lg.get("courses_a_venir"),
        "courses_annulees": lg.get("courses_annulees"),
        "arrets_non_desservis": lg.get("arrets_non_desservis"),
        "vehicules_localises": lg.get("vehicules_localises"),
        "retard_max": lg.get("retard_max"),
        "prochain_depart": lg.get("prochain_depart"),
        "infotrafic_en_cours": lg.get("infotrafic_en_cours"),
        "infotrafic_a_venir": lg.get("infotrafic_a_venir"),
    }


class GrandoleLigneEtatSensor(GrandoleEntity):
    _attr_icon = "mdi:bus-alert"

    def __init__(self, coordinator: GrandoleCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        ed = entry.data["entry"]
        self._id_ligne = str(ed[CONF_ID_LIGNE])
        self._num_ligne = ed[CONF_NUM_LIGNE]
        self._attr_unique_id = f"grandole_ligne_{self._id_ligne}_etat"
        self._attr_name = f"Grandole Ligne {self._num_ligne} État"

    def _ligne(self) -> dict | None:
        etats, _ = self.coordinator.etats_et_messages()
        for lg in etats:
            if str(lg.get("idLigne")) == self._id_ligne:
                return lg
        return None

    @property
    def native_value(self) -> str | None:
        lg = self._ligne()
        return etat_meta(lg.get("etat")).get("label") if lg else None

    @property
    def icon(self) -> str:
        lg = self._ligne()
        return etat_meta(lg.get("etat") if lg else None).get("icon", self._attr_icon)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        lg = self._ligne()
        if not lg:
            return self._base_attributes()
        meta = etat_meta(lg.get("etat"))
        return {
            **_ligne_detail(lg),
            "etat_description": meta["description"],
            "couleur_etat": meta["couleur"],
            **self._base_attributes(),
        }


class GrandoleLigneMessagesSensor(GrandoleEntity):
    _attr_icon = "mdi:message-alert"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "messages"

    def __init__(self, coordinator: GrandoleCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        ed = entry.data["entry"]
        self._id_ligne = str(ed[CONF_ID_LIGNE])
        self._num_ligne = str(ed[CONF_NUM_LIGNE])
        self._attr_unique_id = f"grandole_ligne_{self._id_ligne}_messages"
        self._attr_name = f"Grandole Ligne {self._num_ligne} Messages"

    def _messages(self) -> list[dict]:
        _, messages = self.coordinator.etats_et_messages()
        return [m for m in messages if self._num_ligne in [str(l) for l in m.get("lignes", [])]]

    @property
    def native_value(self) -> int:
        return len(self._messages())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        messages = self._messages()
        return {
            "messages": messages,
            "num_ligne": self._num_ligne,
            "infotrafic": sum(1 for m in messages if m.get("type") == "infotrafic"),
            **self._base_attributes(),
        }


class GrandoleEtatLignesSensor(GrandoleEntity):
    _attr_unique_id = "grandole_etat_lignes"
    _attr_name = "Grandole État Lignes"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "lignes perturbées"
    _attr_icon = "mdi:bus-alert"

    @property
    def native_value(self) -> int:
        etats, _ = self.coordinator.etats_et_messages()
        return sum(1 for lg in etats if etat_meta(lg.get("etat"))["perturbation_active"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        etats, _ = self.coordinator.etats_et_messages()
        detaillees = [_ligne_detail(lg) for lg in etats]
        return {
            "perturbations_en_cours": sum(1 for l in detaillees if l["perturbation_active"]),
            "perturbations_prevues": sum(1 for l in detaillees if l["perturbation_prevue"]),
            "lignes_perturbees": [l for l in detaillees if l["perturbation_active"] or l["perturbation_prevue"]],
            "lignes_en_service": sum(1 for l in detaillees if l["etat"] != 3),
            "vehicules_localises": sum(l["vehicules_localises"] or 0 for l in detaillees),
            "lignes": detaillees,
            **self._base_attributes(),
        }


class GrandoleMessagesSensor(GrandoleEntity):
    _attr_unique_id = "grandole_messages"
    _attr_name = "Grandole Messages"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "messages"
    _attr_icon = "mdi:message-alert"

    @property
    def native_value(self) -> int:
        _, messages = self.coordinator.etats_et_messages()
        return len(messages)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        _, messages = self.coordinator.etats_et_messages()
        return {
            "messages": messages,
            "infotrafic": sum(1 for m in messages if m.get("type") == "infotrafic"),
            "temps_reel_anomalies": sum(1 for m in messages if m.get("type") != "infotrafic"),
            "infotrafic_horodatage": self.coordinator.infotrafic_horodatage,
            **self._base_attributes(),
        }


class GrandoleSuiviLigneSensor(GrandoleEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "bus"
    _attr_icon = "mdi:bus-marker"

    def __init__(self, coordinator: GrandoleCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        ed = entry.data["entry"]
        self._id_ligne = str(ed[CONF_ID_LIGNE])
        self._num_ligne = str(ed[CONF_NUM_LIGNE])
        self._attr_unique_id = f"grandole_suivi_ligne_{entry.entry_id}"
        self._attr_name = f"Grandole Bus Ligne {self._num_ligne}"

    def _buses(self) -> list[dict]:
        reseau = self.coordinator.reseau
        if reseau is None:
            return []
        return reseau.positions_ligne(self._id_ligne, self.coordinator.maintenant(), self.coordinator.data)

    @property
    def native_value(self) -> int:
        return len(self._buses())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        reseau = self.coordinator.reseau
        ligne = reseau.lignes.get(self._id_ligne) if reseau else None
        return {
            "grandole_mode": "suivi",
            "num_ligne": self._num_ligne,
            "nom_ligne": ligne.nom if ligne else None,
            "couleurFond": ligne.couleur_fond if ligne else None,
            "couleurTexte": ligne.couleur_texte if ligne else None,
            "buses": self._buses(),
            **self._base_attributes(),
        }
