"""Sensors of a guest panel: status, end of access, link, PIN, last guest action."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, STATUSES, SUBENTRY_PANEL
from .entity import PanelEntity
from .hub import AccessHub


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    hub: AccessHub = hass.data[DOMAIN][entry.entry_id]
    for sub in entry.subentries.values():
        if sub.subentry_type != SUBENTRY_PANEL or "panel_id" not in sub.data:
            continue
        pid = sub.data["panel_id"]
        async_add_entities(
            [StatusSensor(hub, pid), ValidUntilSensor(hub, pid), LinkSensor(hub, pid), PinSensor(hub, pid), LastActionSensor(hub, pid)],
            config_subentry_id=sub.subentry_id,
        )


class StatusSensor(PanelEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = STATUSES

    def __init__(self, hub: AccessHub, panel_id: str) -> None:
        super().__init__(hub, panel_id, "status")

    @property
    def native_value(self) -> str:
        return self.hub.status(self.panel_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        p, rt = self.panel, self.runtime
        attrs: dict[str, Any] = {
            "valid_from": dt_util.utc_from_timestamp(p["valid_from"]).isoformat() if p else None,
            "failed_pin_attempts": rt.get("failed_pin", 0),
        }
        if p.get("schedule"):
            s = p["schedule"]
            attrs["days"] = s.get("days")
            if s.get("from"):
                attrs["hours"] = f"{s['from']}–{s['to']}"
        for cid, c in (p.get("controls") or {}).items():
            if c.get("max_uses"):
                attrs[f"uses_left_{c['name']}"] = max(0, c["max_uses"] - rt["uses"].get(cid, 0))
        return attrs


class ValidUntilSensor(PanelEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, hub: AccessHub, panel_id: str) -> None:
        super().__init__(hub, panel_id, "valid_until")

    @property
    def native_value(self) -> datetime | None:
        return dt_util.utc_from_timestamp(self.panel["valid_until"]) if self.panel else None


class LinkSensor(PanelEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hub: AccessHub, panel_id: str) -> None:
        super().__init__(hub, panel_id, "link")

    @property
    def native_value(self) -> str | None:
        return self.panel.get("url")


class PinSensor(PanelEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hub: AccessHub, panel_id: str) -> None:
        super().__init__(hub, panel_id, "pin")

    @property
    def native_value(self) -> str | None:
        return self.panel.get("pin")


class LastActionSensor(PanelEntity, SensorEntity):
    """Text of the last guest action; its history is the guest's activity log."""

    def __init__(self, hub: AccessHub, panel_id: str) -> None:
        super().__init__(hub, panel_id, "last_action")

    @property
    def native_value(self) -> str | None:
        la = self.runtime.get("last_action")
        if not la:
            return None
        pl = (self.hass.config.language or "pl").startswith("pl")
        return describe_action(la, pl)[:255]

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return self.runtime.get("last_action")


ACTION_PL = {"on": "włączył", "off": "wyłączył", "press": "użył"}
ACTION_EN = {"on": "turned on", "off": "turned off", "press": "used"}
REASON_PL = {
    "expired": "dostęp nieaktywny",
    "outside_schedule": "poza godzinami",
    "limit_reached": "limit użyć",
    "not_allowed": "niedozwolone",
    "error": "błąd urządzenia",
}
REASON_EN = {
    "expired": "access not active",
    "outside_schedule": "outside hours",
    "limit_reached": "use limit",
    "not_allowed": "not allowed",
    "error": "device error",
}


def describe_action(la: dict[str, Any], pl: bool) -> str:
    verb = (ACTION_PL if pl else ACTION_EN).get(la.get("action"), la.get("action") or "")
    control = la.get("control") or "?"
    if la.get("result") == "ok":
        return f"Gość {verb}: {control}" if pl else f"Guest {verb}: {control}"
    reason = (REASON_PL if pl else REASON_EN).get(la.get("reason"), la.get("reason") or "")
    return f"Odrzucono ({reason}): {control}" if pl else f"Rejected ({reason}): {control}"
