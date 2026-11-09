"""Connection status to the portal."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_CONNECTION
from .hub import AccessHub


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    hub: AccessHub = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PortalConnectionSensor(hub, entry)])


class PortalConnectionSensor(BinarySensorEntity):
    """On while the WebSocket to the portal is open."""

    _attr_has_entity_name = True
    _attr_translation_key = "connection"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False

    def __init__(self, hub: AccessHub, entry: ConfigEntry) -> None:
        self._hub = hub
        self._attr_unique_id = f"{hub.instance_id}_connection"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, hub.instance_id)},
            name=entry.title,
            manufacturer="Temporary Access",
            model="Portal connection",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=hub.api.base_url,
        )

    @property
    def is_on(self) -> bool:
        return self._hub.connected

    async def async_added_to_hass(self) -> None:
        @callback
        def _update(_value: bool) -> None:
            self.async_write_ha_state()

        self.async_on_remove(async_dispatcher_connect(self.hass, f"{SIGNAL_CONNECTION}_{self._hub.instance_id}", _update))
