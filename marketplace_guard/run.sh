#!/usr/bin/with-contenv bashio
# with-contenv provides SUPERVISOR_TOKEN and the other Supervisor variables.
# Prefers code in the add-on's configuration folder (/config/code here, addon_configs/<...>_marketplace_guard/code on the
# host): only the operator can write there, not Home Assistant Core or its integrations (ADR-0033). An add-on restart
# picks it up, no rebuild. Falls back to the code built into the image in /opt/marketplace_guard.
CODE_DIR="/config/code"
if [ -f "${CODE_DIR}/guard.py" ] && [ -f "${CODE_DIR}/scanner.py" ]; then
  SUM=$(cat "${CODE_DIR}/guard.py" "${CODE_DIR}/scanner.py" | sha256sum | cut -c1-16)
  bashio::log.warning "Marketplace Guard starting with OVERRIDE code from ${CODE_DIR} (sha256 ${SUM}) - not the code of this version"
  exec python3 "${CODE_DIR}/guard.py" daemon
fi
bashio::log.info "Marketplace Guard starting (built-in code /opt/marketplace_guard)"
exec python3 /opt/marketplace_guard/guard.py daemon
