"""Describe guest actions in the logbook."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.logbook import LOGBOOK_ENTRY_ENTITY_ID, LOGBOOK_ENTRY_MESSAGE, LOGBOOK_ENTRY_NAME
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, EVENT_COMMAND
from .sensor import describe_action


@callback
def async_describe_events(hass: HomeAssistant, async_describe_event: Callable[[str, str, Callable[[Event], dict[str, Any]]], None]) -> None:
    @callback
    def describe(event: Event) -> dict[str, Any]:
        d = event.data
        pl = (hass.config.language or "pl").startswith("pl")
        la = {"action": d.get("action"), "control": d.get("control_name"), "result": d.get("result"), "reason": d.get("reason")}
        entry: dict[str, Any] = {
            LOGBOOK_ENTRY_NAME: d.get("panel_title") or ("Panel gościa" if pl else "Guest panel"),
            LOGBOOK_ENTRY_MESSAGE: describe_action(la, pl).replace("Gość ", "gość ", 1).replace("Guest ", "guest ", 1),
        }
        # Attach the entry to the panel device, so it shows in the panel's activity.
        ent_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{d.get('panel_id')}_last_action")
        if ent_id:
            entry[LOGBOOK_ENTRY_ENTITY_ID] = ent_id
        return entry

    async_describe_event(DOMAIN, EVENT_COMMAND, describe)
