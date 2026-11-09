"""Connection to the portal and execution of guest commands."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from datetime import datetime
from typing import Any

import aiohttp

from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .api import PortalApi
from .const import (
    BACKOFF_MAX,
    BACKOFF_MIN,
    COMMAND_TTL_SECONDS,
    DEFAULT_PULSE_SECONDS,
    DOMAIN,
    EVENT_COMMAND,
    PING_INTERVAL,
    RECEIVE_TIMEOUT,
    SIGNAL_CONNECTION,
    STORAGE_VERSION,
    TYPE_SWITCH,
)

_LOGGER = logging.getLogger(__name__)


class AccessHub:
    """Keeps the WebSocket to the portal open and executes commands on mapped entities."""

    def __init__(self, hass: HomeAssistant, entry_id: str, api: PortalApi, session: aiohttp.ClientSession, instance_id: str) -> None:
        self.hass = hass
        self.api = api
        self.instance_id = instance_id
        self._session = session
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}")
        self.data: dict[str, Any] = {"last_seq": 0, "panels": {}}
        self.connected = False
        self._task: asyncio.Task | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._clock_offset = 0.0  # portal time minus local time, seconds
        self._stopping = False

    # ---------------- lifecycle ----------------

    async def async_load(self) -> None:
        stored = await self._store.async_load()
        if stored:
            self.data.update(stored)

    @callback
    def _save(self) -> None:
        self._store.async_delay_save(lambda: self.data, 1)

    def start(self) -> None:
        self._stopping = False
        self._task = self.hass.async_create_background_task(self._run(), f"{DOMAIN}_connection")

    async def stop(self) -> None:
        self._stopping = True
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        await self._store.async_save(self.data)
        self._set_connected(False)

    # ---------------- panels ----------------

    def add_panel(self, panel_id: str, panel: dict[str, Any]) -> None:
        self.data["panels"][panel_id] = panel
        self._save()

    def mark_revoked(self, panel_id: str) -> None:
        if panel_id in self.data["panels"]:
            self.data["panels"][panel_id]["revoked"] = True
            self._save()

    def prune_panels(self) -> None:
        """Forget panels that ended more than 7 days ago (the portal deletes them too)."""
        cutoff = time.time() - 7 * 86400
        stale = [pid for pid, p in self.data["panels"].items() if p["valid_until"] < cutoff]
        for pid in stale:
            del self.data["panels"][pid]
        if stale:
            self._save()

    # ---------------- connection ----------------

    @callback
    def _set_connected(self, value: bool) -> None:
        if self.connected != value:
            self.connected = value
            async_dispatcher_send(self.hass, f"{SIGNAL_CONNECTION}_{self.instance_id}", value)

    async def _run(self) -> None:
        backoff = BACKOFF_MIN
        while not self._stopping:
            try:
                await self._connect_once()
                backoff = BACKOFF_MIN  # we had a working session
            except asyncio.CancelledError:
                raise
            except _PermanentError as err:
                _LOGGER.error("Portal refused the connection: %s. Not retrying for 15 minutes", err)
                self._set_connected(False)
                await asyncio.sleep(900)
                continue
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Portal connection failed: %s", err)
            self._set_connected(False)
            if self._stopping:
                break
            delay = backoff * random.uniform(0.8, 1.2)
            _LOGGER.debug("Reconnecting to the portal in %.1f s", delay)
            await asyncio.sleep(delay)
            backoff = min(backoff * 2, BACKOFF_MAX)

    async def _connect_once(self) -> None:
        url = self.api.ws_url(self.instance_id, int(self.data.get("last_seq", 0)))
        try:
            ws = await self._session.ws_connect(url, headers=self.api.auth_headers, heartbeat=None, timeout=aiohttp.ClientWSTimeout(ws_close=10))
        except aiohttp.WSServerHandshakeError as err:
            if err.status in (401, 403):
                raise _PermanentError(f"HTTP {err.status}") from err
            raise
        self._ws = ws
        pinger = self.hass.async_create_background_task(self._ping_loop(ws), f"{DOMAIN}_ping")
        try:
            while True:
                msg = await ws.receive(timeout=RECEIVE_TIMEOUT)
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self._handle(ws, msg.data)
                elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    code = ws.close_code
                    _LOGGER.info("Portal closed the connection (code %s)", code)
                    if code == 4003:
                        raise _PermanentError("instance blocked")
                    return
        finally:
            pinger.cancel()
            if not ws.closed:
                await ws.close()
            self._ws = None

    async def _ping_loop(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        while not ws.closed:
            await asyncio.sleep(PING_INTERVAL)
            try:
                await ws.send_str('{"type":"ping"}')
            except Exception:  # noqa: BLE001
                return

    async def _handle(self, ws: aiohttp.ClientWebSocketResponse, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except ValueError:
            return
        kind = msg.get("type")
        if kind == "hello":
            self._clock_offset = msg.get("server_time", time.time() * 1000) / 1000 - time.time()
            self._set_connected(True)
            _LOGGER.info("Connected to the access portal")
            self.prune_panels()
        elif kind == "command":
            seq = int(msg.get("seq", 0))
            if seq <= int(self.data.get("last_seq", 0)):
                return
            result, reason = await self.execute(msg)
            self.data["last_seq"] = seq
            self._save()
            ack: dict[str, Any] = {"type": "ack", "seq": seq, "result": result}
            if reason:
                ack["reason"] = reason
            await ws.send_str(json.dumps(ack))

    # ---------------- execution ----------------

    def check(self, msg: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None]:
        """Local, authoritative checks. Returns (panel, control, rejection reason)."""
        panel = self.data["panels"].get(msg.get("panel_id"))
        if panel is None:
            return None, None, "not_allowed"
        control = panel["controls"].get(msg.get("control_id"))
        if control is None:
            return panel, None, "not_allowed"
        now = time.time()
        age = now + self._clock_offset - msg.get("ts", 0) / 1000
        if age > COMMAND_TTL_SECONDS:
            return panel, control, "expired"
        if panel.get("revoked"):
            return panel, control, "expired"
        if now < panel["valid_from"] or now >= panel["valid_until"]:
            return panel, control, "expired"
        if not schedule_allows(panel.get("schedule"), dt_util.now()):
            return panel, control, "outside_schedule"
        if control.get("max_uses") is not None and control.get("uses", 0) >= control["max_uses"]:
            return panel, control, "limit_reached"
        action = msg.get("action")
        if control["type"] == TYPE_SWITCH and action not in ("on", "off"):
            return panel, control, "not_allowed"
        if control["type"] != TYPE_SWITCH and action != "press":
            return panel, control, "not_allowed"
        if self.hass.states.get(control["entity_id"]) is None:
            return panel, control, "error"
        return panel, control, None

    async def execute(self, msg: dict[str, Any]) -> tuple[str, str | None]:
        panel, control, reason = self.check(msg)
        event = {
            "panel_id": msg.get("panel_id"),
            "panel_title": panel["title"] if panel else None,
            "control_id": msg.get("control_id"),
            "control_name": control["name"] if control else None,
            "entity_id": control["entity_id"] if control else None,
            "action": msg.get("action"),
            "result": "rejected" if reason else "ok",
            "reason": reason,
        }
        if reason is None and control is not None:
            try:
                await asyncio.wait_for(self._perform(control, msg["action"]), timeout=15)
                control["uses"] = control.get("uses", 0) + 1
                self._save()
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Could not run %s on %s: %s", msg.get("action"), control["entity_id"], err)
                event["result"], event["reason"], reason = "rejected", "error", "error"
        self.hass.bus.async_fire(EVENT_COMMAND, event)
        if reason:
            _LOGGER.info("Rejected guest command %s/%s: %s", msg.get("panel_id"), msg.get("control_id"), reason)
            return "rejected", reason
        _LOGGER.info("Guest of '%s' ran %s on %s", event["panel_title"], msg["action"], event["entity_id"])
        return "ok", None

    async def _perform(self, control: dict[str, Any], action: str) -> None:
        entity_id = control["entity_id"]
        domain = entity_id.split(".", 1)[0]
        ctx = Context()
        call = self.hass.services.async_call

        async def svc(service_domain: str, service: str) -> None:
            await call(service_domain, service, {"entity_id": entity_id}, blocking=True, context=ctx)

        if control["type"] == TYPE_SWITCH:
            if domain == "cover":
                await svc("cover", "open_cover" if action == "on" else "close_cover")
            elif domain == "valve":
                await svc("valve", "open_valve" if action == "on" else "close_valve")
            else:
                await svc(domain, "turn_on" if action == "on" else "turn_off")
            return

        how = control["action"]
        if how == "press":
            await svc(domain, "press")
        elif how == "run":
            await svc(domain, "turn_on")
        elif how == "unlock":
            await svc("lock", "unlock")
        elif how == "open":
            if domain == "lock":
                await svc("lock", "open")
            elif domain == "cover":
                await svc("cover", "open_cover")
            elif domain == "valve":
                await svc("valve", "open_valve")
            else:
                await svc(domain, "turn_on")
        elif how == "toggle":
            if domain == "cover":
                await svc("cover", "toggle")
            elif domain == "valve":
                await svc("valve", "toggle")
            else:
                await svc(domain, "toggle")
        elif how == "pulse":
            await svc(domain, "turn_on")
            await asyncio.sleep(float(control.get("pulse_seconds") or DEFAULT_PULSE_SECONDS))
            await svc(domain, "turn_off")
        else:
            raise ValueError(f"unknown action {how}")


class _PermanentError(Exception):
    """The portal rejected us; retrying quickly will not help."""


def schedule_allows(schedule: dict[str, Any] | None, now: datetime) -> bool:
    """Same rules as the portal: days of week and an HH:MM window that may cross midnight."""
    if not schedule:
        return True
    tz = schedule.get("tz")
    if tz:
        zone = dt_util.get_time_zone(tz)
        if zone is not None:
            now = now.astimezone(zone)
    days = schedule.get("days")
    if days and ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][now.weekday()] not in days:
        return False
    start, end = schedule.get("from"), schedule.get("to")
    if start and end:
        hm = now.strftime("%H:%M")
        return start <= hm < end if start < end else hm >= start or hm < end
    return True
