"""The Google Weather AQI component."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .config_flow import GoogleAQIOptionsFlowHandler
from .coordinator import (
    GoogleAQIDataCoordinator,
    GoogleAQIForecastCoordinator,
)

DOMAIN = "google_aqi"
PLATFORMS = ["sensor"]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Google AQI entity."""

    if not entry.options:
        hass.config_entries.async_update_entry(entry, options=entry.data)

    data = entry.options or entry.data

    _LOGGER.debug("Setting up Google AQI integration with config: %s", data)

    # Extract config values
    api_key = entry.data.get("api_key")
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    update_interval = data.get("update_interval", 1)
    forecast_interval = data.get("forecast_interval", 3)
    forecast_length = data.get("forecast_length", 24)
    get_additional_info = data.get("get_additional_info", False)

    # Instantiate both coordinators
    aqi_coordinator = GoogleAQIDataCoordinator(
        hass,
        api_key,
        latitude,
        longitude,
        update_interval,
        forecast_interval,
        forecast_length,
        get_additional_info,
    )

    forecast_coordinator = GoogleAQIForecastCoordinator(
        hass,
        api_key,
        latitude,
        longitude,
        forecast_interval,
        forecast_length,
    )

    # Initial data fetch
    await aqi_coordinator.async_config_entry_first_refresh()
    await forecast_coordinator.async_config_entry_first_refresh()

    _LOGGER.debug("AQI coordinator timer: %s", aqi_coordinator.update_interval)
    _LOGGER.debug(
        "Forecast coordinator timer: %s", forecast_coordinator.update_interval
    )

    # Store both coordinators
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "aqi": aqi_coordinator,
        "forecast": forecast_coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_get_options_flow(config_entry: ConfigEntry):
    """Set up the Google AQI options flow."""
    return GoogleAQIOptionsFlowHandler(config_entry)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update: reload the integration to apply changes."""
    await hass.config_entries.async_reload(entry.entry_id)
