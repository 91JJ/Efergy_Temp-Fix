"""The Efergy integration."""

from __future__ import annotations

from pyefergy import Efergy, exceptions
from lxml import html

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import BASE_URL, INTERSTITIAL_URL, INTERSTITIAL_TEXT, API_HEADERS

PLATFORMS = [Platform.SENSOR]
type EfergyConfigEntry = ConfigEntry[Efergy]


async def async_setup_entry(hass: HomeAssistant, entry: EfergyConfigEntry) -> bool:
    """Set up Efergy from a config entry."""
    api = Efergy(
        entry.data[CONF_API_KEY],
        session=async_get_clientsession(hass),
        utc_offset=hass.config.time_zone,
        currency=hass.config.currency,
    )

    try:
        # Attempt to fetch status
        response = await api.async_status()
        # Check if response is HTML indicating interstitial page
        if isinstance(response, str) and INTERSTITIAL_TEXT in response:
            async with async_get_clientsession(hass) as session:
                await session.get(INTERSTITIAL_URL, headers=API_HEADERS)  # Simulate button click
            response = await api.async_status()  # Retry
    except (exceptions.ConnectError, exceptions.DataError) as ex:
        raise ConfigEntryNotReady(f"Failed to connect to device: {ex}") from ex
    except exceptions.InvalidAuth as ex:
        raise ConfigEntryAuthFailed(
            "API Key is no longer valid. Please reauthenticate"
        ) from ex

    entry.runtime_data = api
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EfergyConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)