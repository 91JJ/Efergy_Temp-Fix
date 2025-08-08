"""Support for Efergy sensors."""

from __future__ import annotations

import dataclasses
import json
from typing import cast
from datetime import datetime

from pyefergy import Efergy
from pyefergy.exceptions import ConnectError, DataError, ServiceError

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from . import EfergyConfigEntry
from .const import LOGGER, GET_INSTANT_URL, INTERSTITIAL_URL, INTERSTITIAL_TEXT, API_HEADERS
from .entity import EfergyEntity

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="instant_readings",
        name="Power Usage",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="energy_total",
        name="Total Energy Consumption",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EfergyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    api: Efergy = entry.runtime_data
    sensors = [
        EfergySensor(api, description, entry.entry_id)
        for description in SENSOR_TYPES
    ]
    async_add_entities(sensors, True)


class EfergySensor(EfergyEntity, SensorEntity):
    """Implementation of an Efergy sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        api: Efergy,
        description: SensorEntityDescription,
        server_unique_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(api, server_unique_id)
        self.entity_description = description
        self._attr_unique_id = f"{server_unique_id}/{description.key}"
        # For energy_total sensor: track cumulative energy and last update
        self._energy_total = 0.0  # Cumulative energy in kWh
        self._last_power = None  # Last power reading in watts
        self._last_update = None  # Last update timestamp

    async def async_update(self) -> None:
        """Get the Efergy monitor data from the web service."""
        try:
            # Construct the URL for getInstant
            url = f"{GET_INSTANT_URL}?token={self.api._api_key}"
            LOGGER.debug(" tyrosineFetching data from URL: %s", url)

            async with self.api._session.get(url, headers=API_HEADERS) as response:
                content_type = response.headers.get("Content-Type", "")
                LOGGER.debug("Response Content-Type: %s, Status: %s", content_type, response.status)
                response_text = await response.text()
                try:
                    response_data = json.loads(response_text)
                    LOGGER.debug("Parsed JSON response: %s", response_data)
                    power_value = response_data.get("reading")
                    if power_value is None:
                        LOGGER.error("No 'reading' key in response: %s", response_data)
                        raise DataError("Invalid response format: missing 'reading' key")
                except json.JSONDecodeError:
                    LOGGER.debug("Non-JSON response received: %s", response_text[:500])
                    if INTERSTITIAL_TEXT in response_text:
                        LOGGER.debug("Interstitial page detected, attempting to bypass")
                        async with self.api._session.get(INTERSTITIAL_URL, headers=API_HEADERS) as interstitial_response:
                            LOGGER.debug(
                                "Interstitial response status: %s, Headers: %s",
                                interstitial_response.status,
                                dict(interstitial_response.headers),
                            )
                            if interstitial_response.status != 200:
                                raise DataError("Failed to bypass interstitial page")
                        async with self.api._session.get(url, headers=API_HEADERS) as retry_response:
                            retry_text = await retry_response.text()
                            try:
                                response_data = json.loads(retry_text)
                                LOGGER.debug("Parsed JSON response after retry: %s", response_data)
                                power_value = response_data.get("reading")
                                if power_value is None:
                                    LOGGER.error("No 'reading' key in retry response: %s", response_data)
                                    raise DataError("Invalid response format: missing 'reading' key")
                            except json.JSONDecodeError:
                                LOGGER.error("Non-JSON response after retry: %s", retry_text[:500])
                                raise DataError("Unexpected HTML response after retry")
                    else:
                        LOGGER.error("Unexpected non-JSON response: %s", response_text[:500])
                        raise DataError("Unexpected HTML response")

                # Update sensor value based on type
                if self.entity_description.key == "instant_readings":
                    self._attr_native_value = cast(StateType, power_value)
                elif self.entity_description.key == "energy_total":
                    # Calculate energy increment
                    current_time = dt_util.utcnow()
                    if self._last_power is not None and self._last_update is not None:
                        # Convert power (W) to energy (kWh): (P1 + P2)/2 * Δt(hours) / 1000
                        time_diff_hours = (current_time - self._last_update).total_seconds() / 3600.0
                        avg_power = (float(self._last_power) + float(power_value)) / 2.0
                        energy_increment_kwh = avg_power * time_diff_hours / 1000.0
                        self._energy_total += energy_increment_kwh
                        LOGGER.debug(
                            "Energy increment: %.6f kWh (avg_power=%.2f W, time_diff=%.6f hours), total=%.6f kWh",
                            energy_increment_kwh, avg_power, time_diff_hours, self._energy_total
                        )
                    self._attr_native_value = cast(StateType, round(self._energy_total, 6))
                    # Update last values
                    self._last_power = power_value
                    self._last_update = current_time

        except (ConnectError, DataError, ServiceError) as ex:
            if self._attr_available:
                self._attr_available = False
                LOGGER.error("Error getting data: %s", ex)
            return
        if not self._attr_available:
            self._attr_available = True
            LOGGER.debug("Connection has resumed")