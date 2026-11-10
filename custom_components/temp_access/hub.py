"""Connection to the portal and execution of guest commands."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from datetime import datetime, timedelta
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, Context, HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .api import PortalApi, PortalConnectionError, PortalError
from .const import (
    BACKOFF_MAX,
    BACKOFF_MIN,
    COMMAND_TTL_SECONDS,
    DEFAULT_PULSE_SECONDS,
    DISCONNECTED_ISSUE_AFTER,
    DOMAIN,
    EVENT_COMMAND,
    PING_INTERVAL,
    PORTAL_SYNC_SECONDS,
    RECEIVE_TIMEOUT,
    SIGNAL_CONNECTION,
    SIGNAL_PANEL,
    STATUS_ACTIVE,
    STATUS_EXPIRED,
    STATUS_LOCKED,
    STATUS_NOT_STARTED,
    STATUS_OUTSIDE,
    STATUS_REVOKED,
    STORAGE_VERSION,
    SUBENTRY_PANEL,
    TYPE_SWITCH,
)

_LOGGER = logging.getLogger(__name__)


class AccessHub:
    """Keeps the WebSocket to the portal open and executes commands on mapped entities.

    Static panel definitions live in config subentries; changing state (uses, revocation,
    last guest action, lock reported by the portal) lives in a Store keyed by panel_id.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: PortalApi, session: aiohttp.ClientSession, instance_id: str) -> None:
        self.hass = hass
        self.entry = entry
        self.api = api
        self.instance_id = instance_id
        self._session = session
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self.data: dict[str, Any] = {"last_seq": 0, "runtime": {}}
        self.connected = False
        self._task: asyncio.Task | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._clock_offset = 0.0  # portal time minus local time, seconds
        self._stopping = False
        self._unsubs: list[CALLBACK_TYPE] = []
        self._issue_timer: CALLBACK_TYPE | None = None
        self._statuses: dict[str, str] = {}

    # ---------------- panels ----------------

    @property
    def panels(self) -> dict[str, dict[str, Any]]:
        """panel_id -> static definition (from subentries)."""
        return {
            s.data["panel_id"]: dict(s.data)
            for s in self.entry.subentries.values()
            if s.subentry_type == SUBENTRY_PANEL and "panel_id" in s.data
        }

    def subentry_id(self, panel_id: str) -> str | None:
        for s in self.entry.subentries.values():
            if s.data.get("panel_id") == panel_id:
                return s.subentry_id
        return None

    def runtime(self, panel_id: str) -> dict[str, Any]:
        return self.data["runtime"].setdefault(panel_id, {"uses": {}, "revoked": False, "locked": False, "failed_pin": 0, "last_action": None})

    def status(self, panel_id: str) -> str:
        from .panel import panel_status

        panel = self.panels.get(panel_id)
        if panel is None:
            return STATUS_EXPIRED
        return panel_status(panel, self.runtime(panel_id))

    async def async_revoke(self, panel_id: str) -> None:
        """Revoke locally first (works offline), then on the portal."""
        rt = self.runtime(panel_id)
        rt["revoked"] = True
        self._save()
        self._panel_changed(panel_id)
        try:
            await self.api.revoke_panel(panel_id)
        except PortalError as err:
            if err.status != 404:
                raise
        finally:
            from homeassistant.components import persistent_notification

            persistent_notification.async_dismiss(self.hass, f"{DOMAIN}_{panel_id}")

    @callback
    def _panel_changed(self, panel_id: str) -> None:
        self._statuses[panel_id] = self.status(panel_id)
        async_dispatcher_send(self.hass, f"{SIGNAL_PANEL}_{panel_id}")

    # ---------------- lifecycle ----------------

    async def async_load(self) -> None:
        stored = await self._store.async_load()
        if stored:
            self.data["last_seq"] = stored.get("last_seq", 0)
            self.data["runtime"] = stored.get("runtime", {})
        for pid in self.panels:
            self.runtime(pid)
            self._statuses[pid] = self.status(pid)

    @callback
    def _save(self) -> None:
        self._store.async_delay_save(lambda: self.data, 1)

    def start(self) -> None:
        self._stopping = False
        self._task = self.hass.async_create_background_task(self._run(), f"{DOMAIN}_connection")
        self._unsubs.append(async_track_time_interval(self.hass, self._tick, timedelta(seconds=30)))
        self._unsubs.append(async_track_time_interval(self.hass, self._sync_from_portal, timedelta(seconds=PORTAL_SYNC_SECONDS)))
        self._schedule_issue()

    async def stop(self) -> None:
        self._stopping = True
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._issue_timer:
            self._issue_timer()
            self._issue_timer = None
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        await self._store.async_save(self.data)
        self.connected = False

    @callback
    def _tick(self, _now: datetime | None = None) -> None:
        """Statuses change with time (start, end, schedule); notify entities when they do."""
        for pid in self.panels:
            new = self.status(pid)
            if self._statuses.get(pid) != new:
                self._statuses[pid] = new
                async_dispatcher_send(self.hass, f"{SIGNAL_PANEL}_{pid}")

    async def _sync_from_portal(self, _now: datetime | None = None) -> None:
        """Pick up what only the portal knows: PIN lockouts and failed attempts."""
        try:
            remote = {p["panel_id"]: p for p in await self.api.list_panels()}
        except (PortalError, PortalConnectionError) as err:
            _LOGGER.debug("Portal sync failed: %s", err)
            return
        for pid in self.panels:
            p = remote.get(pid)
            if p is None:
                continue
            rt = self.runtime(pid)
            locked = p.get("status") == STATUS_LOCKED
            failed = int(p.get("failed_pin_attempts", 0))
            if p.get("status") == STATUS_REVOKED and not rt["revoked"]:
                rt["revoked"] = True
            if rt.get("locked") != locked or rt.get("failed_pin") != failed:
                rt["locked"], rt["failed_pin"] = locked, failed
            self._save()
            self._panel_changed(pid)

    # ---------------- connection ----------------

    @callback
    def _set_connected(self, value: bool) -> None:
        if self.connected == value:
            return
        self.connected = value
        async_dispatcher_send(self.hass, f"{SIGNAL_CONNECTION}_{self.instance_id}", value)
        if value:
            if self._issue_timer:
                self._issue_timer()
                self._issue_timer = None
            ir.async_delete_issue(self.hass, DOMAIN, f"disconnected_{self.entry.entry_id}")
        else:
            self._schedule_issue()

    @callback
    def _schedule_issue(self) -> None:
        if self._issue_timer or self._stopping:
            return

        @callback
        def _raise(_now: datetime) -> None:
            self._issue_timer = None
            if not self.connected and not self._stopping:
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    f"disconnected_{self.entry.entry_id}",
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="disconnected",
                    translation_placeholders={"name": self.entry.title, "url": self.api.base_url},
                )

        self._issue_timer = async_call_later(self.hass, DISCONNECTED_ISSUE_AFTER, _raise)

    async def _run(self) -> None:
        backoff = BACKOFF_MIN
        while not self._stopping:
            try:
                await self._connect_once()
                backoff = BACKOFF_MIN
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
            self.hass.async_create_task(self._sync_from_portal())
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
        panel_id = msg.get("panel_id")
        panel = self.panels.get(panel_id)
        if panel is None:
            return None, None, "not_allowed"
        control = panel["controls"].get(msg.get("control_id"))
        if control is None:
            return panel, None, "not_allowed"
        age = time.time() + self._clock_offset - msg.get("ts", 0) / 1000
        if age > COMMAND_TTL_SECONDS:
            return panel, control, "expired"
        status = self.status(panel_id)
        if status in (STATUS_REVOKED, STATUS_EXPIRED, STATUS_NOT_STARTED, STATUS_LOCKED):
            return panel, control, "expired"
        if status == STATUS_OUTSIDE:
            return panel, control, "outside_schedule"
        uses = self.runtime(panel_id)["uses"].get(msg.get("control_id"), 0)
        if control.get("max_uses") is not None and uses >= control["max_uses"]:
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
        panel_id = msg.get("panel_id")
        event = {
            "panel_id": panel_id,
            "panel_title": panel["title"] if panel else None,
            "control_id": msg.get("control_id"),
            "control_name": control["name"] if control else None,
            "entity_id": control["entity_id"] if control else None,
            "action": msg.get("action"),
            "result": "rejected" if reason else "ok",
            "reason": reason,
        }
        ctx = Context()
        if reason is None and control is not None:
            try:
                await asyncio.wait_for(self._perform(control, msg["action"], ctx), timeout=15)
                uses = self.runtime(panel_id)["uses"]
                uses[msg["control_id"]] = uses.get(msg["control_id"], 0) + 1
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Could not run %s on %s: %s", msg.get("action"), control["entity_id"], err)
                event["result"], event["reason"], reason = "rejected", "error", "error"
        if panel is not None:
            self.runtime(panel_id)["last_action"] = {
                "time": dt_util.utcnow().isoformat(),
                "control": event["control_name"],
                "entity_id": event["entity_id"],
                "action": event["action"],
                "result": event["result"],
                "reason": event["reason"],
            }
            self._save()
            self._panel_changed(panel_id)
        self.hass.bus.async_fire(EVENT_COMMAND, event, context=ctx)
        if reason:
            _LOGGER.info("Rejected guest command %s/%s: %s", panel_id, msg.get("control_id"), reason)
            return "rejected", reason
        _LOGGER.info("Guest of '%s' ran %s on %s", event["panel_title"], msg["action"], event["entity_id"])
        return "ok", None

    async def _perform(self, control: dict[str, Any], action: str, ctx: Context) -> None:
        entity_id = control["entity_id"]
        domain = entity_id.split(".", 1)[0]
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
