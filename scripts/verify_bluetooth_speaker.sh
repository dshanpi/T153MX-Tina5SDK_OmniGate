#!/bin/sh
set -eu

PACKAGE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
OVERLAY_DIR="${PACKAGE_DIR}/overlay"
TARGET_DIR="${1:-}"

FILES="
device/config/chips/t153/configs/omnigate/buildroot/overlay/etc/init.d/S45aic8800-bluetooth
device/config/chips/t153/configs/omnigate/buildroot/overlay/usr/bin/bt-speaker
device/config/chips/t153/configs/omnigate/buildroot/overlay/etc/bluetooth/bt-speaker.conf
device/config/chips/t153/configs/omnigate/buildroot/overlay/etc/asound.conf
buildroot/buildroot-202205/package/bluez-alsa/bluez-alsa.mk
device/config/chips/t153/configs/omnigate/linux-5.10-origin/board.dts
bsp/drivers/net/wireless/aic8800/aic8800_btlpm/aic8800_btlpm.c
"

fail()
{
	echo "[FAIL] $*" >&2
	exit 1
}

for path in ${FILES}; do
	[ -f "${OVERLAY_DIR}/${path}" ] ||
		fail "overlay file missing: ${path}"
done

sh -n "${OVERLAY_DIR}/device/config/chips/t153/configs/omnigate/buildroot/overlay/etc/init.d/S45aic8800-bluetooth"
sh -n "${OVERLAY_DIR}/device/config/chips/t153/configs/omnigate/buildroot/overlay/usr/bin/bt-speaker"

BLUEZ_ALSA_MK="${OVERLAY_DIR}/buildroot/buildroot-202205/package/bluez-alsa/bluez-alsa.mk"
grep -q -- '--disable-aptx' "${BLUEZ_ALSA_MK}" ||
	fail "BlueALSA is not explicitly disabling aptX"
grep -q -- '--disable-aptx-hd' "${BLUEZ_ALSA_MK}" ||
	fail "BlueALSA is not explicitly disabling aptX HD"
if grep -q -- '--enable-aptx' "${BLUEZ_ALSA_MK}"; then
	fail "BlueALSA still enables an unverified aptX endpoint"
fi

if [ -n "${TARGET_DIR}" ]; then
	[ -d "${TARGET_DIR}/.repo" ] ||
		fail "not a Tina SDK root: ${TARGET_DIR}"
	for path in ${FILES}; do
		cmp -s "${OVERLAY_DIR}/${path}" "${TARGET_DIR}/${path}" ||
			fail "target differs from overlay: ${path}"
	done
	echo "[OK] Bluetooth speaker overlay matches target SDK"
else
	echo "[OK] Bluetooth speaker delivery files are complete"
fi
