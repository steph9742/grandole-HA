from __future__ import annotations

import logging
import os

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.loader import async_get_integration

from .const import DOMAIN
from .coordinator import GrandoleCoordinator, async_get_store
from .services import async_register_services

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor"]

_CARD_URL = "/grandole_card"
_CARD_FILES = ["grandole-card.js", "grandole-card-editor.js"]


async def _register_lovelace_resources(hass: HomeAssistant, version: str) -> None:
    store = Store(hass, 1, "lovelace_resources")
    data: dict = await store.async_load() or {}
    items: list[dict] = data.get("items", [])

    changed = 0
    for fname in _CARD_FILES:
        base = f"{_CARD_URL}/{fname}"
        url = f"{base}?v={version}"
        existing = next(
            (item for item in items if str(item.get("url", "")).split("?")[0] == base),
            None,
        )
        if existing is None:
            items.append({"id": f"grandole_{fname}", "type": "module", "url": url})
            changed += 1
        elif existing.get("url") != url:
            existing["url"] = url
            changed += 1

    if changed:
        data["items"] = items
        await store.async_save(data)
        _LOGGER.info("Grandole : %d ressource(s) Lovelace mise(s) à jour (v%s)", changed, version)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    async_get_store(hass)
    async_register_services(hass)

    card_dir = hass.config.path("custom_components", DOMAIN, "lovelace")
    if not os.path.isdir(card_dir):
        _LOGGER.warning("Grandole : dossier lovelace/ introuvable, cartes non disponibles")
        return True

    try:
        await hass.http.async_register_static_paths([
            StaticPathConfig(_CARD_URL, card_dir, cache_headers=True)
        ])
    except Exception:
        _LOGGER.exception("Grandole : erreur lors de l'enregistrement du chemin statique")

    try:
        integration = await async_get_integration(hass, DOMAIN)
        version = str(integration.version or "0")
    except Exception:
        version = "0"

    try:
        for fname in _CARD_FILES:
            add_extra_js_url(hass, f"{_CARD_URL}/{fname}?v={version}")
    except Exception:
        _LOGGER.exception("Grandole : erreur lors de l'injection JS")

    try:
        await _register_lovelace_resources(hass, version)
    except Exception:
        _LOGGER.exception("Grandole : erreur lors de l'enregistrement des ressources Lovelace")

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = hass.data.setdefault(DOMAIN, {})
    coordinator: GrandoleCoordinator | None = data.get("coordinator")
    if coordinator is None:
        coordinator = GrandoleCoordinator(hass, async_get_store(hass))
        await coordinator.async_config_entry_first_refresh()
        data["coordinator"] = coordinator
    coordinator.entrees.add(entry.entry_id)
    data[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        data = hass.data[DOMAIN]
        data.pop(entry.entry_id, None)
        if data.get("_info_sensors_owner") == entry.entry_id:
            data.pop("_info_sensors_owner", None)
        coordinator: GrandoleCoordinator | None = data.get("coordinator")
        if coordinator is not None:
            coordinator.entrees.discard(entry.entry_id)
            if not coordinator.entrees:
                data.pop("coordinator", None)
                await coordinator.async_shutdown()
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
