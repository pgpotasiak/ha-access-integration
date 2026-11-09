"""REST client for the access portal."""

from __future__ import annotations

from typing import Any

import aiohttp


class PortalError(Exception):
    """The portal answered with an error."""

    def __init__(self, status: int, code: str, message: str | None = None) -> None:
        super().__init__(f"{status} {code}" + (f": {message}" if message else ""))
        self.status = status
        self.code = code
        self.message = message


class PortalConnectionError(Exception):
    """The portal could not be reached."""


class PortalApi:
    """Thin wrapper around the portal's JSON API."""

    def __init__(self, session: aiohttp.ClientSession, base_url: str, api_key: str | None = None) -> None:
        self._session = session
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key

    def ws_url(self, instance_id: str, after: int) -> str:
        return self.base_url.replace("https://", "wss://", 1).replace("http://", "ws://", 1) + f"/api/v1/instances/{instance_id}/ws?after={after}"

    @property
    def auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}

    async def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            async with self._session.request(
                method,
                self.base_url + path,
                json=body,
                headers=self.auth_headers,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                try:
                    data = await resp.json(content_type=None)
                except ValueError:
                    data = {}
                if resp.status >= 400:
                    raise PortalError(resp.status, str(data.get("error", "error")), data.get("message"))
                return data
        except (aiohttp.ClientError, TimeoutError) as err:
            raise PortalConnectionError(str(err)) from err

    async def register(self, invite_code: str, name: str) -> dict[str, Any]:
        return await self._request("POST", "/api/v1/instances", {"invite_code": invite_code, "name": name})

    async def create_panel(self, body: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/api/v1/panels", body)

    async def list_panels(self) -> list[dict[str, Any]]:
        return (await self._request("GET", "/api/v1/panels")).get("panels", [])

    async def revoke_panel(self, panel_id: str) -> dict[str, Any]:
        return await self._request("DELETE", f"/api/v1/panels/{panel_id}")
