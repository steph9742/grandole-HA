from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import (
    CONF_ID_LIGNE,
    CONF_ITEMS,
    CONF_MAX_STOPS,
    CONF_MODE,
    CONF_NB_PASSAGES,
    CONF_NOM,
    CONF_NOM_LIGNE,
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
)
from .coordinator import async_get_store
from .gtfs import Reseau

_LOGGER = logging.getLogger(__name__)


async def _charger_reseau(hass) -> Reseau | None:
    try:
        return await async_get_store(hass).async_get()
    except Exception as err:
        _LOGGER.warning("Grandole : GTFS indisponible pendant la configuration : %s", err)
        return None


def _options_arrets(reseau: Reseau) -> list[dict]:
    return [{"value": nom, "label": nom} for nom in reseau.noms_arrets()]


def _options_lignes(lignes) -> list[dict]:
    return [{"value": l.id, "label": f"{l.num} : {l.nom}"} for l in lignes]


def _options_sens(sens: list[dict]) -> list[dict]:
    options = []
    for s in sens:
        fleche = "→" if s["sens_aller"] else "←"
        label = f"{fleche} {s['destination']}"
        autres = [d for d in s.get("destinations", []) if d != s["destination"]]
        if autres:
            label += f" ({', '.join(autres[:2])})"
        options.append({"value": "true" if s["sens_aller"] else "false", "label": label})
    if not options:
        options = [{"value": "true", "label": "→ Aller"}, {"value": "false", "label": "← Retour"}]
    return options


def _selecteur_nb(defaut: int) -> NumberSelector:
    return NumberSelector(NumberSelectorConfig(min=1, max=5, step=1, mode=NumberSelectorMode.BOX))


class GrandoleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._mode: str = ""
        self._name: str = ""
        self._items: list[dict] = []
        self._nb_passages: int = DEFAULT_NB_PASSAGES
        self._pending_nom: str = ""
        self._pending_ligne_id: str = ""
        self._reseau: Reseau | None = None

    async def _reseau_ou_erreur(self) -> Reseau | None:
        if self._reseau is None:
            self._reseau = await _charger_reseau(self.hass)
        return self._reseau

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        if user_input is not None:
            self._mode = user_input[CONF_MODE]
            self._name = user_input.get("name", "").strip()
            if self._mode == MODE_LIEU:
                return await self.async_step_lieu()
            if self._mode == MODE_PERSON:
                return await self.async_step_person()
            if self._mode == MODE_LIGNE:
                return await self.async_step_ligne()
            if self._mode == MODE_SUIVI_LIGNE:
                return await self.async_step_suivi_ligne()
            return await self.async_step_liste()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_MODE, default=MODE_LIEU): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            {"value": MODE_LIEU, "label": "Arrêt par nom (toutes les lignes)"},
                            {"value": MODE_LISTE, "label": "Arrêt par ligne et direction"},
                            {"value": MODE_PERSON, "label": "Arrêts proches d'une personne"},
                            {"value": MODE_LIGNE, "label": "État d'une ligne"},
                            {"value": MODE_SUIVI_LIGNE, "label": "Positions des véhicules d'une ligne"},
                        ],
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Optional("name", default=""): TextSelector(),
            }),
        )

    async def async_step_lieu(self, user_input: dict | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        reseau = await self._reseau_ou_erreur()
        if reseau is None:
            errors["base"] = "gtfs_indisponible"
        elif user_input is not None:
            nom = reseau.resoudre_nom(str(user_input[CONF_NOM]).strip())
            if nom is None:
                errors["base"] = "arret_inconnu"
            else:
                await self.async_set_unique_id(f"lieu:{nom}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=self._name or f"Grandole {nom}",
                    data={"entry": {
                        "mode": MODE_LIEU,
                        CONF_NOM: nom,
                        CONF_NB_PASSAGES: int(user_input[CONF_NB_PASSAGES]),
                    }},
                )

        return self.async_show_form(
            step_id="lieu",
            data_schema=vol.Schema({
                vol.Required(CONF_NOM): SelectSelector(
                    SelectSelectorConfig(
                        options=_options_arrets(reseau) if reseau else [],
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                    )
                ),
                vol.Required(CONF_NB_PASSAGES, default=DEFAULT_NB_PASSAGES): _selecteur_nb(DEFAULT_NB_PASSAGES),
            }),
            errors=errors,
        )

    async def async_step_person(self, user_input: dict | None = None) -> FlowResult:
        if user_input is not None:
            person_id = user_input[CONF_PERSON_ENTITY]
            await self.async_set_unique_id(f"person:{person_id}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._name or f"Grandole {person_id.split('.')[-1]}",
                data={"entry": {
                    "mode": MODE_PERSON,
                    CONF_PERSON_ENTITY: person_id,
                    CONF_NB_PASSAGES: int(user_input[CONF_NB_PASSAGES]),
                    CONF_MAX_STOPS: int(user_input[CONF_MAX_STOPS]),
                }},
            )

        return self.async_show_form(
            step_id="person",
            data_schema=vol.Schema({
                vol.Required(CONF_PERSON_ENTITY): EntitySelector(EntitySelectorConfig(domain="person")),
                vol.Required(CONF_NB_PASSAGES, default=DEFAULT_NB_PASSAGES): NumberSelector(
                    NumberSelectorConfig(min=1, max=5, step=1, mode=NumberSelectorMode.SLIDER)
                ),
                vol.Required(CONF_MAX_STOPS, default=DEFAULT_MAX_STOPS): NumberSelector(
                    NumberSelectorConfig(min=1, max=10, step=1, mode=NumberSelectorMode.SLIDER)
                ),
            }),
        )

    async def _step_ligne(self, step_id: str, mode: str, user_input: dict | None) -> FlowResult:
        errors: dict[str, str] = {}
        reseau = await self._reseau_ou_erreur()
        if reseau is None:
            errors["base"] = "gtfs_indisponible"
        elif user_input is not None:
            ligne = reseau.lignes.get(user_input[CONF_ID_LIGNE])
            if ligne is None:
                errors["base"] = "ligne_inconnue"
            else:
                prefixe = "ligne" if mode == MODE_LIGNE else "suivi"
                await self.async_set_unique_id(f"{prefixe}:{ligne.id}")
                self._abort_if_unique_id_configured()
                titre = f"Grandole Ligne {ligne.num}" if mode == MODE_LIGNE else f"Grandole Bus {ligne.num}"
                return self.async_create_entry(
                    title=self._name or titre,
                    data={"entry": {
                        "mode": mode,
                        CONF_ID_LIGNE: ligne.id,
                        CONF_NUM_LIGNE: ligne.num,
                        CONF_NOM_LIGNE: ligne.nom,
                    }},
                )

        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema({
                vol.Required(CONF_ID_LIGNE): SelectSelector(
                    SelectSelectorConfig(
                        options=_options_lignes(reseau.lignes_triees()) if reseau else [],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
            errors=errors,
        )

    async def async_step_ligne(self, user_input: dict | None = None) -> FlowResult:
        return await self._step_ligne("ligne", MODE_LIGNE, user_input)

    async def async_step_suivi_ligne(self, user_input: dict | None = None) -> FlowResult:
        return await self._step_ligne("suivi_ligne", MODE_SUIVI_LIGNE, user_input)

    async def async_step_liste(self, user_input: dict | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        is_first = len(self._items) == 0
        reseau = await self._reseau_ou_erreur()
        if reseau is None:
            errors["base"] = "gtfs_indisponible"
        elif user_input is not None:
            nom = reseau.resoudre_nom(str(user_input[CONF_NOM]).strip())
            if nom is None:
                errors["base"] = "arret_inconnu"
            elif not reseau.lignes_arret(nom):
                errors["base"] = "aucune_ligne"
            else:
                self._pending_nom = nom
                if is_first:
                    self._nb_passages = int(user_input[CONF_NB_PASSAGES])
                return await self.async_step_liste_ligne()

        champs: dict = {
            vol.Required(CONF_NOM): SelectSelector(
                SelectSelectorConfig(
                    options=_options_arrets(reseau) if reseau else [],
                    mode=SelectSelectorMode.DROPDOWN,
                    custom_value=True,
                )
            )
        }
        if is_first:
            champs[vol.Required(CONF_NB_PASSAGES, default=DEFAULT_NB_PASSAGES)] = _selecteur_nb(DEFAULT_NB_PASSAGES)
        return self.async_show_form(step_id="liste", data_schema=vol.Schema(champs), errors=errors)

    async def async_step_liste_ligne(self, user_input: dict | None = None) -> FlowResult:
        reseau = self._reseau
        assert reseau is not None
        lignes = reseau.lignes_arret(self._pending_nom)
        if user_input is not None:
            self._pending_ligne_id = user_input["ligne"]
            return await self.async_step_liste_sens()

        return self.async_show_form(
            step_id="liste_ligne",
            data_schema=vol.Schema({
                vol.Required("ligne"): SelectSelector(
                    SelectSelectorConfig(options=_options_lignes(lignes), mode=SelectSelectorMode.DROPDOWN)
                ),
            }),
            description_placeholders={
                "info": f"**{len(lignes)}** ligne(s) desservent l'arrêt **{self._pending_nom}**.",
            },
        )

    async def async_step_liste_sens(self, user_input: dict | None = None) -> FlowResult:
        reseau = self._reseau
        assert reseau is not None
        ligne = reseau.lignes.get(self._pending_ligne_id)
        sens_options = _options_sens(reseau.sens_ligne_arret(self._pending_nom, self._pending_ligne_id))

        if user_input is not None:
            self._items.append({
                CONF_NOM: self._pending_nom,
                CONF_ID_LIGNE: self._pending_ligne_id,
                CONF_SENS_ALLER: user_input["sens"] == "true",
            })
            if user_input.get("add_another", False):
                return await self.async_step_liste()
            premier = self._items[0][CONF_NOM]
            return self.async_create_entry(
                title=self._name or f"Grandole {premier} (liste)",
                data={"entry": {
                    "mode": MODE_LISTE,
                    CONF_ITEMS: self._items,
                    CONF_NB_PASSAGES: self._nb_passages,
                }},
            )

        libelle = f"{ligne.num} : {ligne.nom}" if ligne else self._pending_ligne_id
        nb_deja = len(self._items)
        info = (
            f"Ligne sélectionnée : **{libelle}**."
            if nb_deja == 0
            else f"**{nb_deja}** combinaison(s) déjà ajoutée(s). Ligne : **{libelle}**."
        )
        return self.async_show_form(
            step_id="liste_sens",
            data_schema=vol.Schema({
                vol.Required("sens", default=sens_options[0]["value"]): SelectSelector(
                    SelectSelectorConfig(options=sens_options, mode=SelectSelectorMode.LIST)
                ),
                vol.Optional("add_another", default=False): BooleanSelector(),
            }),
            description_placeholders={"info": info},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return GrandoleOptionsFlow(config_entry)


class GrandoleOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry
        entry_data = config_entry.data["entry"]
        self._mode: str = entry_data["mode"]
        self._nb_passages: int = int(config_entry.options.get(
            CONF_NB_PASSAGES, entry_data.get(CONF_NB_PASSAGES, DEFAULT_NB_PASSAGES)
        ))
        self._max_stops: int = int(config_entry.options.get(
            CONF_MAX_STOPS, entry_data.get(CONF_MAX_STOPS, DEFAULT_MAX_STOPS)
        ))
        self._items: list[dict] = list(entry_data.get(CONF_ITEMS, []))
        self._pending_nom: str = ""
        self._pending_ligne_id: str = ""
        self._reseau: Reseau | None = None

    def _options(self) -> dict:
        options = {}
        if self._mode in (MODE_LIEU, MODE_LISTE, MODE_PERSON):
            options[CONF_NB_PASSAGES] = self._nb_passages
        if self._mode == MODE_PERSON:
            options[CONF_MAX_STOPS] = self._max_stops
        return options

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        if self._mode in (MODE_LIGNE, MODE_SUIVI_LIGNE):
            return self.async_abort(reason="aucune_option")

        if user_input is not None:
            self._nb_passages = int(user_input.get(CONF_NB_PASSAGES, self._nb_passages))
            if self._mode == MODE_PERSON:
                self._max_stops = int(user_input.get(CONF_MAX_STOPS, self._max_stops))
            if self._mode == MODE_LISTE and user_input.get("add_item"):
                return await self.async_step_add_item()
            return self.async_create_entry(title="", data=self._options())

        champs: dict = {
            vol.Required(CONF_NB_PASSAGES, default=self._nb_passages): _selecteur_nb(self._nb_passages),
        }
        if self._mode == MODE_PERSON:
            champs[vol.Required(CONF_MAX_STOPS, default=self._max_stops)] = NumberSelector(
                NumberSelectorConfig(min=1, max=10, step=1, mode=NumberSelectorMode.SLIDER)
            )
        if self._mode == MODE_LISTE:
            champs[vol.Optional("add_item", default=False)] = BooleanSelector()
        return self.async_show_form(step_id="init", data_schema=vol.Schema(champs))

    async def async_step_add_item(self, user_input: dict | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if self._reseau is None:
            self._reseau = await _charger_reseau(self.hass)
        reseau = self._reseau
        if reseau is None:
            errors["base"] = "gtfs_indisponible"
        elif user_input is not None:
            nom = reseau.resoudre_nom(str(user_input[CONF_NOM]).strip())
            if nom is None:
                errors["base"] = "arret_inconnu"
            elif not reseau.lignes_arret(nom):
                errors["base"] = "aucune_ligne"
            else:
                self._pending_nom = nom
                return await self.async_step_add_item_ligne()

        return self.async_show_form(
            step_id="add_item",
            data_schema=vol.Schema({
                vol.Required(CONF_NOM): SelectSelector(
                    SelectSelectorConfig(
                        options=_options_arrets(reseau) if reseau else [],
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                    )
                ),
            }),
            errors=errors,
        )

    async def async_step_add_item_ligne(self, user_input: dict | None = None) -> FlowResult:
        reseau = self._reseau
        assert reseau is not None
        if user_input is not None:
            self._pending_ligne_id = user_input["ligne"]
            return await self.async_step_add_item_sens()
        lignes = reseau.lignes_arret(self._pending_nom)
        return self.async_show_form(
            step_id="add_item_ligne",
            data_schema=vol.Schema({
                vol.Required("ligne"): SelectSelector(
                    SelectSelectorConfig(options=_options_lignes(lignes), mode=SelectSelectorMode.DROPDOWN)
                ),
            }),
            description_placeholders={
                "info": f"**{len(lignes)}** ligne(s) desservent l'arrêt **{self._pending_nom}**.",
            },
        )

    async def async_step_add_item_sens(self, user_input: dict | None = None) -> FlowResult:
        reseau = self._reseau
        assert reseau is not None
        sens_options = _options_sens(reseau.sens_ligne_arret(self._pending_nom, self._pending_ligne_id))
        if user_input is not None:
            self._items.append({
                CONF_NOM: self._pending_nom,
                CONF_ID_LIGNE: self._pending_ligne_id,
                CONF_SENS_ALLER: user_input["sens"] == "true",
            })
            if user_input.get("add_another", False):
                return await self.async_step_add_item()
            new_data = dict(self._entry.data)
            new_data["entry"] = {**self._entry.data["entry"], CONF_ITEMS: self._items}
            self.hass.config_entries.async_update_entry(self._entry, data=new_data)
            return self.async_create_entry(title="", data=self._options())

        ligne = reseau.lignes.get(self._pending_ligne_id)
        libelle = f"{ligne.num} : {ligne.nom}" if ligne else self._pending_ligne_id
        return self.async_show_form(
            step_id="add_item_sens",
            data_schema=vol.Schema({
                vol.Required("sens", default=sens_options[0]["value"]): SelectSelector(
                    SelectSelectorConfig(options=sens_options, mode=SelectSelectorMode.LIST)
                ),
                vol.Optional("add_another", default=False): BooleanSelector(),
            }),
            description_placeholders={"info": f"Ligne sélectionnée : **{libelle}**."},
        )
