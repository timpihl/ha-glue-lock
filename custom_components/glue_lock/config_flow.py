"""Config flow for the Glue Lock integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import GlueApiClient, GlueApiError, GlueAuthError, create_api_key
from .const import (
    API_KEY_NAME,
    CONF_FAST_POLL,
    CONF_POLL_INTERVAL,
    DEFAULT_FAST_POLL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    MAX_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
)

_PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))

API_KEY_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): _PASSWORD_SELECTOR})
CREDENTIALS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TextSelector(),
        vol.Required(CONF_PASSWORD): _PASSWORD_SELECTOR,
    }
)


class GlueConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up a Glue account."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> GlueOptionsFlow:
        """Return the options flow."""
        return GlueOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user choose how to give the API key."""
        return self.async_show_menu(
            step_id="user", menu_options=["credentials", "api_key"]
        )

    async def async_step_api_key(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up with an existing API key."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            if not (error := await self._async_validate(api_key)):
                return self._async_create(api_key)
            errors["base"] = error
        return self.async_show_form(
            step_id="api_key", data_schema=API_KEY_SCHEMA, errors=errors
        )

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create an API key with the Glue account. Only the key is stored."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                api_key = await create_api_key(
                    async_get_clientsession(self.hass),
                    user_input[CONF_USERNAME].strip(),
                    user_input[CONF_PASSWORD],
                    API_KEY_NAME,
                )
            except GlueAuthError:
                errors["base"] = "invalid_auth"
            except GlueApiError:
                errors["base"] = "cannot_connect"
            else:
                # The key is new, so it is kept even if the first read fails.
                return self._async_create(api_key)
        return self.async_show_form(
            step_id="credentials",
            data_schema=self.add_suggested_values_to_schema(
                CREDENTIALS_SCHEMA,
                {CONF_USERNAME: (user_input or {}).get(CONF_USERNAME)},
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Glue no longer accepts the API key."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new API key."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            if not (error := await self._async_validate(api_key)):
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates={CONF_API_KEY: api_key}
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=API_KEY_SCHEMA, errors=errors
        )

    async def _async_validate(self, api_key: str) -> str | None:
        """Return an error key, or None when Glue accepts the API key."""
        client = GlueApiClient(async_get_clientsession(self.hass), api_key)
        try:
            await client.get_locks()
        except GlueAuthError:
            return "invalid_auth"
        except GlueApiError:
            return "cannot_connect"
        return None

    def _async_create(self, api_key: str) -> ConfigFlowResult:
        self._async_abort_entries_match({CONF_API_KEY: api_key})
        return self.async_create_entry(title="Glue", data={CONF_API_KEY: api_key})


class GlueOptionsFlow(OptionsFlow):
    """Change how often the locks are read."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            user_input[CONF_POLL_INTERVAL] = int(user_input[CONF_POLL_INTERVAL])
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_POLL_INTERVAL,
                    default=options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_POLL_INTERVAL,
                        max=MAX_POLL_INTERVAL,
                        step=1,
                        unit_of_measurement="s",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_FAST_POLL,
                    default=options.get(CONF_FAST_POLL, DEFAULT_FAST_POLL),
                ): BooleanSelector(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
