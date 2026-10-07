import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from google.transit import gtfs_realtime_pb2
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.grandole.const import (
    DATAGOUV_DATASET_URL,
    DOMAIN,
    GTFS_URL,
    INFOTRAFIC_URL,
    TRANSPORT_DATASET_URL,
    TRIP_UPDATES_URL,
    VEHICLE_POSITIONS_URL,
)
from custom_components.grandole.infotrafic import analyser_infotrafic

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
TZ = ZoneInfo("Europe/Paris")
NOW = datetime(2026, 10, 7, 14, 55, 0, tzinfo=TZ)
ORIGINAL_URL = "https://static.data.gouv.fr/resources/reseau-de-transport-du-grand-dole/20260902-113949/gtfs-dole.zip"


def _lire(nom: str, mode: str = "rb"):
    with open(os.path.join(FIXTURES, nom), mode, **({} if mode == "rb" else {"encoding": "utf-8"})) as f:
        return f.read()


def _flux(decalage: int = 0) -> tuple[bytes, bytes]:
    tu = gtfs_realtime_pb2.FeedMessage()
    tu.ParseFromString(_lire("trip_updates.pb"))
    vp = gtfs_realtime_pb2.FeedMessage()
    vp.ParseFromString(_lire("vehicle_positions.pb"))
    if decalage:
        for e in tu.entity:
            e.trip_update.timestamp -= decalage
            for s in e.trip_update.stop_time_update:
                if s.HasField("arrival") and s.arrival.HasField("time"):
                    s.arrival.time -= decalage
        for e in vp.entity:
            e.vehicle.timestamp -= decalage
    return tu.SerializeToString(), vp.SerializeToString()


def _datagouv() -> str:
    return json.dumps({
        "last_modified": "2026-09-02T11:39:50.120000+00:00",
        "resources": [
            {"format": "gtfs-rt", "last_modified": "2026-08-02T03:47:51+00:00", "url": "x"},
            {"format": "zip", "last_modified": "2026-09-02T11:39:50.120000+00:00", "url": ORIGINAL_URL},
        ],
    })


def _transport() -> str:
    return json.dumps({"resources": [
        {"format": "gtfs-rt", "url": TRIP_UPDATES_URL, "original_url": TRIP_UPDATES_URL, "updated": "2026-05-03T12:12:21Z"},
        {"format": "GTFS", "url": GTFS_URL, "original_url": ORIGINAL_URL, "updated": "2026-09-02T11:39:50.120000Z"},
    ]})


@pytest.fixture
def mocks(aioclient_mock, freezer):
    freezer.move_to(NOW)
    tu, vp = _flux()
    aioclient_mock.get(GTFS_URL, content=_lire("gtfs.zip"), headers={"Last-Modified": "Wed, 02 Sep 2026 11:39:49 GMT"})
    aioclient_mock.get(DATAGOUV_DATASET_URL, text=_datagouv())
    aioclient_mock.get(TRANSPORT_DATASET_URL, text=_transport())
    aioclient_mock.get(TRIP_UPDATES_URL, content=tu)
    aioclient_mock.get(VEHICLE_POSITIONS_URL, content=vp)
    aioclient_mock.get(INFOTRAFIC_URL, text=_lire("traffic-infos.html", "r"))
    return aioclient_mock


async def _setup(hass: HomeAssistant, entry_data: dict, options: dict | None = None, unique_id: str | None = None):
    entry = MockConfigEntry(domain=DOMAIN, data={"entry": entry_data}, options=options or {}, unique_id=unique_id, title="test")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_lieu(hass: HomeAssistant, mocks):
    await _setup(hass, {"mode": "lieu", "nom": "Dole Gare", "nb_passages": 2})
    state = hass.states.get("sensor.grandole_dole_gare")
    assert state is not None, [s.entity_id for s in hass.states.async_all()]
    assert int(state.state) > 0
    passages = state.attributes["passages"]
    for key in ("idLigne", "numLignePublic", "couleurFond", "couleurTexte", "destination", "temps",
                "tempsEnSeconde", "typeDeTemps", "fiable", "numVehicule", "modeTransport",
                "accessibiliteVehicule", "accessibiliteArret", "idArret", "nomExact", "latitude",
                "longitude", "sensAller", "heure", "heureTheorique", "retard", "idCourse"):
        assert key in passages[0], key
    assert passages[0]["couleurFond"].startswith("#")
    assert passages[0]["temps"].endswith("min")
    assert passages[0]["typeDeTemps"] == 0
    fiables = [p for p in passages if p["fiable"]]
    assert fiables and all(p["retard"] is not None for p in fiables)
    assert any(p["numVehicule"] for p in fiables)
    assert state.attributes["grandole_mode"] == "lieu"
    assert state.attributes["temps_reel"] is True
    assert state.attributes["temps_reel_age"] < 120
    assert state.attributes["nom_arret"] == "Dole Gare"
    assert hass.states.get("sensor.grandole_etat_lignes") is not None
    assert hass.states.get("sensor.grandole_messages") is not None
    assert os.path.exists(hass.config.path(".storage", "grandole_gtfs.zip"))


async def test_lieu_nom_partiel(hass: HomeAssistant, mocks):
    await _setup(hass, {"mode": "lieu", "nom": "theatre 1", "nb_passages": 3})
    state = hass.states.get("sensor.grandole_theatre_1")
    assert state is not None
    assert state.attributes["nom_arret"] == "Théâtre 1"
    compteur: dict = {}
    for p in state.attributes["passages"]:
        cle = (p["idLigne"], p["sensAller"])
        compteur[cle] = compteur.get(cle, 0) + 1
    assert max(compteur.values()) <= 3


async def test_liste(hass: HomeAssistant, mocks):
    await _setup(hass, {"mode": "liste", "nb_passages": 2, "items": [
        {"nom": "Dole Gare", "id_ligne": "2", "sens_aller": False},
        {"nom": "Dole Gare", "id_ligne": "1", "sens_aller": True},
    ]})
    state = hass.states.get("sensor.grandole_dole_gare_2_retour")
    assert state is not None, [s.entity_id for s in hass.states.async_all()]
    assert state.state not in ("unknown", "unavailable")
    assert state.attributes["destination"] == "Tavaux Collège"
    assert state.attributes["grandole_mode"] == "liste"
    assert all(p["idLigne"] == "2" and p["sensAller"] is False for p in state.attributes["passages"])
    assert int(state.state) == state.attributes["tempsEnSeconde"] // 60
    assert hass.states.get("sensor.grandole_dole_gare_1_aller") is not None


async def test_person(hass: HomeAssistant, mocks):
    hass.states.async_set("person.steph", "not_home", {"latitude": 47.0959, "longitude": 5.4881, "friendly_name": "Steph"})
    await _setup(hass, {"mode": "person_proximity", "person_entity_id": "person.steph", "nb_passages": 1, "max_stops": 3})
    state = hass.states.get("sensor.grandole_proximite_steph")
    assert state is not None, [s.entity_id for s in hass.states.async_all()]
    assert int(state.state) == 3
    arrets = state.attributes["arrets"]
    assert arrets[0]["nom"] == "Dole Gare"
    assert arrets[0]["distance"] == 0
    assert arrets[0]["passages"]
    assert state.attributes["person_state"] == "not_home"


async def test_ligne_et_suivi(hass: HomeAssistant, mocks):
    await _setup(hass, {"mode": "ligne", "id_ligne": "3", "num_ligne": "3", "nom_ligne": "Dole Lycée Duhamel <> Dole La Paule"}, unique_id="ligne:3")
    await _setup(hass, {"mode": "suivi_ligne", "id_ligne": "1", "num_ligne": "1", "nom_ligne": "Choisey Autoroute <> Dole Grandes Epenottes 1"}, unique_id="suivi:1")
    etat = hass.states.get("sensor.grandole_ligne_3_etat")
    assert etat is not None, [s.entity_id for s in hass.states.async_all()]
    assert etat.state == "Normal"
    assert etat.attributes["vehicules_localises"] == 2
    assert etat.attributes["courses_en_cours"] == 2
    assert etat.attributes["num"] == "3"
    messages = hass.states.get("sensor.grandole_ligne_3_messages")
    assert messages.state == "0"
    suivi = hass.states.get("sensor.grandole_bus_ligne_1")
    assert suivi is not None
    assert suivi.state == "4"
    buses = suivi.attributes["buses"]
    assert all(b["gps"] is True and b["latitude"] is not None and b["prochain_arret"] for b in buses)
    assert {b["id"] for b in buses} == {"269063", "209126", "229063", "229058"}
    assert all(b["statut"] in ("a_quai", "en_route", "depart") for b in buses)
    assert suivi.attributes["grandole_mode"] == "suivi"
    assert suivi.attributes["couleurFond"] == "#D82080"
    global_etat = hass.states.get("sensor.grandole_etat_lignes")
    lignes = global_etat.attributes["lignes"]
    assert len(lignes) == 16
    assert lignes[0]["num"] == "1" and lignes[0]["couleur_fond"] == "#D82080"
    assert global_etat.attributes["vehicules_localises"] == 8
    assert len(hass.data[DOMAIN]["coordinator"].entrees) == 2


async def test_infotrafic_etats(hass: HomeAssistant, mocks):
    await _setup(hass, {"mode": "ligne", "id_ligne": "18", "num_ligne": "18", "nom_ligne": "x"}, unique_id="ligne:18")
    await _setup(hass, {"mode": "ligne", "id_ligne": "2", "num_ligne": "2", "nom_ligne": "y"}, unique_id="ligne:2")
    assert hass.states.get("sensor.grandole_ligne_18_etat").state == "Perturbation en cours"
    assert hass.states.get("sensor.grandole_ligne_18_etat").attributes["infotrafic_en_cours"] == 1
    assert hass.states.get("sensor.grandole_ligne_2_etat").state == "Information"
    assert hass.states.get("sensor.grandole_ligne_2_etat").attributes["etat"] == 2
    l18 = hass.states.get("sensor.grandole_ligne_18_messages")
    assert l18.state == "1" and l18.attributes["messages"][0]["type"] == "infotrafic"
    global_msgs = hass.states.get("sensor.grandole_messages")
    assert global_msgs.attributes["infotrafic"] == 2
    assert global_msgs.attributes["infotrafic_horodatage"] is not None
    global_etat = hass.states.get("sensor.grandole_etat_lignes")
    assert global_etat.state == "1"
    par_num = {l["num"]: l for l in global_etat.attributes["lignes"]}
    assert par_num["10"]["etat"] == 2 and par_num["1"]["etat"] == 1


def test_analyser_infotrafic():
    messages = analyser_infotrafic(_lire("traffic-infos.html", "r"), TZ)
    assert len(messages) == 2
    m18 = next(m for m in messages if m["lignes"] == ["18"])
    assert m18["gravite"] == "WARN" and m18["etat"] == "en_cours"
    assert m18["titre"] == "Perturbation sur la ligne 18"
    assert m18["debut"] == "2026-09-06T06:15:00+02:00" and m18["fin"] == "2027-03-26T10:00:00+01:00"
    assert m18["causes"] == ["Travaux", "Service modifié"] and m18["effet"] == "modified_service"
    assert "<span" not in m18["corps"] and "style=" not in m18["corps"] and "Vriange" in m18["corps"]
    assert m18["mise_a_jour"].startswith("Mise à jour le lundi 7 septembre 2026")
    m2 = next(m for m in messages if "2" in m["lignes"])
    assert m2["lignes"] == ["2", "10"] and m2["gravite"] == "INFO"
    assert analyser_infotrafic("<html></html>", TZ) == []


async def test_services_et_unload(hass: HomeAssistant, mocks):
    entry = await _setup(hass, {"mode": "lieu", "nom": "Dole Gare", "nb_passages": 2})
    resp = await hass.services.async_call(DOMAIN, "chercher_arret", {"recherche": "gare", "limite": 5}, blocking=True, return_response=True)
    assert [a["nom"] for a in resp["arrets"]] == ["Dole Gare", "Foucherans Gare", "Jantet Gare"]
    assert "2" in resp["arrets"][0]["lignes"]
    resp = await hass.services.async_call(DOMAIN, "get_horaires", {"nom": "theatre 1", "nb": 1}, blocking=True, return_response=True)
    assert resp["nom"] == "Théâtre 1"
    assert resp["nb_passages"] == len(resp["passages"]) > 0
    assert resp["temps_reel"] is True
    with pytest.raises(Exception):
        await hass.services.async_call(DOMAIN, "get_horaires", {"nom": "zzzz"}, blocking=True, return_response=True)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert "coordinator" not in hass.data[DOMAIN]
    assert hass.states.get("sensor.grandole_dole_gare").state == "unavailable"


async def test_config_flow_lieu(hass: HomeAssistant, mocks):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == "form" and result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"mode": "lieu", "name": ""})
    assert result["step_id"] == "lieu"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"nom": "dole gare", "nb_passages": 3})
    assert result["type"] == "create_entry", result
    assert result["title"] == "Grandole Dole Gare"
    assert result["data"]["entry"]["nom"] == "Dole Gare"
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"mode": "lieu", "name": ""})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"nom": "Dole Gare", "nb_passages": 3})
    assert result["type"] == "abort" and result["reason"] == "already_configured"


async def test_config_flow_liste_et_options(hass: HomeAssistant, mocks):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"mode": "liste", "name": "Mon arrêt"})
    assert result["step_id"] == "liste"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"nom": "Dole Gare", "nb_passages": 2})
    assert result["step_id"] == "liste_ligne", result
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"ligne": "2"})
    assert result["step_id"] == "liste_sens"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"sens": "false", "add_another": True})
    assert result["step_id"] == "liste"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"nom": "Théâtre 1"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"ligne": "1"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"sens": "true", "add_another": False})
    assert result["type"] == "create_entry"
    assert result["title"] == "Mon arrêt"
    assert len(result["data"]["entry"]["items"]) == 2
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"nb_passages": 4, "add_item": True})
    assert result["step_id"] == "add_item"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"nom": "Gujean"})
    assert result["step_id"] == "add_item_ligne"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"ligne": "17"})
    assert result["step_id"] == "add_item_sens"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"sens": "true"})
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    assert len(entry.data["entry"]["items"]) == 3
    assert entry.options["nb_passages"] == 4
    assert hass.states.get("sensor.grandole_gujean_17_aller") is not None


async def test_config_flow_ligne_et_person(hass: HomeAssistant, mocks):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"mode": "suivi_ligne"})
    assert result["step_id"] == "suivi_ligne"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"id_ligne": "LZ"})
    assert result["type"] == "create_entry"
    assert result["title"] == "Grandole Bus LZ"
    assert result["data"]["entry"]["num_ligne"] == "LZ"
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"mode": "ligne"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"id_ligne": "2"})
    assert result["type"] == "create_entry" and result["title"] == "Grandole Ligne 2"
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"mode": "person_proximity"})
    assert result["step_id"] == "person"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"person_entity_id": "person.steph", "nb_passages": 2, "max_stops": 4})
    assert result["type"] == "create_entry" and result["title"] == "Grandole steph"


async def test_flux_indisponibles(hass: HomeAssistant, aioclient_mock, freezer):
    freezer.move_to(NOW)
    aioclient_mock.get(GTFS_URL, content=_lire("gtfs.zip"))
    aioclient_mock.get(DATAGOUV_DATASET_URL, status=500)
    aioclient_mock.get(TRANSPORT_DATASET_URL, status=500)
    aioclient_mock.get(TRIP_UPDATES_URL, status=503)
    aioclient_mock.get(VEHICLE_POSITIONS_URL, exc=TimeoutError())
    aioclient_mock.get(INFOTRAFIC_URL, status=500)
    await _setup(hass, {"mode": "lieu", "nom": "Dole Gare", "nb_passages": 2})
    state = hass.states.get("sensor.grandole_dole_gare")
    assert state is not None and int(state.state) > 0
    assert state.attributes["temps_reel"] is False
    assert all(p["fiable"] is False for p in state.attributes["passages"])
    assert hass.states.get("sensor.grandole_messages").state == "0"


async def test_flux_fige(hass: HomeAssistant, aioclient_mock, freezer):
    freezer.move_to(NOW)
    tu, vp = _flux(decalage=12 * 3600)
    aioclient_mock.get(GTFS_URL, content=_lire("gtfs.zip"))
    aioclient_mock.get(DATAGOUV_DATASET_URL, text=_datagouv())
    aioclient_mock.get(TRIP_UPDATES_URL, content=tu)
    aioclient_mock.get(VEHICLE_POSITIONS_URL, content=vp)
    aioclient_mock.get(INFOTRAFIC_URL, text=_lire("traffic-infos.html", "r"))
    await _setup(hass, {"mode": "lieu", "nom": "Dole Gare", "nb_passages": 2})
    await _setup(hass, {"mode": "suivi_ligne", "id_ligne": "1", "num_ligne": "1", "nom_ligne": "x"}, unique_id="suivi:1")
    state = hass.states.get("sensor.grandole_dole_gare")
    assert int(state.state) > 0
    assert state.attributes["temps_reel"] is False
    assert state.attributes["temps_reel_age"] > 40000
    assert all(p["fiable"] is False for p in state.attributes["passages"])
    assert hass.states.get("sensor.grandole_bus_ligne_1").state == "0"
    lignes = {l["num"]: l for l in hass.states.get("sensor.grandole_etat_lignes").attributes["lignes"]}
    assert lignes["1"]["vehicules_localises"] == 0
    assert lignes["1"]["courses_jour"] == 61


async def test_gtfs_repli_transport(hass: HomeAssistant, aioclient_mock, freezer):
    freezer.move_to(NOW)
    tu, vp = _flux()
    aioclient_mock.get(GTFS_URL, status=500)
    aioclient_mock.get(DATAGOUV_DATASET_URL, status=500)
    aioclient_mock.get(TRANSPORT_DATASET_URL, text=_transport())
    aioclient_mock.get(ORIGINAL_URL, content=_lire("gtfs.zip"))
    aioclient_mock.get(TRIP_UPDATES_URL, content=tu)
    aioclient_mock.get(VEHICLE_POSITIONS_URL, content=vp)
    aioclient_mock.get(INFOTRAFIC_URL, text=_lire("traffic-infos.html", "r"))
    await _setup(hass, {"mode": "lieu", "nom": "Dole Gare", "nb_passages": 2})
    state = hass.states.get("sensor.grandole_dole_gare")
    assert state is not None and int(state.state) > 0
    assert hass.data[DOMAIN]["store"].version == "2026-09-02T11:39:50.120000Z"
    assert len([c for c in aioclient_mock.mock_calls if str(c[1]) == ORIGINAL_URL]) == 1


async def test_gtfs_cache_et_mise_a_jour(hass: HomeAssistant, mocks, aioclient_mock):
    await _setup(hass, {"mode": "lieu", "nom": "Dole Gare", "nb_passages": 2})
    store = hass.data[DOMAIN]["store"]
    assert store.version == "2026-09-02T11:39:50.120000+00:00"
    assert len([c for c in aioclient_mock.mock_calls if str(c[1]) == GTFS_URL]) == 1
    aioclient_mock.clear_requests()
    aioclient_mock.get(GTFS_URL, content=_lire("gtfs.zip"))
    aioclient_mock.get(DATAGOUV_DATASET_URL, text=json.dumps({"resources": [
        {"format": "zip", "last_modified": "2026-10-01T00:00:00+00:00", "url": "https://x/gtfs.zip"},
    ]}))
    tu, vp = _flux()
    aioclient_mock.get(TRIP_UPDATES_URL, content=tu)
    aioclient_mock.get(VEHICLE_POSITIONS_URL, content=vp)
    store.derniere_verification = 0.0
    coordinator = hass.data[DOMAIN]["coordinator"]
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert store.version == "2026-10-01T00:00:00+00:00"
    assert len([c for c in aioclient_mock.mock_calls if str(c[1]) == GTFS_URL]) == 1
