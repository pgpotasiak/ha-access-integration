"""Config flow (portal registration) and subentry flow (guest panels)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector as sel
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .api import PortalApi, PortalConnectionError, PortalError
from .const import (
    ALLOWED_DOMAINS,
    BUTTON_DEFAULT_ACTION,
    CONTROL_DOMAINS,
    READ_DOMAINS,
    CONF_API_KEY,
    CONF_INSTANCE_ID,
    CONF_INVITE_CODE,
    CONF_PORTAL_URL,
    DAYS,
    DEFAULT_PORTAL_URL,
    DEFAULT_PULSE_SECONDS,
    DOMAIN,
    SUBENTRY_PANEL,
    SWITCH_DOMAINS,
    TYPE_BUTTON,
    TYPE_SENSOR,
    TYPE_SWITCH,
)
from .panel import PanelError, async_create_on_portal, build_controls, build_schedule, default_type

# Which button actions make sense for each domain (first one is the default).
ACTIONS_BY_DOMAIN: dict[str, list[str]] = {
    "button": ["press"],
    "input_button": ["press"],
    "script": ["run"],
    "scene": ["run"],
    "lock": ["unlock", "open"],
    "cover": ["toggle", "open"],
    "valve": ["toggle", "open"],
    "light": ["pulse", "toggle"],
    "switch": ["pulse", "toggle"],
    "input_boolean": ["pulse", "toggle"],
    "siren": ["pulse", "toggle"],
    "fan": ["toggle", "pulse"],
}


class TempAccessConfigFlow(ConfigFlow, domain=DOMAIN):
    """Register this Home Assistant with the portal using an invite code."""

    VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_PANEL: PanelSubentryFlow}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_PORTAL_URL].strip().rstrip("/")
            if not url.startswith(("https://", "http://")):
                errors[CONF_PORTAL_URL] = "invalid_url"
            else:
                api = PortalApi(async_get_clientsession(self.hass), url)
                try:
                    res = await api.register(user_input[CONF_INVITE_CODE].strip(), user_input[CONF_NAME])
                except PortalError as err:
                    errors["base"] = "invalid_invite" if err.code == "invalid_invite" else "portal_error"
                except PortalConnectionError:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(res["instance_id"])
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=user_input[CONF_NAME],
                        data={
                            CONF_PORTAL_URL: url,
                            CONF_INSTANCE_ID: res["instance_id"],
                            CONF_API_KEY: res["api_key"],
                        },
                    )

        defaults = user_input or {}
        schema = vol.Schema(
            {
                vol.Required(CONF_PORTAL_URL, default=defaults.get(CONF_PORTAL_URL, DEFAULT_PORTAL_URL)): str,
                vol.Required(CONF_INVITE_CODE): str,
                vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, self.hass.config.location_name or "Home Assistant")): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class PanelSubentryFlow(ConfigSubentryFlow):
    """Add a guest panel from the UI: panel settings first, then one short step per entity."""

    def __init__(self) -> None:
        self._panel: dict[str, Any] = {}
        self._entities: list[str] = []
        self._controls: list[dict[str, Any]] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        entry = self._get_entry()
        if entry.state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="not_loaded")

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                build_schedule(self.hass, user_input.get("days"), user_input.get("time_from"), user_input.get("time_to"))
                duration = timedelta(**(user_input.get("duration") or {}))
                if duration.total_seconds() < 60:
                    raise PanelError("too short", "bad_duration")
                pin = (user_input.get("pin") or "").strip()
                if pin and not (pin.isdigit() and 4 <= len(pin) <= 8):
                    raise PanelError("bad pin", "bad_pin")
                if not user_input.get("entities"):
                    raise PanelError("no entities", "no_entities")
                if len(user_input["entities"]) > 20:
                    raise PanelError("too many", "too_many")
            except PanelError as err:
                errors["base"] = err.key
            else:
                self._panel = user_input
                self._entities = list(dict.fromkeys(user_input["entities"]))
                self._controls = []
                return await self.async_step_control()

        lang = "pl" if (self.hass.config.language or "pl").startswith("pl") else "en"
        schema = vol.Schema(
            {
                vol.Required("title"): sel.TextSelector(),
                vol.Required("entities"): sel.EntitySelector(sel.EntitySelectorConfig(domain=sorted(ALLOWED_DOMAINS), multiple=True)),
                vol.Optional("start"): sel.DateTimeSelector(),
                vol.Required("duration", default={"days": 1, "hours": 0, "minutes": 0}): sel.DurationSelector(sel.DurationSelectorConfig(enable_day=True)),
                vol.Optional("days"): sel.SelectSelector(sel.SelectSelectorConfig(options=DAYS, multiple=True, translation_key="days")),
                vol.Optional("time_from"): sel.TimeSelector(),
                vol.Optional("time_to"): sel.TimeSelector(),
                vol.Optional("pin"): sel.TextSelector(),
                vol.Required("language", default=lang): sel.SelectSelector(sel.SelectSelectorConfig(options=["pl", "en"], translation_key="language")),
            }
        )
        if user_input is not None:
            schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_control(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        index = len(self._controls)
        entity_id = self._entities[index]
        domain = entity_id.split(".", 1)[0]
        state = self.hass.states.get(entity_id)
        friendly = (state.attributes.get("friendly_name") if state else None) or entity_id
        actions = ACTIONS_BY_DOMAIN.get(domain, [BUTTON_DEFAULT_ACTION.get(domain, "press")])
        errors: dict[str, str] = {}

        if user_input is not None:
            ctype = user_input.get("type") or default_type(entity_id)
            self._controls.append(
                {
                    "entity_id": entity_id,
                    "name": (user_input.get("name") or friendly).strip(),
                    "type": ctype,
                    "action": (user_input.get("action") or actions[0]) if ctype == TYPE_BUTTON else None,
                    "pulse_seconds": user_input.get("pulse_seconds"),
                    "max_uses": int(user_input["max_uses"]) if user_input.get("max_uses") and ctype != TYPE_SENSOR else None,
                    "show_state": bool(user_input.get("show_state")),
                }
            )
            if len(self._controls) < len(self._entities):
                return await self.async_step_control()
            result = await self._async_finish()
            if not isinstance(result, str):
                return result
            # Show the error on the last step and let the user retry.
            self._controls.pop()
            errors["base"] = result

        fields: dict[Any, Any] = {vol.Optional("name", default=friendly[:40]): sel.TextSelector()}
        if domain in CONTROL_DOMAINS:
            kinds = ([TYPE_SWITCH] if domain in SWITCH_DOMAINS else []) + [TYPE_BUTTON] + ([TYPE_SENSOR] if domain in READ_DOMAINS else [])
            if len(kinds) > 1:
                fields[vol.Required("type", default=default_type(entity_id))] = sel.SelectSelector(
                    sel.SelectSelectorConfig(options=kinds, translation_key="control_type", mode=sel.SelectSelectorMode.LIST)
                )
            if len(actions) > 1:
                fields[vol.Required("action", default=actions[0])] = sel.SelectSelector(
                    sel.SelectSelectorConfig(options=actions, translation_key="button_action")
                )
            if "pulse" in actions:
                fields[vol.Optional("pulse_seconds", default=DEFAULT_PULSE_SECONDS)] = sel.NumberSelector(
                    sel.NumberSelectorConfig(min=0.2, max=30, step=0.1, unit_of_measurement="s", mode=sel.NumberSelectorMode.BOX)
                )
            fields[vol.Optional("max_uses")] = sel.NumberSelector(sel.NumberSelectorConfig(min=1, max=1000, step=1, mode=sel.NumberSelectorMode.BOX))
            if domain in READ_DOMAINS:
                fields[vol.Optional("show_state", default=False)] = sel.BooleanSelector()

        return self.async_show_form(
            step_id="control" if domain in CONTROL_DOMAINS else "control_read",
            data_schema=vol.Schema(fields),
            errors=errors,
            description_placeholders={"entity": friendly, "entity_id": entity_id, "index": str(index + 1), "total": str(len(self._entities))},
            last_step=index + 1 == len(self._entities),
        )

    async def async_step_control_read(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Same as the control step, for entities a guest can only look at."""
        return await self.async_step_control(user_input)

    async def _async_finish(self) -> SubentryFlowResult | str:
        entry = self._get_entry()
        hub = self.hass.data[DOMAIN][entry.entry_id]
        p = self._panel
        now = dt_util.utcnow()
        valid_from = now
        if p.get("start"):
            parsed = dt_util.parse_datetime(p["start"])
            if parsed is None:
                return "bad_dates"
            valid_from = dt_util.as_utc(parsed)
        valid_until = max(valid_from, now) + timedelta(**p["duration"])
        try:
            controls = build_controls(self.hass, self._controls)
            schedule = build_schedule(self.hass, p.get("days"), p.get("time_from"), p.get("time_to"))
            data = await async_create_on_portal(
                self.hass, hub, title=p["title"].strip()[:80], controls=controls, valid_from=valid_from,
                valid_until=valid_until, schedule=schedule, pin=(p.get("pin") or "").strip() or None, language=p["language"],
            )
        except PanelError as err:
            return err.key
        from . import notify_new_panel

        notify_new_panel(self.hass, data)
        return self.async_create_entry(title=data["title"], data=data, unique_id=data["panel_id"])
