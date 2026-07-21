---
name: "t153-lvgl-ui-demo-dev"
description: "在T153上创建/编译/烧写/验证LVGL界面示例。需要新增或调试LVGL应用并完成板端运行闭环时调用。"
---

# T153 LVGL界面示例开发

用于在 `T153MX/T153_Tina_V1.0` 中快速完成 LVGL 示例应用开发闭环：  
新增示例代码 -> 交叉编译 -> 烧写系统 -> 启动后运行验证。

## 何时调用

- 需要在 T153 上新增一个 LVGL 界面示例程序
- 需要验证 LVGL 程序可在板端正常启动并显示
- 需要联动 `OpenixCLI` 完成烧写与启动回归

## 默认约定

- SDK 根目录：`/home/ubuntu/T153MX/T153_Tina_V1.0`
- LVGL8 代码根：`platform/thirdparty/gui/lvgl-8`
- 示例名：`lv_hello_t153`
- 显示/输入后端：`sunxifb + evdev`
- 镜像：`out/t153_linux_omnigate_uart0.img`

## 1. 新增示例源码

建议目录结构：

- `platform/thirdparty/gui/lvgl-8/lv_hello_t153/src/main.c`
- `platform/thirdparty/gui/lvgl-8/lv_hello_t153/src/Makefile`
- `openwrt/package/thirdparty/gui/lvgl-8/lv_hello_t153/Makefile`

关键点：

- `main.c` 使用：
  - `#include "lv_drivers/display/sunxifb.h"`
  - `#include "lv_drivers/indev/evdev.h"`
- 初始化流程：
  - `lv_init()` -> `sunxifb_init()` -> 注册 `lv_disp_drv` -> `evdev_init()` -> UI 创建 -> `while(1){ lv_task_handler(); usleep(5000); }`
- `custom_tick_get()` 保持与 LVGL 配置一致。
- 字体优先使用当前配置已启用字体（如 `lv_font_montserrat_16`），避免链接期符号缺失。

## 2. 包构建接入（OpenWrt包）

`openwrt/package/thirdparty/gui/lvgl-8/lv_hello_t153/Makefile` 需包含：

- `include ../sunxifb.mk`
- `Build/Prepare` 拷贝：
  - `src/`
  - `../lvgl`
  - `../lv_drivers`
  - `../lv_examples/src/lv_conf.h`
  - `../lv_examples/src/lv_drv_conf.h`
- `Build/Compile` 使用 `TARGET_CC / TARGET_CFLAGS / TARGET_LDFLAGS`
- 安装到 `/usr/bin/lv_hello_t153`

## 3. 本地交叉编译快速验证（推荐先做）

```bash
TMP=/tmp/lv_hello_t153_build
rm -rf "$TMP"
mkdir -p "$TMP/src"
cp platform/thirdparty/gui/lvgl-8/lv_hello_t153/src/main.c "$TMP/src/"
cp platform/thirdparty/gui/lvgl-8/lv_hello_t153/src/Makefile "$TMP/src/"
cp platform/thirdparty/gui/lvgl-8/lv_examples/src/lv_conf.h "$TMP/src/"
cp platform/thirdparty/gui/lvgl-8/lv_examples/src/lv_drv_conf.h "$TMP/src/"
cp -r platform/thirdparty/gui/lvgl-8/lvgl "$TMP/src/"
cp -r platform/thirdparty/gui/lvgl-8/lv_drivers "$TMP/src/"
make -C "$TMP/src" clean all \
  CC=out/t153/omnigate/buildroot/buildroot/host/opt/ext-toolchain/bin/arm-linux-gnueabihf-gcc
file "$TMP/src/lv_hello_t153"
```

期望输出：`ELF 32-bit LSB executable, ARM`。

## 4. 烧写并启动验证

### 4.1 进入烧录模式

```bash
HOME=/tmp/adbhome adb shell 'reboot efex'
cd /home/ubuntu/T153MX/T153_Tina_V1.0
sudo tools/OpenixCLI/openixcli scan -l
```

期望看到 `Mode: FEL`。

### 4.2 烧写镜像

```bash
sudo tools/OpenixCLI/openixcli flash /home/ubuntu/T153MX/T153_Tina_V1.0/out/t153_linux_omnigate_uart0.img \
  --reconnect-timeout-sec 240 \
  --reconnect-interval-ms 300 \
  -v
```

期望日志：`All partitions flashed successfully`。

### 4.3 启动回归

```bash
HOME=/tmp/adbhome adb wait-for-device
HOME=/tmp/adbhome adb shell 'uname -a'
```

## 5. 板端运行示例验证

将示例推到板端并运行：

```bash
HOME=/tmp/adbhome adb push /tmp/lv_hello_t153_build/src/lv_hello_t153 /tmp/lv_hello_t153
HOME=/tmp/adbhome adb shell 'chmod +x /tmp/lv_hello_t153'
HOME=/tmp/adbhome adb shell '/tmp/lv_hello_t153 > /tmp/lv_hello_run.log 2>&1 & echo $!'
HOME=/tmp/adbhome adb shell 'ps | grep lv_hello_t153 | grep -v grep'
```

有进程即表示示例已启动。停止命令：

```bash
HOME=/tmp/adbhome adb shell 'killall lv_hello_t153'
```

## 常见问题

- `openixcli scan -l` 找不到设备：先 `adb shell reboot efex`，或在 U-Boot 执行 `efex`。
- 构建时报 `lv_conf.h` 缺失：在 `Build/Prepare` 补拷贝 `lv_examples/src/lv_conf.h` 与 `lv_drv_conf.h`。
- 字体符号未定义：改用配置里已启用字体（优先 `lv_font_montserrat_16`）。
- `buildroot` 阶段出现 `chown ... Invalid argument`：通常是宿主文件系统权限能力限制，先用“本地交叉编译 + adb push运行”验证功能，再迁移到支持完整权限语义的构建盘做固化镜像。
