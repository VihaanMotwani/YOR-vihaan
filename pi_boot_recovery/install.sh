#!/usr/bin/env sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this installer with sudo: sudo ./install.sh" >&2
  exit 1
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
INSTALL_DIR=/usr/local/lib/yor-network-recovery
SERVICE_PATH=/etc/systemd/system/yor-network-recovery.service
DEFAULTS_PATH=/etc/default/yor-network-recovery

install -d -m 0755 "$INSTALL_DIR"
install -m 0755 "$SCRIPT_DIR/yor_network_recovery.py" "$INSTALL_DIR/yor_network_recovery.py"
install -m 0644 "$SCRIPT_DIR/README.md" "$INSTALL_DIR/README.md"
install -m 0644 "$SCRIPT_DIR/yor-network-recovery.service" "$SERVICE_PATH"

if [ ! -f "$DEFAULTS_PATH" ]; then
  umask 077
  cat > "$DEFAULTS_PATH" <<'EOF'
YOR_RECOVERY_INTERFACE=wlan0
YOR_RECOVERY_SSID=YOR-Setup
YOR_RECOVERY_PASSWORD=yor-setup-robot
YOR_RECOVERY_WAIT_SECONDS=90
YOR_RECOVERY_POLL_SECONDS=5
EOF
  echo "Created $DEFAULTS_PATH. Edit it to change the hotspot SSID/password."
else
  echo "Keeping existing $DEFAULTS_PATH."
fi

systemctl daemon-reload
systemctl enable yor-network-recovery.service

echo "Installed yor-network-recovery.service."
echo "Reboot to test boot fallback, or run: sudo systemctl start yor-network-recovery.service"
