from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_URL, FORECAST_URL

_LOGGER = logging.getLogger(__name__)


class GoogleAQIDataCoordinator(DataUpdateCoordinator):
    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        latitude: float,
        longitude: float,
        update_interval: int,
        forecast_interval: int,
        forecast_length: int,
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

        self._pollutants: dict = {}
        self._indexes: list = []
        self._forecast_data: list = []
        self._last_forecast_update: datetime | None = None

    @property
    def pollutants(self) -> dict:
        """Return the latest pollutants data."""
        return self._pollutants

    @property
    def indexes(self) -> list:
        """Return the latest AQI indexes."""
        return self._indexes

    @property
    def forecast_data(self) -> list:
        """Return the latest forecast data."""
        return self._forecast_data

    @property
    def last_forecast_update(self) -> datetime | None:
        """Return the timestamp of the last forecast update."""
        return self._last_forecast_update

    async def _async_update_data(self) -> dict:
        """Fetch current pollutant and index data from API."""
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
                    raise UpdateFailed(f"API response {response.status}: {text}")

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

                return data

        except Exception as err:
            raise UpdateFailed(f"Error fetching current AQI data: {err}") from err

    async def async_update_forecast(self) -> None:
        """Fetch and update forecast data, respecting forecast_interval."""
        now = datetime.now(UTC)
        if self._last_forecast_update is None or (
            now - self._last_forecast_update
        ) >= timedelta(hours=self._forecast_interval):
            session = async_get_clientsession(self.hass)

            # Align startTime to next full hour
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

            try:
                async with session.post(
                    FORECAST_URL, json=payload, params=params
                ) as response:
                    if response.status != 200:
                        text = await response.text()
                        _LOGGER.error(
                            "Forecast API error %s: %s", response.status, text
                        )
                        return

                    data = await response.json()

                    if not data or "hourlyForecasts" not in data:
                        _LOGGER.warning("Received invalid forecast data from API")
                        self._forecast_data = []
                        return

                    # Extract forecast info: datetime, uaqi index and dominant pollutant
                    forecast = []
                    for forecast_entry in data["hourlyForecasts"]:
                        uaqi_index = next(
                            (
                                idx
                                for idx in forecast_entry.get("indexes", [])
                                if idx.get("code") == "uaqi"
                            ),
                            None,
                        )
                        forecast.append(
                            {
                                "datetime": forecast_entry.get("dateTime"),
                                "aqi": uaqi_index.get("aqi") if uaqi_index else None,
                                "dominant_pollutant": uaqi_index.get(
                                    "dominantPollutant"
                                )
                                if uaqi_index
                                else None,
                            }
                        )

                    self._forecast_data = forecast
                    self._last_forecast_update = now

            except Exception as err:
                _LOGGER.error("Error fetching forecast data: %s", err)
