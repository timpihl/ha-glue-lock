"""Constants for the Glue Lock integration."""

from __future__ import annotations

DOMAIN = "glue_lock"
MANUFACTURER = "Glue"

CONF_POLL_INTERVAL = "poll_interval"
CONF_FAST_POLL = "fast_poll_after_operation"

DEFAULT_POLL_INTERVAL = 30
MIN_POLL_INTERVAL = 15
MAX_POLL_INTERVAL = 3600
DEFAULT_FAST_POLL = True

# After a lock or unlock, Glue can report the new lock event some seconds late.
# The lock is read more often for a short time so the result shows up quickly.
FAST_POLL_INTERVAL = 5
FAST_POLL_WINDOW = 60

# Glue normally reports a final operation status after 5-10 seconds.
OPERATION_POLL_ATTEMPTS = 30
OPERATION_POLL_INTERVAL = 1

# A short API outage keeps the last known values. After this many failed
# reads in a row the entities become unavailable.
MAX_FAILURES_BEFORE_UNAVAILABLE = 3

API_KEY_NAME = "home-assistant"
