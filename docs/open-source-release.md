# OmniGate Industrial Control Desktop open-source release model

## Layering

1. **Platform layer** — manifest, local database, `/api/v1`, Web UI, HMI,
   supervisor and application profiles.  This is intended to be reusable.
2. **Protocol adapters** — CAN/CANopen, Modbus, EtherCAT, MQTT and cellular
   integration.  Availability is declared by the board manifest.
3. **Board-support layer** — kernel, device tree, boot configuration, rootfs
   overlay and firmware for a specific board such as T153MX.
4. **Vendor SDK/toolchain** — obtained under the vendor's terms and not
   automatically relicensed by this repository.

## Release artifacts

`make package` produces two deliberately separate artifacts:

- `omnigate-industrial-desktop-platform-*.tar.gz` contains the reusable
  GPL-3.0-only application sources, tests and runtime configuration.
- `omnigate-t153-integration-bundle-*.tar.gz` contains the complete T153
  overlay, including vendor/BSP/firmware material that retains its original
  terms and is not represented as wholly open source.
- `omnigate-release-*.json` records the two artifacts' relative filenames,
  sizes, SHA-256 values, profile set and non-certified production-security
  status. Adjacent `.sha256` files also use relative filenames so the release
  directory can be moved and verified offline.

A firmware release additionally needs the exact image SHA-256, partition
manifest, build configuration, source-offer obligations, SBOM, third-party
notices and board validation report.

Run:

```sh
make test-bootstrap
make test
make verify-sdk SDK_ROOT=..
make gate RELEASE_CLASS=development PROFILE=lite
OMNIGATE_RELEASE_VERSION=0.1.0 make package
```

## Licensing boundary

The repository-level original work uses GPL-3.0-only.  Third-party packages
retain their own licenses.  Wireless firmware, Allwinner BSP content and vendor
tools may be redistributable but are not necessarily open source.  Review all
vendor terms before publishing a combined image or charging for redistribution.

## Acceptance language

Use `PASS`, `FAIL`, or `PASS WITH PERIPHERAL LIMITATIONS`.  Host-side Node-RED
tests are not enhanced-board tests.  Interface enumeration is not protocol
interoperability.  A development-security result is not IEC 62443 certification.
The normative gate definitions and machine-readable status vocabulary are in
`omnigate-platform/docs/system-gate-requirements.md` and
`omnigate-platform/gates/system-gates.json`.
