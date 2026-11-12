"""Marketplace Guard Gate: asks the Marketplace Guard app about content the Marketplace wrote, before Home Assistant
loads it (ADR-0042). Installed by the app when its option `marketplace_gate` is on."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import os

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from . import gatecore

_LOGGER = logging.getLogger(__name__)
DOMAIN = "marketplace_guard_gate"
POLL_SECONDS = 0.5
DEFAULTS = {"timeout": 120, "on_no_answer": "refuse"}
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
HERE = os.path.dirname(os.path.abspath(__file__))
# Both read while Python imports this module (ADR-0044); Home Assistant imports custom integrations in an executor
# thread, so neither blocks its event loop. RUNNING_VERSION is the version of the code that runs: the loader's own
# record of the manifest can be older than the import (it is read when custom_components is scanned), so it is not
# used. SET_RESTART_REQUIRED is Home Assistant's restart flag, None in a version without it.
RUNNING_VERSION = gatecore.manifest_version(HERE)
SET_RESTART_REQUIRED = gatecore.find_function(*gatecore.RESTART_FLAG)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Watch the gate's own folder for as long as this code is loaded (ADR-0044): once per run of Home Assistant, also
    when the gate does not become active, since an update of Marketplace Guard is the fix then and its new copy needs
    a restart. A failed entry setup would stop a watch bound to the entry."""
    if RUNNING_VERSION is None:
        _LOGGER.warning("Marketplace Guard Gate cannot read its own version in %s; a new copy is not noticed", HERE)
        return True
    if SET_RESTART_REQUIRED is None:
        _LOGGER.warning("This Home Assistant has no %s.%s; a new copy of the gate is announced by a notification",
                        *gatecore.RESTART_FLAG)
    watch = gatecore.CopyWatch(HERE, RUNNING_VERSION, lambda on_disk: _restart_required(hass, on_disk))
    stop = None

    async def check(_now=None) -> None:
        if watch.judge(await hass.async_add_executor_job(watch.read)) == "replaced" and stop is not None:
            stop()  # Home Assistant's flag latches until the restart: nothing more to watch

    await check()
    if watch.state != "replaced":
        stop = async_track_time_interval(hass, check, timedelta(seconds=gatecore.COPY_CHECK_SECONDS),
                                         name=f"{DOMAIN} copy check", cancel_on_shutdown=True)
    return True


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


def _restart_required(hass: HomeAssistant, on_disk: str) -> None:
    """Tell Home Assistant that the gate's new copy waits for a restart: its own restart flag, which automations can
    use (trigger and condition `homeassistant.restart_required`), else a notification."""
    if SET_RESTART_REQUIRED is not None:
        SET_RESTART_REQUIRED(hass, DOMAIN)
        _LOGGER.info("Marketplace Guard Gate %s is installed, %s runs: Home Assistant is marked as needing a restart",
                     on_disk, RUNNING_VERSION)
        return
    _LOGGER.warning("Marketplace Guard Gate %s is installed, %s runs until Home Assistant restarts", on_disk,
                    RUNNING_VERSION)
    persistent_notification.async_create(
        hass, f"Marketplace Guard Gate {on_disk} is installed; version {RUNNING_VERSION} keeps checking until Home "
        "Assistant restarts. Restart Home Assistant to load the new version.",
        title="Marketplace Guard Gate: restart Home Assistant", notification_id=f"{DOMAIN}_restart")


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
