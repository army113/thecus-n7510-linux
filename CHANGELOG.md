# Changelog

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
