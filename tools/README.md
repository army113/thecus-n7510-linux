# Tools

Helpers used to map the hardware. Run them as root on the NAS.

| File | Purpose | Safety |
|---|---|---|
| `beep.py [hz] [s]` | PC-speaker tone | safe |
| `gpio-dump.py [pins]` | read ICH10 GPIO configuration | read-only |
| `gpio-pin.py <pin> low\|high\|restore\|show` | set or restore one ICH10 GPIO pin (original state saved) | changes hardware; one pin at a time |
| `gpio-led-test.py HH:MM:SS [pins]` | timed low/high test of ICH10 GPIO pins; start it with `setsid nohup` on its own | changes hardware; restores each pin |
| `tray-led-test.sh HH:MM:SS` | light PCA9532 `0x64` outputs one by one on a timer | safe (tray LEDs only) |
| `tray-activity-test.sh HH:MM:SS` | read each RAID member in turn to identify its tray | read-only |
| `fan-map.sh` | map PWM outputs to fan tachometers; ends at full speed | briefly slows each fan |

`gpio-pin.py` and `gpio-led-test.py` need `/dev/port` (no kernel lockdown).
The shell tools need `i2c-tools`. Stop `n7510-leds` before probing LEDs or GPIO
by hand, or it will overwrite your changes. Never drive PCA9532 `0x62` pin 7.
