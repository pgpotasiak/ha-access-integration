"""Sidebar entry "Guest access"."""

from __future__ import annotations

import json
from pathlib import Path

from homeassistant.components import panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN

URL_BASE = f"/{DOMAIN}_static"
PANEL_URL = "guest-access"


async def async_register_panel(hass: HomeAssistant) -> None:
    if PANEL_URL in hass.data.get("frontend_panels", {}):
        return
    root = Path(__file__).parent
    version = json.loads((root / "manifest.json").read_text(encoding="utf-8"))["version"]
    await hass.http.async_register_static_paths([StaticPathConfig(URL_BASE, str(root / "frontend"), cache_headers=False)])
    pl = (hass.config.language or "").startswith("pl")
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL,
        webcomponent_name="temp-access-panel",
        sidebar_title="Dostęp gości" if pl else "Guest access",
        sidebar_icon="mdi:account-key",
        module_url=f"{URL_BASE}/panel.js?v={version}",
        require_admin=True,
    )
