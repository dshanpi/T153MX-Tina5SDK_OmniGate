#!/bin/sh
set -eu

PACKAGE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SOURCE_ROOT="${1:-${PACKAGE_DIR}/overlay}"
DL_DIR="${SOURCE_ROOT}/buildroot/buildroot-202205/dl"

fail()
{
	echo "[FAIL] $*" >&2
	exit 1
}

check_archive()
{
	relative="$1"
	expected="$2"
	archive="${DL_DIR}/${relative}"

	[ -f "${archive}" ] || fail "offline source missing: ${relative}"
	actual=$(sha256sum "${archive}" | awk '{print $1}')
	[ "${actual}" = "${expected}" ] || fail "offline source checksum mismatch: ${relative}"
}

check_archive libmbim/libmbim-1.26.2.tar.gz c12e61ea462fca40ddba2a8e1e401242d4f13827944369fad27ff70936b1e09d
check_archive libqmi/libqmi-1.30.4.tar.gz 82ddd3f77c602b1e0c11d3e41d0563ede11f95036ebfcf929bc89157b13928e6
check_archive libubox/libubox-d716ac4bc4236031d4c3cc1ed362b502e20e3787-br1.tar.gz 54f65299439dab4be8f203588bcefd9b60052ae87d12c6d012f6278a2a111b4e
check_archive modem-manager/ModemManager-1.18.6.tar.xz d4f804b31cf504239c5f1d4973c62095c00cba1ee9abb503718dac6d146a470a
check_archive pppd/pppd-2.4.9.tar.gz 675bff4f366174649f4a3c92fd32ac476e694164ff2b0b7710019b6ead9c561e
check_archive uqmi/uqmi-0a19b5b77140465c29e2afa7d611fe93abc9672f-br1.tar.gz aae6a72791da8f58012303ba3bfeeb613e74597cbebfb9e7c2d9125e6f256799
check_archive usb_modeswitch/usb-modeswitch-2.6.1.tar.bz2 5195d9e136e52f658f19e9f93e4f982b1b67bffac197d0a455cd8c2cd245fa34
check_archive usb_modeswitch_data/usb-modeswitch-data-20191128.tar.bz2 3f039b60791c21c7cb15c7986cac89650f076dc274798fa242231b910785eaf9

echo "[OK] 8 offline 4G source archives passed SHA-256 verification"
