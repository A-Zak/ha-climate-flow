"""Config flow for the Climate Flow integration."""

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class ClimateFlowConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Climate Flow."""

    async def async_step_user(
        self, user_input: dict[str, object] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup step."""
        if user_input is not None:
            return self.async_create_entry(title="Climate Flow", data={})

        return self.async_show_form(step_id="user")
