"""The Google AQI sensors."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GoogleAQIDataCoordinator, GoogleAQIForecastCoordinator

_LOGGER = logging.getLogger(__name__)

POLLUTANTS = {
    "pm25": ("PM2.5", "µg/m³", "mdi:blur"),
    "pm10": ("PM10", "µg/m³", "mdi:blur-radial"),
    "co": ("Carbon Monoxide", "ppm", "mdi:molecule-co"),
    "no2": ("Nitrogen Dioxide", "ppb", "mdi:molecule"),
    "so2": ("Sulfur Dioxide", "ppb", "mdi:molecule"),
    "o3": ("Ozone", "ppb", "mdi:molecule"),
}


class GoogleAQIPollutantSensor(CoordinatorEntity, SensorEntity):
    """The Google AQI pollutant sensor."""

    def __init__(
        self,
        coordinator: GoogleAQIDataCoordinator,
        entry_id: str,
        code: str,
        name: str,
        unit: str,
        icon: str,
    ) -> None:
        """Initialize the AQI pollutant sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._attr_name = f"Google AQI {name}"
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_class = None
        self._attr_should_poll = False
        self._attr_unique_id = f"google_aqi_pollutant_{entry_id}_{code}"
        self._code = code

    @property
    def native_value(self) -> StateType:
        """Return the current pollutant value."""
        return self.coordinator.pollutants.get(self._code, {}).get("value")

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Return extra information about the pollutant."""
        if not getattr(self.coordinator, "get_additional_info", False):
            return {}
        data = self.coordinator.pollutants.get(self._code, {})
        return {
            "sources": data.get("sources"),
            "effects": data.get("effects"),
        }


class GoogleAQIIndexSensor(CoordinatorEntity, SensorEntity):
    """The Google AQI index sensor."""

    def __init__(
        self,
        coordinator: GoogleAQIDataCoordinator,
        entry_id: str,
        code: str,
        name: str,
    ) -> None:
        """Initialize the AQI index sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._attr_name = f"Google AQI {name}"
        self._attr_icon = "mdi:gauge"
        self._attr_should_poll = False
        self._attr_unique_id = f"google_aqi_index_{entry_id}_{code}"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_class = SensorDeviceClass.AQI
        self._code = code

    @property
    def native_value(self) -> StateType:
        """Return the AQI value."""
        for index in self.coordinator.indexes:
            if index.get("code") == self._code:
                return index.get("aqi")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Return the AQI value from the index."""
        if not getattr(self.coordinator, "get_additional_info", False):
            return {}
        for index in self.coordinator.indexes:
            if index.get("code") == self._code:
                return {
                    "category": index.get("category"),
                    "dominant_pollutant": index.get("dominantPollutant"),
                }
        return {}


class GoogleAQIForecastSensor(CoordinatorEntity, SensorEntity):
    """The Google AQI forecast sensor."""

    def __init__(
        self, coordinator: GoogleAQIForecastCoordinator, entry_id: str
    ) -> None:
        """Initialize the Google AQI forecast sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._attr_name = "Google AQI Forecast"
        self._attr_icon = "mdi:chart-line"
        self._attr_should_poll = False
        self._attr_unique_id = f"google_aqi_forecast_{entry_id}"

    @property
    def native_value(self) -> StateType:
        """Return the first AQI index as the native value."""
        if self.coordinator.forecast_data:
            return self.coordinator.forecast_data[0].get("aqi")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, str | list]:
        """Return the rest of the forecast as extra state attributes."""
        return {
            "forecast": self.coordinator.forecast_data,
        }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Google AQI sensors."""

    coordinators = hass.data[DOMAIN][entry.entry_id]
    aqi_coordinator: GoogleAQIDataCoordinator = coordinators["aqi"]
    forecast_coordinator: GoogleAQIForecastCoordinator = coordinators["forecast"]

    entities: list[SensorEntity] = []

    # Pollutant sensors
    for code, (name, unit, icon) in POLLUTANTS.items():
        entities.append(
            GoogleAQIPollutantSensor(
                aqi_coordinator, entry.entry_id, code, name, unit, icon
            )
        )

    # AQI Index sensors
    for index in aqi_coordinator.indexes:
        code = index.get("code")
        name = index.get("displayName", code.upper())
        if code:
            entities.append(
                GoogleAQIIndexSensor(aqi_coordinator, entry.entry_id, code, name)
            )

    # Forecast sensor using forecast coordinator
    entities.append(GoogleAQIForecastSensor(forecast_coordinator, entry.entry_id))

    async_add_entities(entities)
