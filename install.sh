#!/bin/bash
# Install Thecus N7510 hardware support (fans, LCD, LEDs, beeper).
# Run as root from a checkout of this repository: ./install.sh
set -eu
cd "$(dirname "$0")"

if ! grep -q "GraniteWell\|Granite Well" /sys/class/dmi/id/board_name 2>/dev/null; then
  echo "warning: board is '$(cat /sys/class/dmi/id/board_name 2>/dev/null)', not the N7510's Granite Well" >&2
  read -r -p "continue anyway? [y/N] " a; [ "$a" = y ] || exit 1
fi
for cmd in python3 systemctl; do command -v $cmd >/dev/null || { echo "missing $cmd" >&2; exit 1; }; done

install -d -m 755 /opt/n7510 /etc/n7510
install -m 755 src/n7510-fan.py src/n7510-lcd.py src/n7510-leds.py /opt/n7510/

# The IT8728F PWM outputs are active-high; the Thecus firmware sets the same.
cat > /etc/modprobe.d/n7510.conf <<'EOF'
options it87 fix_pwm_polarity=1
EOF
cat > /etc/modules-load.d/n7510.conf <<'EOF'
it87
drivetemp
i2c-i801
i2c-dev
pcspkr
EOF
it87_has_pwm() {
  for h in /sys/class/hwmon/hwmon*; do
    [ "$(cat "$h/name" 2>/dev/null)" = it8728 ] && [ -e "$h/pwm1" ] && return 0
  done
  return 1
}
for m in it87 drivetemp i2c-i801 i2c-dev pcspkr; do modprobe "$m"; done
# it87 loaded earlier without the option exposes no PWM controls; reload it.
it87_has_pwm || { modprobe -r it87; modprobe it87; }
it87_has_pwm || echo "warning: it87 still exposes no PWM controls" >&2

install -m 644 systemd/n7510-fan.service systemd/n7510-lcd.service systemd/n7510-leds.service /etc/systemd/system/

# Power-off fix: systemd-shutdown runs hooks from one of these, depending on
# whether /usr is merged; install into each directory that exists.
for d in /usr/lib/systemd/system-shutdown /lib/systemd/system-shutdown; do
  [ -d "$d" ] && install -m 755 src/n7510-poweroff "$d/n7510-poweroff"
done
if systemctl list-unit-files folder2ram_startup.service >/dev/null 2>&1 && \
   systemctl cat folder2ram_startup.service >/dev/null 2>&1; then
  install -d /etc/systemd/system/folder2ram_startup.service.d
  install -m 644 systemd/folder2ram-journald.conf /etc/systemd/system/folder2ram_startup.service.d/journald.conf
  echo "openmediavault folder2ram detected: installed the journald fix"
fi

# Older installs used the name n7510-trayled.
if [ -f /etc/systemd/system/n7510-trayled.service ]; then
  systemctl disable --now n7510-trayled.service || true
  rm -f /etc/systemd/system/n7510-trayled.service /opt/n7510/n7510-trayled.py
fi

systemctl daemon-reload
systemctl enable n7510-fan.service n7510-lcd.service n7510-leds.service
systemctl restart n7510-fan.service n7510-lcd.service n7510-leds.service
sleep 5
systemctl --no-pager is-active n7510-fan.service n7510-lcd.service n7510-leds.service
if [ -e /etc/n7510/lcd-actions-enabled ]; then
  echo "LCD menu actions are enabled (/etc/n7510/lcd-actions-enabled)."
else
  echo "LCD menu actions are off (dry-run). Enable with: touch /etc/n7510/lcd-actions-enabled && systemctl restart n7510-lcd"
fi
