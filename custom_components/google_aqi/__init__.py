"""The Google Weather AQI component."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .config_flow import GoogleAQIOptionsFlowHandler
from .coordinator import GoogleAQIDataCoordinator

DOMAIN = "google_aqi"
PLATFORMS = ["sensor"]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Google AQI entity."""

    _LOGGER.info("Setting up Google AQI integration with config: %s", entry.data)

    if not entry.options:
        hass.config_entries.async_update_entry(entry, options=entry.data)

    data = entry.options or entry.data

    # Extract config values from entry.data
    api_key = entry.data.get("api_key")
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    update_interval = data.get("update_interval", 1)  # default 1 hour
    forecast_interval = data.get("forecast_interval", 3)  # default 3 hours
    forecast_length = data.get("forecast_length", 24)  # default 24 hours

    coordinator = GoogleAQIDataCoordinator(
        hass,
        api_key,
        latitude,
        longitude,
        update_interval,
        forecast_interval,
        forecast_length,
    )

    # Perform initial data fetch
    await coordinator.async_config_entry_first_refresh()

    # Save coordinator instance in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward setup to sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    # Reload the integration after changing configuration
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
