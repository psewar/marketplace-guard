"""Set up the gate (one entry), and choose what happens when Marketplace Guard does not answer (ADR-0042)."""
from __future__ import annotations

from typing import Any

import probatio

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlowWithReload
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from . import DEFAULTS, DOMAIN


class GateConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="Marketplace Guard Gate", data={}, options=dict(DEFAULTS))
        return self.async_show_form(step_id="user")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> GateOptionsFlow:
        return GateOptionsFlow()


class GateOptionsFlow(OptionsFlowWithReload):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data={**self.config_entry.options, **user_input,
                                                 "timeout": int(user_input["timeout"])})
        schema = probatio.Schema({
            probatio.Required("on_no_answer"): SelectSelector(SelectSelectorConfig(
                options=["refuse", "allow"], mode=SelectSelectorMode.LIST, translation_key="on_no_answer")),
            probatio.Required("timeout"): NumberSelector(NumberSelectorConfig(
                min=10, max=600, step=10, unit_of_measurement="s", mode=NumberSelectorMode.BOX)),
        })
        return self.async_show_form(step_id="init", data_schema=self.add_suggested_values_to_schema(
            schema, {**DEFAULTS, **self.config_entry.options}))
