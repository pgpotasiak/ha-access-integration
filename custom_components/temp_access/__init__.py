"""Temporary guest access to Home Assistant entities through an external portal."""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from types import MappingProxyType
from typing import Any

import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .api import PortalApi, PortalConnectionError, PortalError
from .const import (
    BUTTON_ACTIONS,
    CONF_API_KEY,
    CONF_INSTANCE_ID,
    CONF_PORTAL_URL,
    DAYS,
    DOMAIN,
    PANEL_RETENTION_SECONDS,
    SUBENTRY_PANEL,
    TYPE_BUTTON,
    TYPE_SWITCH,
)
from .hub import AccessHub
from .panel import PanelError, async_create_on_portal, build_controls, build_schedule

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.IMAGE, Platform.SENSOR]
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


@callback
def notify_new_panel(hass: HomeAssistant, data: dict[str, Any]) -> None:
    until = dt_util.as_local(dt_util.utc_from_timestamp(data["valid_until"])).strftime("%Y-%m-%d %H:%M")
    persistent_notification.async_create(
        hass,
        (
            f"**{data['title']}**\n\n"
            f"Link: {data['url']}\n\n"
            f"PIN: **{data['pin']}**\n\n"
            f"Ważny do: {until}\n\n"
            "Wyślij link i PIN gościowi dwiema osobnymi wiadomościami. "
            "Kod QR z linkiem znajdziesz na urządzeniu panelu."
        ),
        title="Nowy panel dostępu",
        notification_id=f"{DOMAIN}_{data['panel_id']}",
    )


@callback
def add_panel_subentry(hass: HomeAssistant, entry: ConfigEntry, data: dict[str, Any]) -> None:
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=MappingProxyType(data),
            subentry_type=SUBENTRY_PANEL,
            title=data["title"],
            unique_id=data["panel_id"],
        ),
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register actions once for all entries."""

    def pick_entry(call: ServiceCall) -> ConfigEntry:
        hubs: dict[str, AccessHub] = hass.data.get(DOMAIN, {})
        entry_id = call.data.get("config_entry_id")
        if entry_id:
            if entry_id not in hubs:
                raise ServiceValidationError(f"Unknown config entry {entry_id}")
            return hubs[entry_id].entry
        if not hubs:
            raise ServiceValidationError("Temporary Access is not set up")
        return next(iter(hubs.values())).entry

    async def create_panel(call: ServiceCall) -> ServiceResponse:
        entry = pick_entry(call)
        hub: AccessHub = hass.data[DOMAIN][entry.entry_id]
        data = call.data
        now = dt_util.utcnow()
        valid_from = dt_util.as_utc(data["valid_from"]) if data.get("valid_from") else now
        start = max(valid_from, now)
        if data.get("valid_until"):
            valid_until = dt_util.as_utc(data["valid_until"])
        else:
            valid_until = start + (data.get("duration") or timedelta(hours=24))
        try:
            controls = build_controls(hass, [dict(c) for c in data["controls"]])
            schedule = build_schedule(hass, data.get("days"), data.get("time_from"), data.get("time_to"))
            panel = await async_create_on_portal(
                hass, hub, title=data["title"], controls=controls, valid_from=valid_from,
                valid_until=valid_until, schedule=schedule, pin=data.get("pin"), language=data["language"],
            )
        except PanelError as err:
            if err.key in ("portal_error", "cannot_connect"):
                raise HomeAssistantError(str(err)) from err
            raise ServiceValidationError(str(err)) from err
        add_panel_subentry(hass, entry, panel)
        if data["notify"]:
            notify_new_panel(hass, panel)
        return {
            "panel_id": panel["panel_id"],
            "panel_url": panel["url"],
            "pin": panel["pin"],
            "valid_from": valid_from.isoformat(),
            "valid_until": valid_until.isoformat(),
        }

    async def revoke_panel(call: ServiceCall) -> None:
        entry = pick_entry(call)
        hub: AccessHub = hass.data[DOMAIN][entry.entry_id]
        panel_id = call.data["panel_id"]
        if panel_id not in hub.panels:
            raise ServiceValidationError(f"Unknown panel {panel_id}")
        try:
            await hub.async_revoke(panel_id)
        except PortalError as err:
            raise HomeAssistantError(f"Portal error: {err.message or err.code}") from err
        except PortalConnectionError as err:
            raise HomeAssistantError(
                f"Panel blocked locally, but the portal is unreachable ({err}). Run the action again later."
            ) from err

    hass.services.async_register(DOMAIN, "create_panel", create_panel, schema=CREATE_PANEL_SCHEMA, supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, "revoke_panel", revoke_panel, schema=REVOKE_PANEL_SCHEMA)

    from . import websocket

    websocket.async_register(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    api = PortalApi(session, entry.data[CONF_PORTAL_URL], entry.data[CONF_API_KEY])
    hub = AccessHub(hass, entry, api, session, entry.data[CONF_INSTANCE_ID])
    await hub.async_load()
    from .frontend import async_register_panel

    await async_register_panel(hass)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = hub

    # Panels whose subentry the user deleted: revoke them on the portal, then forget them.
    orphans = [pid for pid in list(hub.data["runtime"]) if pid not in hub.panels]
    if orphans:
        hass.async_create_background_task(_async_revoke_orphans(hub, orphans), f"{DOMAIN}_orphans")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    hub.start()
    entry.async_on_unload(entry.add_update_listener(_async_reload))

    # Panels that ended long ago: remove their devices (the portal has deleted them too).
    cutoff = time.time() - PANEL_RETENTION_SECONDS
    stale = [s.subentry_id for s in entry.subentries.values() if s.subentry_type == SUBENTRY_PANEL and s.data.get("valid_until", 0) < cutoff]
    for sid in stale:
        hass.config_entries.async_remove_subentry(entry, sid)
    return True


async def _async_revoke_orphans(hub: AccessHub, panel_ids: list[str]) -> None:
    for pid in panel_ids:
        try:
            await hub.api.revoke_panel(pid)
        except PortalError as err:
            if err.status != 404:
                _LOGGER.warning("Could not revoke deleted panel %s: %s", pid, err)
                continue
        except PortalConnectionError as err:
            _LOGGER.warning("Could not revoke deleted panel %s now, will retry on next start: %s", pid, err)
            continue
        hub.data["runtime"].pop(pid, None)
        persistent_notification.async_dismiss(hub.hass, f"{DOMAIN}_{pid}")
    hub._save()  # noqa: SLF001


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """A panel was added or removed: rebuild entities."""
    hass.config_entries.async_schedule_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hub: AccessHub = hass.data[DOMAIN].pop(entry.entry_id)
    await hub.stop()
    return unloaded
