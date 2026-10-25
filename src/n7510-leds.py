#!/usr/bin/env python3
"""Front-panel LEDs for the Thecus N7510.

Trays: red = disk missing or out of sync, green = activity.
System "!": red = a tray is bad, an md array is degraded, or n7510-fan reports
a fault; orange = an md resync/recovery/check is running. USB LED = a USB
storage device other than the boot disk is present. The PC speaker beeps three
times when "!" turns red.

Distribution-independent: Python standard library, sysfs, /dev/i2c-*, and
either the kernel's gpio_ich driver (sysfs GPIO) or /dev/port.

Hardware (mapped on a live N7510, one pin at a time):
  front  PCA9532 at SMBus 0x62: pin 9 "!" orange, pin 10 USB, pin 12 "!" red.
         Pins 0-3 are board-ID inputs and PIN 7 HARD-RESETS THE BOARD; only
         pins 9, 10 and 12 are ever written (register LS2/LS3 bits).
  buzzer the PC speaker (pcspkr input device)
  red    PCA9532 at SMBus 0x64 (i801 bus), outputs 0-6 = trays 1-7 from the top
  green  trays 1-5: ICH10 GPIO 0, 2, 3, 4, 5, active-low (driven here);
         trays 6-7: SiI3132 ports, blink in hardware
  ports  trays 1-5 = chipset AHCI ports 1-5, trays 6-7 = SiI3132
         0000:04:00.0 ports 0-1 (all verified with per-disk reads);
         AHCI port 0 holds the internal DOM

On first run the tray -> disk serial map is saved to /etc/n7510/tray-map.json.
"""
import ctypes, fcntl, glob, json, os, re, signal, struct, sys, time

PCA_ADDR = 0x64
I2C_SLAVE = 0x0703
GREEN_GPIO = {1: 0, 2: 2, 3: 3, 4: 4, 5: 5}
MAP_FILE = "/etc/n7510/tray-map.json"
POLL = 0.05          # activity sampling
BLINK = 0.05         # minimum on-time per burst
STATUS_EVERY = 10    # seconds between RAID / presence checks


# ---- I2C (PCA9532) ----------------------------------------------------------

def i801_bus():
    for d in glob.glob("/sys/bus/i2c/devices/i2c-*"):
        if open(os.path.join(d, "name")).read().startswith("SMBus I801"):
            return int(d.rsplit("-", 1)[1])
    raise RuntimeError("i801 SMBus not found (load i2c-i801 and i2c-dev)")


class SmbusData(ctypes.Union):
    _fields_ = [("byte", ctypes.c_uint8), ("word", ctypes.c_uint16), ("block", ctypes.c_uint8 * 34)]


class SmbusIoctl(ctypes.Structure):
    _fields_ = [("read_write", ctypes.c_uint8), ("command", ctypes.c_uint8),
                ("size", ctypes.c_uint32), ("data", ctypes.POINTER(SmbusData))]


I2C_SMBUS, I2C_SMBUS_WRITE, I2C_SMBUS_BYTE_DATA = 0x0720, 0, 2


class PCA9532:
    # The i801 controller only does SMBus transactions, not raw I2C writes.
    def __init__(self, addr=PCA_ADDR):
        self.fd = os.open(f"/dev/i2c-{i801_bus()}", os.O_RDWR)
        fcntl.ioctl(self.fd, I2C_SLAVE, addr)

    def write_reg(self, reg, value):
        data = SmbusData(byte=value)
        args = SmbusIoctl(I2C_SMBUS_WRITE, reg, I2C_SMBUS_BYTE_DATA, ctypes.pointer(data))
        fcntl.ioctl(self.fd, I2C_SMBUS, args)

    def set_on(self, outputs):
        regs = [0, 0, 0, 0]
        for out in outputs:
            regs[out // 4] |= 1 << (2 * (out % 4))   # LSx value 01 = output on
        for i, v in enumerate(regs):
            self.write_reg(6 + i, v)


class FrontPanel:
    """PCA9532 0x62. Writes only LS2 (pins 8-11) and LS3 (pins 12-15), and only
    sets pins 9, 10 and 12, so the reset pin 7 (LS1) is never touched."""
    ALLOWED = {"orange": 9, "usb": 10, "red": 12}

    def __init__(self):
        self.chip = PCA9532(0x62)

    def set(self, on):
        pins = {self.ALLOWED[name] for name in on}
        ls2 = sum(1 << (2 * (p - 8)) for p in pins if 8 <= p <= 11)
        ls3 = sum(1 << (2 * (p - 12)) for p in pins if 12 <= p <= 15)
        self.chip.write_reg(8, ls2)
        self.chip.write_reg(9, ls3)


def beep(times=3, hz=2000, secs=0.15):
    path = "/dev/input/by-path/platform-pcspkr-event-spkr"
    try:
        fd = os.open(path, os.O_WRONLY)
    except OSError:
        return
    for _ in range(times):
        os.write(fd, struct.pack("llHHi", 0, 0, 0x12, 0x02, hz))
        time.sleep(secs)
        os.write(fd, struct.pack("llHHi", 0, 0, 0x12, 0x02, 0))
        time.sleep(secs)
    os.close(fd)


def md_state():
    """('degraded' | 'busy' | 'ok') across all md arrays."""
    try:
        text = open("/proc/mdstat").read()
    except OSError:
        return "ok"
    if any("_" in m for m in re.findall(r"\[([U_]+)\]", text)):
        return "degraded"
    if re.search(r"\b(resync|recovery|reshape|check)\b", text):
        return "busy"
    return "ok"


def fan_fault():
    try:
        return open("/run/n7510/fan-status").read().strip() not in ("", "ok")
    except OSError:
        return False


def usb_storage_present():
    root = os.stat("/").st_dev
    boot_disk = None
    for dev in glob.glob("/sys/block/sd*"):
        name = os.path.basename(dev)
        for part in [name] + [os.path.basename(p) for p in glob.glob(f"{dev}/{name}*")]:
            try:
                major, minor = open(f"/sys/class/block/{part}/dev").read().strip().split(":")
            except OSError:
                continue
            if os.makedev(int(major), int(minor)) == root:
                boot_disk = name
    return any("/usb" in os.path.realpath(f"{dev}/device") and os.path.basename(dev) != boot_disk
               for dev in glob.glob("/sys/block/sd*"))


# ---- GPIO (green LEDs) --------------------------------------------------------

class SysfsGpio:
    """gpio_ich through the sysfs GPIO interface (needs acpi_enforce_resources=lax)."""

    def __init__(self, pins):
        base = None
        for chip in glob.glob("/sys/class/gpio/gpiochip*"):
            if open(os.path.join(chip, "label")).read().strip() == "gpio_ich":
                base = int(open(os.path.join(chip, "base")).read())
        if base is None:
            raise RuntimeError("gpio_ich not loaded")
        self.files = {}
        for p in pins:
            n = base + p
            path = f"/sys/class/gpio/gpio{n}"
            if not os.path.exists(path):
                with open("/sys/class/gpio/export", "w") as f:
                    f.write(str(n))
            with open(f"{path}/direction", "w") as f:
                f.write("high")                      # active-low: high = off
            self.files[p] = open(f"{path}/value", "w")

    def set(self, pin, on):
        f = self.files[pin]
        f.write("0" if on else "1")
        f.flush()

    def release(self):
        for f in self.files.values():
            f.write("1")
            f.close()


class PortGpio:
    """Direct ICH10 GPIO registers via /dev/port (GPIOBASE 0x500, bank 1)."""
    BASE, USE_SEL, IO_SEL, LVL = 0x500, 0x00, 0x04, 0x0C

    def __init__(self, pins):
        self.fd = os.open("/dev/port", os.O_RDWR)
        self.mask = sum(1 << p for p in pins)
        self.saved = {o: self.rd(o) for o in (self.USE_SEL, self.IO_SEL, self.LVL)}
        self.wr(self.LVL, self.rd(self.LVL) | self.mask)            # off first
        self.wr(self.IO_SEL, self.rd(self.IO_SEL) & ~self.mask)     # outputs
        self.wr(self.USE_SEL, self.rd(self.USE_SEL) | self.mask)    # GPIO function
        self.level = self.rd(self.LVL)

    def rd(self, off):
        os.lseek(self.fd, self.BASE + off, 0)
        return struct.unpack("<I", os.read(self.fd, 4))[0]

    def wr(self, off, val):
        os.lseek(self.fd, self.BASE + off, 0)
        os.write(self.fd, struct.pack("<I", val))

    def set(self, pin, on):
        self.level = self.level & ~(1 << pin) if on else self.level | (1 << pin)
        self.wr(self.LVL, (self.rd(self.LVL) & ~self.mask) | (self.level & self.mask))

    def release(self):
        for off in (self.LVL, self.IO_SEL, self.USE_SEL):
            self.wr(off, (self.rd(off) & ~self.mask) | (self.saved[off] & self.mask))


def open_gpio(pins):
    try:
        g = SysfsGpio(pins)
        print("green LEDs via gpio_ich", flush=True)
        return g
    except Exception as e:
        print(f"gpio_ich unavailable ({e}); using /dev/port", flush=True)
        return PortGpio(pins)


# ---- disks ----------------------------------------------------------------

def disk_ports():
    """{(controller, port): blockdev} for SATA disks, ports numbered per controller."""
    hosts = {}
    for dev in glob.glob("/sys/block/sd*"):
        real = os.path.realpath(os.path.join(dev, "device"))
        m = re.search(r"/(0000:[0-9a-f:.]+)/ata(\d+)/", real)
        if m:
            hosts.setdefault(m.group(1), []).append((int(m.group(2)), os.path.basename(dev)))
    out = {}
    for pci, items in hosts.items():
        first = min(int(p.split("ata")[1]) for p in glob.glob(f"/sys/bus/pci/devices/{pci}/ata*"))
        for ata, name in items:
            out[(pci, ata - first)] = name
    return out


# Board-fixed PCI addresses: ICH10R AHCI, and the SiI3132 that serves trays 6-7
# (the second SiI3132 at 0000:05:00.0 is eSATA).
AHCI, SIL = "0000:00:1f.2", "0000:04:00.0"
TRAY_PORT = {1: (AHCI, 1), 2: (AHCI, 2), 3: (AHCI, 3), 4: (AHCI, 4), 5: (AHCI, 5),
             6: (SIL, 0), 7: (SIL, 1)}


def serial(name):
    # SCSI VPD page 0x80 (unit serial number); libata fills it for SATA disks.
    p = f"/sys/block/{name}/device/vpd_pg80"
    try:
        return open(p, "rb").read()[4:].decode("ascii", "replace").strip(" \x00")
    except OSError:
        return ""


def load_map(ports):
    if os.path.exists(MAP_FILE):
        with open(MAP_FILE) as f:
            return {int(k): v for k, v in json.load(f).items()}
    tray_map = {t: serial(ports[p]) for t, p in TRAY_PORT.items() if p in ports}
    os.makedirs(os.path.dirname(MAP_FILE), exist_ok=True)
    with open(MAP_FILE, "w") as f:
        json.dump(tray_map, f, indent=2)
    print(f"recorded tray map {tray_map}", flush=True)
    return tray_map


def in_sync_members():
    names = set()
    for state in glob.glob("/sys/block/md*/md/dev-*/state"):
        if "in_sync" in open(state).read():
            names.add(os.path.basename(os.path.dirname(state))[4:])
    return names


def io_count(name):
    try:
        f = open(f"/sys/block/{name}/stat").read().split()
        return int(f[0]) + int(f[4])          # reads + writes completed
    except OSError:
        return None


# ---- main -----------------------------------------------------------------

def main():
    red = PCA9532()
    front = FrontPanel()
    gpio = open_gpio(list(GREEN_GPIO.values()))

    def stop(*_):
        red.set_on([])
        front.set([])
        gpio.release()
        sys.exit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    tray_map = load_map(disk_ports())
    last_bad, last_front, next_status = None, None, 0.0
    tray_dev, prev, lit_until = {}, {}, {}
    while True:
        now = time.time()
        if now >= next_status:
            by_serial = {serial(n): n for n in disk_ports().values()}
            tray_dev = {t: by_serial.get(s) for t, s in tray_map.items()}
            members = in_sync_members()
            bad = sorted(t for t, d in tray_dev.items() if d is None or d not in members)
            if bad != last_bad:
                red.set_on([t - 1 for t in bad])
                print(f"bad trays: {bad or 'none'}", flush=True)
                last_bad = bad
            md = md_state()
            on = set()
            if bad or md == "degraded" or fan_fault():
                on.add("red")
            elif md == "busy":
                on.add("orange")
            if usb_storage_present():
                on.add("usb")
            if on != last_front:
                front.set(on)
                print(f"front: {sorted(on) or 'off'} (md {md})", flush=True)
                if "red" in on and (last_front is None or "red" not in last_front):
                    beep()
                last_front = on
            next_status = now + STATUS_EVERY
        for tray, pin in GREEN_GPIO.items():
            dev = tray_dev.get(tray)
            count = io_count(dev) if dev else None
            busy = count is not None and prev.get(tray) is not None and count != prev[tray]
            prev[tray] = count
            if busy:
                if lit_until.get(tray, 0) < now:
                    gpio.set(pin, True)
                lit_until[tray] = now + BLINK
            elif tray in lit_until and lit_until[tray] < now:
                gpio.set(pin, False)
                del lit_until[tray]
        time.sleep(POLL)


if __name__ == "__main__":
    main()
