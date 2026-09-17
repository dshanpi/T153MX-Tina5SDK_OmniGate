---
name: omnigate-release-gate
description: Evaluate OmniGate development, release-candidate, or production readiness from build, flash, board, soak, interoperability, security, and Enhanced-runtime evidence. Use for release audits, acceptance conclusions, evidence gaps, or go/no-go decisions; do not use it as permission to flash hardware or send fieldbus control traffic.
---

# OmniGate Release Gate

Apply the repository's gate policy without turning missing evidence into success.

## Workflow

1. Identify the requested release class (`development`, `release-candidate`, or
   `production`), profile (`lite` or `enhanced`), and whether the release claims
   fieldbus interoperability.
2. Read the canonical requirements at
   `omnigate-platform/docs/system-gate-requirements.md` and the machine policy at
   `omnigate-platform/gates/system-gates.json`. If working from an installed
   skill without those paths, read [references/evidence-map.md](references/evidence-map.md).
3. Resolve the exact source revision, image SHA-256, board ID, execution time,
   and evidence directory before judging results. Evidence from a different
   image or board does not satisfy a gate.
4. Run the non-mutating policy check:

   ```sh
   python3 scripts/check_release_gates.py --release-class development --profile lite
   ```

   Add `--claim-fieldbus` only when that claim is in scope. The checker validates
   closure; inspect every referenced artifact before accepting its output.
5. Report each required gate as passed, passed-with-limitations, failed, not-run,
   or not-applicable, followed by the evidence path and exact gap. End with one
   overall verdict and the minimum work needed to reach the next release class.

## Invariants

- Never equate interface enumeration with protocol interoperability, driver
  registration with physical touch, or host Node-RED tests with Enhanced-board
  qualification.
- State the actual flash mode. A successful `partition` task after an earlier
  full erase is not a successful full-erase task.
- `not-run`, unknown task state, incomplete verification, and stale evidence do
  not pass.
- Do not flash, reboot, fault-inject, run a soak, or transmit fieldbus writes
  merely to complete an audit. Those actions require task scope and applicable
  authorization.
- Preserve explicit limitations in release notes. Development evidence is not
  IEC 62443 certification.
