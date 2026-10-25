#!/bin/bash
# Remove Thecus N7510 hardware support. Stopping n7510-fan leaves the fans at
# full speed; after a reboot they return to the BIOS defaults.
# Keeps /etc/n7510 (LCD password, tray map) unless --purge is given.
set -eu
systemctl disable --now n7510-fan.service n7510-lcd.service n7510-leds.service 2>/dev/null || true
rm -f /etc/systemd/system/n7510-fan.service /etc/systemd/system/n7510-lcd.service \
      /etc/systemd/system/n7510-leds.service \
      /etc/systemd/system/folder2ram_startup.service.d/journald.conf \
      /etc/modprobe.d/n7510.conf /etc/modules-load.d/n7510.conf \
      /usr/lib/systemd/system-shutdown/n7510-poweroff /lib/systemd/system-shutdown/n7510-poweroff
rm -rf /opt/n7510
[ "${1:-}" = --purge ] && rm -rf /etc/n7510 /run/n7510
systemctl daemon-reload
echo "removed; reboot to unload it87 with default options"
