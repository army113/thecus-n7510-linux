#!/usr/bin/env python3
"""Front-panel LCD daemon for the Thecus N7510 under openmediavault.

Replaces Thecus's agent2. The panel is an ATmega168 on /dev/ttyS0 at 9600 8N1
that draws pages and menus and handles the buttons itself; the host answers its
requests. Frames both ways: 02 <seq> <len hi> <len lo> <body> 03, body[0] = command.

MCU -> host
  19        GETSYSINFO  reply 19 + four 33-byte "LABEL:value" slots (pages)
  16 n      GETCFG      reply with menu n (0 = root, n = 1-based root position)
  17 ...    SETCFG      user chose a list item (body[1], 1-based) or entered
                        values (at body+0x19 and body+0x44)
  1a        USB copy confirmed; reply 1b 00 <text> so the panel stops waiting
  1c        GETPASSWD   reply 1c <password> NUL-padded to 22 bytes
  1e ver    reply to the host's 1e version request
Host -> MCU: 15 STARTWD, 1e GETAVRVN, 31 SETEXCFG, 22 backlight timer, 14 heartbeat.

Protocol recovered from Thecus agent2 (firmware 2.06.02.10.cdv on the internal
DOM; see docs/lcd-protocol.md) and ipilcher/n5550.
Menu actions stay in dry-run (logged only) until /etc/n7510/lcd-actions-enabled
exists. Interface names for the WAN/LAN pages: N7510_WAN / N7510_LAN.
"""
import os, re, select, socket, subprocess, sys, termios, time

PORT = os.environ.get("N7510_LCD_PORT", "/dev/ttyS0")
WAN = os.environ.get("N7510_WAN", "enp1s0")   # rear WAN/LAN1 port (82574L on PCI 01:00.0)
LAN = os.environ.get("N7510_LAN", "enp2s0")   # rear LAN2 port (82574L on PCI 02:00.0)
LOG = "/var/log/n7510-lcd.log"
STATE_DIR = "/etc/n7510"
PASSWORD_FILE = f"{STATE_DIR}/lcd-password"
FAN_MODE_FILE = "/run/n7510/fan-mode"
ACTIONS_ENABLED = os.path.exists(f"{STATE_DIR}/lcd-actions-enabled")
HEARTBEAT = 20

seq = 0


def log(msg):
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    try:
        with open(LOG, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass


def open_port():
    fd = os.open(PORT, os.O_RDWR | os.O_NOCTTY)
    a = termios.tcgetattr(fd)
    a[0] = termios.IGNPAR
    a[1] = 0
    a[2] = termios.CLOCAL | termios.HUPCL | termios.CREAD | termios.CS8
    a[3] = 0
    a[4] = a[5] = termios.B9600
    a[6][termios.VMIN] = 0
    a[6][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW, a)
    termios.tcflush(fd, termios.TCIOFLUSH)
    return fd


def send(fd, body):
    global seq
    n = len(body)
    frame = bytes([0x02, seq & 0xFF, n >> 8, n & 0xFF]) + body + b"\x03"
    seq += 1
    os.write(fd, frame)
    termios.tcdrain(fd)
    time.sleep(0.1)


def field(text, size):
    b = text.encode("ascii", "replace")[:size - 1]
    return b + b"\x00" * (size - len(b))


# ---- data sources ---------------------------------------------------------

def ipv4(ifname):
    try:
        out = subprocess.run(["ip", "-4", "-o", "addr", "show", "dev", ifname],
                             capture_output=True, text=True, timeout=5).stdout.split()
        return out[out.index("inet") + 1].split("/")[0] if "inet" in out else "N/A"
    except Exception:
        return "N/A"


def raid_state():
    try:
        text = open("/proc/mdstat").read()
    except OSError:
        return "N/A"
    arrays = [l.split()[0] for l in text.splitlines() if l.startswith("md")]
    if not arrays:
        return "none"
    bad = any("_" in m for m in re.findall(r"\[([U_]+)\]", text))
    return f"{arrays[0]} {'degraded' if bad else 'clean'}"


def password():
    try:
        p = open(PASSWORD_FILE).read().strip()
        return p if re.fullmatch(r"\d{4}", p) else "0000"
    except OSError:
        return "0000"


def fan_mode():
    try:
        return open(FAN_MODE_FILE).read().strip() or "auto"
    except OSError:
        return "auto"


def sysinfo():
    fields = [
        f"HOSTNAME:{socket.gethostname()}",
        f"WAN IP:{ipv4(WAN)}",
        f"LAN IP:{ipv4(LAN)}",
        f"RAID:{raid_state()}",
    ]
    return b"\x19" + b"".join(field(f, 33) for f in fields)


# ---- menus ----------------------------------------------------------------

def list_menu(items):
    return bytes([0x16, 0x00, len(items)]) + b"".join(field(i, 21) for i in items)


def edit_menu(fields):
    # fields: (label, type, value); type 01 = IP entry, 02 = text/password
    body = bytearray([0x16, 0x01, len(fields)])
    for label, kind, value in fields:
        body += field(label, 21) + bytes([kind]) + field(value, 21)
    return bytes(body)


def act_fan(choice):
    mode = {1: "auto", 2: "full"}.get(choice)
    if mode:
        os.makedirs(os.path.dirname(FAN_MODE_FILE), exist_ok=True)
        with open(FAN_MODE_FILE, "w") as f:
            f.write(mode + "\n")
        return f"fan mode {mode}"


def act_reboot(choice):
    if choice == 2:
        subprocess.Popen(["systemctl", "reboot"])
        return "reboot"


def act_poweroff(choice):
    if choice == 2:
        subprocess.Popen(["systemctl", "poweroff"])
        return "poweroff"


def act_password(values):
    new = values[0]
    if re.fullmatch(r"\d{4}", new):
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(PASSWORD_FILE, "w") as f:
            f.write(new + "\n")
        os.chmod(PASSWORD_FILE, 0o600)
        return "password changed"
    return f"password rejected ({len(new)} chars, need 4 digits)"


MENUS = [
    ("Fan mode", lambda: list_menu(["Auto", "Full speed"]), "list", act_fan),
    ("Reboot NAS", lambda: list_menu(["No", "Yes"]), "list", act_reboot),
    ("Power off", lambda: list_menu(["No", "Yes"]), "list", act_poweroff),
    ("Change Passwd", lambda: edit_menu([("Enter New Passwd:", 0x02, "")]), "edit", act_password),
]


def root_menu():
    return list_menu([m[0] for m in MENUS])


def cstr(b):
    return b.split(b"\x00")[0].decode("ascii", "replace").strip()


def handle_setcfg(body, current):
    if current is None or not 1 <= current <= len(MENUS):
        log(f"SETCFG with no open menu: {body.hex(' ')}")
        return
    name, _, kind, action = MENUS[current - 1]
    if kind == "list":
        arg = body[1] if len(body) > 1 else 0
        desc = f"{name}: item {arg}"
    else:
        arg = [cstr(body[0x19:0x19 + 21]), cstr(body[0x44:0x44 + 21])]
        desc = f"{name}: values {['*' * len(v) for v in arg] if kind == 'edit' and 'Passwd' in name else arg}"
    log(f"SETCFG {desc} raw={body.hex(' ')}")
    if not ACTIONS_ENABLED:
        log("dry-run: action not executed")
        return
    result = action(arg)
    if result:
        log(f"action: {result}")


# ---- main loop ------------------------------------------------------------

def handshake(fd):
    send(fd, b"\x15")              # STARTWD
    send(fd, b"\x15")
    send(fd, b"\x1e")              # GETAVRVN
    send(fd, b"\x31\x00\xff")      # SETEXCFG 90
    send(fd, b"\x22\x05")          # BACKLIGHT_OFF_TIMER 5


def frames(buf):
    out = []
    while True:
        i = buf.find(b"\x02")
        if i < 0:
            return out, b""
        if len(buf) < i + 4:
            return out, buf[i:]
        n = buf[i + 2] << 8 | buf[i + 3]
        if len(buf) < i + 5 + n:
            return out, buf[i:]
        f = buf[i:i + 5 + n]
        buf = buf[i + 5 + n:]
        if f[-1] == 0x03:
            out.append(f[4:-1])


def main():
    fd = open_port()
    log(f"start (actions {'enabled' if ACTIONS_ENABLED else 'dry-run'})")
    handshake(fd)
    buf = b""
    next_push = 0.0
    next_beat = time.time() + HEARTBEAT
    on_pages = True
    current_menu = None
    while True:
        now = time.time()
        if now >= next_push:
            send(fd, sysinfo())
            next_push = now + 60
        if on_pages and now >= next_beat:
            send(fd, b"\x14")
            next_beat = now + HEARTBEAT
        r, _, _ = select.select([fd], [], [], 1.0)
        if not r:
            continue
        data = os.read(fd, 512)
        if not data:
            continue
        got, buf = frames(buf + data)
        for body in got:
            cmd = body[:1]
            if body == b"\x06" or body[1:] == b"\x06" or body == b"\x14":   # acks, heartbeat reply
                continue
            if cmd == b"\x19":
                send(fd, sysinfo())
                on_pages = True
            elif cmd == b"\x16":
                n = body[1] if len(body) > 1 else 0
                on_pages = False
                if n == 0:
                    send(fd, root_menu())
                    current_menu = None
                elif 1 <= n <= len(MENUS):
                    send(fd, MENUS[n - 1][1]())
                    current_menu = n
                else:
                    send(fd, root_menu())
                log(f"GETCFG {n} answered")
            elif cmd == b"\x17":
                handle_setcfg(body, current_menu)
            elif cmd == b"\x1a":
                # agent2 sends progress (1a 02) before the result (1b 00); the MCU waits for that order.
                on_pages = False
                send(fd, b"\x1a\x02" + field("USBCopy Progress +", 21))
                time.sleep(1.5)
                send(fd, b"\x1b\x00" + field("USB Copy N/A", 21))
                log("USB copy request answered (not supported)")
            elif cmd == b"\x1c":
                send(fd, b"\x1c" + field(password(), 21))
            elif cmd == b"\x1e":
                log(f"MCU version {cstr(body[1:])}")
            else:
                log(f"unhandled {body.hex(' ')}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
