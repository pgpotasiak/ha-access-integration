# Temporary Access for Home Assistant

*[Polska wersja](README.pl.md)*

Send a guest a link and a PIN that lets them control chosen Home Assistant entities, or just see their state, for a limited time. Home Assistant is never exposed to the internet: it keeps an outgoing WebSocket open to a small portal, and it checks every guest command itself before running it.

The portal is a free Cloudflare Worker: [ha-access-portal](https://github.com/pgpotasiak/ha-access-portal). You need its address and a one-time invite code from whoever runs it. Requires Home Assistant 2025.6 or newer. MIT licence.

## Features

- **Guest page** on any phone: PIN, big buttons, hold-to-activate for gates, Polish and English, light and dark mode.
- **Time limits**: start and end, days of the week, daily hours (also overnight), use limits per control, instant revoke.
- **Read-outs**: show a guest a temperature, a door contact or whether a light is on, without giving any control.
- **Guest access** page in the Home Assistant sidebar: all panels with status, QR code, copy link and PIN, revoke, delete and a form for new panels.
- One **device per panel** with status, end time, last guest action, QR code and a *Revoke* button; guest actions appear in the logbook.
- A repair issue appears when the portal connection has been down for 15 minutes.

## Installation

**HACS** (recommended): HACS → ⋮ → *Custom repositories* → `https://github.com/pgpotasiak/ha-access-integration`, type *Integration*. Download *Temporary Access* and restart Home Assistant.

**Manual**: copy `custom_components/temp_access` to `/config/custom_components/` and restart.

Then *Settings → Devices & services → Add integration → Temporary Access*, enter the portal address and your invite code.

## Creating a panel

Open **Guest access** in the sidebar and press **New panel**, or use *Add guest panel* on the integration page, or the `temp_access.create_panel` action:

```yaml
action: temp_access.create_panel
data:
  title: Access for Mark
  duration:
    hours: 24
  days: [sat, sun]
  time_from: "08:00"
  time_to: "20:00"
  controls:
    - entity_id: light.garage
      name: Garage light
      show_state: true
    - entity_id: switch.gate_relay
      name: Gate
      type: button
      action: pulse
      pulse_seconds: 1
      max_uses: 3
    - entity_id: sensor.living_room_temperature
      name: Living room
```

The action returns `panel_id`, `panel_url` and `pin`. Send the link and the PIN to the guest in two separate messages.

| Control field | Meaning |
| --- | --- |
| `entity_id` | Entity to share |
| `name` | Name shown to the guest |
| `type` | `switch` (On/Off), `button` (hold for a second) or `sensor` (read-out only) |
| `action` | For buttons: `press`, `run`, `unlock`, `open`, `toggle`, `pulse` |
| `pulse_seconds` | Length of a `pulse` |
| `max_uses` | Use limit |
| `show_state` | Show the state of a switch or button to the guest |

Controllable domains: `light`, `switch`, `fan`, `input_boolean`, `siren`, `cover`, `valve`, `lock`, `button`, `input_button`, `script`, `scene`. Read-outs also work for `sensor`, `binary_sensor`, `input_number`, `input_select`, `input_text`, `counter`, `number`, `select`. People, trackers and cameras are deliberately not supported.

## Security

- The portal never learns entity IDs: it only knows `ctrl_1` and the name you gave it. The mapping to entities exists only in Home Assistant.
- Before running anything, Home Assistant checks the panel, the control, the time window, the schedule, the use limit and that the command is less than 30 seconds old. Commands sent while Home Assistant was offline never run later.
- The portal stores only the latest value of entities you chose to show, and only while the panel exists.
- Revoking works locally at once, even when the portal is unreachable.
- Every guest action fires a `temp_access_command` event you can use in automations.

## Tests

The tests run a real Home Assistant against a local copy of the portal (`npx wrangler dev --port 8787 --ip 127.0.0.1` in the portal repository), then `pytest`.
