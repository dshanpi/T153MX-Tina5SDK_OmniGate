# OmniGate WLAN 复位与 AIC8800D80 蓝牙启动记录

本文记录 2026-07-24 在 OmniGate 实板上验证通过的 WLAN/蓝牙修改。相关文件均已按 Tina SDK 根目录的相对路径收纳到 `overlay/`，可通过 `scripts/apply_overlay.sh` 应用。

## 结论

- 硬件去掉 D30 后，RESET 期间 PJ10/WLAN_REGON 的异常 1.8～1.9 V 消失。
- U-Boot 启动早期主动将 PJ10 拉低，并把未使用的 SDC3 主控侧引脚 PE0、PE5～PE9 配成 GPIO 输入，降低经 TXB0108 倒灌的风险。
- AIC8800D80 蓝牙不能沿用 `hciattach ... any 115200 noflow`。必须使用 AIC vendor 初始化，并在初始化前拉起 BT_WAKE。
- 蓝牙 PCM 已配置到 I2S0：PB5～PB8。
- 完整镜像经 FEL 烧录并启动验证，`hci0` 为 `UP RUNNING`，控制器名称为 `AIC8820`，PCM pinmux 生效。

## 修改文件

### U-Boot 防倒灌

- `overlay/brandy/brandy-2.0/u-boot-bsp/board/sunxi/board.c`
  - 在 `sunxi_plat_init()` 后保持 PJ10/WLAN_REGON 为低。
  - 将 SDC3 的 PE0、PE5、PE6、PE7、PE8、PE9 请求为 GPIO 输入。
- `overlay/device/config/chips/t153/configs/omnigate/uboot-board.dts`
  - 增加 `/wlan-reset`，声明 PJ10 和上述 SDC3 GPIO。

`u-boot-2023/bsp` 是当前构建环境使用的工作路径，实际对应受控源码目录 `u-boot-bsp`；overlay 仅保留后者，避免打包构建别名。

### 蓝牙启动

- `overlay/device/config/chips/t153/configs/omnigate/buildroot/overlay/etc/init.d/S45aic8800-bluetooth`
  - 加载 `aic8800_bsp`、`aic8800_fdrv`、`aic8800_btlpm`。
  - 按 rfkill 的 `name` 同时控制 `sunxi-bt` 和 `bluetooth`，不依赖不稳定的 `rfkill0` 编号。
  - 写入 `/proc/bluetooth/sleep/btwrite` 拉起 BT_WAKE。
  - 使用 `hciattach -n /dev/ttyAS7 aic` 执行 AIC vendor 初始化。
  - 等待 `hci0` 出现后执行 `hciconfig hci0 up`。

AIC 固件补丁要求 UART 工作到 1500000 baud 并启用流控。`aic` 类型的 `hciattach` 会完成 vendor 初始化和速率切换；固定使用 `any 115200 noflow` 会卡在 HCI Reset。

### 蓝牙 PCM

- `overlay/device/config/chips/t153/configs/omnigate/linux-5.10-origin/board.dts`

| SoC 引脚 | I2S0 功能 | 蓝牙侧信号 |
| --- | --- | --- |
| PB5 | `i2s0_bclk` | PCM_CLK |
| PB6 | `i2s0_lrck` | PCM_SYNC |
| PB7 | `i2s0_dout0` | PCM_IN |
| PB8 | `i2s0_din0` | PCM_OUT |

`&i2s0_plat` 已绑定 default/sleep pinctrl，睡眠状态将 PB5～PB8 切换为 `io_disabled`。

## 应用、编译与烧录

在本交付仓库外的 Tina SDK 根目录执行：

```sh
/path/to/t153mx-ominigate-v1/scripts/apply_overlay.sh /path/to/TinaSDK

cd /path/to/TinaSDK
source build/envsetup.sh
lunch t153_omnigate_mmc-buildroot
make
pack
```

本次生成并验证的镜像名称为：

```text
out/t153_linux_omnigate_uart0.img
```

设备进入 FEL 后可使用 OpenixCLI 烧录：

```sh
sudo /path/to/openixcli flash out/t153_linux_omnigate_uart0.img
```

## 启动后检查

```sh
/etc/init.d/S45aic8800-bluetooth restart
hciconfig -a

for path in /sys/class/rfkill/rfkill*; do
	name="$(cat "$path/name")"
	state="$(cat "$path/state")"
	soft="$(cat "$path/soft")"
	echo "$path name=$name state=$state soft=$soft"
done

grep -E 'pin (37|38|39|40) ' /sys/kernel/debug/pinctrl/*/pinmux-pins
```

预期结果：

- `hci0` 显示 `UP RUNNING`，名称为 `AIC8820`。
- `sunxi-bt` 和 `bluetooth` 对应 rfkill 均为 `state=1`、`soft=0`。
- pin 37～40 分别由 `i2s0_bclk`、`i2s0_lrck`、`i2s0_dout0`、`i2s0_din0` 占用。

如自动脚本失败，先查看：

```sh
cat /tmp/hciattach-aic.log
dmesg | grep -Ei 'aic|bluetooth|hci|rfkill'
```

手工恢复时的关键顺序是：加载模块、按名称开启两个 Bluetooth rfkill、拉起 BT_WAKE，最后执行 AIC vendor `hciattach`。

## 手动启用蓝牙音响（A2DP Sink）

固件中的 BlueZ、BlueALSA 和板载 `audiocodec` 已由 `/usr/bin/bt-speaker`
串成一个可手动启停的蓝牙音响。它不会随系统自动启动。

```sh
# 启用；手机搜索 “T153 Bluetooth Speaker”，配对后直接播放音乐
bt-speaker start

# 查看控制器、连接、进程和功放状态
bt-speaker status

# 重启用户态蓝牙音频服务
bt-speaker restart

# 停止音频服务、关闭功放并关闭蓝牙控制器
bt-speaker stop
```

启动时脚本会：

1. 调用 `S45aic8800-bluetooth` 完成 AIC vendor HCI 初始化。
2. 启动 `bluetoothd`，注册 `NoInputNoOutput` 配对代理并自动批准首次
   A2DP 服务授权。
3. 使用专用 `bt-speaker.conf` 将设备设为永久可发现、可配对的
   Audio/Video Loudspeaker，不修改系统默认 `main.conf`。
4. 启动 `bluealsa -p a2dp-sink`，由 `bluealsa-aplay` 输出到
   `bt_speaker`；该 ALSA route 将手机双声道以 0.5 + 0.5 混合成板载
   codec 支持的单声道，并保持原始采样率。
5. 按原理图将 codec 切换为差分 `LINEOUTP/LINEOUTN`，并打开
   `LINEOUTL` 与 `SPK` 通路；板载 AW8010 的 `SHUTDOWN#` 已由硬件上拉。

可临时自定义广播名称或 ALSA 设备：

```sh
BT_NAME='My Speaker' bt-speaker start
ALSA_PCM='hw:0,0' bt-speaker restart
```

排障日志：

```sh
cat /tmp/bt-speaker-bluetoothd.log
cat /tmp/bt-speaker-bluealsa.log
cat /tmp/bt-speaker-aplay.log
cat /tmp/bt-speaker-agent.log
```

## aptX 实板结论

当前固件只启用 SBC。实板测试中，一加 13 能分别协商到标准 aptX 和 aptX HD，
但音乐开始传输后，两种 aptX 的 BlueALSA 蓝牙接收线程都会立即报
`BT poll and read error: Function not implemented`，PCM 随即关闭。板端直接
播放测试音正常，确认 DAC、AW8010 功放和喇叭无故障。问题位于当前 BlueZ
5.54、BlueALSA 3.1.0（20211122 源码快照）与板级 5.10 内核的厂商 A2DP
codec 传输组合。

为保证蓝牙音响实际可用，Buildroot 规则明确关闭 aptX 与 aptX HD，手机会
回退到已验证可持续播放的 SBC。后续只有在升级或修复内核/蓝牙传输栈，并
完成实板连续播放验证后，才应重新开放 aptX endpoint。

编译后检查：

```sh
bluealsa --help
```

预期 A2DP profile 的 codec 列表包含：

```text
Advanced Audio Sink (SBC)
```

连接手机并播放后检查实际协商结果：

```sh
bluealsa-aplay -L
```

连接并开始播放后，输出中应出现 `A2DP (SBC)`。

本次使用一加 13 实板验证的协商结果为：

```text
A2DP (SBC): S16_LE 2 channels 44100 Hz
```

限制：

- SBC 是有损编码；当前固件不提供 aptX、aptX HD、aptX Adaptive 或
  aptX Lossless。
- OmniGate 板载 codec/喇叭通路为单声道，ALSA route 会将接收到的双声道
  混合为单声道；SBC 输入不会使硬件变为立体声。
