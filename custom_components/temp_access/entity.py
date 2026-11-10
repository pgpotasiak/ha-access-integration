"""Base class for entities that belong to one guest panel."""

from __future__ import annotations

from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, SIGNAL_PANEL
from .hub import AccessHub


class PanelEntity(Entity):
    """Entity on the device of one guest panel; refreshed when the panel changes."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hub: AccessHub, panel_id: str, key: str) -> None:
        self.hub = hub
        self.panel_id = panel_id
        self._attr_translation_key = key
        self._attr_unique_id = f"{panel_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, panel_id)},
            name=self.panel["title"],
            manufacturer="Temporary Access",
            model="Guest panel",
            entry_type=DeviceEntryType.SERVICE,
            via_device=(DOMAIN, hub.instance_id),
            configuration_url=self.panel["url"],
        )

    @property
    def panel(self) -> dict[str, Any]:
        return self.hub.panels.get(self.panel_id) or {}

    @property
    def runtime(self) -> dict[str, Any]:
        return self.hub.runtime(self.panel_id)

    async def async_added_to_hass(self) -> None:
        @callback
        def _update() -> None:
            self._handle_update()
            self.async_write_ha_state()

        self.async_on_remove(async_dispatcher_connect(self.hass, f"{SIGNAL_PANEL}_{self.panel_id}", _update))

    @callback
    def _handle_update(self) -> None:
        """Hook for subclasses."""
