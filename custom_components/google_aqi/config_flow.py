"""The Google Weather AQI config flow."""

import voluptuous as vol
from homeassistant import config_entries

DOMAIN = "google_aqi"  # Define the domain here


class GoogleAQIConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Google AQI."""

    async def async_step_user(self, user_input=None):
        """Handle the initial step where the user configures the integration."""
        if user_input is not None:
            # Validate forecast length and intervals
            if user_input["forecast_length"] > 96:
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._get_form_schema(),
                    errors={"forecast_length": "max_length_96"},
                )
            if user_input["update_interval"] > 24 or user_input["update_interval"] < 1:
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._get_form_schema(),
                    errors={"update_interval": "invalid_interval"},
                )
            if (
                user_input["forecast_interval"] > 24
                or user_input["forecast_interval"] < 1
            ):
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._get_form_schema(),
                    errors={"forecast_interval": "invalid_interval"},
                )

            # Save the configuration and create an entry
            return self.async_create_entry(title="Google AQI", data=user_input)

        # Get default latitude and longitude from Home Assistant configuration
        default_latitude = self.hass.config.latitude or 0.0
        default_longitude = self.hass.config.longitude or 0.0

        # Show the form with pre-filled values
        return self.async_show_form(
            step_id="user",
            data_schema=self._get_form_schema(default_latitude, default_longitude),
        )

    def _get_form_schema(self, default_latitude=0.0, default_longitude=0.0):
        """Define the schema for the configuration form."""
        return vol.Schema(
            {
                vol.Required("api_key"): str,  # API key must be entered by the user
                vol.Optional("latitude", default=default_latitude): float,
                vol.Optional("longitude", default=default_longitude): float,
                vol.Optional("update_interval", default=1): vol.All(
                    int, vol.Range(min=1, max=24)
                ),
                vol.Optional("forecast_interval", default=6): vol.All(
                    int, vol.Range(min=1, max=24)
                ),
                vol.Optional("forecast_length", default=48): vol.All(
                    int, vol.Range(min=1, max=96)
                ),
                vol.Optional("get_additional_info", default=False): bool,
            }
        )


class GoogleAQIOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Google AQI."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data = self.config_entry.options or self.config_entry.data
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional("latitude", default=data.get("latitude", 0.0)): float,
                    vol.Optional(
                        "longitude", default=data.get("longitude", 0.0)
                    ): float,
                    vol.Optional("interval", default=data.get("interval", 1)): vol.All(
                        int, vol.Range(min=1, max=24)
                    ),
                    vol.Optional(
                        "forecast_interval", default=data.get("forecast_interval", 6)
                    ): vol.All(int, vol.Range(min=1, max=24)),
                    vol.Optional(
                        "forecast_length", default=data.get("forecast_length", 48)
                    ): vol.All(int, vol.Range(min=1, max=96)),
                    vol.Optional(
                        "get_additional_info",
                        default=data.get("get_additional_info", False),
                    ): bool,
                }
            ),
        )


# Link it to the flow
async def async_get_options_flow(config_entry):
    return GoogleAQIOptionsFlowHandler(config_entry)
