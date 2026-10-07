from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import timedelta

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DATAGOUV_DATASET_URL,
    DOMAIN,
    GTFS_CACHE_FILE,
    GTFS_CHECK_INTERVAL,
    GTFS_META_STORE,
    GTFS_URL,
    INFOTRAFIC_INTERVAL,
    INFOTRAFIC_SITE,
    INFOTRAFIC_URL,
    SCAN_INTERVAL_TEMPS_REEL,
    TRANSPORT_DATASET_URL,
    TRIP_UPDATES_URL,
    VEHICLE_POSITIONS_URL,
)
from .gtfs import Reseau, TempsReel
from .infotrafic import analyser_infotrafic
from .realtime import construire_temps_reel

_LOGGER = logging.getLogger(__name__)


class GrandoleStore:
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.reseau: Reseau | None = None
        self.version: str | None = None
        self.derniere_verification = 0.0
        self._lock = asyncio.Lock()
        self._meta = Store(hass, 1, GTFS_META_STORE)
        self._cache = hass.config.path(".storage", GTFS_CACHE_FILE)

    async def async_get(self) -> Reseau:
        if self.reseau is not None:
            return self.reseau
        async with self._lock:
            if self.reseau is not None:
                return self.reseau
            meta = await self._meta.async_load() or {}
            contenu = await self.hass.async_add_executor_job(self._lire_cache)
            if contenu:
                try:
                    await self._installer(contenu, meta.get("last_modified") or "cache")
                    _LOGGER.debug("Grandole : GTFS chargé depuis le cache (%s)", self.version)
                    return self.reseau
                except Exception as err:
                    _LOGGER.warning("Grandole : cache GTFS illisible (%s), nouveau téléchargement", err)
            await self._telecharger(None)
            return self.reseau

    async def async_verifier_si_necessaire(self) -> None:
        if time.monotonic() - self.derniere_verification < GTFS_CHECK_INTERVAL and self.derniere_verification:
            return
        self.derniere_verification = time.monotonic()
        try:
            derniere = await self._derniere_modification()
        except Exception as err:
            _LOGGER.debug("Grandole : vérification data.gouv impossible : %s", err)
            return
        if derniere and derniere != self.version:
            _LOGGER.info("Grandole : nouvelle version du GTFS (%s), rechargement", derniere)
            async with self._lock:
                try:
                    await self._telecharger(derniere)
                except Exception as err:
                    _LOGGER.warning("Grandole : rechargement du GTFS impossible : %s", err)

    async def _derniere_modification(self) -> str | None:
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(DATAGOUV_DATASET_URL, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
            ressources = data.get("resources") or []
            candidates = [
                r for r in ressources
                if str(r.get("format", "")).lower() == "zip" or str(r.get("url", "")).lower().endswith(".zip")
            ]
            for r in candidates:
                if r.get("last_modified"):
                    return str(r["last_modified"])
            if data.get("last_modified"):
                return str(data["last_modified"])
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            _LOGGER.debug("Grandole : data.gouv indisponible (%s), repli sur transport.data.gouv.fr", err)
        ressource = await self._ressource_transport()
        return str(ressource["updated"]) if ressource and ressource.get("updated") else None

    async def _ressource_transport(self) -> dict | None:
        session = async_get_clientsession(self.hass)
        async with session.get(TRANSPORT_DATASET_URL, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
        for r in data.get("resources") or []:
            if str(r.get("format", "")).upper() == "GTFS":
                return r
        return None

    async def _telecharger_zip(self) -> tuple[bytes, str | None]:
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(GTFS_URL, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                resp.raise_for_status()
                return await resp.read(), resp.headers.get("Last-Modified")
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.warning("Grandole : téléchargement GTFS impossible via %s (%s), repli sur l'URL d'origine", GTFS_URL, err)
        ressource = await self._ressource_transport()
        url = (ressource or {}).get("original_url") or (ressource or {}).get("url")
        if not url:
            raise ValueError("aucune URL de repli pour le GTFS")
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
            resp.raise_for_status()
            return await resp.read(), resp.headers.get("Last-Modified")

    async def _telecharger(self, version: str | None) -> None:
        contenu, en_tete = await self._telecharger_zip()
        if version is None:
            try:
                version = await self._derniere_modification()
            except Exception:
                version = None
        version = version or en_tete or dt_util.utcnow().isoformat()
        await self._installer(contenu, version)
        await self.hass.async_add_executor_job(self._ecrire_cache, contenu)
        await self._meta.async_save({"last_modified": version, "telecharge_le": dt_util.utcnow().isoformat()})
        _LOGGER.info(
            "Grandole : GTFS %s chargé (%d arrêts, %d lignes, %d courses, validité %s à %s)",
            version, len(self.reseau.arrets), len(self.reseau.lignes), len(self.reseau.courses),
            self.reseau.debut_validite, self.reseau.fin_validite,
        )

    async def _installer(self, contenu: bytes, version: str) -> None:
        reseau = await self.hass.async_add_executor_job(Reseau.depuis_zip, contenu, version)
        if not reseau.arrets or not reseau.courses:
            raise ValueError("GTFS vide")
        self.reseau = reseau
        self.version = version

    def _lire_cache(self) -> bytes | None:
        try:
            with open(self._cache, "rb") as f:
                return f.read()
        except OSError:
            return None

    def _ecrire_cache(self, contenu: bytes) -> None:
        os.makedirs(os.path.dirname(self._cache), exist_ok=True)
        temporaire = f"{self._cache}.tmp"
        with open(temporaire, "wb") as f:
            f.write(contenu)
        os.replace(temporaire, self._cache)


def async_get_store(hass: HomeAssistant) -> GrandoleStore:
    data = hass.data.setdefault(DOMAIN, {})
    if "store" not in data:
        data["store"] = GrandoleStore(hass)
    return data["store"]


class GrandoleCoordinator(DataUpdateCoordinator[TempsReel]):
    def __init__(self, hass: HomeAssistant, store: GrandoleStore) -> None:
        super().__init__(
            hass, _LOGGER, name="Grandole",
            update_interval=timedelta(seconds=SCAN_INTERVAL_TEMPS_REEL),
        )
        self.store = store
        self.entrees: set[str] = set()
        self.infotrafic: list[dict] = []
        self.infotrafic_horodatage: str | None = None
        self._infotrafic_prochain = 0.0
        self._echecs: dict[str, int] = {}
        self._cache_etats: tuple[TempsReel | None, float, list, list] | None = None

    @property
    def reseau(self) -> Reseau | None:
        return self.store.reseau

    def maintenant(self):
        return dt_util.utcnow()

    async def _async_update_data(self) -> TempsReel:
        try:
            await self.store.async_get()
        except Exception as err:
            raise UpdateFailed(f"GTFS indisponible : {err}") from err
        await self.store.async_verifier_si_necessaire()
        maintenant = self.maintenant().timestamp()
        mises_a_jour, positions = await asyncio.gather(
            self._telecharger(TRIP_UPDATES_URL), self._telecharger(VEHICLE_POSITIONS_URL)
        )
        await self._rafraichir_infotrafic()
        try:
            return await self.hass.async_add_executor_job(construire_temps_reel, mises_a_jour, positions, maintenant)
        except Exception as err:
            _LOGGER.warning("Grandole : flux GTFS-RT illisible : %s", err)
            return TempsReel()

    async def _rafraichir_infotrafic(self) -> None:
        if time.monotonic() < self._infotrafic_prochain:
            return
        self._infotrafic_prochain = time.monotonic() + INFOTRAFIC_INTERVAL
        contenu = await self._telecharger(INFOTRAFIC_URL, {"Referer": INFOTRAFIC_SITE})
        if contenu is None:
            return
        reseau = self.reseau
        fuseau = reseau.fuseau if reseau else dt_util.get_default_time_zone()
        try:
            messages = await self.hass.async_add_executor_job(
                analyser_infotrafic, contenu.decode("utf-8", "replace"), fuseau
            )
        except Exception as err:
            _LOGGER.warning("Grandole : infotrafic illisible : %s", err)
            return
        if messages != self.infotrafic:
            _LOGGER.info("Grandole : infotrafic mis à jour, %d message(s)", len(messages))
        self.infotrafic = messages
        self.infotrafic_horodatage = dt_util.utcnow().isoformat()

    async def _telecharger(self, url: str, headers: dict | None = None) -> bytes | None:
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                resp.raise_for_status()
                contenu = await resp.read()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            echecs = self._echecs.get(url, 0) + 1
            self._echecs[url] = echecs
            if echecs in (1, 10) or echecs % 100 == 0:
                _LOGGER.warning("Grandole : flux %s injoignable (%s, échec n°%d)", url, err, echecs)
            return None
        if self._echecs.get(url):
            _LOGGER.info("Grandole : flux %s de nouveau joignable", url)
            self._echecs[url] = 0
        return contenu

    def etats_et_messages(self) -> tuple[list[dict], list[dict]]:
        reseau = self.reseau
        if reseau is None:
            return [], []
        maintenant = self.maintenant()
        cache = self._cache_etats
        if cache is not None and cache[0] is self.data and maintenant.timestamp() - cache[1] < 5:
            return cache[2], cache[3]
        etats, messages = reseau.etat_lignes(maintenant, self.data, self.infotrafic)
        self._cache_etats = (self.data, maintenant.timestamp(), etats, messages)
        return etats, messages
