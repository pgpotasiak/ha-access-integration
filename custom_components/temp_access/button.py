"""Revoke button of a guest panel."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import PortalConnectionError, PortalError
from .const import DOMAIN, STATUS_EXPIRED, STATUS_REVOKED, SUBENTRY_PANEL
from .entity import PanelEntity
from .hub import AccessHub


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    hub: AccessHub = hass.data[DOMAIN][entry.entry_id]
    for sub in entry.subentries.values():
        if sub.subentry_type == SUBENTRY_PANEL and "panel_id" in sub.data:
            async_add_entities([RevokeButton(hub, sub.data["panel_id"])], config_subentry_id=sub.subentry_id)


class RevokeButton(PanelEntity, ButtonEntity):
    def __init__(self, hub: AccessHub, panel_id: str) -> None:
        super().__init__(hub, panel_id, "revoke")

    @property
    def available(self) -> bool:
        return self.hub.status(self.panel_id) not in (STATUS_REVOKED, STATUS_EXPIRED)

    async def async_press(self) -> None:
        try:
            await self.hub.async_revoke(self.panel_id)
        except PortalError as err:
            raise HomeAssistantError(f"Portal error: {err.message or err.code}") from err
        except PortalConnectionError as err:
            raise HomeAssistantError(f"Panel blocked locally, but the portal is unreachable ({err})") from err
