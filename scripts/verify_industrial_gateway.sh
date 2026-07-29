#!/bin/sh
set -eu

SDK=${1:-$(pwd)}
FAILED=0

check_file()
{
	if [ -e "$SDK/$1" ]; then
		printf 'OK   %s\n' "$1"
	else
		printf 'MISS %s\n' "$1" >&2
		FAILED=1
	fi
}

check_exec()
{
	if [ -x "$SDK/$1" ]; then
		printf 'OK   %s (executable)\n' "$1"
	else
		printf 'MISS %s (not executable)\n' "$1" >&2
		FAILED=1
	fi
}

check_config()
{
	file=$1
	option=$2
	if grep -q "^${option}=y$" "$SDK/$file"; then
		printf 'OK   %s: %s\n' "$file" "$option"
	else
		printf 'MISS %s: %s\n' "$file" "$option" >&2
		FAILED=1
	fi
}

check_file buildroot/buildroot-202205/package/soem/soem.mk
check_file buildroot/buildroot-202205/package/omnigate-ethercat/omnigate-ethercat.mk
check_file buildroot/buildroot-202205/package/thingsboard-gateway/thingsboard-gateway.mk
check_file buildroot/buildroot-202205/package/python-jsonpath-rw/python-jsonpath-rw.mk
check_file platform/allwinner/system/amp_shell/files/rawdev/rpmsg.c
check_file device/config/chips/t153/bin/amp_rv0.bin
check_exec device/config/chips/t153/configs/omnigate/buildroot/overlay/usr/bin/soem-scan
check_exec device/config/chips/t153/configs/omnigate/buildroot/overlay/usr/bin/soem-run
check_exec device/config/chips/t153/configs/omnigate/buildroot/overlay/usr/bin/omnigate-can
check_exec device/config/chips/t153/configs/omnigate/buildroot/overlay/usr/bin/omnigate-amp
check_exec device/config/chips/t153/configs/omnigate/buildroot/overlay/etc/init.d/S46omnigate-wifi
check_file device/config/chips/t153/configs/omnigate/buildroot/overlay/etc/thingsboard-gateway/config/tb_gateway.json
check_exec device/config/chips/t153/configs/omnigate/buildroot/overlay/etc/init.d/S71omnigate-web
check_file device/config/chips/t153/configs/omnigate/buildroot/overlay/etc/omnigate-web/config.json
check_file device/config/chips/t153/configs/omnigate/buildroot/overlay/usr/lib/omnigate-web/app.py
check_file device/config/chips/t153/configs/omnigate/buildroot/overlay/usr/share/omnigate-web/index.html
check_config buildroot/buildroot-202205/configs/sun8iw22p1_t153_mmc_defconfig BR2_PACKAGE_AMP_SHELL

BR_CONFIG=out/t153/omnigate/buildroot/buildroot/.config
K_CONFIG=out/t153/kernel/build/.config
if [ -f "$SDK/$BR_CONFIG" ]; then
	check_config "$BR_CONFIG" BR2_PACKAGE_SOEM
	if grep -q '^BR2_PACKAGE_OMNIGATE_ETHERCAT=y$' "$SDK/$BR_CONFIG"; then
		check_config "$BR_CONFIG" BR2_PACKAGE_OMNIGATE_ETHERCAT
	else
		printf 'SKIP %s: BR2_PACKAGE_OMNIGATE_ETHERCAT (旧构建配置，重新 defconfig 后启用)\n' "$BR_CONFIG"
	fi
	check_config "$BR_CONFIG" BR2_PACKAGE_THINGSBOARD_GATEWAY
	check_config "$BR_CONFIG" BR2_PACKAGE_NTP
	check_config "$BR_CONFIG" BR2_PACKAGE_PYTHON_CANOPEN
	check_config "$BR_CONFIG" BR2_PACKAGE_PYTHON_FLASK
	check_config "$BR_CONFIG" BR2_PACKAGE_LIBQMI
	check_config "$BR_CONFIG" BR2_PACKAGE_PPPD
	check_config "$BR_CONFIG" BR2_PACKAGE_AMP_SHELL
else
	printf 'SKIP %s (尚未完成 Buildroot 配置/编译)\n' "$BR_CONFIG"
fi

if [ -f "$SDK/$K_CONFIG" ]; then
	check_config "$K_CONFIG" CONFIG_USB_NET_QMI_WWAN
	check_config "$K_CONFIG" CONFIG_USB_SERIAL_OPTION
	check_config "$K_CONFIG" CONFIG_PPP
	check_config "$K_CONFIG" CONFIG_AW_REMOTEPROC
	check_config "$K_CONFIG" CONFIG_AW_RPMSG_CTRL
	check_config "$K_CONFIG" CONFIG_RPMSG_VIRTIO
else
	printf 'SKIP %s (尚未完成内核编译)\n' "$K_CONFIG"
fi

if [ -d "$SDK/out/t153/omnigate/buildroot/buildroot/target" ]; then
	check_exec out/t153/omnigate/buildroot/buildroot/target/usr/bin/omnigate-ethercat
	check_exec out/t153/omnigate/buildroot/buildroot/target/usr/bin/amp_shell
	check_exec out/t153/omnigate/buildroot/buildroot/target/usr/bin/omnigate-amp
fi

if [ "$FAILED" -ne 0 ]; then
	echo "Industrial gateway verification failed." >&2
	exit 1
fi

echo "Industrial gateway integration files/configuration verified."
