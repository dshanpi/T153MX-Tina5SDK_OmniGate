#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
OUTPUT=${1:-$ROOT/dist}
VERSION=${OMNIGATE_RELEASE_VERSION:-0.1.0-dev}
case "$VERSION" in
	*[!A-Za-z0-9._-]*) echo "Invalid release version: $VERSION" >&2; exit 2 ;;
esac
PLATFORM_NAME="omnigate-industrial-desktop-platform-$VERSION"
INTEGRATION_NAME="omnigate-t153-integration-bundle-$VERSION"

mkdir -p "$OUTPUT"
OUTPUT=$(CDPATH= cd -- "$OUTPUT" && pwd)
PLATFORM_ARCHIVE="$OUTPUT/$PLATFORM_NAME.tar.gz"
INTEGRATION_ARCHIVE="$OUTPUT/$INTEGRATION_NAME.tar.gz"

# Reusable GPL-3.0-only application/platform sources. Keep board SDK,
# wireless firmware and vendor tools outside this artifact.
tar --sort=name --owner=0 --group=0 --numeric-owner \
	--exclude='__pycache__' --exclude='*.pyc' \
	-C "$ROOT" -czf "$PLATFORM_ARCHIVE" \
	--transform "s,^,$PLATFORM_NAME/," \
	LICENSE README.md CONTRIBUTING.md SECURITY.md Makefile \
	docs/open-source-release.md omnigate-platform tests \
	scripts/check_release_gates.py scripts/test_all.sh scripts/test_web_api.py \
	overlay/skills/omnigate-release-gate \
	overlay/buildroot/buildroot-202205/package/omnigate-core \
	overlay/buildroot/buildroot-202205/package/omnigate-hmi \
	overlay/device/config/chips/t153/configs/omnigate/buildroot/overlay/etc/default/omnigate-web \
	overlay/device/config/chips/t153/configs/omnigate/buildroot/overlay/etc/default/omnigate-supervisor \
	overlay/device/config/chips/t153/configs/omnigate/buildroot/overlay/etc/init.d/S71omnigate-web \
	overlay/device/config/chips/t153/configs/omnigate/buildroot/overlay/etc/init.d/S72omnigate-supervisor \
	overlay/device/config/chips/t153/configs/omnigate/buildroot/overlay/etc/omnigate-web \
	overlay/device/config/chips/t153/configs/omnigate/buildroot/overlay/etc/omnigate \
	overlay/device/config/chips/t153/configs/omnigate/buildroot/overlay/usr/bin/omnigate-acceptance-snapshot \
	overlay/device/config/chips/t153/configs/omnigate/buildroot/overlay/usr/lib/omnigate-supervisor \
	overlay/device/config/chips/t153/configs/omnigate/buildroot/overlay/usr/lib/omnigate-web \
	overlay/device/config/chips/t153/configs/omnigate/buildroot/overlay/usr/share/omnigate-web

# Complete T153 integration bundle. Vendor/BSP and firmware material retains
# its original terms and this archive must not be advertised as wholly open.
tar --sort=name --owner=0 --group=0 --numeric-owner \
	--exclude='./.git' --exclude='./.test-venv' --exclude='./dist' \
	--exclude='__pycache__' --exclude='*.pyc' \
	-C "$ROOT" -czf "$INTEGRATION_ARCHIVE" \
	--transform "s,^\.,$INTEGRATION_NAME," .

PLATFORM_FILE=$(basename "$PLATFORM_ARCHIVE")
INTEGRATION_FILE=$(basename "$INTEGRATION_ARCHIVE")
(cd "$OUTPUT" && sha256sum "$PLATFORM_FILE") > "$PLATFORM_ARCHIVE.sha256"
(cd "$OUTPUT" && sha256sum "$INTEGRATION_FILE") > "$INTEGRATION_ARCHIVE.sha256"

PLATFORM_SHA=$(awk '{print $1}' "$PLATFORM_ARCHIVE.sha256")
INTEGRATION_SHA=$(awk '{print $1}' "$INTEGRATION_ARCHIVE.sha256")
PLATFORM_BYTES=$(stat -c '%s' "$PLATFORM_ARCHIVE")
INTEGRATION_BYTES=$(stat -c '%s' "$INTEGRATION_ARCHIVE")
RELEASE_MANIFEST="$OUTPUT/omnigate-release-$VERSION.json"
{
	printf '{\n'
	printf '  "schema_version": 1,\n'
	printf '  "product": "OmniGate Industrial Control Desktop",\n'
	printf '  "version": "%s",\n' "$VERSION"
	printf '  "profiles": ["lite", "enhanced"],\n'
	printf '  "production_security": "not-certified",\n'
	printf '  "artifacts": [\n'
	printf '    {"file": "%s", "bytes": %s, "sha256": "%s", "license_scope": "open-platform"},\n' \
		"$PLATFORM_FILE" "$PLATFORM_BYTES" "$PLATFORM_SHA"
	printf '    {"file": "%s", "bytes": %s, "sha256": "%s", "license_scope": "mixed-vendor-integration"}\n' \
		"$INTEGRATION_FILE" "$INTEGRATION_BYTES" "$INTEGRATION_SHA"
	printf '  ]\n'
	printf '}\n'
} > "$RELEASE_MANIFEST"

printf '%s\n' "$PLATFORM_ARCHIVE" "$PLATFORM_ARCHIVE.sha256"
printf '%s\n' "$INTEGRATION_ARCHIVE" "$INTEGRATION_ARCHIVE.sha256"
printf '%s\n' "$RELEASE_MANIFEST"
