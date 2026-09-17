# Gate evidence map

Use this compact map only when the canonical platform policy is unavailable.

| Gate | Minimum evidence | Common false positive |
| --- | --- | --- |
| G0 source | host tests, schema checks, overlay/SDK match | JSON parses but cross-file references are broken |
| G1 image | clean build log, image SHA-256/size/partitions, package hashes | old Buildroot stamp reused |
| G2 deploy | transferred hash, terminal flash record, cold-boot log | partial writes or a later partition update called full erase |
| G3 Lite | API/auth/audit, SQLite, services, framebuffer, input, kernel review | enumerated peripheral called functionally verified |
| G4 soak | at least 24 hours of timestamped samples and final thresholds | interrupted or combined shorter runs |
| G5 fieldbus | named real peer, protocol transcript, authorized bounded writes | link Up, process running, or empty-bus scan |
| G6 security | threat model, secure boot, signed OTA and automatic rollback | HTTPS alone or unsigned A/B update |
| G7 Enhanced | per-board OCI limits, isolation, persistence, power-loss and load | host container smoke test |

Allowed statuses are `passed`, `passed-with-limitations`, `failed`, `not-run`,
and `not-applicable`. Development requires G0–G3 and permits limitations only
at G3. Release candidate requires G0–G4 without limitations. Production
requires G0–G6 without limitations. Enhanced additionally requires G7; a
fieldbus interoperability claim additionally requires G5.
