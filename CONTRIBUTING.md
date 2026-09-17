# Contributing

Run `make test-bootstrap` once, then `make test` before submitting changes.
Changes that affect a T153 image must also pass `make verify-sdk SDK_ROOT=..`, a
clean image build, and the applicable non-destructive board checks.

Keep board-independent behavior behind the platform manifest and `/api/v1`.
Do not hard-code `can0`, serial paths, Ethernet names or framebuffer paths in
new business logic.  Protocol writes and machine-control actions must require
authentication, CSRF protection, bounded input and explicit operator intent.

Do not report protocol interoperability without a real compatible slave and
captured evidence.  Never add credentials, private keys, production tokens or
customer data to examples, logs, fixtures or commits.
