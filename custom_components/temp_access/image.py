"""QR code with the panel link."""

from __future__ import annotations

import io

import segno

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, SUBENTRY_PANEL
from .entity import PanelEntity
from .hub import AccessHub


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    hub: AccessHub = hass.data[DOMAIN][entry.entry_id]
    for sub in entry.subentries.values():
        if sub.subentry_type == SUBENTRY_PANEL and "panel_id" in sub.data:
            async_add_entities([QrImage(hass, hub, sub.data["panel_id"])], config_subentry_id=sub.subentry_id)


class QrImage(PanelEntity, ImageEntity):
    _attr_content_type = "image/png"

    def __init__(self, hass: HomeAssistant, hub: AccessHub, panel_id: str) -> None:
        PanelEntity.__init__(self, hub, panel_id, "qr")
        ImageEntity.__init__(self, hass)
        self._attr_image_last_updated = dt_util.utc_from_timestamp(self.panel.get("created", 0))
        self._png: bytes | None = None

    async def async_image(self) -> bytes | None:
        if self._png is None and self.panel.get("url"):
            buf = io.BytesIO()
            segno.make(self.panel["url"], error="m").save(buf, kind="png", scale=10, border=3)
            self._png = buf.getvalue()
        return self._png
