"""End-to-end tests: the integration inside a test Home Assistant talks to a real portal (wrangler dev).

Run the portal first:  npx wrangler dev --port 8787 --ip 127.0.0.1
"""

from __future__ import annotations

import asyncio
import os
import time
from datetime import timedelta

import aiohttp
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.temp_access.const import DOMAIN, EVENT_COMMAND
from custom_components.temp_access.hub import schedule_allows

PORTAL = os.environ.get("PORTAL_URL", "http://127.0.0.1:8787")
ADMIN = os.environ.get("ADMIN_TOKEN", "dev-admin-token")


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def allow_network(socket_enabled):
    """These tests talk to a real portal on 127.0.0.1."""
    import pytest_socket

    pytest_socket.socket_allow_hosts(["127.0.0.1"], allow_unix_socket=True)
    yield


async def _json(session: aiohttp.ClientSession, method: str, path: str, *, body=None, headers=None):
    async with session.request(method, PORTAL + path, json=body, headers=headers or {}) as r:
        try:
            return r.status, await r.json(content_type=None)
        except Exception:  # noqa: BLE001
            return r.status, None


class Guest:
    def __init__(self, session: aiohttp.ClientSession, url: str) -> None:
        self.s = session
        self.path = url.replace(PORTAL, "")
        self.cookie = ""

    async def call(self, method: str, sub: str, body=None):
        async with self.s.request(
            method,
            f"{PORTAL}{self.path}/api/{sub}",
            json=body,
            headers={"x-requested-with": "access", "cookie": self.cookie, "cf-connecting-ip": "203.0.113.5"},
        ) as r:
            sc = r.headers.get("set-cookie")
            if sc:
                self.cookie = sc.split(";")[0]
            try:
                return r.status, await r.json(content_type=None)
            except Exception:  # noqa: BLE001
                return r.status, None

    async def press(self, control: str, action: str, want: str, timeout: float = 8):
        st, data = await self.call("POST", "press", {"control_id": control, "action": action})
        assert st == 200, (st, data)
        end = time.monotonic() + timeout
        last = None
        while time.monotonic() < end:
            _, last = await self.call("GET", f"status/{data['seq']}")
            if last and last.get("status") == want:
                return last
            await asyncio.sleep(0.2)
        raise AssertionError(f"status never became {want}: {last}")


async def wait_for(cond, timeout: float = 10, step: float = 0.1):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        await asyncio.sleep(step)
    return False


def test_schedule_rules():
    tz = dt_util.get_time_zone("Europe/Warsaw")
    wed_10 = dt_util.as_utc(dt_util.parse_datetime("2026-11-11T10:00:00").replace(tzinfo=tz))
    wed_23 = dt_util.as_utc(dt_util.parse_datetime("2026-11-11T23:30:00").replace(tzinfo=tz))
    base = {"tz": "Europe/Warsaw"}
    assert schedule_allows(None, wed_10)
    assert schedule_allows({**base, "days": ["wed"]}, wed_10)
    assert not schedule_allows({**base, "days": ["mon", "tue"]}, wed_10)
    assert schedule_allows({**base, "from": "08:00", "to": "16:00"}, wed_10)
    assert not schedule_allows({**base, "from": "08:00", "to": "16:00"}, wed_23)
    assert schedule_allows({**base, "from": "22:00", "to": "06:00"}, wed_23)
    assert not schedule_allows({**base, "from": "22:00", "to": "06:00"}, wed_10)


async def test_full_flow_against_live_portal(hass: HomeAssistant) -> None:
    async with aiohttp.ClientSession() as s:
        st, _ = await _json(s, "GET", "/")
        if st != 200:
            pytest.skip("portal is not running")
        st, inv = await _json(s, "POST", "/api/v1/admin/invites", headers={"Authorization": f"Bearer {ADMIN}"})
        assert st == 201

        # Entities a guest will control.
        assert await async_setup_component(
            hass, "input_boolean", {"input_boolean": {"garaz": {"name": "Światło garaż"}, "przekaznik": {"name": "Przekaźnik bramy"}}}
        )
        await hass.async_block_till_done()

        # ---------- config flow ----------
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        assert result["type"] == "form"
        bad = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"portal_url": PORTAL, "invite_code": "INV-wrong", "name": "Dom testowy"}
        )
        assert bad["type"] == "form" and bad["errors"] == {"base": "invalid_invite"}
        done = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"portal_url": PORTAL, "invite_code": inv["invite_code"], "name": "Dom testowy"}
        )
        assert done["type"] == "create_entry", done
        entry = done["result"]
        await hass.async_block_till_done()

        sensor = "binary_sensor.dom_testowy_portal_connection"
        assert await wait_for(lambda: (st := hass.states.get(sensor)) is not None and st.state == "on"), hass.states.async_entity_ids("binary_sensor")

        events = []
        hass.bus.async_listen(EVENT_COMMAND, lambda e: events.append(e.data))

        # ---------- create a panel ----------
        resp = await hass.services.async_call(
            DOMAIN,
            "create_panel",
            {
                "title": "Dostęp dla Marka",
                "duration": {"hours": 24},
                "controls": [
                    {"entity_id": "input_boolean.garaz"},
                    {"entity_id": "input_boolean.przekaznik", "name": "Brama wjazdowa", "type": "button", "action": "pulse", "pulse_seconds": 0.3, "max_uses": 2},
                ],
            },
            blocking=True,
            return_response=True,
        )
        assert resp["panel_url"].startswith(PORTAL + "/p/")
        assert len(resp["pin"]) == 4
        hub = hass.data[DOMAIN][entry.entry_id]
        assert resp["panel_id"] in hub.data["panels"]

        g = Guest(s, resp["panel_url"])
        st, data = await g.call("POST", "unlock", {"pin": resp["pin"]})
        assert st == 200, data
        st, state = await g.call("GET", "state")
        assert state["online"] is True and [c["name"] for c in state["controls"]] == ["Światło garaż", "Brama wjazdowa"]

        # ---------- switch ----------
        await g.press("ctrl_1", "on", "done")
        assert hass.states.get("input_boolean.garaz").state == "on"
        await g.press("ctrl_1", "off", "done")
        assert hass.states.get("input_boolean.garaz").state == "off"

        # ---------- pulse button ----------
        seen = []
        hass.bus.async_listen("state_changed", lambda e: e.data["entity_id"] == "input_boolean.przekaznik" and seen.append(e.data["new_state"].state))
        await g.press("ctrl_2", "press", "done")
        assert await wait_for(lambda: seen[-2:] == ["on", "off"]), seen
        assert hub.data["panels"][resp["panel_id"]]["controls"]["ctrl_2"]["uses"] == 1

        assert events[0]["result"] == "ok" and events[0]["entity_id"] == "input_boolean.garaz"
        assert events[-1]["control_name"] == "Brama wjazdowa"

        # ---------- HA enforces validity even if the portal would allow ----------
        hub.data["panels"][resp["panel_id"]]["valid_until"] = time.time() - 1
        r = await g.press("ctrl_1", "on", "rejected")
        assert r["reason"] == "expired"
        assert hass.states.get("input_boolean.garaz").state == "off"
        hub.data["panels"][resp["panel_id"]]["valid_until"] = time.time() + 3600

        # ---------- HA enforces the use limit locally too ----------
        hub.data["panels"][resp["panel_id"]]["controls"]["ctrl_2"]["uses"] = 2
        r = await g.press("ctrl_2", "press", "rejected")
        assert r["reason"] == "limit_reached"
        hub.data["panels"][resp["panel_id"]]["controls"]["ctrl_2"]["uses"] = 1

        # ---------- a panel HA does not know is refused ----------
        st, foreign = await _json(
            s, "POST", "/api/v1/panels",
            body={"pin": "1234", "title": "Obcy", "valid_until": (dt_util.utcnow() + timedelta(hours=1)).isoformat(),
                  "controls": [{"id": "ctrl_1", "name": "X", "type": "switch"}]},
            headers={"Authorization": f"Bearer {entry.data['api_key']}"},
        )
        assert st == 201
        g2 = Guest(s, foreign["panel_url"])
        await g2.call("POST", "unlock", {"pin": "1234"})
        r = await g2.press("ctrl_1", "on", "rejected")
        assert r["reason"] == "not_allowed"
        assert hass.states.get("input_boolean.garaz").state == "off"

        # ---------- reconnect after the connection drops ----------
        await hub._ws.close()
        assert await wait_for(lambda: hass.states.get(sensor).state == "off", timeout=5)
        assert await wait_for(lambda: hass.states.get(sensor).state == "on", timeout=10)
        await g.press("ctrl_1", "on", "done")
        assert hass.states.get("input_boolean.garaz").state == "on"

        # ---------- validation errors ----------
        with pytest.raises(Exception, match="cannot be shared"):
            await hass.services.async_call(DOMAIN, "create_panel", {"title": "x", "controls": [{"entity_id": "sensor.foo"}]}, blocking=True, return_response=True)
        with pytest.raises(Exception, match="not found"):
            await hass.services.async_call(DOMAIN, "create_panel", {"title": "x", "controls": [{"entity_id": "light.nope"}]}, blocking=True, return_response=True)

        # ---------- schedule is passed to the portal ----------
        today = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][dt_util.now().weekday()]
        other_days = [d for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] if d != today]
        sched = await hass.services.async_call(
            DOMAIN, "create_panel",
            {"title": "Weekend", "days": other_days, "controls": [{"entity_id": "input_boolean.garaz"}]},
            blocking=True, return_response=True,
        )
        g3 = Guest(s, sched["panel_url"])
        await g3.call("POST", "unlock", {"pin": sched["pin"]})
        _, st3 = await g3.call("GET", "state")
        assert st3["status"] == "outside_schedule"

        # ---------- revoke ----------
        await hass.services.async_call(DOMAIN, "revoke_panel", {"panel_id": resp["panel_id"]}, blocking=True)
        _, after = await g.call("GET", "state")
        assert after["status"] == "revoked"
        assert hub.data["panels"][resp["panel_id"]]["revoked"] is True

        # ---------- restart keeps panels and last_seq ----------
        last_seq = hub.data["last_seq"]
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        hub2 = hass.data[DOMAIN][entry.entry_id]
        assert hub2.data["last_seq"] == last_seq and sched["panel_id"] in hub2.data["panels"]
        assert await wait_for(lambda: hass.states.get(sensor).state == "on")

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
