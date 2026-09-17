---
name: t153-goodix-touch-debug
description: Diagnose and validate Goodix GT911 touch on the OmniGate T153MX, including DTS address/IRQ/reset invariants, compiled-DTB checks, probe failures, input-event evidence, and physical-touch claims. Use for Goodix I2C errors, probe error -22, missing event nodes, wrong coordinates, or touch regression after firmware changes.
---

# T153 Goodix Touch Debug

Use an evidence ladder: source DTS → compiled DTB → boot probe → input events →
physical coordinate behavior. Stop at the highest level actually observed.

## Known-good T153MX binding

For this board revision, preserve all of these together:

- `compatible = "goodix,gt911"`;
- I2C address `0x14`;
- PJ7 as falling-edge interrupt through `interrupts`;
- PJ6 as active-low `reset-gpios`;
- no `irq-gpios` property;
- coordinate range 1024×768.

Do not change the address to `0x5d` just because GT911 can use it. Do not add
`irq-gpios`: on this board the generic driver then tries to switch the
pinctrl-owned PJ7 IRQ pin to output and can fail probe with `-EINVAL` (`-22`).

## Diagnostic workflow

1. Capture the image SHA-256, kernel build ID, board revision, complete Goodix
   boot log, I2C address, and `/proc/bus/input/devices` before editing.
2. Compare every active T153MX DTS variant. Remove stale contradictory changes;
   do not edit backup files as though they were build inputs.
3. Inspect the compiled DTB used by the packed image, not only source text.
   Confirm `reg`, `interrupts`, `reset-gpios`, absence of `irq-gpios`, and the
   coordinate range.
4. Rebuild the DTB/kernel and packed image through the configured SDK path.
   Record the new image SHA-256 so old and new board evidence cannot mix.
5. After an authorized, verified flash, require the boot log to identify the
   device at `2-0014`, register `Goodix Capacitive TouchScreen`, and create the
   expected `/dev/input/event*` node without probe `-22` or I2C transfer errors.
6. Capture real input events and test representative corners/center. Driver
   registration proves enumeration only; claim physical touch success only
   from actual events or a recorded operator check.

## Failure interpretation

- Repeated transfers to `0x5d`: the active DTB likely contains the wrong board
  address or the wrong DTB was packed.
- `probe failed with error -22` after adding `irq-gpios`: restore the fixed IRQ
  input binding above; do not work around it by weakening unrelated GPIO code.
- Correct source but wrong runtime behavior: verify the compiled DTB, packed
  image identity, flash verification, and booted slot before another source edit.
- Correct events but wrong positions: check axis ranges, swap/invert settings,
  display rotation, and calibration; do not treat this as an I2C probe failure.

USB transfer failure or incomplete flash verification is a deployment failure,
not a touch result. Do not loop destructive retries. Preserve the failed task,
fully re-enumerate the device, and retry only within the user's authorized
flashing scope and stated stopping condition.
