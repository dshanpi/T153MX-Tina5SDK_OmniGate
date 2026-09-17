#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON=${TEST_PYTHON:-$ROOT/.test-venv/bin/python}
CORE=$ROOT/overlay/buildroot/buildroot-202205/package/omnigate-core/src
BYTECODE_DIR=$(mktemp -d "${TMPDIR:-/tmp}/omnigate-pycache.XXXXXX")
trap 'rm -rf "$BYTECODE_DIR"' EXIT HUP INT TERM
export PYTHONDONTWRITEBYTECODE=1

if [ ! -x "$PYTHON" ]; then
	echo "Missing test interpreter: $PYTHON" >&2
	echo "Run 'make test-bootstrap' first." >&2
	exit 2
fi

"$PYTHON" -c 'import flask; assert flask.__version__ == "2.1.2"'
PYTHONWARNINGS=ignore PYTHONPATH="$CORE" "$PYTHON" -m unittest discover \
	-s "$ROOT/overlay/buildroot/buildroot-202205/package/omnigate-core/tests" -v
PYTHONWARNINGS=ignore "$PYTHON" -m unittest discover -s "$ROOT/tests" -v

PYTHONPYCACHEPREFIX="$BYTECODE_DIR" "$PYTHON" -m py_compile \
	"$ROOT"/overlay/buildroot/buildroot-202205/package/omnigate-core/src/omnigate_core/*.py \
	"$ROOT"/overlay/device/config/chips/t153/configs/omnigate/buildroot/overlay/usr/lib/omnigate-web/*.py \
	"$ROOT"/overlay/device/config/chips/t153/configs/omnigate/buildroot/overlay/usr/lib/omnigate-supervisor/*.py \
	"$ROOT"/scripts/*.py

sh -n "$ROOT/omnigate-platform/apps/node-red/init-data.sh"
sh -n "$ROOT/overlay/buildroot/buildroot-202205/package/omnigate-hmi/omnigate-hmi-launcher"
sh -n "$ROOT/overlay/buildroot/buildroot-202205/package/omnigate-hmi/S75omnigate-hmi"
for script in "$ROOT"/scripts/*.sh; do sh -n "$script"; done

"$PYTHON" -m json.tool "$ROOT/omnigate-platform/components.json" >/dev/null
"$PYTHON" -m json.tool "$ROOT/omnigate-platform/release-status.json" >/dev/null
"$PYTHON" -m json.tool "$ROOT/omnigate-platform/gates/system-gates.json" >/dev/null
for value in "$ROOT"/omnigate-platform/profiles/*.json \
	"$ROOT"/omnigate-platform/boards/*.json \
	"$ROOT"/omnigate-platform/schemas/*.json; do
	"$PYTHON" -m json.tool "$value" >/dev/null
done
"$PYTHON" -m json.tool "$ROOT/omnigate-platform/apps/node-red/flows.json" >/dev/null
if command -v node >/dev/null 2>&1; then
	node --check "$ROOT/omnigate-platform/apps/node-red/settings.js"
fi

"$PYTHON" "$ROOT/scripts/check_release_gates.py" \
	--release-class development --profile lite >/dev/null

echo "All host-side OmniGate tests passed."
