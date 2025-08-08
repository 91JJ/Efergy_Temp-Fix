"""Config flow for Efergy integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pyefergy import Efergy, exceptions
import voluptuous as vol
import json

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_NAME, DOMAIN, LOGGER, BASE_URL, INTERSTITIAL_URL, GET_ENERGY_URL, INTERSTITIAL_TEXT, API_HEADERS


class EfergyFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Efergy."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY]

            self._async_abort_entries_match({CONF_API_KEY: api_key})
            hid, error = await self._async_try_connect(api_key)
            if error is None:
                await self.async_set_unique_id(hid)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data={CONF_API_KEY: api_key},
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a reauthorization flow request."""
        return await self.async_step_user()

    async def _async_try_connect(self, api_key: str) -> tuple[str | None, str | None]:
        """Try connecting to Efergy servers."""
        session = async_get_clientsession(self.hass)
        max_retries = 3
        try:
            # Pre-visit homepage to establish session and cookies
            LOGGER.debug("Pre-visiting %s to establish session", BASE_URL)
            async with session.get(BASE_URL, headers=API_HEADERS) as home_response:
                LOGGER.debug(
                    "Homepage response status: %s, Headers: %s, Cookies: %s",
                    home_response.status,
                    dict(home_response.headers),
                    session.cookie_jar.filter_cookies(BASE_URL),
                )
                if "text/html" in home_response.headers.get("Content-Type", "") and INTERSTITIAL_TEXT in await home_response.text():
                    LOGGER.debug("Interstitial page detected on homepage, bypassing")
                    async with session.get(INTERSTITIAL_URL, headers=API_HEADERS) as interstitial_response:
                        LOGGER.debug(
                            "Interstitial response status: %s, Headers: %s, Cookies: %s",
                            interstitial_response.status,
                            dict(interstitial_response.headers),
                            session.cookie_jar.filter_cookies(BASE_URL),
                        )
        except Exception as e:
            LOGGER.warning("Failed to pre-visit homepage: %s", str(e))

        for attempt in range(max_retries):
            try:
                url = f"{GET_ENERGY_URL}?token={api_key}&period=year&offset=0"
                LOGGER.debug("Attempt %s: Sending request to %s with headers: %s", attempt + 1, url, API_HEADERS)
                async with session.get(url, headers=API_HEADERS) as response:
                    content_type = response.headers.get("Content-Type", "")
                    LOGGER.debug(
                        "Attempt %s: Response status: %s, Content-Type: %s, Headers: %s, Cookies: %s",
                        attempt + 1,
                        response.status,
                        content_type,
                        dict(response.headers),
                        session.cookie_jar.filter_cookies(BASE_URL),
                    )
                    if response.status == 400:
                        error_data = await response.json()
                        LOGGER.error("Attempt %s: Bad request error: %s", attempt + 1, error_data)
                        return None, "invalid_auth" if "Bad Request" in str(error_data) else "unknown"
                    if response.status == 404:
                        LOGGER.error("Attempt %s: Endpoint not found (404)", attempt + 1)
                        return None, "cannot_connect"
                    # Try parsing as JSON, handling incorrect Content-Type
                    response_text = await response.text()
                    try:
                        response_data = json.loads(response_text)
                        LOGGER.debug("Attempt %s: Parsed JSON response: %s", attempt + 1, response_data)
                        if "error" in response_data:
                            LOGGER.error("Attempt %s: API returned error: %s", attempt + 1, response_data)
                            return None, "invalid_auth" if response_data["error"].get("id") == 400 else "unknown"
                        if "sum" in response_data and "units" in response_data:
                            LOGGER.debug("Attempt %s: Valid energy data received: %s", attempt + 1, response_data)
                            return api_key, None  # Use API key as unique ID
                        LOGGER.error("Attempt %s: Unexpected JSON format: %s", attempt + 1, response_data)
                        return None, "unknown"
                    except json.JSONDecodeError:
                        # Handle case where response is not JSON
                        LOGGER.debug("Attempt %s: Non-JSON response received: %s", attempt + 1, response_text[:500])
                        if INTERSTITIAL_TEXT in response_text:
                            LOGGER.debug("Attempt %s: Interstitial page detected, attempting to bypass", attempt + 1)
                            async with session.get(INTERSTITIAL_URL, headers=API_HEADERS) as interstitial_response:
                                LOGGER.debug(
                                    "Attempt %s: Interstitial response status: %s, Headers: %s, Cookies: %s",
                                    attempt + 1,
                                    interstitial_response.status,
                                    dict(interstitial_response.headers),
                                    session.cookie_jar.filter_cookies(BASE_URL),
                                )
                                if interstitial_response.status != 200:
                                    LOGGER.error("Attempt %s: Failed to bypass interstitial: %s", 
                                                attempt + 1, interstitial_response.status)
                                    return None, "cannot_connect"
                            if attempt == max_retries - 1:
                                LOGGER.error("Max retries reached, still receiving HTML")
                                return None, "unknown"
                            continue
                        LOGGER.error("Attempt %s: Unexpected non-JSON response: %s", attempt + 1, response_text[:500])
                        return None, "unknown"
            except exceptions.ConnectError:
                LOGGER.error("Connection error during API call")
                return None, "cannot_connect"
            except exceptions.InvalidAuth:
                LOGGER.error("Invalid API key provided")
                return None, "invalid_auth"
            except Exception as e:
                LOGGER.exception("Unexpected exception: %s", str(e))
                return None, "unknown"
        return None, "unknown"