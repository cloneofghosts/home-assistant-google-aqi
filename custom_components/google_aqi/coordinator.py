"""The Google AQI coordinator."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_URL, FORECAST_URL

_LOGGER = logging.getLogger(__name__)


class GoogleAQIDataCoordinator(DataUpdateCoordinator):
    """The Google AQI data coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        latitude: float,
        longitude: float,
        update_interval: int,
        forecast_interval: int,
        forecast_length: int,
        get_additional_info: bool,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Google AQI Data Coordinator",
            update_interval=timedelta(hours=update_interval),
        )
        self._api_key = api_key
        self._latitude = latitude
        self._longitude = longitude
        self._forecast_interval = forecast_interval
        self._forecast_length = forecast_length
        self.get_additional_info = get_additional_info

        self._pollutants: dict = {}
        self._indexes: list = []

    @property
    def pollutants(self) -> dict:
        """Return the latest pollutants data."""
        return self._pollutants

    @property
    def indexes(self) -> list:
        """Return the latest AQI indexes."""
        return self._indexes

    async def _async_update_data(self) -> dict:
        """Fetch current pollutant and index data from API."""
        _LOGGER.debug("Fetching current AQI data from API...")

        session = async_get_clientsession(self.hass)
        payload = {
            "location": {"latitude": self._latitude, "longitude": self._longitude},
            "extraComputations": [
                "HEALTH_RECOMMENDATIONS",
                "LOCAL_AQI",
                "POLLUTANT_ADDITIONAL_INFO",
                "DOMINANT_POLLUTANT_CONCENTRATION",
                "POLLUTANT_CONCENTRATION",
            ],
        }
        params = {"key": self._api_key}

        try:
            async with session.post(API_URL, json=payload, params=params) as response:
                if response.status != 200:
                    text = await response.text()
                    _raise_update_failed(response.status, text)

                data = await response.json()

                # Parse pollutants
                pollutants = {}
                for pollutant in data.get("pollutants", []):
                    code = pollutant.get("code")
                    concentration = pollutant.get("concentration", {})
                    pollutants[code] = {
                        "value": concentration.get("value"),
                        "units": concentration.get("units"),
                        "sources": pollutant.get("additionalInfo", {}).get("sources"),
                        "effects": pollutant.get("additionalInfo", {}).get("effects"),
                    }

                # Parse indexes
                indexes = data.get("indexes", [])

                self._pollutants = pollutants
                self._indexes = indexes

                _LOGGER.debug(
                    "Fetched %d pollutants and %d index values",
                    len(pollutants),
                    len(indexes),
                )

                return data

        except Exception as err:
            raise UpdateFailed(f"Error fetching current AQI data: {err}") from err


def _raise_update_failed(status: int, text: str) -> None:
    """Return UpdateFailed if the data could not be fetched."""
    raise UpdateFailed(f"API response {status}: {text}")


class GoogleAQIForecastCoordinator(DataUpdateCoordinator):
    """Coordinator for Google AQI forecast data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        latitude: float,
        longitude: float,
        forecast_interval: int,
        forecast_length: int,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Google AQI Forecast Coordinator",
            update_interval=timedelta(hours=forecast_interval),
        )

        self._api_key = api_key
        self._latitude = latitude
        self._longitude = longitude
        self._forecast_length = forecast_length

        self.forecast_data: list = []

    async def _async_update_data(self) -> list:
        """Fetch forecast data."""
        _LOGGER.debug(
            "Fetching forecast data (interval: %d hours, length: %d hours)...",
            self.update_interval.total_seconds() // 3600,
            self._forecast_length,
        )
        session = async_get_clientsession(self.hass)
        now = datetime.now(UTC)

        next_full_hour = (now + timedelta(hours=1)).replace(
            minute=0, second=0, microsecond=0
        )
        end_time = next_full_hour + timedelta(hours=self._forecast_length)

        payload = {
            "universalAqi": "true",
            "location": {
                "latitude": str(self._latitude),
                "longitude": str(self._longitude),
            },
            "period": {
                "startTime": next_full_hour.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "endTime": end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            "languageCode": "en",
            "extraComputations": [
                "HEALTH_RECOMMENDATIONS",
                "DOMINANT_POLLUTANT_CONCENTRATION",
                "POLLUTANT_ADDITIONAL_INFO",
                "LOCAL_AQI",
            ],
            "uaqiColorPalette": "RED_GREEN",
        }

        params = {"key": self._api_key}

        async with session.post(FORECAST_URL, json=payload, params=params) as response:
            if response.status != 200:
                text = await response.text()
                raise UpdateFailed(f"Forecast API error {response.status}: {text}")

            data = await response.json()

            if not data or "hourlyForecasts" not in data:
                raise UpdateFailed("Invalid forecast data received")

            forecasts = []
            for forecast_entry in data["hourlyForecasts"]:
                uaqi_index = next(
                    (
                        idx
                        for idx in forecast_entry.get("indexes", [])
                        if idx.get("code") == "uaqi"
                    ),
                    None,
                )
                forecasts.append(
                    {
                        "datetime": forecast_entry.get("dateTime"),
                        "aqi": uaqi_index.get("aqi") if uaqi_index else None,
                        "dominant_pollutant": uaqi_index.get("dominantPollutant")
                        if uaqi_index
                        else None,
                    }
                )

            self.forecast_data = forecasts
            _LOGGER.debug("Received %d forecast entries", len(forecasts))
            return forecasts
