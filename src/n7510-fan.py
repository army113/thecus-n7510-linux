#!/usr/bin/env python3
"""Fan control for the Thecus N7510 (IT8728F) under openmediavault.

Needs it87 loaded with fix_pwm_polarity=1 (the Thecus firmware sets the same
active-high polarity) and drivetemp for disk temperatures.
pwm1 drives fan1 and pwm3 drives fan3; pwm2 is not connected (mapped on a live N7510).

Speed follows the hottest RAID member disk; CPU temperature overrides to full.
Any read error, a stalled fan, or stopping the service sets both fans to full.
"""
import glob, os, signal, sys, time

PWMS = {"pwm1": "fan1_input", "pwm3": "fan3_input"}
DISK_LOW, DISK_HIGH = 35.0, 45.0      # °C: minimum speed below, full speed above
CPU_FULL = 70.0                        # °C: full speed at or above
PWM_MIN, PWM_MAX = 100, 255
INTERVAL = 10
FAN_MODE_FILE = "/run/n7510/fan-mode"
STATUS_FILE = "/run/n7510/fan-status"
EXCLUDE_MODELS = ("UDinfo",)           # the internal DOM runs warm and is not cooled by these fans


def hwmon(name):
    for n in glob.glob("/sys/class/hwmon/hwmon*/name"):
        if open(n).read().strip() == name:
            return os.path.dirname(n)
    raise RuntimeError(f"hwmon {name} not found")


def read_int(path):
    with open(path) as f:
        return int(f.read().strip())


def disk_temps():
    temps = {}
    for n in glob.glob("/sys/class/hwmon/hwmon*/name"):
        if open(n).read().strip() != "drivetemp":
            continue
        h = os.path.dirname(n)
        dev = os.path.realpath(os.path.join(h, "device"))
        blocks = os.listdir(os.path.join(dev, "block")) if os.path.isdir(os.path.join(dev, "block")) else []
        model = open(os.path.join(dev, "model")).read().strip() if os.path.exists(os.path.join(dev, "model")) else ""
        if not blocks or model.startswith(EXCLUDE_MODELS):
            continue
        try:
            temps[blocks[0]] = read_int(os.path.join(h, "temp1_input")) / 1000
        except OSError:
            pass
    return temps


def cpu_temp():
    h = hwmon("coretemp")
    return max(read_int(p) / 1000 for p in glob.glob(f"{h}/temp*_input"))


def write_status(status):
    # Read by n7510-trayled to light the red System LED: "ok", "stall" or "read-error".
    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    with open(STATUS_FILE + ".tmp", "w") as f:
        f.write(status + "\n")
    os.replace(STATUS_FILE + ".tmp", STATUS_FILE)


def fan_mode():
    # Set from the front-panel menu by n7510-lcd: "auto" (default) or "full".
    try:
        return open(FAN_MODE_FILE).read().strip()
    except OSError:
        return "auto"


def curve(disk, cpu):
    if cpu >= CPU_FULL or disk >= DISK_HIGH:
        return PWM_MAX
    if disk <= DISK_LOW:
        return PWM_MIN
    return int(PWM_MIN + (disk - DISK_LOW) / (DISK_HIGH - DISK_LOW) * (PWM_MAX - PWM_MIN))


def set_all(it, value):
    for p in PWMS:
        with open(f"{it}/{p}_enable", "w") as f:
            f.write("1")
        with open(f"{it}/{p}", "w") as f:
            f.write(str(value))


def main():
    it = hwmon("it8728")

    def full_and_exit(*_):
        set_all(it, PWM_MAX)
        sys.exit(0)

    signal.signal(signal.SIGTERM, full_and_exit)
    signal.signal(signal.SIGINT, full_and_exit)
    last = None
    stalled_since = {}
    while True:
        try:
            disks = disk_temps()
            if not disks:
                raise RuntimeError("no disk temperatures")
            hottest = max(disks.values())
            cpu = cpu_temp()
            target = curve(hottest, cpu)
            if fan_mode() == "full":
                target = PWM_MAX
            for p, tach in PWMS.items():
                rpm = read_int(f"{it}/{tach}")
                if rpm == 0 and last is not None:
                    stalled_since.setdefault(p, time.time())
                    if time.time() - stalled_since[p] > 30:
                        target = PWM_MAX
                        print(f"{p}: {tach} reads 0 RPM, forcing full speed", flush=True)
                else:
                    stalled_since.pop(p, None)
        except Exception as e:
            target = PWM_MAX
            hottest = cpu = float("nan")
            print(f"read error ({e}), full speed", flush=True)
        set_all(it, target)
        status = "read-error" if hottest != hottest else ("stall" if any(
            time.time() - t > 30 for t in stalled_since.values()) else "ok")
        write_status(status)
        if target != last:
            print(f"disk max {hottest:.0f}C cpu {cpu:.0f}C -> pwm {target}", flush=True)
            last = target
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
