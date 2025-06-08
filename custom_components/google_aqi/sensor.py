from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import GoogleAQIDataCoordinator

_LOGGER = logging.getLogger(__name__)

POLLUTANTS = {
    "pm25": ("PM2.5", "µg/m³", "mdi:blur"),
    "pm10": ("PM10", "µg/m³", "mdi:blur-radial"),
    "co": ("Carbon Monoxide", "ppm", "mdi:molecule-co"),
    "no2": ("Nitrogen Dioxide", "ppb", "mdi:molecule"),
    "so2": ("Sulfur Dioxide", "ppb", "mdi:molecule"),
    "o3": ("Ozone", "ppb", "mdi:molecule"),
}


class GoogleAQIPollutantSensor(SensorEntity):
    def __init__(
        self,
        coordinator: GoogleAQIDataCoordinator,
        code: str,
        name: str,
        unit: str,
        icon: str,
    ) -> None:
        self.coordinator = coordinator
        self._attr_name = f"Google AQI {name}"
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit
        self._code = code
        self._attr_should_poll = False
        self._attr_unique_id = f"google_aqi_pollutant_{code}"

    @property
    def native_value(self) -> StateType:
        return self.coordinator.pollutants.get(self._code, {}).get("value")

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        data = self.coordinator.pollutants.get(self._code, {})
        return {
            "sources": data.get("sources"),
            "effects": data.get("effects"),
        }

    async def async_update(self) -> None:
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()


class GoogleAQIIndexSensor(SensorEntity):
    def __init__(
        self,
        coordinator: GoogleAQIDataCoordinator,
        code: str,
        name: str,
    ) -> None:
        self.coordinator = coordinator
        self._attr_name = f"Google AQI {name}"
        self._attr_icon = "mdi:gauge"
        self._attr_should_poll = False
        self._attr_unique_id = f"google_aqi_index_{code}"
        self._code = code

    @property
    def native_value(self) -> StateType:
        for index in self.coordinator.indexes:
            if index.get("code") == self._code:
                return index.get("aqi")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        for index in self.coordinator.indexes:
            if index.get("code") == self._code:
                return {
                    "category": index.get("category"),
                    "dominant_pollutant": index.get("dominantPollutant"),
                }
        return {}

    async def async_update(self) -> None:
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()


class GoogleAQIForecastSensor(SensorEntity):
    def __init__(self, coordinator: GoogleAQIDataCoordinator) -> None:
        self.coordinator = coordinator
        self._attr_name = "Google AQI Forecast"
        self._attr_icon = "mdi:chart-line"
        self._attr_should_poll = False
        self._attr_unique_id = "google_aqi_forecast"

    @property
    def native_value(self) -> StateType:
        if self.coordinator.forecast_data:
            return self.coordinator.forecast_data[0].get("aqi")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, str | list]:
        return {
            "forecast": self.coordinator.forecast_data,
        }

    async def async_update(self) -> None:
        await self.coordinator.async_update_forecast()
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GoogleAQIDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []

    # Pollutant sensors
    for code, (name, unit, icon) in POLLUTANTS.items():
        entities.append(GoogleAQIPollutantSensor(coordinator, code, name, unit, icon))

    # Dynamically create AQI index sensors from available data
    for index in coordinator.indexes:
        code = index.get("code")
        name = index.get("displayName", code.upper())
        if code:
            entities.append(GoogleAQIIndexSensor(coordinator, code, name))

    # Forecast Sensor
    entities.append(GoogleAQIForecastSensor(coordinator))

    async_add_entities(entities)
