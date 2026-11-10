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
ADMIN = os.environ.get("ADMIN_TOKEN", "dev-admin-token-0123456789")


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


def ent(hass: HomeAssistant, platform: str, unique_id: str) -> str:
    from homeassistant.helpers import entity_registry as er

    eid = er.async_get(hass).async_get_entity_id(platform, DOMAIN, unique_id)
    assert eid, f"no {platform} entity with unique_id {unique_id}"
    return eid


async def settle(hass: HomeAssistant, entry, sensor: str):
    """After a reload: let it finish, return the new hub and wait for the connection."""
    await hass.async_block_till_done()
    hub = hass.data[DOMAIN][entry.entry_id]
    assert await wait_for(lambda: (st := hass.states.get(sensor)) is not None and st.state == "on"), "not connected"
    return hub


async def test_full_flow_against_live_portal(hass: HomeAssistant, monkeypatch, hass_ws_client) -> None:
    from custom_components.temp_access import hub as hub_mod

    monkeypatch.setattr(hub_mod, "DISCONNECTED_ISSUE_AFTER", 0.5)
    async with aiohttp.ClientSession() as s:
        st, _ = await _json(s, "GET", "/")
        if st != 200:
            pytest.skip("portal is not running")
        admin = {"Authorization": f"Bearer {ADMIN}"}
        st, inv = await _json(s, "POST", "/api/v1/admin/invites", headers=admin)
        assert st == 201

        assert await async_setup_component(
            hass, "input_boolean", {"input_boolean": {"garaz": {"name": "Światło garaż"}, "przekaznik": {"name": "Przekaźnik bramy"}}}
        )
        assert await async_setup_component(hass, "script", {"script": {"furtka": {"sequence": [{"event": "furtka_otwarta"}]}}})
        await hass.async_block_till_done()

        # ---------- config flow ----------
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        bad = await hass.config_entries.flow.async_configure(result["flow_id"], {"portal_url": PORTAL, "invite_code": "INV-wrong", "name": "Dom testowy"})
        assert bad["errors"] == {"base": "invalid_invite"}
        done = await hass.config_entries.flow.async_configure(result["flow_id"], {"portal_url": PORTAL, "invite_code": inv["invite_code"], "name": "Dom testowy"})
        assert done["type"] == "create_entry", done
        entry = done["result"]
        sensor = "binary_sensor.dom_testowy_portal_connection"
        hub = await settle(hass, entry, sensor)

        events = []
        hass.bus.async_listen(EVENT_COMMAND, lambda e: events.append(e))

        # ---------- panel from the action ----------
        resp = await hass.services.async_call(
            DOMAIN, "create_panel",
            {
                "title": "Dostęp dla Marka",
                "duration": {"hours": 24},
                "controls": [
                    {"entity_id": "input_boolean.garaz"},
                    {"entity_id": "input_boolean.przekaznik", "name": "Brama wjazdowa", "type": "button", "action": "pulse", "pulse_seconds": 0.3, "max_uses": 2},
                ],
            },
            blocking=True, return_response=True,
        )
        pid = resp["panel_id"]
        hub = await settle(hass, entry, sensor)
        assert pid in hub.panels and len(entry.subentries) == 1

        status = ent(hass, "sensor", f"{pid}_status")
        assert hass.states.get(status).state == "active"
        assert hass.states.get(ent(hass, "sensor", f"{pid}_link")).state == resp["panel_url"]
        assert hass.states.get(ent(hass, "sensor", f"{pid}_pin")).state == resp["pin"]
        assert hass.states.get(ent(hass, "sensor", f"{pid}_valid_until")).state.startswith(resp["valid_until"][:16])
        qr = ent(hass, "image", f"{pid}_qr")
        png = await hass.data["image"].get_entity(qr).async_image()
        assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 500
        from homeassistant.helpers import device_registry as dr

        dev = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, pid)})
        assert dev and dev.name == "Dostęp dla Marka"

        g = Guest(s, resp["panel_url"])
        st, data = await g.call("POST", "unlock", {"pin": resp["pin"]})
        assert st == 200, data

        # ---------- guest controls ----------
        await g.press("ctrl_1", "on", "done")
        assert hass.states.get("input_boolean.garaz").state == "on"
        last = ent(hass, "sensor", f"{pid}_last_action")
        assert await wait_for(lambda: hass.states.get(last).state == "Guest turned on: Światło garaż"), hass.states.get(last)
        await g.press("ctrl_1", "off", "done")
        assert hass.states.get("input_boolean.garaz").state == "off"

        seen = []
        hass.bus.async_listen("state_changed", lambda e: e.data["entity_id"] == "input_boolean.przekaznik" and seen.append(e.data["new_state"].state))
        await g.press("ctrl_2", "press", "done")
        assert await wait_for(lambda: seen[-2:] == ["on", "off"]), seen
        assert hub.runtime(pid)["uses"]["ctrl_2"] == 1
        attrs = hass.states.get(status).attributes
        assert await wait_for(lambda: hass.states.get(status).attributes.get("uses_left_Brama wjazdowa") == 1), attrs

        # The guest action and the entity change share one context (logbook links them).
        assert events[0].data["result"] == "ok" and events[0].data["entity_id"] == "input_boolean.garaz"

        # ---------- logbook text ----------
        from custom_components.temp_access import logbook as lb

        described = {}
        lb.async_describe_events(hass, lambda d, ev, fn: described.setdefault("fn", fn))
        entry_text = described["fn"](events[0])
        assert entry_text["name"] == "Dostęp dla Marka" and "Światło garaż" in entry_text["message"] and entry_text["entity_id"] == last

        # ---------- HA enforces validity even if the portal would allow it ----------
        sub = next(iter(entry.subentries.values()))
        original = dict(sub.data)
        hass.config_entries.async_update_subentry(entry, sub, data={**original, "valid_until": time.time() - 1})
        hub = await settle(hass, entry, sensor)
        assert hass.states.get(status).state == "expired"
        r = await g.press("ctrl_1", "on", "rejected")
        assert r["reason"] == "expired" and hass.states.get("input_boolean.garaz").state == "off"
        hass.config_entries.async_update_subentry(entry, sub, data=original)
        hub = await settle(hass, entry, sensor)
        assert hass.states.get(status).state == "active"

        # ---------- local use limit ----------
        hub.runtime(pid)["uses"]["ctrl_2"] = 2
        r = await g.press("ctrl_2", "press", "rejected")
        assert r["reason"] == "limit_reached"
        assert await wait_for(lambda: hass.states.get(last).state.startswith("Rejected (use limit)")), hass.states.get(last)

        # ---------- panel from the UI form (subentry flow) ----------
        flow = await hass.config_entries.subentries.async_init((entry.entry_id, "panel"), context={"source": "user"})
        assert flow["type"] == "form" and flow["step_id"] == "user"
        bad = await hass.config_entries.subentries.async_configure(
            flow["flow_id"], {"title": "Z formularza", "entities": ["input_boolean.garaz"], "duration": {"days": 0, "hours": 2, "minutes": 0}, "time_from": "08:00:00", "language": "pl"}
        )
        assert bad["errors"] == {"base": "hours_pair"}
        step = await hass.config_entries.subentries.async_configure(
            flow["flow_id"],
            {"title": "Z formularza", "entities": ["input_boolean.garaz", "script.furtka"], "duration": {"days": 0, "hours": 2, "minutes": 0}, "pin": "13579", "language": "pl"},
        )
        assert step["step_id"] == "control" and step["description_placeholders"]["index"] == "1"
        step = await hass.config_entries.subentries.async_configure(flow["flow_id"], {"name": "Garaż", "type": "switch", "action": "pulse"})
        assert step["step_id"] == "control" and step["description_placeholders"]["entity_id"] == "script.furtka"
        done = await hass.config_entries.subentries.async_configure(flow["flow_id"], {"name": "Furtka", "max_uses": 1})
        assert done["type"] == "create_entry", done
        hub = await settle(hass, entry, sensor)
        form_pid = next(p for p, d in hub.panels.items() if d["title"] == "Z formularza")
        form = hub.panels[form_pid]
        assert form["pin"] == "13579" and form["controls"]["ctrl_2"] == {**form["controls"]["ctrl_2"], "type": "button", "action": "run", "max_uses": 1}
        g2 = Guest(s, form["url"])
        assert (await g2.call("POST", "unlock", {"pin": "13579"}))[0] == 200
        fired = []
        hass.bus.async_listen("furtka_otwarta", lambda e: fired.append(e))
        await g2.press("ctrl_2", "press", "done")
        assert await wait_for(lambda: len(fired) == 1)

        # ---------- revoke button ----------
        btn = ent(hass, "button", f"{form_pid}_revoke")
        await hass.services.async_call("button", "press", {"entity_id": btn}, blocking=True)
        assert hass.states.get(ent(hass, "sensor", f"{form_pid}_status")).state == "revoked"
        assert hass.states.get(btn).state == "unavailable"
        _, after = await g2.call("GET", "state")
        assert after["status"] == "revoked"

        # ---------- deleting the panel device's subentry revokes it on the portal ----------
        sub_id = hub.subentry_id(pid)
        hass.config_entries.async_remove_subentry(entry, sub_id)
        hub = await settle(hass, entry, sensor)
        assert await wait_for(lambda: pid not in hub.data["runtime"])
        _, after = await g.call("GET", "state")
        assert after["status"] == "revoked"
        assert dr.async_get(hass).async_get_device(identifiers={(DOMAIN, pid)}) is None

        # ---------- PIN lockout reported by the portal ----------
        lock = await hass.services.async_call(DOMAIN, "create_panel", {"title": "Blokada", "controls": [{"entity_id": "input_boolean.garaz"}]}, blocking=True, return_response=True)
        hub = await settle(hass, entry, sensor)
        for i in range(20):
            async with s.post(f"{lock['panel_url']}/api/unlock", json={"pin": "0000"}, headers={"x-requested-with": "access", "cf-connecting-ip": f"198.51.100.{i}"}) as r:
                await r.read()
        await hub._sync_from_portal()
        lock_status = ent(hass, "sensor", f"{lock['panel_id']}_status")
        assert await wait_for(lambda: hass.states.get(lock_status).state == "locked"), hass.states.get(lock_status)
        assert hass.states.get(lock_status).attributes["failed_pin_attempts"] == 20

        # ---------- reconnect after the connection drops ----------
        await hub._ws.close()
        assert await wait_for(lambda: hass.states.get(sensor).state == "off", timeout=5)
        assert await wait_for(lambda: hass.states.get(sensor).state == "on", timeout=10)

        # ---------- repair issue when the portal refuses us for a while ----------
        from homeassistant.helpers import issue_registry as ir

        st, _ = await _json(s, "POST", f"/api/v1/admin/instances/{entry.data['instance_id']}/block", body={"blocked": True}, headers=admin)
        assert st == 200
        issue_id = f"disconnected_{entry.entry_id}"
        assert await wait_for(lambda: ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is not None, timeout=5)
        await _json(s, "POST", f"/api/v1/admin/instances/{entry.data['instance_id']}/block", body={"blocked": False}, headers=admin)
        assert await hass.config_entries.async_reload(entry.entry_id)
        hub = await settle(hass, entry, sensor)
        assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None

        # ---------- validation errors from the action ----------
        with pytest.raises(Exception, match="cannot be shared"):
            await hass.services.async_call(DOMAIN, "create_panel", {"title": "x", "controls": [{"entity_id": "sensor.foo"}]}, blocking=True, return_response=True)
        with pytest.raises(Exception, match="not found"):
            await hass.services.async_call(DOMAIN, "create_panel", {"title": "x", "controls": [{"entity_id": "light.nope"}]}, blocking=True, return_response=True)

        # ---------- sidebar page: panel registered, WebSocket commands ----------
        assert "guest-access" in hass.data["frontend_panels"]
        assert hass.data["frontend_panels"]["guest-access"].require_admin
        client = await hass_ws_client(hass)
        await client.send_json({"id": 1, "type": "temp_access/list"})
        res = await client.receive_json()
        assert res["success"], res
        lst = res["result"]
        assert lst["entries"][0]["connected"] is True and "input_boolean" in lst["domains"] and lst["actions"]["lock"] == ["unlock", "open"]
        by_title = {p["title"]: p for p in lst["panels"]}
        assert set(by_title) >= {"Z formularza", "Blokada"}
        zf = by_title["Z formularza"]
        assert zf["status"] == "revoked" and zf["entities"]["qr"] and zf["controls"][1]["type"] == "button" and zf["last_action"]["result"] == "ok"

        # create through call_service with a response, as the page does
        await client.send_json({"id": 2, "type": "call_service", "domain": DOMAIN, "service": "create_panel", "return_response": True,
                                "service_data": {"title": "Ze strony", "duration": {"days": 0, "hours": 3, "minutes": 0}, "notify": False,
                                                 "valid_from": dt_util.now().replace(tzinfo=None).isoformat(timespec="minutes"),
                                                 "days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"], "time_from": "00:00", "time_to": "23:59",
                                                 "controls": [{"entity_id": "input_boolean.przekaznik", "type": "button", "action": "pulse", "pulse_seconds": 0.5, "max_uses": 3}]}})
        res = await client.receive_json()
        assert res["success"], res
        page_pid = res["result"]["response"]["panel_id"]
        hub = await settle(hass, entry, sensor)
        assert hub.panels[page_pid]["controls"]["ctrl_1"]["pulse_seconds"] == 0.5

        client = await hass_ws_client(hass)  # the reload does not drop it, but start clean
        await client.send_json({"id": 3, "type": "temp_access/revoke", "panel_id": page_pid})
        res = await client.receive_json()
        assert res["success"] and res["result"]["status"] == "revoked", res
        await client.send_json({"id": 4, "type": "temp_access/revoke", "panel_id": "nope"})
        assert (await client.receive_json())["error"]["code"] == "not_found"
        await client.send_json({"id": 5, "type": "temp_access/delete", "panel_id": page_pid})
        assert (await client.receive_json())["success"]
        hub = await settle(hass, entry, sensor)
        assert page_pid not in hub.panels

        # ---------- restart keeps everything ----------
        last_seq = hub.data["last_seq"]
        assert await hass.config_entries.async_reload(entry.entry_id)
        hub = await settle(hass, entry, sensor)
        assert hub.data["last_seq"] == last_seq and form_pid in hub.panels and hub.runtime(form_pid)["revoked"]

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
