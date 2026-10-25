# Changelog

## Unreleased

- Documented the ICH10 hardware watchdog (`iTCO_wdt`, tested) and how to use
  it instead of openmediavault's `softdog`.
- Tested on openmediavault 8 / Debian 13 (kernels 6.12 and 7.2): `install.sh`
  unchanged, all three services start; Debian 13 has no `gpio_ich`, so
  `n7510-leds` drives the green LEDs through `/dev/port` (verified: a
  per-tray read test lit each tray in turn).

## 0.1.3 (2026-10-25)

- Tested: scheduled power-on with `rtcwake` from power-off.
- Documented the BIOS settings (`docs/hardware.md`), including power after
  AC loss (*PWRON After PWR-Fail*, default *Former-Sts*) and why Console
  Redirection must stay off (COM1 is the LCD).

## 0.1.2 (2026-10-25)

- `n7510-fan`: overheat alarm. Full speed and status `hot` (red System "!"
  and beeps via `n7510-leds`) when an IT8728 board sensor reaches 60 °C (the
  Thecus OS limit), the CPU 70 °C, or any disk 50 °C.
- Tested: the power button (clean shutdown and power off) and Wake-on-LAN
  from power-off. Documented openmediavault's power-button default (Standby)
  and the Thecus fan logic for reference.

## 0.1.1 (2026-10-25)

- Power off now switches the board off. New systemd `system-shutdown` hook
  `n7510-poweroff` clears the ICH10 `SLP_SMI_EN` bit before power-off, so the
  BIOS's failing SMM handler no longer swallows the ACPI S5 request. Installed
  and removed by `install.sh` / `uninstall.sh`.
- New read-only tool `tools/acpi-s5-info.py`.
- Tested: power off and the orange System "!" during a RAID check.

## 0.1.0 (2026-10-25)

First release, tested on one Thecus N7510 under openmediavault 6.

- `n7510-fan`: IT8728F fan control from disk temperatures (`drivetemp`), with
  full speed on CPU heat, read errors, a stalled fan or service stop.
- `n7510-lcd`: replacement for Thecus `agent2`. Info pages (hostname, WAN/LAN
  IP, RAID), password-protected menu (fan mode, reboot, power off, change
  password), USB Copy answered as not supported. Menu actions start in
  dry-run.
- `n7510-leds`: red/green tray LEDs, System "!" red/orange, USB LED, alarm
  beeps on the PC speaker. Writes only the known-safe PCA9532 pins.
- `install.sh` / `uninstall.sh`, and a journald fix for openmediavault's
  folder2ram.
- Documentation: hardware reference and pin map, the recovered LCD protocol,
  and the firmware analysis method with scripts.
