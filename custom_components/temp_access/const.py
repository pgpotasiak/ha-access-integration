"""Constants for the Temporary Access integration."""

from __future__ import annotations

DOMAIN = "temp_access"

CONF_PORTAL_URL = "portal_url"
CONF_INVITE_CODE = "invite_code"
CONF_INSTANCE_ID = "instance_id"
CONF_API_KEY = "api_key"

DEFAULT_PORTAL_URL = "https://access.iloveha.workers.dev"

STORAGE_VERSION = 1

# Commands older than this are never executed (the portal uses the same limit).
COMMAND_TTL_SECONDS = 30
PING_INTERVAL = 30
# No message (not even a pong) for this long means the connection is dead.
RECEIVE_TIMEOUT = 75
BACKOFF_MIN = 1
BACKOFF_MAX = 60

SIGNAL_CONNECTION = f"{DOMAIN}_connection"
EVENT_COMMAND = f"{DOMAIN}_command"

TYPE_SWITCH = "switch"
TYPE_BUTTON = "button"

# Domains a guest may control, and how.
SWITCH_DOMAINS = {"light", "switch", "fan", "input_boolean", "cover", "valve", "siren"}
BUTTON_DEFAULT_ACTION = {
    "button": "press",
    "input_button": "press",
    "script": "run",
    "scene": "run",
    "lock": "unlock",
    "cover": "toggle",
    "valve": "toggle",
    "light": "pulse",
    "switch": "pulse",
    "input_boolean": "pulse",
    "fan": "toggle",
    "siren": "pulse",
}
BUTTON_ACTIONS = {"press", "run", "unlock", "open", "toggle", "pulse"}
ALLOWED_DOMAINS = SWITCH_DOMAINS | set(BUTTON_DEFAULT_ACTION)
DEFAULT_PULSE_SECONDS = 1.0

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
