#!/bin/sh
# Board-side, non-destructive AMP Shell smoke test for T153MX OmniGate.
set -eu

command_text=${1:-help}

if ! command -v omnigate-amp >/dev/null 2>&1; then
	echo "ERROR: omnigate-amp is not installed" >&2
	exit 127
fi

echo "== AMP status before test =="
omnigate-amp status

echo "== Execute one E907 command =="
echo "command: $command_text"
omnigate-amp exec "$command_text"

echo "== AMP diagnostic snapshot =="
omnigate-amp diagnose

echo "== AMP status after test =="
omnigate-amp status

