"""Temporary guest access to Home Assistant entities through an external portal."""

from __future__ import annotations

import logging
import secrets
import time
from datetime import timedelta
from typing import Any

import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .api import PortalApi, PortalConnectionError, PortalError
from .const import (
    ALLOWED_DOMAINS,
    BUTTON_ACTIONS,
    BUTTON_DEFAULT_ACTION,
    CONF_API_KEY,
    CONF_INSTANCE_ID,
    CONF_PORTAL_URL,
    DAYS,
    DOMAIN,
    SWITCH_DOMAINS,
    TYPE_BUTTON,
    TYPE_SWITCH,
)
from .hub import AccessHub

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

HM = vol.Match(r"^([01]\d|2[0-3]):[0-5]\d$")

CONTROL_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("name"): vol.All(cv.string, vol.Length(min=1, max=40)),
        vol.Optional("type"): vol.In([TYPE_SWITCH, TYPE_BUTTON]),
        vol.Optional("action"): vol.In(sorted(BUTTON_ACTIONS)),
        vol.Optional("pulse_seconds"): vol.All(vol.Coerce(float), vol.Range(min=0.2, max=30)),
        vol.Optional("max_uses"): vol.All(vol.Coerce(int), vol.Range(min=1, max=1000)),
    }
)

CREATE_PANEL_SCHEMA = vol.Schema(
    {
        vol.Required("title"): vol.All(cv.string, vol.Length(min=1, max=80)),
        vol.Required("controls"): vol.All(cv.ensure_list, [CONTROL_SCHEMA], vol.Length(min=1, max=20)),
        vol.Optional("pin"): vol.All(vol.Coerce(str), vol.Match(r"^\d{4,8}$")),
        vol.Optional("valid_from"): cv.datetime,
        vol.Exclusive("valid_until", "end"): cv.datetime,
        vol.Exclusive("duration", "end"): cv.positive_time_period,
        vol.Optional("days"): vol.All(cv.ensure_list, [vol.In(DAYS)], vol.Length(min=1)),
        vol.Optional("time_from"): vol.All(cv.string, HM),
        vol.Optional("time_to"): vol.All(cv.string, HM),
        vol.Optional("language", default="pl"): vol.In(["pl", "en"]),
        vol.Optional("notify", default=True): cv.boolean,
        vol.Optional("config_entry_id"): cv.string,
    }
)

REVOKE_PANEL_SCHEMA = vol.Schema(
    {
        vol.Required("panel_id"): cv.string,
        vol.Optional("config_entry_id"): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register services once for all entries."""

    def pick_hub(call: ServiceCall) -> AccessHub:
        hubs: dict[str, AccessHub] = hass.data.get(DOMAIN, {})
        entry_id = call.data.get("config_entry_id")
        if entry_id:
            if entry_id not in hubs:
                raise ServiceValidationError(f"Unknown config entry {entry_id}")
            return hubs[entry_id]
        if not hubs:
            raise ServiceValidationError("Temporary Access is not set up")
        return next(iter(hubs.values()))

    async def create_panel(call: ServiceCall) -> ServiceResponse:
        hub = pick_hub(call)
        data = call.data
        now = dt_util.utcnow()

        valid_from = dt_util.as_utc(data["valid_from"]) if data.get("valid_from") else now
        if data.get("valid_until"):
            valid_until = dt_util.as_utc(data["valid_until"])
        elif data.get("duration"):
            valid_until = max(valid_from, now) + data["duration"]
        else:
            valid_until = max(valid_from, now) + timedelta(hours=24)
        if valid_until <= max(valid_from, now):
            raise ServiceValidationError("The panel must end in the future and after it starts")

        if bool(data.get("time_from")) != bool(data.get("time_to")):
            raise ServiceValidationError("Set both time_from and time_to, or neither")
        schedule: dict[str, Any] | None = None
        if data.get("days") or data.get("time_from"):
            schedule = {"tz": str(hass.config.time_zone)}
            if data.get("days"):
                schedule["days"] = list(dict.fromkeys(data["days"]))
            if data.get("time_from"):
                if data["time_from"] == data["time_to"]:
                    raise ServiceValidationError("time_from and time_to must differ")
                schedule["from"], schedule["to"] = data["time_from"], data["time_to"]

        controls: dict[str, dict[str, Any]] = {}
        portal_controls: list[dict[str, Any]] = []
        for i, c in enumerate(data["controls"], start=1):
            entity_id = c["entity_id"]
            domain = entity_id.split(".", 1)[0]
            if domain not in ALLOWED_DOMAINS:
                raise ServiceValidationError(f"{entity_id}: domain '{domain}' cannot be shared with guests")
            state = hass.states.get(entity_id)
            if state is None:
                raise ServiceValidationError(f"{entity_id}: entity not found")
            ctype = c.get("type") or (TYPE_SWITCH if domain in SWITCH_DOMAINS else TYPE_BUTTON)
            if ctype == TYPE_SWITCH and domain not in SWITCH_DOMAINS:
                raise ServiceValidationError(f"{entity_id}: '{domain}' can only be a button")
            action = None
            if ctype == TYPE_BUTTON:
                action = c.get("action") or BUTTON_DEFAULT_ACTION.get(domain)
                if action is None:
                    raise ServiceValidationError(f"{entity_id}: choose an action for this button")
            name = (c.get("name") or state.attributes.get("friendly_name") or entity_id)[:40]
            cid = f"ctrl_{i}"
            controls[cid] = {
                "entity_id": entity_id,
                "name": name,
                "type": ctype,
                "action": action,
                "pulse_seconds": c.get("pulse_seconds"),
                "max_uses": c.get("max_uses"),
                "uses": 0,
            }
            pc: dict[str, Any] = {"id": cid, "name": name, "type": ctype}
            if c.get("max_uses"):
                pc["max_uses"] = c["max_uses"]
            portal_controls.append(pc)

        pin = data.get("pin") or f"{secrets.randbelow(10000):04d}"
        body: dict[str, Any] = {
            "pin": pin,
            "title": data["title"],
            "language": data["language"],
            "valid_from": valid_from.isoformat(),
            "valid_until": valid_until.isoformat(),
            "controls": portal_controls,
        }
        if schedule:
            body["schedule"] = schedule
        try:
            res = await hub.api.create_panel(body)
        except PortalError as err:
            raise HomeAssistantError(f"Portal refused the panel: {err.message or err.code}") from err
        except PortalConnectionError as err:
            raise HomeAssistantError(f"Cannot reach the portal: {err}") from err

        hub.add_panel(
            res["panel_id"],
            {
                "title": data["title"],
                "url": res["panel_url"],
                "valid_from": valid_from.timestamp(),
                "valid_until": valid_until.timestamp(),
                "schedule": schedule,
                "controls": controls,
                "created": time.time(),
            },
        )

        local_until = dt_util.as_local(valid_until).strftime("%Y-%m-%d %H:%M")
        if data["notify"]:
            persistent_notification.async_create(
                hass,
                (
                    f"**{data['title']}**\n\n"
                    f"Link: {res['panel_url']}\n\n"
                    f"PIN: **{pin}**\n\n"
                    f"Ważny do: {local_until}\n\n"
                    "Wyślij link i PIN gościowi dwiema osobnymi wiadomościami."
                ),
                title="Nowy panel dostępu",
                notification_id=f"{DOMAIN}_{res['panel_id']}",
            )
        return {
            "panel_id": res["panel_id"],
            "panel_url": res["panel_url"],
            "pin": pin,
            "valid_from": valid_from.isoformat(),
            "valid_until": valid_until.isoformat(),
        }

    async def revoke_panel(call: ServiceCall) -> None:
        hub = pick_hub(call)
        panel_id = call.data["panel_id"]
        # Local revocation first: works even when the portal is unreachable.
        hub.mark_revoked(panel_id)
        try:
            await hub.api.revoke_panel(panel_id)
        except PortalError as err:
            if err.status != 404:
                raise HomeAssistantError(f"Portal error: {err.message or err.code}") from err
        except PortalConnectionError as err:
            raise HomeAssistantError(
                f"Panel blocked locally, but the portal is unreachable ({err}). Run the action again later."
            ) from err
        persistent_notification.async_dismiss(hass, f"{DOMAIN}_{panel_id}")

    hass.services.async_register(DOMAIN, "create_panel", create_panel, schema=CREATE_PANEL_SCHEMA, supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, "revoke_panel", revoke_panel, schema=REVOKE_PANEL_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    api = PortalApi(session, entry.data[CONF_PORTAL_URL], entry.data[CONF_API_KEY])
    hub = AccessHub(hass, entry.entry_id, api, session, entry.data[CONF_INSTANCE_ID])
    await hub.async_load()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = hub
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    hub.start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hub: AccessHub = hass.data[DOMAIN].pop(entry.entry_id)
    await hub.stop()
    return unloaded
