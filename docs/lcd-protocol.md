# Thecus N7510 front-panel MCU protocol, recovered from agent2

Source: `/img/bin/agent2` from Thecus firmware 2.06.02.10.cdv (version string
"1.0.1", stripped x86-64), the daemon that drives the front-panel LCD. Static
analysis with objdump, cross-checked against an `strace` of agent2 talking to
the MCU (`firmware/run-agent2.sh`, `firmware/decode-trace.py`) and against
live tests with this repository's `src/n7510-lcd.py`. Addresses refer to that
binary. The MCU is an ATmega168 on `/dev/ttyS0`, 9600 8N1, firmware `01.04.00`.

Confidence tags: **T** = verified by trace or live hardware, **D** = read from
the disassembly, **I** = inferred.

## Framing (T/D)
`02 <seq> <lenHi> <lenLo> <body…> 03`. The length is a 16-bit big-endian count of body bytes (`htons` in `build_pkt` 0x4024cc). The host seq is a global uint8 that increments on each frame. SETEXCFG and BACKLIGHT_OFF_TIMER are hand-built frames with seq fixed at `01`. The host never ACKs MCU frames. The MCU ACKs with body `06` or `<cmd> 06`. `wait4Ack` (0x403070) checks only `body[0]==06`, and only STARTWD uses it. Read bytes are masked with `&0x7f` (readport 0x4022e3).

## Host → MCU (D unless noted)
The avrpipe line format is `<name> <level-digit> <rest>\n` (do_avrpipe 0x4094f3).
- level `0`: `<rest>` = `CMD args` is looked up in the name table 0x60ea00, which maps to handlers 0x60ea80.
- level ≠ 0: an OOBM text frame (0x403a1f).
- Unknown CMDs print "Can't support cmd" and are ignored.

| pipe CMD | handler | frame body | notes |
|---|---|---|---|
| STARTWD | 0x409182 | `15` | Repeats every 1 s until ACKed (T: 37 tries in the trace). Then it enables the MCU-request thread and sends GETAVRVN. |
| GETAVRVN | 0x408f00 | `1e` | MCU replies `1e "01.04.00"` padded (T). |
| SETBTO n | 0x408eb6 | `13 n` | n = atoi. pic.sh `START` sends this. Meaning I: boot-timeout or boot-status. |
| BACKLIGHT_ON | 0x408f18 | `20` | |
| BACKLIGHT_OFF | 0x408f30 | `21` | |
| BACKLIGHT_OFF_TIMER n | 0x403dfd | `22 n` (seq 01) | T |
| SETEXCFG n | 0x403cfb | `31 a b` (seq 01) | a = 0 if n%10==0, 1 if n%10==1, else ff. b = 0 if \|n\|≤9, 1 if 10≤n≤19, else ff. pic.sh sends 90, which gives `31 00 ff` (T). |
| SETLOGO text | 0x4036d7 | `11 text` | len = 1+strlen. Up to 19 chars; the trailing `\n` is dropped. |
| BTMSG text | 0x409091 | `1d "agent2\0" ?? ?? 00 text…` | Fixed body length 32. Bytes 8–9 are uninitialised. Byte 10 = level 0. Text at +11 (≤21 chars, trimmed by isgraph/isprint). |
| (level≠0 line) | 0x403a1f | `18 name[≤9]\0 … lvl text` | Same 32-byte layout: name at +1, level at +10, text at +11. Used by `UPGRADE 2 msg` and OOBM_*. |
| USBCP 0/1/2 | 0x40921f | 0: `1b 00 "USB Copy Failed"`, 1: `1b 00 "USB Copy Success."`, 2: `1a 02 "USBCopy Progress +"`/`x` (alternates) | Builder 0x408d5f: `cmd sub text`, fixed len 23 (21-byte text). |
| DEBUG | 0x408e72 | none | Toggles the debug flag. |
| (timer) | 0x408d1b | `14` | HBT heartbeat, see below. |

Unused builders: `10` (0x403676) and `12 text` (0x403933, built but never written).
**There is no ACPWR, POWER_OFF, UPGRADE_PIC, BOOT_LOADER or SLED command in agent2.** pic.sh writes those as `0 0 POWER_OFF …` and agent2 rejects them as unsupported.

## MCU → host (dispatcher 0x4032da, jump table 0x40a318, body[0]−0x10)
| id | meaning | host action |
|---|---|---|
| `06` / `xx 06` | ACK | Only STARTWD looks at it. |
| `16 n` | **GETCFG** | Stops the timers and replies with menu n (below). T: `16 00`, `16 01`, `16 03` were seen live. |
| `17 …` | **SETCFG** | Calls `menu[cur].set(body)`, where cur = the last n−1 requested. No reply. |
| `19` | GETSYSINFO | Starts the HBT/WDT timers and replies `19` + slots (T). |
| `1a` | **USB copy request** | Stops the timers and runs `system("/img/bin/btn_copy")`. No reply. (D, 0x4034de/0x4035a0) |
| `1c` | GETPASSWD | Replies `1c "<lcmcfg_pwd>\0"`, fixed body len 22, the rest is stack garbage (T). Default "0000". |
| `1e "ver"` | GETVER reply | Writes /tmp/avr-version and sets the "version known" flag and the slot width. |
| `10–15,18,20–22` | | Logged only. |
| `1b,1d,1f`, others | | Ignored. |

**GETSYSINFO reply (T/D, 0x403af1):** `19` followed by N slots. Each slot is 33 bytes when the AVR version string is greater than "01.02.c6" (0x408f48), otherwise 21 bytes. Each slot holds a NUL-padded printf of the item format.
- Before GETVER has arrived, the reply is a bare `19` (T).
- The items are paged by an internal counter (get_sysinfo 0x4049c2, up to 17 items). Formats: `HOSTNAME:%s`, `WAN IP:%s`/`WAN:%s`, `LAN IP:%s`/`LAN:%s`, `Link Aggr:%s`, `RAID:%s`, `CPU FAN: %s `, `SYS FAN[ n]: %s `, `DATE TIME:%s`, `Ver: %s`, `miniUPS:%s`.

## Menus (GETCFG reply, 0x4045e1)
The reply body goes into the static buffer 0x60fa00, which is never cleared. **Zero-pad all slots.**
- **n=0, root (genrootmenu 0x4044d0):** `16 00 <count> name[21]×count`, len = 3+21·count. The list is dynamic (getrootmenu 0x403e82):
  1. "WAN Setting", if `rc.net check_ha_vip eth0` ≠ 0.
  2. "LAN Setting", if eth1 is not an HA VIP and (WAN DHCP is on, or (nic2 is disabled… and 802.3ad mode = 0)). Exact flags: 0x60f545/0x60f548.
  3. "Link Aggregation", if eth0 is not an HA VIP, the switch-status flag is 0 and DHCP is off.
  4. "Reset to Default", always.
  5. "Change Passwd", always.

  n is the 1-based index into *this* list.
- The menu table is at 0x60d880 in 48-byte entries: `name[20], flag(1)@+0x14, get()@+0x18, set()@+0x20`.

**List-type reply:** `16 00 <count> item[21]…`
- Reset to Default (0x403fb7): `16 00 02 "No" "Yes"`, len 45.
- Link Aggregation (0x404204): `16 00 06 "Disabled" "Load Bal." "Failover" "Balance-XOR" "802.3ad" "Balance-TLB"`, len 129.

**Edit-type reply:** `16 01 <nfields> {label[21], type(1), value[21]}…` (43 bytes per field). type `01` = IP entry, `02` = text/password entry.
- WAN (0x404415): `16 01 02 "IP:" 01 <nic1_ip> "Netmask:" 01 <nic1_netmask>`, len 89.
- LAN (0x40438f): same layout with nic2_ip and nic2_netmask, len 89.
- Change Passwd (0x4040f3): `16 01 01 "Enter New Passwd:" 02 ""`, len 46.

## SETCFG (MCU `17`) layout and actions (D; the MCU-side layout is I, inferred from the offsets agent2 reads)
- **List menus:** body[1] = 1-based chosen item.
  - Reset to Default: item 2 (Yes) runs `system("/img/bin/rst2dft.sh")`, a **factory reset**.
  - Link Aggregation: mode = table 0x60e8c0[item−1] (`none,lbrr,actbkp,lbxor,8023ad,bltlb,blalb,bcast`). update_8023ad 0x407479 then runs `update conf set v='%s' where k='nic1_mode_8023ad'`, `rc.net destory_one_link eth0`, `rc.net change_default_gw`, `8023ad.sh eth0` / `rc.net link_wan_lan 'no'` and `staticip.sh`.
- **Edit menus:** the echoed form, with value1 at body+0x19 and value2 at body+0x44 (= 3+21+1 and 3+43+21+1).
  - Change Passwd (0x4072f8): `update conf set v='%s' where k='lcmcfg_pwd'`.
  - LAN (0x407893): updates nic2_ip and nic2_netmask, then `staticip.sh … eth1`.
  - WAN (0x407f83): IP `0.0.0.0` means DHCP. It sets nic1_ipv4_dhcp_client, nic1_dhcp and nic1_dns_type, rewrites /etc/resolv.conf and nic1_dns. Otherwise it sets nic1_ip and nic1_netmask, then `rc.net link_wan_lan 'yes'` and `staticip.sh … eth0`.

## USB copy (D)
1. The MCU shows "USB Copy?" and the user confirms. The MCU sends `1a`.
2. agent2 runs btn_copy and sends nothing back.
3. btn_copy reports through `pic.sh LCM_USB 102/103/104|105`, which becomes `usbcp 0 USBCP 2/1/0`.
4. agent2 then sends `1a 02 "USBCopy Progress +|x"`, `1b 00 "USB Copy Success."` or `1b 00 "USB Copy Failed"`.

## Heartbeat / watchdog (D)
- The timer thread (0x408bdf) ticks every 2 s. Two timers are defined (0x60e930 WDT and 0x60e940 HBT), each with a period of 20×0.5 = 10 ticks, so **20 s**.
- Both timers are enabled on every GETSYSINFO and disabled on GETCFG and `1a`.
- HBT sends `14` every 20 s.
- watchdog_handler (0x408c6f) only counts: after 3×5 periods it logs "Avr heartbt fails → Reset AVR". The `/img/bin/reset51.sh` pointer is loaded but **never executed**, and the counter-reset function 0x408d4f has no caller. The host watchdog is therefore a no-op.
- agent2 parses no MCU frame that reports buttons or power. The panel buttons stay inside the MCU, and the power button is handled by the kernel's thecus_io.

## Dangerous / avoid
- No upgrade, bootloader or power-off frames exist in agent2, so their IDs are unknown. **Never send IDs outside the table above.**
- Host-side SETCFG effects (factory reset, network rewrite, password change) must be gated or stubbed in a replacement daemon.

## Confirmed on live hardware
- The MCU answers each `14` heartbeat with its own `14` (T).
- `1a` is repeated every ~5.5 s until the host answers. A progress frame
  `1a 02 <text[21]>` followed about 1.5 s later by a result frame
  `1b 00 <text[21]>` ends the USB-copy screen; a result frame alone does not (T).
- SETCFG for a list menu arrives as `17 <item>`, 1-based (T: `17 02` for the
  second item, `17 01` for the first).
- The host may serve its own menus: any root list (`16 00 <count> name[21]…`)
  works, and `16 n` then asks for entry n of that list (T).
- The MCU asks for the password (`1c`) at start-up and on entering the menu,
  and checks the entered digits itself (T).
- The MCU requests GETSYSINFO again for every page it shows (~7 s) (T).

## Open questions
1. Does the MCU need `14` heartbeats at all? Sending one every 20 s is harmless.
2. The edit-menu SETCFG layout (values at body+0x19 / +0x44) is read from the
   disassembly, not yet confirmed live.
3. The meaning of SETBTO (`13`), SETEXCFG (`31`) and `10` is inferred.
4. The sysinfo page rotation rules (0x60e7d0, curidx) are not fully decoded.
