#!/bin/sh
set -eu

PACKAGE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
OVERLAY_DIR="${PACKAGE_DIR}/overlay"
TARGET_DIR="${1:-}"

fail()
{
	echo "[FAIL] $*" >&2
	exit 1
}

[ -n "${TARGET_DIR}" ] || fail "Usage: $0 /path/to/TinaSDK"
[ -d "${TARGET_DIR}/.repo" ] || fail "not a Tina SDK root: ${TARGET_DIR}"

LIST_FILE=$(mktemp "${TMPDIR:-/tmp}/omnigate-overlay.XXXXXX") || exit 1
trap 'rm -f "${LIST_FILE}"' EXIT HUP INT TERM

(cd "${OVERLAY_DIR}" && find . \( -type f -o -type l \) -print | LC_ALL=C sort) > "${LIST_FILE}"

checked=0
while IFS= read -r relative; do
	relative=${relative#./}
	source_path="${OVERLAY_DIR}/${relative}"
	target_path="${TARGET_DIR}/${relative}"

	if [ -L "${source_path}" ]; then
		[ -L "${target_path}" ] || fail "target symlink missing: ${relative}"
		[ "$(readlink "${source_path}")" = "$(readlink "${target_path}")" ] ||
			fail "target symlink differs: ${relative}"
	else
		[ -f "${target_path}" ] || fail "target file missing: ${relative}"
		cmp -s "${source_path}" "${target_path}" || fail "target file differs: ${relative}"
		[ "$(stat -c '%a' "${source_path}")" = "$(stat -c '%a' "${target_path}")" ] ||
			fail "target mode differs: ${relative}"
	fi
	checked=$((checked + 1))
done < "${LIST_FILE}"

"${PACKAGE_DIR}/scripts/verify_offline_sources.sh" "${TARGET_DIR}"
echo "[OK] ${checked} overlay files match target SDK"
