"""Panel creation shared by the UI form and the create_panel action."""

from __future__ import annotations

import secrets
import time
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .api import PortalConnectionError, PortalError
from .const import (
    ALLOWED_DOMAINS,
    BUTTON_ACTIONS,
    BUTTON_DEFAULT_ACTION,
    STATUS_ACTIVE,
    STATUS_EXPIRED,
    STATUS_LOCKED,
    STATUS_NOT_STARTED,
    STATUS_OUTSIDE,
    STATUS_REVOKED,
    SWITCH_DOMAINS,
    TYPE_BUTTON,
    TYPE_SWITCH,
)


class PanelError(Exception):
    """Invalid panel definition or portal failure; message is shown to the user."""

    def __init__(self, message: str, key: str = "invalid") -> None:
        super().__init__(message)
        self.key = key


def default_type(entity_id: str) -> str:
    return TYPE_SWITCH if entity_id.split(".", 1)[0] in SWITCH_DOMAINS else TYPE_BUTTON


def build_controls(hass: HomeAssistant, items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Validate control definitions and return them keyed ctrl_1, ctrl_2, ..."""
    if not items:
        raise PanelError("Choose at least one entity", "no_entities")
    if len(items) > 20:
        raise PanelError("At most 20 controls", "too_many")
    controls: dict[str, dict[str, Any]] = {}
    for i, c in enumerate(items, start=1):
        entity_id = c["entity_id"]
        domain = entity_id.split(".", 1)[0]
        if domain not in ALLOWED_DOMAINS:
            raise PanelError(f"{entity_id}: domain '{domain}' cannot be shared with guests", "bad_domain")
        state = hass.states.get(entity_id)
        if state is None:
            raise PanelError(f"{entity_id}: entity not found", "not_found")
        ctype = c.get("type") or default_type(entity_id)
        if ctype == TYPE_SWITCH and domain not in SWITCH_DOMAINS:
            raise PanelError(f"{entity_id}: '{domain}' can only be a button", "button_only")
        action = None
        if ctype == TYPE_BUTTON:
            action = c.get("action") or BUTTON_DEFAULT_ACTION.get(domain)
            if action not in BUTTON_ACTIONS:
                raise PanelError(f"{entity_id}: choose an action for this button", "bad_action")
        name = (c.get("name") or state.attributes.get("friendly_name") or entity_id).strip()[:40]
        max_uses = c.get("max_uses")
        controls[f"ctrl_{i}"] = {
            "entity_id": entity_id,
            "name": name,
            "type": ctype,
            "action": action,
            "pulse_seconds": c.get("pulse_seconds"),
            "max_uses": int(max_uses) if max_uses else None,
        }
    return controls


def build_schedule(hass: HomeAssistant, days: list[str] | None, time_from: str | None, time_to: str | None) -> dict[str, Any] | None:
    time_from = time_from[:5] if time_from else None
    time_to = time_to[:5] if time_to else None
    if bool(time_from) != bool(time_to):
        raise PanelError("Set both hours (from and to), or neither", "hours_pair")
    if time_from and time_from == time_to:
        raise PanelError("The start and end hour must differ", "hours_equal")
    if not days and not time_from:
        return None
    schedule: dict[str, Any] = {"tz": str(hass.config.time_zone)}
    if days:
        schedule["days"] = list(dict.fromkeys(days))
    if time_from:
        schedule["from"], schedule["to"] = time_from, time_to
    return schedule


async def async_create_on_portal(
    hass: HomeAssistant,
    hub: Any,
    *,
    title: str,
    controls: dict[str, dict[str, Any]],
    valid_from: datetime,
    valid_until: datetime,
    schedule: dict[str, Any] | None,
    pin: str | None,
    language: str,
) -> dict[str, Any]:
    """Create the panel on the portal; returns the data stored in the subentry."""
    now = dt_util.utcnow()
    if valid_until <= max(valid_from, now):
        raise PanelError("The panel must end in the future and after it starts", "bad_dates")
    pin = pin or f"{secrets.randbelow(10000):04d}"
    body: dict[str, Any] = {
        "pin": pin,
        "title": title,
        "language": language,
        "valid_from": valid_from.isoformat(),
        "valid_until": valid_until.isoformat(),
        "controls": [
            {"id": cid, "name": c["name"], "type": c["type"], **({"max_uses": c["max_uses"]} if c["max_uses"] else {})}
            for cid, c in controls.items()
        ],
    }
    if schedule:
        body["schedule"] = schedule
    try:
        res = await hub.api.create_panel(body)
    except PortalError as err:
        raise PanelError(f"Portal refused the panel: {err.message or err.code}", "portal_error") from err
    except PortalConnectionError as err:
        raise PanelError(f"Cannot reach the portal: {err}", "cannot_connect") from err
    return {
        "panel_id": res["panel_id"],
        "url": res["panel_url"],
        "pin": pin,
        "title": title,
        "language": language,
        "valid_from": valid_from.timestamp(),
        "valid_until": valid_until.timestamp(),
        "schedule": schedule,
        "controls": controls,
        "created": time.time(),
    }


def panel_status(panel: dict[str, Any], runtime: dict[str, Any], now: float | None = None) -> str:
    from .hub import schedule_allows  # local import to avoid a cycle

    now = time.time() if now is None else now
    if runtime.get("revoked"):
        return STATUS_REVOKED
    if now >= panel["valid_until"]:
        return STATUS_EXPIRED
    if runtime.get("locked"):
        return STATUS_LOCKED
    if now < panel["valid_from"]:
        return STATUS_NOT_STARTED
    if not schedule_allows(panel.get("schedule"), dt_util.utc_from_timestamp(now)):
        return STATUS_OUTSIDE
    return STATUS_ACTIVE
