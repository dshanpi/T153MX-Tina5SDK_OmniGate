#!/bin/sh
set -e
SRC_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TARGET=${1:-$(pwd)}
if [ ! -d "$TARGET/.repo" ]; then
  echo "无效 Tina SDK 目录: $TARGET" >&2
  exit 1
fi
echo "[OVERLAY] copy files from $SRC_DIR/overlay to $TARGET"
(cd "$SRC_DIR/overlay" && tar -cpf - .) | (cd "$TARGET" && tar -xpf -)
BR_CONFIG_IN="$TARGET/buildroot/buildroot-202205/package/Config.in"
insert_after()
{
	anchor="$1"
	line="$2"
	if ! grep -Fq "$line" "$BR_CONFIG_IN"; then
		sed -i "\\|$anchor|a\\$line" "$BR_CONFIG_IN"
	fi
}

# Custom Buildroot packages must also be visible to Kconfig. Keep these
# insertions here instead of carrying a complete vendor package/Config.in.
insert_after 'source "package/openpowerlink/Config.in"' \
	'	source "package/soem/Config.in"'
insert_after 'source "package/soem/Config.in"' \
	'	source "package/omnigate-ethercat/Config.in"'
insert_after 'source "package/python-iso8601/Config.in"' \
	'	source "package/python-jsonpath-rw/Config.in"'
insert_after 'menu "Networking applications"' \
	'	source "package/thingsboard-gateway/Config.in"'

"$SRC_DIR/scripts/verify_overlay.sh" "$TARGET"
echo "Done: overlay copied and verified. 删除动作未执行；如需删除，先审查 meta/delete_list.txt，再运行 scripts/apply_deletes.sh"
