# OmniGate 蓝牙音响交付变更说明

本文只描述手动蓝牙音响功能的交付内容。所有可覆盖到 Tina SDK 的文件均位于
`overlay/`，不依赖工作区中的 `out/` 编译产物。

## 最终功能

- 通过 `bt-speaker start` 手动把设备切换为 A2DP Sink 蓝牙音响。
- 广播名称为 `T153 Bluetooth Speaker`，采用无输入、无输出的 Just Works
  配对方式，并自动批准首次 A2DP 服务授权。
- 接收手机 SBC 双声道音频，通过 ALSA route 混合为板载 codec 所需的单声道。
- 使用差分 `LINEOUTP/LINEOUTN` 驱动 AW8010，启动时打开 DAC、LINEOUT 和
  SPK 通路。
- `start`、`restart` 会等待旧进程退出，避免新旧 `bluetoothd` 抢占 D-Bus
  名称而出现“看似启动、实际无声”。
- `stop` 会停止用户态音频服务、关闭输出通路并关闭蓝牙控制器。

## Overlay 文件清单

| Tina SDK 相对路径 | 用途 |
| --- | --- |
| `device/config/chips/t153/configs/omnigate/buildroot/overlay/etc/init.d/S45aic8800-bluetooth` | 加载 AIC 模块、控制 rfkill/BT_WAKE，并用 vendor `hciattach` 初始化 UART HCI |
| `device/config/chips/t153/configs/omnigate/buildroot/overlay/usr/bin/bt-speaker` | 蓝牙音响 start/stop/restart/status 主控脚本 |
| `device/config/chips/t153/configs/omnigate/buildroot/overlay/etc/bluetooth/bt-speaker.conf` | 独立 BlueZ 音响配置，不修改系统默认 `main.conf` |
| `device/config/chips/t153/configs/omnigate/buildroot/overlay/etc/asound.conf` | 将手机左右声道各按 0.5 混合到单声道硬件 PCM |
| `buildroot/buildroot-202205/package/bluez-alsa/bluez-alsa.mk` | 明确构建为 SBC-only，关闭实板不可用的 aptX/aptX HD endpoint |
| `device/config/chips/t153/configs/omnigate/linux-5.10-origin/board.dts` | 配置 AIC 蓝牙 PCM 使用的 I2S0 PB5～PB8 pinmux |
| `bsp/drivers/net/wireless/aic8800/aic8800_btlpm/aic8800_btlpm.c` | AIC 蓝牙低功耗/BT_WAKE 板级配合 |

仓库内的精确清单另见
[`meta/bluetooth-speaker-files.tsv`](../meta/bluetooth-speaker-files.tsv)。

## 应用与编译

```sh
cd /path/to/t153mx-ominigate-v1
./scripts/verify_bluetooth_speaker.sh
./scripts/apply_overlay.sh /path/to/T153_Tina_V1.0

cd /path/to/T153_Tina_V1.0
source build/envsetup.sh
lunch t153_omnigate_mmc-buildroot
make
pack
```

若要核对 overlay 是否已完整复制到目标 SDK：

```sh
cd /path/to/t153mx-ominigate-v1
./scripts/verify_bluetooth_speaker.sh /path/to/T153_Tina_V1.0
```

## 设备使用

```sh
bt-speaker start
bt-speaker status
bt-speaker restart
bt-speaker stop
```

手机搜索并连接 `T153 Bluetooth Speaker`。连接后可用以下命令确认实际音频
状态：

```sh
bluealsa-aplay -L
cat /proc/asound/card0/pcm0p/sub0/status
cat /proc/asound/card0/pcm0p/sub0/hw_params
```

本次一加 13 实板验证结果：

```text
A2DP (SBC): S16_LE 2 channels 44100 Hz
state: RUNNING
format: S16_LE
channels: 1
rate: 44100
```

同时使用板端 880 Hz 测试音验证了 DAC、差分 LINEOUT、AW8010 和喇叭硬件
通路，持续测试音可正常听到。

## aptX 结论

本次曾编入并实测标准 aptX 和 aptX HD。两者都能完成 codec 协商，但音乐
开始传输后立即出现：

```text
BT poll and read error: Function not implemented
```

PCM 随即关闭且喇叭无声。由于标准 aptX 与 aptX HD 均复现，问题不属于
24-bit 格式转换或功放，而是当前 BlueZ 5.54、BlueALSA 3.1.0 与板级 5.10
内核的厂商 A2DP codec 传输组合。交付版本因此固定为已验证可播放的
SBC-only。不要仅凭 `bluealsa --help` 能列出 aptX 就重新开放 endpoint；
必须完成实际连续播放验证。

## 运行日志与已知提示

```sh
cat /tmp/hciattach-aic.log
cat /tmp/bt-speaker-bluetoothd.log
cat /tmp/bt-speaker-bluealsa.log
cat /tmp/bt-speaker-aplay.log
cat /tmp/bt-speaker-agent.log
```

BlueALSA 可能输出以下兼容性警告，但 SBC 持续播放不受影响：

```text
Capabilities blob size exceeded: 40 > 17
Couldn't open mixer: Mixer element not found
```

音量和输出开关由 `bt-speaker` 直接设置，未依赖 BlueALSA mixer 元素。

## 回退

该交付没有删除系统文件。需要停用时执行：

```sh
bt-speaker stop
```

若需要从源码树移除功能，应在目标 SDK 中按
`meta/bluetooth-speaker-files.tsv` 审查并恢复相应文件；不要直接删除
`board.dts`、`aic8800_btlpm.c` 或整个 Buildroot package 文件。
