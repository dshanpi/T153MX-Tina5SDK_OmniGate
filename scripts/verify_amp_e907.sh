#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_DIR=$(dirname "$SCRIPT_DIR")
SDK=${1:-$(pwd)}
FAILED=0

ok()
{
	printf 'OK   %s\n' "$1"
}

fail()
{
	printf 'FAIL %s\n' "$1" >&2
	FAILED=1
}

require_file()
{
	[ -f "$SDK/$1" ] && ok "$1" || fail "$1"
}

require_exec()
{
	[ -x "$SDK/$1" ] && ok "$1 executable" || fail "$1 executable"
}

require_config()
{
	file=$1
	option=$2
	grep -q "^${option}=y$" "$SDK/$file" &&
		ok "$file: $option" ||
		fail "$file: $option"
}

require_text()
{
	file=$1
	text=$2
	grep -Fq "$text" "$SDK/$file" &&
		ok "$file contains $text" ||
		fail "$file contains $text"
}

require_file device/config/chips/t153/bin/amp_rv0.bin
require_file platform/allwinner/system/amp_shell/files/rawdev/rpmsg.c
require_file rtos/lichee/rtos-components/aw/multi_console/shell.c
require_exec device/config/chips/t153/configs/omnigate/buildroot/overlay/usr/bin/omnigate-amp
require_config buildroot/buildroot-202205/configs/sun8iw22p1_t153_mmc_defconfig BR2_PACKAGE_AMP_SHELL

for variant in linux-5.10-origin linux-5.10-rt; do
	config=device/config/chips/t153/configs/omnigate/$variant/buildroot_linux_defconfig
	dts=device/config/chips/t153/configs/omnigate/$variant/board.dts
	require_config "$config" CONFIG_AW_MSGBOX
	require_config "$config" CONFIG_AW_REMOTEPROC
	require_config "$config" CONFIG_AW_REMOTEPROC_E907_BOOT
	require_config "$config" CONFIG_AW_RPMSG_CTRL
	require_text "$dts" "e907_rproc:"
	require_text "$dts" 'share-irq = "e907"'
	require_text "$dts" "rv_vdev0buffer:"
	require_text "$dts" "rv_vdev0vring0:"
	require_text "$dts" "rv_vdev0vring1:"
done

if ! cmp -s \
	"$REPO_DIR/overlay/platform/allwinner/system/amp_shell/files/rawdev/rpmsg.c" \
	"$SDK/platform/allwinner/system/amp_shell/files/rawdev/rpmsg.c"; then
	fail "amp_shell rpmsg.c overlay differs from SDK"
else
	ok "amp_shell rpmsg.c overlay matches SDK"
fi

if ! cmp -s \
	"$REPO_DIR/overlay/rtos/lichee/rtos-components/aw/multi_console/shell.c" \
	"$SDK/rtos/lichee/rtos-components/aw/multi_console/shell.c"; then
	fail "multi_console shell.c overlay differs from SDK"
else
	ok "multi_console shell.c overlay matches SDK"
fi
require_text \
	rtos/lichee/rtos-components/aw/multi_console/shell.c \
	"} while (ret);"

BR_CONFIG=out/t153/omnigate/buildroot/buildroot/.config
K_CONFIG=out/t153/kernel/build/.config
TARGET=out/t153/omnigate/buildroot/buildroot/target

if [ -f "$SDK/$BR_CONFIG" ]; then
	require_config "$BR_CONFIG" BR2_PACKAGE_AMP_SHELL
fi
if [ -f "$SDK/$K_CONFIG" ]; then
	require_config "$K_CONFIG" CONFIG_AW_REMOTEPROC
	require_config "$K_CONFIG" CONFIG_AW_RPMSG_CTRL
	require_config "$K_CONFIG" CONFIG_RPMSG_VIRTIO
fi
if [ -d "$SDK/$TARGET" ]; then
	require_exec "$TARGET/usr/bin/amp_shell"
	require_exec "$TARGET/usr/bin/omnigate-amp"
	if cmp -s \
		"$SDK/device/config/chips/t153/bin/amp_rv0.bin" \
		"$SDK/$TARGET/lib/firmware/amp_rv0.bin"; then
		ok "Buildroot target amp_rv0.bin matches RTOS output"
	else
		fail "Buildroot target amp_rv0.bin differs from RTOS output; run ./build.sh rootfs"
	fi
	if strings "$SDK/$TARGET/usr/bin/amp_shell" |
		grep -Fq "fallback to RPMSG_CREATE_EPT_IOCTL"; then
		ok "amp_shell contains runtime ioctl fallback"
	else
		fail "amp_shell runtime ioctl fallback"
	fi
fi

PACKED_RTOS=out/t153/omnigate/pack_out/amp_rv0.fex
if [ -f "$SDK/$PACKED_RTOS" ]; then
	if cmp -s \
		"$SDK/device/config/chips/t153/bin/amp_rv0.bin" \
		"$SDK/$PACKED_RTOS"; then
		ok "pack_out amp_rv0.fex matches RTOS output"
	else
		fail "pack_out amp_rv0.fex differs from RTOS output; run ./build.sh pack"
	fi
fi

if [ "$FAILED" -ne 0 ]; then
	echo "A7/E907 AMP integration verification failed." >&2
	exit 1
fi

echo "A7/E907 AMP integration files and build output verified."
