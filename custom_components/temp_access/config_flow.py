"""Config flow: register this Home Assistant with the portal using an invite code."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PortalApi, PortalConnectionError, PortalError
from .const import CONF_API_KEY, CONF_INSTANCE_ID, CONF_INVITE_CODE, CONF_PORTAL_URL, DEFAULT_PORTAL_URL, DOMAIN


class TempAccessConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_PORTAL_URL].strip().rstrip("/")
            if not url.startswith(("https://", "http://")):
                errors[CONF_PORTAL_URL] = "invalid_url"
            else:
                api = PortalApi(async_get_clientsession(self.hass), url)
                try:
                    res = await api.register(user_input[CONF_INVITE_CODE].strip(), user_input[CONF_NAME])
                except PortalError as err:
                    errors["base"] = "invalid_invite" if err.code == "invalid_invite" else "portal_error"
                except PortalConnectionError:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(res["instance_id"])
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=user_input[CONF_NAME],
                        data={
                            CONF_PORTAL_URL: url,
                            CONF_INSTANCE_ID: res["instance_id"],
                            CONF_API_KEY: res["api_key"],
                        },
                    )

        defaults = user_input or {}
        schema = vol.Schema(
            {
                vol.Required(CONF_PORTAL_URL, default=defaults.get(CONF_PORTAL_URL, DEFAULT_PORTAL_URL)): str,
                vol.Required(CONF_INVITE_CODE): str,
                vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, self.hass.config.location_name or "Home Assistant")): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
