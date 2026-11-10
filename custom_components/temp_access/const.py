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
TYPE_SENSOR = "sensor"  # read-only: the guest sees the value

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
CONTROL_DOMAINS = SWITCH_DOMAINS | set(BUTTON_DEFAULT_ACTION)
# Entities whose value a guest may see. People, trackers and cameras are left out on purpose.
READ_ONLY_DOMAINS = {"sensor", "binary_sensor", "input_number", "input_select", "input_text", "counter", "number", "select"}
READ_DOMAINS = READ_ONLY_DOMAINS | CONTROL_DOMAINS - {"button", "input_button", "script", "scene"}
ALLOWED_DOMAINS = CONTROL_DOMAINS | READ_DOMAINS

# At most one value update per control per this many seconds (keeps the portal within free limits).
STATE_THROTTLE_SENSOR = 30
STATE_THROTTLE_CONTROL = 2
DEFAULT_PULSE_SECONDS = 1.0

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

SUBENTRY_PANEL = "panel"
SIGNAL_PANEL = f"{DOMAIN}_panel"  # + _<panel_id>

STATUS_ACTIVE = "active"
STATUS_NOT_STARTED = "not_started"
STATUS_OUTSIDE = "outside_schedule"
STATUS_EXPIRED = "expired"
STATUS_REVOKED = "revoked"
STATUS_LOCKED = "locked"
STATUSES = [STATUS_ACTIVE, STATUS_NOT_STARTED, STATUS_OUTSIDE, STATUS_EXPIRED, STATUS_REVOKED, STATUS_LOCKED]

# Forget a panel (and remove its device) this long after it ended; the portal deletes it too.
PANEL_RETENTION_SECONDS = 7 * 86400
PORTAL_SYNC_SECONDS = 15 * 60
DISCONNECTED_ISSUE_AFTER = 15 * 60
