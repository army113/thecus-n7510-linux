# Thecus N7510 on modern Linux

Front-panel LCD, buttons, fans, LEDs and beeper for the **Thecus N7510**
(7-bay, Intel Atom D2701, "Granite Well" board) running any current Linux
distribution instead of the end-of-life Thecus OS.

Thecus stopped updating these boxes years ago. The hardware is a plain x86 PC,
so it runs Debian, openmediavault, Ubuntu, Fedora and others fine, but out of
the box the LCD sits on its boot animation, the buttons do nothing, the fans
run at fixed BIOS speeds and none of the tray or status LEDs work. This
repository fixes that with three small daemons that use only the Python 3
standard library and mainline kernel drivers.

| Feature | Without this | With this |
|---|---|---|
| Front LCD | stuck on the boot animation | pages: hostname, WAN/LAN IP, RAID state |
| Buttons and menu | dead | password-protected menu: fan mode, reboot, power off, change password |
| Fans | fixed BIOS speeds, PWM disabled | follow the hottest disk; full speed on any fault |
| Tray LEDs (red) | off | lit while that tray's disk is missing or out of sync |
| Tray LEDs (green) | only trays 6–7 | all seven blink on disk activity |
| System "!" LED | off | red on a fault (plus three beeps), orange during RAID resync |
| USB LED | off | on while a USB storage device is attached |

Tested on openmediavault 6 (Debian 11, kernel 6.0). The code avoids
distribution-specific pieces so it should move to newer releases unchanged.

> **Not affiliated with Thecus.** Use at your own risk. This drives hardware
> directly; read [Safety](#safety) first.

## Install

```sh
git clone https://github.com/army113/thecus-n7510-linux.git
cd thecus-n7510-linux
sudo ./install.sh
```

The installer copies the daemons to `/opt/n7510/`, sets the `it87` option
`fix_pwm_polarity=1`, autoloads `it87`, `drivetemp`, `i2c-i801`, `i2c-dev`
and `pcspkr`, and enables `n7510-fan`, `n7510-lcd` and `n7510-leds`. On
openmediavault it also installs a small fix that keeps the systemd journal
working under folder2ram. `sudo ./uninstall.sh` removes everything.

Requirements: Python 3.7+, systemd, a kernel with the drivers above
(any mainstream distribution kernel). Optional: `gpio_ich` with
`acpi_enforce_resources=lax` on the kernel command line; without it, the green
tray LEDs are driven through `/dev/port`, which Secure Boot lockdown blocks.

LCD menu actions start in **dry-run** mode (choices are only logged). Enable
them with `sudo touch /etc/n7510/lcd-actions-enabled && sudo systemctl restart n7510-lcd`.
The default LCD password is `0000`.

## Safety

- **PCA9532 `0x62` pin 7 hard-resets the whole board.** The daemons only ever
  write pins 9, 10 and 12 of that chip (enforced in code). If you probe pins
  yourself, stop your RAID arrays first and switch one pin at a time.
- Pins 0–3 of `0x62` are board-ID inputs; never drive them.
- The original Thecus firmware lives on an internal 1 GB DOM. Nothing here
  writes to it, and the firmware tools work on an image copy.
- Stopping `n7510-fan` sets both fans to full speed.

## How it was done

The protocols were recovered from the Thecus firmware still sitting on the
internal DOM:

1. Image the DOM and unpack its ramdisk. Partition 3 is encrypted (loop-AES,
   AES-128) with a key built into Thecus's modified `losetup -n`. Running that
   binary under `strace` in a chroot shows the key in the `LOOP_SET_STATUS64`
   ioctl, even though a modern kernel rejects the call. The key is **not**
   published here; `firmware/capture-dom-key.sh` recovers it from your own DOM.
2. The decrypted partition holds Thecus's per-model configs, scripts and the
   LCD daemon `agent2`. Running `agent2` under `strace` recorded its serial
   exchange with the panel's ATmega168, and disassembling it decoded the menus
   and settings: [LCD protocol](docs/lcd-protocol.md).
3. Every LED, fan and pin was then mapped on a live unit, one pin at a time:
   [hardware reference](docs/hardware.md).

Details of the firmware layout and tools: [firmware analysis](docs/firmware.md).

## Repository layout

| Path | Contents |
|---|---|
| `src/` | the three daemons |
| `systemd/` | service units and the openmediavault journald fix |
| `tools/` | probing and test helpers, see [tools](tools/README.md) |
| `firmware/` | DOM imaging, decryption and `agent2` tracing scripts |
| `docs/` | hardware reference, LCD protocol, firmware analysis |

## Related models

The N7510 shares its firmware build (`2.06.x.cdv`) with the N2800, N4510U,
N4800 and N5550, and its board design with the N5550. Much of this probably
applies there too, but pin maps differ between boards (the N5550 reports
board ID 2, the N7510 6), so verify one pin at a time before trusting this
map on another model. Reports and pull requests are welcome.

## Credits

- [ipilcher/n5550](https://github.com/ipilcher/n5550): the N5550 board
  module, LCD notes and the Debian/openmediavault recipe that made this
  possible.
- [Nicholas Starke](https://starkeblog.com/cryptography/firmware/2024/06/11/thecus-nas-firmware-decrypt.html):
  Thecus firmware-update decryption.
- [jncronin/pymonitor](https://github.com/jncronin/pymonitor),
  [system1357/Thecus_tools](https://github.com/system1357/Thecus_tools) and
  [mStirner/thecus-nas](https://github.com/mStirner/thecus-nas): earlier
  Thecus LCD and GPIO work.
- The openmediavault forum threads on Thecus hardware.

## License

[MIT](LICENSE). Thecus is a trademark of its owner; this project contains no
Thecus code or firmware.
