# Security policy

Report vulnerabilities privately to the project maintainer before publishing
details.  Include the affected version, reproduction steps and impact.

The current T153 image is a development image.  ADB, the empty root password,
firewall policy, secure boot, signed OTA and automatic rollback do not yet meet
an IEC 62443 production baseline.  Do not expose the management service to an
untrusted network or claim production-security certification.

Production derivatives must replace default credentials on first use, enable
verified TLS, restrict debug access, generate per-device secrets, define update
signing and rollback policy, and produce an SBOM plus license bundle.
