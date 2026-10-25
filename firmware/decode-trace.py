#!/usr/bin/env python3
"""Decode serial frames (fd 3) from the agent2 strace into STX/ETX messages."""
import ast, os, re, sys

path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.environ.get("THECUS_DOM_DIR", "/root/thecus-dom"), "agent2.trace")
pat = re.compile(r'^(\d+) (\S+) (?:(write|read)\(3, |<\.\.\. read resumed>)"((?:[^"\\]|\\.)*)"')
tx, rx = [], []
for line in open(path):
    m = pat.match(line)
    if not m:
        continue
    data = ast.literal_eval('b"' + m.group(4) + '"')
    kind = m.group(3) or "read"
    (tx if kind == "write" else rx).append((m.group(2), data))


def frames(chunks):
    buf = b""
    for ts, d in chunks:
        buf += d
        while True:
            i = buf.find(b"\x02")
            if i < 0 or len(buf) < i + 4:
                break
            n = buf[i + 3]
            if len(buf) < i + 5 + n:
                break
            yield ts, buf[i:i + 5 + n]
            buf = buf[i + 5 + n:]


for label, chunks in (("TX host->MCU", tx), ("RX MCU->host", rx)):
    print("==", label)
    for ts, f in frames(chunks):
        body = f[4:-1]
        printable = "".join(chr(c) if 32 <= c < 127 else "." for c in body)
        print(f"{ts} seq={f[1]:02x} len={f[3]:3d} cmd={body[:1].hex()} | {printable}")
        if len(body) > 40:
            print("     hex:", body.hex(" "))
