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

GOODIX_DRIVER="$TARGET/kernel/linux-5.10-origin/drivers/input/touchscreen/goodix.c"
GOODIX_PATCH="$SRC_DIR/patches/linux-5.10-origin/0001-goodix-reset-without-int-gpio.patch"
if ! grep -Fq 'goodix,reset-without-int-gpio' "$GOODIX_DRIVER"; then
	patch -d "$TARGET" -p1 < "$GOODIX_PATCH"
fi

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
	'	source "package/omnigate-core/Config.in"'
insert_after 'source "package/omnigate-core/Config.in"' \
	'	source "package/omnigate-ethercat/Config.in"'
insert_after 'source "package/omnigate-ethercat/Config.in"' \
	'	source "package/omnigate-hmi/Config.in"'
insert_after 'source "package/python-iso8601/Config.in"' \
	'	source "package/python-jsonpath-rw/Config.in"'
insert_after 'menu "Networking applications"' \
	'	source "package/thingsboard-gateway/Config.in"'

"$SRC_DIR/scripts/verify_overlay.sh" "$TARGET"
echo "Done: overlay copied and verified. 删除动作未执行；如需删除，先审查 meta/delete_list.txt，再运行 scripts/apply_deletes.sh"
