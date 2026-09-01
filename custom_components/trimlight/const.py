"""Constants for the Trimlight integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "trimlight"
CONF_DID: Final = "did"
MANUFACTURER: Final = "Trimlight"
SCAN_INTERVAL: Final = timedelta(seconds=30)
