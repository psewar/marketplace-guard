"""Marketplace Guard Gate: asks the Marketplace Guard app about content the Marketplace wrote, before Home Assistant
loads it (ADR-0042). Installed by the app when its option `marketplace_gate` is on."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import gatecore

_LOGGER = logging.getLogger(__name__)
DOMAIN = "marketplace_guard_gate"
POLL_SECONDS = 0.5
DEFAULTS = {"timeout": 120, "on_no_answer": "refuse"}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Wrap the Marketplace's content checks, or say why the gate is not active."""
    try:
        from homeassistant.components.marketplace.exceptions import MarketplaceError
        from homeassistant.components.marketplace.repositories import base
    except ImportError as err:  # a module that does not exist in this version cannot be checked for beforehand
        _not_active(hass, f"this Home Assistant has no Marketplace modules where the gate looks ({err})")
        return False
    settings = {**DEFAULTS, **entry.options}

    def make_wrapper(original):
        async def checked(self, *args, **kwargs):
            await original(self, *args, **kwargs)  # the Marketplace's own check first
            if str(self.data.category) in gatecore.CATEGORIES:
                await _ask(hass, self, settings, MarketplaceError)

        return checked

    done = gatecore.wrap_check_methods(getattr(base, "Repository", None), make_wrapper)
    if done is None:
        _not_active(hass, f"this Home Assistant's Marketplace has no Repository.{gatecore.METHOD}")
        return False
    hass.data[DOMAIN] = done
    persistent_notification.async_dismiss(hass, DOMAIN)
    _LOGGER.info("Marketplace Guard Gate active: %s checks wrapped, %ss for an answer, %s without one",
                 len(done), settings["timeout"], settings["on_no_answer"])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    gatecore.unwrap(hass.data.pop(DOMAIN, []))
    return True


def _not_active(hass: HomeAssistant, why: str) -> None:
    _LOGGER.error("Marketplace Guard Gate is not active: %s", why)
    persistent_notification.async_create(
        hass, f"The gate does not check Marketplace installs: {why}. Update Marketplace Guard; until then, pre-check "
        "a repository before you install it.", title="Marketplace Guard Gate is not active", notification_id=DOMAIN)


async def _ask(hass: HomeAssistant, repository, settings: dict, error_cls) -> None:
    """Ask the app about the content just written; raise the Marketplace's own error to make it put back what was there."""
    name = repository.data.full_name
    state, rid, payload = gatecore.build_request(hass.config.config_dir, str(repository.content.path.local), name,
                                                 repository.data.category, repository.data.installed)
    if state != "ok":
        raise error_cls(translation_domain="marketplace", translation_key="validation_failed",
                        translation_placeholders={"repository": name, "error": payload})
    await hass.async_add_executor_job(gatecore.write_request, hass.config.config_dir, rid, payload)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + float(settings["timeout"])
    answer = None
    while answer is None and loop.time() < deadline:
        await asyncio.sleep(POLL_SECONDS)
        answer = await hass.async_add_executor_job(gatecore.read_answer, hass.config.config_dir, rid)
    if answer is None:
        await hass.async_add_executor_job(gatecore.withdraw_request, hass.config.config_dir, rid)
    decision, message = gatecore.outcome(answer, settings["on_no_answer"])
    if decision == "refuse":
        _LOGGER.warning("%s: %s", name, message)
        raise error_cls(translation_domain="marketplace", translation_key="validation_failed",
                        translation_placeholders={"repository": name, "error": message})
    _LOGGER.info("%s allowed by Marketplace Guard%s", name, f": {message}" if message else "")
