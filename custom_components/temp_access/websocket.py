"""WebSocket commands used by the "Guest access" sidebar page."""

from __future__ import annotations

import time
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .api import PortalConnectionError, PortalError
from .config_flow import ACTIONS_BY_DOMAIN
from .const import ALLOWED_DOMAINS, CONTROL_DOMAINS, DOMAIN, READ_DOMAINS, SWITCH_DOMAINS
from .hub import AccessHub


@callback
def async_register(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_list)
    websocket_api.async_register_command(hass, ws_revoke)
    websocket_api.async_register_command(hass, ws_delete)


def _hubs(hass: HomeAssistant) -> dict[str, AccessHub]:
    return hass.data.get(DOMAIN, {})


def _find(hass: HomeAssistant, panel_id: str) -> AccessHub | None:
    for hub in _hubs(hass).values():
        if panel_id in hub.panels:
            return hub
    return None


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "temp_access/list"})
@callback
def ws_list(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    ent_reg = er.async_get(hass)

    def eid(platform: str, uid: str) -> str | None:
        return ent_reg.async_get_entity_id(platform, DOMAIN, uid)

    entries, panels = [], []
    for hub in _hubs(hass).values():
        entries.append({"entry_id": hub.entry.entry_id, "title": hub.entry.title, "connected": hub.connected, "portal": hub.api.base_url})
        for pid, p in hub.panels.items():
            rt = hub.runtime(pid)
            panels.append(
                {
                    "panel_id": pid,
                    "entry_id": hub.entry.entry_id,
                    "title": p["title"],
                    "status": hub.status(pid),
                    "url": p["url"],
                    "pin": p["pin"],
                    "language": p.get("language"),
                    "valid_from": p["valid_from"],
                    "valid_until": p["valid_until"],
                    "created": p.get("created"),
                    "schedule": p.get("schedule"),
                    "failed_pin": rt.get("failed_pin", 0),
                    "last_action": rt.get("last_action"),
                    "controls": [
                        {
                            "id": cid,
                            "name": c["name"],
                            "entity_id": c["entity_id"],
                            "type": c["type"],
                            "action": c.get("action"),
                            "max_uses": c.get("max_uses"),
                            "uses": rt["uses"].get(cid, 0),
                            "show_state": bool(c.get("show_state")),
                        }
                        for cid, c in p["controls"].items()
                    ],
                    "entities": {
                        "qr": eid("image", f"{pid}_qr"),
                        "status": eid("sensor", f"{pid}_status"),
                        "last_action": eid("sensor", f"{pid}_last_action"),
                    },
                }
            )
    panels.sort(key=lambda x: x.get("created") or 0, reverse=True)
    connection.send_result(
        msg["id"],
        {
            "now": time.time(),
            "entries": entries,
            "panels": panels,
            "domains": sorted(ALLOWED_DOMAINS),
            "switch_domains": sorted(SWITCH_DOMAINS),
            "control_domains": sorted(CONTROL_DOMAINS),
            "read_domains": sorted(READ_DOMAINS),
            "actions": ACTIONS_BY_DOMAIN,
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "temp_access/revoke", vol.Required("panel_id"): str})
@websocket_api.async_response
async def ws_revoke(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    hub = _find(hass, msg["panel_id"])
    if hub is None:
        connection.send_error(msg["id"], "not_found", "Unknown panel")
        return
    try:
        await hub.async_revoke(msg["panel_id"])
    except (PortalError, PortalConnectionError) as err:
        # Already blocked locally; tell the page the portal part failed.
        connection.send_error(msg["id"], "portal_unreachable", str(err))
        return
    connection.send_result(msg["id"], {"status": hub.status(msg["panel_id"])})


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "temp_access/delete", vol.Required("panel_id"): str})
@callback
def ws_delete(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Remove the panel (its device); the integration then revokes it on the portal."""
    hub = _find(hass, msg["panel_id"])
    sub_id = hub.subentry_id(msg["panel_id"]) if hub else None
    if hub is None or sub_id is None:
        connection.send_error(msg["id"], "not_found", "Unknown panel")
        return
    hass.config_entries.async_remove_subentry(hub.entry, sub_id)
    connection.send_result(msg["id"], {"deleted": True})
