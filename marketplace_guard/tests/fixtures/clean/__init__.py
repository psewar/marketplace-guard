"""TEST FIXTURE - a harmless, typical cloud integration."""
import logging
import aiohttp

_LOGGER = logging.getLogger(__name__)
API = "https://api.vendor.example/v1"


async def async_setup_entry(hass, entry):
    session = aiohttp.ClientSession()
    async with session.get(f"{API}/status", headers={"Authorization": "Bearer x"}) as r:
        data = await r.json()
    _LOGGER.info("status: %s", data)
    return True
