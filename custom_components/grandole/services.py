from __future__ import annotations

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import GrandoleCoordinator, async_get_store
from .gtfs import TempsReel

SERVICE_CHERCHER_ARRET = "chercher_arret"
SERVICE_GET_HORAIRES = "get_horaires"

CHERCHER_ARRET_SCHEMA = vol.Schema({
    vol.Required("recherche"): cv.string,
    vol.Optional("limite", default=10): vol.All(vol.Coerce(int), vol.Range(min=1, max=50)),
})

GET_HORAIRES_SCHEMA = vol.Schema({
    vol.Required("nom"): cv.string,
    vol.Optional("nb", default=3): vol.All(vol.Coerce(int), vol.Range(min=1, max=5)),
})


async def _reseau(hass: HomeAssistant):
    try:
        return await async_get_store(hass).async_get()
    except Exception as err:
        raise HomeAssistantError(f"Données GTFS Grandole indisponibles : {err}") from err


def _temps_reel(hass: HomeAssistant) -> TempsReel | None:
    coordinator: GrandoleCoordinator | None = hass.data.get(DOMAIN, {}).get("coordinator")
    return coordinator.data if coordinator else None


async def _chercher_arret(call: ServiceCall) -> ServiceResponse:
    reseau = await _reseau(call.hass)
    return {"arrets": reseau.chercher_arrets(call.data["recherche"], call.data["limite"])}


async def _get_horaires(call: ServiceCall) -> ServiceResponse:
    nom = call.data["nom"].strip()
    if not nom:
        raise ServiceValidationError("Le nom de l'arrêt est vide.")
    reseau = await _reseau(call.hass)
    nom_exact = reseau.resoudre_nom(nom)
    if nom_exact is None:
        raise ServiceValidationError(f"Arrêt introuvable : {nom}")
    temps_reel = _temps_reel(call.hass)
    maintenant = dt_util.utcnow()
    passages = reseau.passages(reseau.ids_arrets(nom_exact), maintenant, temps_reel, call.data["nb"])
    return {
        "nom": nom_exact,
        "nb_passages": len(passages),
        "passages": passages,
        "temps_reel": bool(temps_reel and temps_reel.frais(maintenant.timestamp())),
    }


def async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_GET_HORAIRES):
        return
    hass.services.async_register(
        DOMAIN, SERVICE_CHERCHER_ARRET, _chercher_arret,
        schema=CHERCHER_ARRET_SCHEMA, supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_GET_HORAIRES, _get_horaires,
        schema=GET_HORAIRES_SCHEMA, supports_response=SupportsResponse.ONLY,
    )
