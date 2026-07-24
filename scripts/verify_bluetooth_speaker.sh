#!/bin/sh
set -eu

PACKAGE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
OVERLAY_DIR="${PACKAGE_DIR}/overlay"
TARGET_DIR="${1:-}"

FILES="
buildroot/buildroot-202205/configs/sun8iw22p1_t153_mmc_defconfig
device/config/chips/t153/configs/omnigate/buildroot/overlay/etc/init.d/S45aic8800-bluetooth
device/config/chips/t153/configs/omnigate/buildroot/overlay/usr/bin/bt-speaker
device/config/chips/t153/configs/omnigate/buildroot/overlay/etc/bluetooth/bt-speaker.conf
device/config/chips/t153/configs/omnigate/buildroot/overlay/etc/asound.conf
buildroot/buildroot-202205/package/bluez-alsa/bluez-alsa.mk
device/config/chips/t153/configs/omnigate/linux-5.10-origin/board.dts
bsp/drivers/net/wireless/aic8800/aic8800_btlpm/aic8800_btlpm.c
platform/allwinner/wireless/firmware/aic8800/sdio/aic8800d80/aic_userconfig_8800d80.txt
platform/allwinner/wireless/firmware/aic8800/sdio/aic8800d80/fmacfw_8800d80_u02.bin
platform/allwinner/wireless/firmware/aic8800/sdio/aic8800d80/fw_adid_8800d80_u02.bin
platform/allwinner/wireless/firmware/aic8800/sdio/aic8800d80/fw_patch_8800d80_u02.bin
platform/allwinner/wireless/firmware/aic8800/sdio/aic8800d80/fw_patch_table_8800d80_u02.bin
platform/allwinner/wireless/firmware/aic8800/sdio/aic8800d80/lmacfw_rf_8800d80_u02.bin
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

DEFCONFIG="${OVERLAY_DIR}/buildroot/buildroot-202205/configs/sun8iw22p1_t153_mmc_defconfig"
for option in \
	'BR2_ROOTFS_OVERLAY=' \
	'BR2_PACKAGE_AIC8800_SDIO_FIRMWARE=y' \
	'BR2_PACKAGE_ALSA_UTILS=y' \
	'BR2_PACKAGE_ALSA_UTILS_AMIXER=y' \
	'BR2_PACKAGE_ALSA_UTILS_APLAY=y' \
	'BR2_PACKAGE_BLUEZ_ALSA=y' \
	'BR2_PACKAGE_BLUEZ5_UTILS_CLIENT=y' \
	'BR2_PACKAGE_BLUEZ5_UTILS_DEPRECATED=y'
do
	grep -q "^${option}" "${DEFCONFIG}" ||
		fail "Buildroot option missing: ${option}"
done

if grep -q '^BR2_PACKAGE_LIBOPENAPTX=y' "${DEFCONFIG}"; then
	fail "defconfig still selects libopenaptx for the SBC-only image"
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
