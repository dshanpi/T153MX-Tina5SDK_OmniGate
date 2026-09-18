# T153MX board validation and Goodix follow-up (2026-09-17)

## Runtime result before the change

The board booted Linux 5.10.198 build `#69` from `rootfsA`. Display, RTC,
storage, the OmniGate Web health endpoint and the HMI process were operational.
The GT911 did not register an input device on this boot:

- the live DT node was `2-0014`;
- TWI2 reported a timeout while sending the ninth SCL clock;
- both Goodix I2C test attempts returned `-22`;
- `/dev/input/touchscreen` and the expected Goodix event node were absent.

The same `#69` image had registered GT911 ID 967 on the earlier verified cold
boot. The compiled DTB still contained the verified address, interrupt, reset
and coordinate values, so this was not a regression to the old `0x5d` DTB.

## Root cause addressed in source

The generic Goodix driver only enabled its probe-time reset when both the reset
and interrupt pins were exposed as GPIO descriptors. The T153MX intentionally
keeps PJ7 owned by pinctrl as a falling-edge interrupt, because exposing it as
`irq-gpios` caused probe error `-22`. As a result, the declared PJ6 reset line
was not used during probe and a controller left in a bad power-on state could
fail both I2C attempts permanently.

The fix adds an opt-in `goodix,reset-without-int-gpio` board property. For this
property only, the driver asserts and releases PJ6 while PJ7 remains a pinctrl
input with pull-up, selecting address `0x14`. Other Goodix boards keep their
existing behavior.

CAN defaults in `/etc/default/can` and `S42can` were also changed from 1 Mbit/s
to 500 kbit/s so they match `/etc/omnigate-web/config.json`.

## Build and pre-flash evidence

- Host tests: 16 passed.
- SDK overlay verification: 167 files matched; 8 offline 4G archives verified.
- Kernel and DTB build: passed.
- Firmware pack: `Dragon execute image.cfg SUCCESS`, `pack finish`.
- Image: `out/t153_linux_omnigate_uart0.img`.
- Bytes: `604364800`.
- SHA-256: `550947c6a1e10d99c508a6a875d0c51bebd2a48b42b7f85f460e95a11f2b226a`.
- Format: unencrypted Allwinner `IMAGEWTY` v3 with 46 embedded objects.
- LYNX transfer completed with the same byte count and SHA-256.

This record is pre-flash evidence only. Do not claim the touch regression fixed
until an authorized verified flash, cold boot, Goodix ID/event-node check and
physical coordinate test have all passed.

## Flash attempt

The image was transferred to LYNX with byte-for-byte SHA-256 verification and
started in `partition + verify + reboot` mode as task
`flash-1789643899503152500`.

The board entered FEL through the bound serial console and completed RAM-only
DRAM/FES initialization. MBR, `boot-resource`, `env` and `env-redund` completed.
USB transport then failed while writing `bootA`:

- overall progress: 20.7631%;
- current partition: `bootA` (3.4539%);
- transferred bytes: 17,177,600 of 497,333,984;
- committed bytes: not reported;
- verification: failed, error code `-1`;
- post-flash reboot: not run;
- terminal error: `USB transfer failed`.

After a controlled power cycle the scoped USB target remained online in FEL and
Linux/ADB did not start. No automatic retry was made because the failure mode is
the same unstable USB transport seen in earlier work. The board is intentionally
left in FEL for a recovery flash after the physical USB connection is reseated.

The operator subsequently authorized an autonomous power-cycle, retry and
post-flash test. LYNX cycled board power for three seconds, rediscovered the
same scoped FEL target, and started recovery task
`flash-1789650619076344200`. DRAM initialization, RAM-only U-Boot/FES startup,
reconnection and the eMMC preflight all succeeded; the device reported eMMC,
7456 MB and the expected 12 partitions. USB transfer failed again while sending
the 64 KiB MBR, before any committed byte count was reported:

- overall progress: 12%;
- transferred bytes: 0;
- committed bytes: not reported;
- verification: failed, error code `-1`;
- post-flash reboot: not run.

This second failure occurred earlier than the first and confirms that software
power cycling cannot stabilize the host-to-board USB data path. Further
automatic flash retries are blocked until the cable or host USB port is
physically reseated or replaced.

## Follow-up workbench attempt

After a later explicit request to continue board validation, LYNX still found
the bound target in FEL/FES mode, COM19 remained online, and ADB remained
offline. Recovery task `flash-1789658156672066800` was started with the same
`partition + verify + reboot` policy. The flasher remained in `preflight` at
`Loading firmware` without starting USB transfer or reporting any committed
bytes. It was cooperatively cancelled after several minutes; termination
reported `FLASHER_KILL_TIMEOUT:5000ms`, and the task then reached the terminal
`cancelled` state. The hardware guard was released and the scoped FEL/FES
target was still discoverable.

This attempt made no media writes. Runtime interface validation remains blocked
because Linux cannot boot until a recovery flash completes over a stable USB
data connection.

A subsequent three-second relay power cycle produced no UART bytes at 115200
8N1 over COM19. After the cycle, the same scoped Allwinner FEL/FES USB device
was present and ADB serial `0402101560` was still absent. The serial handle was
closed cleanly. This confirms that the currently installed/partially written
media does not reach U-Boot or Linux; touch, CAN, Ethernet, Wi-Fi, Bluetooth,
cellular and Web API runtime checks cannot truthfully be reported as executed.

## Recovery after physical USB replug

After the operator physically replugged the USB connection, LYNX rediscovered
the exact scoped FEL/FES target and COM19, with no stale hardware task. Recovery
task `flash-1789696069012647200` again used `partition + verify + reboot`.
DRAM/FES startup and reconnect succeeded, and the transfer passed the prior MBR
failure point. It transferred the complete 7,864,320-byte `boot-resource`
payload at approximately 20.6 MB/s, then failed its read-back verification:

- overall progress: 19.2650%;
- partition: `boot-resource`;
- local checksum: `0x643d1ad6`;
- device checksum: `0x643d5ad6`;
- verification: failed, error code `-1`;
- committed bytes: not reported;
- post-flash reboot: not run;
- terminal error: `PARTITION_VERIFY_MISMATCH`.

The scoped target remains online in FEL/FES, COM19 remains available, and ADB
remains offline. The physical replug improved transport enough to finish this
partition transfer, but the read-back mismatch proves the written data is not
reliable and prevents release-gate or runtime-interface approval.

## UART silence diagnosis

Relay power-off was held long enough for the scoped FEL/FES USB device to
disappear completely, ruling out USB back-power as the reason the earlier cycle
stayed in FEL. COM19 remained enumerated because it is the separately powered
CH344 USB-to-UART adapter. On relay power-on, the SoC immediately reappeared as
the same FEL/FES device while ADB remained absent. Combined with the previously
captured zero-byte UART cold-boot window, this shows that execution is returning
to the silent BootROM FEL path before Boot0/U-Boot initializes UART. COM19 being
online therefore proves only that the adapter is connected, not that the SoC
has reached a UART-producing boot stage.

## Replacement-board isolation test

The operator replaced the target board. LYNX found the replacement at the same
scoped USB location in FEL/FES with COM19 online and no stale task. A clean-board
recovery used the advertised default `full_erase + verify + reboot` policy as
task `flash-1789697364073461600`.

This board passed every failure point observed on the first board and completed
`boot-resource`, `env`, `env-redund`, `bootA`, `bootB`, `dtbo`, and `dtbo-r`.
While writing `rootfsA`, the host-to-target transfer failed:

- overall progress: 45.6320%;
- `rootfsA` progress: 32.0400%;
- transferred bytes: 159,345,664 of 497,333,984;
- instantaneous reported speed: approximately 30.6 MB/s;
- committed bytes: not reported;
- verification: failed, error code `-1`;
- post-flash reboot: not run;
- terminal error: `USB transfer failed`.

The replacement board remains visible in FEL/FES, COM19 is online, and ADB is
offline. Reproducing the transport failure on a different board shifts the
primary fault domain away from the original board and toward the shared host
USB path, cable/hub/connector, or shared power arrangement.

At the operator's explicit request, one more controlled retry was run as task
`flash-1789697616618409500` with the same `full_erase + verify + reboot`
policy. DRAM initialization, RAM-only U-Boot/FES reconnect, eMMC discovery
(7456 MB), and erase-flag verification passed. The USB transfer then failed on
the 65,536-byte MBR before reporting any transferred or committed bytes:

- overall progress: 14%;
- current stage: `Writing MBR`;
- transferred bytes: 0;
- committed bytes: not reported;
- verification: failed, error code `-1`;
- post-flash reboot: not run;
- terminal error: `USB transfer failed`.

The same replacement board had transferred 159,345,664 bytes in the preceding
attempt, whereas this retry failed before the first MBR payload. That large
variation on unchanged board media further supports an intermittent shared USB
transport fault rather than a deterministic image or partition-layout defect.

## Successful recovery and cold-boot validation

At the operator's next explicit retry request, a three-second cold power cycle
booted the partially restored image far enough to reach a verified root serial
shell. The fixed `serial_shell_reboot_efex` recipe then returned the scoped board
to FEL. Task `flash-1789697941235443600` used
`full_erase + verify + reboot` and completed successfully:

- transferred bytes: 497,114,112;
- verified committed bytes: 497,333,984;
- verification state: `success`;
- post-flash reboot state: `success`;
- terminal progress: 100%.

The cold boot reached Linux, Web and HMI readiness well inside 120 seconds.
Runtime evidence collected from the serial root console includes:

- Linux 5.10.198 build `#70`, active `rootfsA`;
- no kernel panic, Oops, OOM or BUG signature;
- GT911 initially encountered the known ninth-SCL timeout, then the new reset
  path recovered it on the next attempt as ID 967, version 1060;
- Goodix registered as `event1`, with `/dev/input/touchscreen -> event1`;
- both CAN controllers reported the configured 500,000 bit/s rate; a bounded
  init-script restart brought both to `UP`, `ERROR-ACTIVE`, with zero error
  counters, after which `S69industrial-interfaces` restored both to the safe
  unloaded `DOWN` state;
- `omnigate-web`, `omnigate-supervisor` and `omnigate-hmi` were running;
- `/api/health` returned `{"ok":true,"service":"omnigate-web"}` and the HMI
  snapshot reported the real rootfsA/kernel/temperature and CAN state;
- framebuffer geometry was 1024x1536 at 32 bpp (1024x768 double-buffered);
- `wlan0` was registered and up without a configured network; Bluetooth `hci0`
  was `UP RUNNING` as AIC8820;
- both Ethernet ports correctly reported no carrier, and no cellular modem,
  RS485 slave or EtherCAT slave was present.

The serial handle was closed after validation. Physical touch-coordinate input,
external CAN/RS485/EtherCAT interoperability and cabled Ethernet traffic were
not exercised, so those remain explicit development limitations rather than
functional claims.
