"""Constants for the Efergy integration."""

from datetime import timedelta
import logging
from typing import Final

DEFAULT_NAME = "Efergy (Custom)"
DOMAIN: Final = "efergy"

# API endpoints
BASE_URL: Final = "https://engage.efergy.com"
INTERSTITIAL_URL: Final = "http://engage.efergy.com"
GET_ENERGY_URL: Final = f"{BASE_URL}/mobile_proxy/getEnergy"
GET_INSTANT_URL: Final = f"{BASE_URL}/mobile_proxy/getInstant"
CONFIGURATION_URL: Final = f"{BASE_URL}/user/login"
INTERSTITIAL_TEXT: Final = "continue to engage.efergy.com"

# Headers for API requests
API_HEADERS: Final = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": BASE_URL + "/",
    "Host": "engage.efergy.com",
    "Connection": "keep-alive",
}

LOGGER = logging.getLogger(__package__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)