# T153MX-Tina5SDK_OmniGate

> Allwinner T153 (4× Cortex-A7) Tina Linux SDK — **OmniGate** 板级配置与开发工具 overlay 包。
> 本仓库是一个 **覆盖式差异备份（overlay package）**，包含对 T153 Tina SDK 的源码改动、板级配置、固件、根文件系统启动脚本、AI 调试 skills 与工具，可一键应用到兼容的 T153 Tina SDK 工作树。

本次 overlay 与 `/home/ubuntu/T153_Tina5SDK-V1` 当前已验证工作树同步，主要包含：

- AIC8800D80 Wi-Fi / Bluetooth 驱动、固件与自动启动配置；
- 双网口自动 DHCP、链路断开后及时清理地址、重新插线后自动获取地址；
- CAN0 / CAN1 默认以 1 Mbps 启动，并降低 runtime PM 无效日志；
- TF 卡轮询检测、热插拔自动挂载/卸载以及 MMC 空卡轮询日志降噪；
- 板载音频上电默认配置、三路 LED 控制与流水灯启动模式；
- USB1 Host、双 4G 相关用户态软件包、G2D/LVGL 加速和 64 MiB CMA；
- 4G 软件栈所需的 8 个 Buildroot 源码归档，可在无法访问 GitHub 等站点时离线命中；
- Linux MIPI DSI 显示配置。U-Boot 显示驱动配置保留，但启动 Logo 默认关闭。

## 硬件概览

OmniGate 是基于全志 T153 SoC（4× Cortex-A7）的工业网关 / 异构控制板：

- **网络**：双 4G LTE + 双 RJ45 千兆以太网（RGMII）；默认 `eth0` 专用于 EtherCAT，`eth1` 用于普通 IP 网络
- **总线**：2× CAN-FD + 2× RS485
- **无线**：Wi-Fi + Bluetooth（AIC8800D80，SDIO + UART）
- **音频**：PCM
- **显示**：RGB888（MIPI DSI ×4 + SPI1）
- **摄像头**：MIPI CSI1/2 ×4 lane

## 硬件实物图

### DshanPI-OminiGate

![DshanPI-OminiGate-1](./images/DshanPI-OminiGate-1.png)
![DshanPI-OminiGate-2](./images/DshanPI-OminiGate-2.png)
![DshanPI-OminiGate-3](./images/DshanPI-OminiGate-3.png)

### mCore-T153MX

![mCore-T153MX-1](./images/mCore-T153MX-1.png)
![mCore-T153MX-2](./images/mCore-T153MX-2.png)
![mCore-T153MX-3](./images/mCore-T153MX-3.png)

## 仓库结构

```
t153mx-ominigate-v1/
├── README.md                  本文档
├── LICENSE                    仓库许可证
├── .gitignore
├── images/                    硬件实物图
├── overlay/                   覆盖到 Tina SDK 工作树的差异文件
│   ├── bsp/                   驱动源码改动（aic8800_btlpm.c 等）
│   ├── buildroot/             buildroot defconfig 改动
│   ├── device/                T153 omnigate 板级配置（BoardConfig.mk / sys_config.fex /
│   │                          sys_partition.fex / dtbo / linux-5.10-origin / linux-5.10-rt / buildroot）
│   ├── platform/              aic8800 固件（sdio / aic8800d80）
│   ├── skills/                AI 辅助开发 skills（见下文）
│   └── tools/                 OpenixCLI 烧录工具 + serial_agent 串口代理
├── meta/                      overlay 元数据
│   ├── changed_files.tsv      完整 overlay 交付文件清单
│   ├── overlay_manifest.sha256 overlay 文件内容校验和
│   ├── offline_4g_sources.tsv 4G 离线源码版本、路径与校验和
│   ├── delete_list.txt        apply 时需要从 SDK 删除的旧固件清单
│   ├── repo_status.txt        `repo status` 原始输出
│   ├── repo_projects.txt      repo 项目列表
│   ├── summary.json           汇总统计
│   ├── skipped_files.tsv
│   └── errors.json
└── scripts/                   应用脚本
    ├── apply_overlay.sh       把 overlay/ 拷到目标 SDK 工作树
    ├── verify_overlay.sh      全量比较 overlay 与目标 SDK
    ├── verify_offline_sources.sh 校验 4G 离线源码包
    └── apply_deletes.sh       按 meta/delete_list.txt 删除 SDK 中的旧文件
```

## 包含 / 排除

**包含**：影响 OmniGate 固件重编和运行行为的源码、配置、启动脚本、板级二进制与无线固件，以及随补丁交付的开发工具、AI skills 和经过校验的 4G 离线源码归档。

**排除**：`out/`、除 4G 离线归档以外的下载缓存、编译中间件、`*.bak*` / `*.orig*` 调试备份、`prebuilt/rootfsbuilt/` 和 `.local_patch/`。

> 注意：`openwrt/target/` 和 `openwrt/openwrt/target/` 是源码配置目录，不按缓存排除。

## 使用方法

### 1. 应用 overlay 到现有 Tina SDK 工作树

```sh
# 假设 Tina SDK 在 /path/to/TinaSDK
/path/to/t153mx-ominigate-v1/scripts/apply_overlay.sh /path/to/TinaSDK

# 核对蓝牙音响相关文件是否完整落到 SDK 的真实路径
/path/to/t153mx-ominigate-v1/scripts/verify_bluetooth_speaker.sh /path/to/TinaSDK

# 核对 ThingsBoard / SOEM / RS485-CAN / EC20 集成及最终配置
/path/to/t153mx-ominigate-v1/scripts/verify_industrial_gateway.sh /path/to/TinaSDK
```

脚本会把 `overlay/` 下所有文件按相对路径 tar 拷贝到目标 SDK，随后逐文件执行内容、符号链接和权限校验。脚本**不执行任何删除动作**。

> 不要执行 `cp -a t153mx-ominigate-v1/* /path/to/TinaSDK/`。这样会得到
> `/path/to/TinaSDK/overlay/device/...`，而构建系统实际读取的是
> `/path/to/TinaSDK/device/...`，最终会报 `Can't find kernel defconfig!`。

也可以单独执行校验：

```sh
/path/to/T153MX-Tina5SDK_OmniGate/scripts/verify_overlay.sh /path/to/TinaSDK
```

### 2. 4G 软件包离线构建

补丁会把以下源码直接放到 Buildroot 的标准 `dl/<package>/` 目录：

- libmbim 1.26.2、libqmi 1.30.4、ModemManager 1.18.6；
- libubox、uqmi；
- pppd 2.4.9；
- usb-modeswitch 2.6.1、usb-modeswitch-data 20191128。

因此这些包不会再访问 GitHub、GitLab、OpenWrt Git 或上游下载站。应用脚本会自动检查八个归档的 SHA-256；也可单独运行：

```sh
/path/to/T153MX-Tina5SDK_OmniGate/scripts/verify_offline_sources.sh /path/to/TinaSDK
```

这里保证的是本方案新增的八个 4G 源码包可离线使用；如果客户的基础 SDK 本身缺少其他通用依赖缓存，Buildroot 仍可能为那些非 4G 新增项发起下载。

### 3. （可选）清理已被替换的旧固件

```sh
# 先人工审查清单
cat /path/to/t153mx-ominigate-v1/meta/delete_list.txt

# 确认无误后执行删除（脚本会要求输入 YES 二次确认）
/path/to/t153mx-ominigate-v1/scripts/apply_deletes.sh /path/to/TinaSDK
```

`delete_list.txt` 主要是 aic8800 旧版固件（已被 `*_u02.bin` 替代）。

### 4. 编译 / 烧录 / 串口调试

应用 overlay 后，在 SDK 根目录执行本版本已经实板验证的构建流程：

```sh
# 在 SDK 根目录
source build/envsetup.sh
lunch t153_omnigate_mmc-buildroot
./build.sh
./build.sh pack
```

若当前 SDK 尚未生成构建配置，也可以先运行 `./build.sh config`，依次选择
`linux / buildroot / t153 / omnigate / default / linux-5.10-origin`。

生成的默认镜像为 `out/t153_linux_omnigate_uart0.img`。

烧录建议使用本仓库自带的 OpenixCLI：

```sh
tools/OpenixCLI/openixcli scan -l
tools/OpenixCLI/openixcli inspect out/t153_linux_omnigate_uart0.img
tools/OpenixCLI/openixcli flash --verify true --mode full_erase \
    --post-action reboot out/t153_linux_omnigate_uart0.img
```

`full_erase` 会清除旧数据和蓝牙配对记录；烧录完成后需要在手机上删除旧记录并
重新配对。

### 4. 工业协议与 ThingsBoard

本 overlay 已集成：

- `http://板子IP/` 本地 Web 管理页面（初始账号 `admin / omnigate`）
- ThingsBoard Gateway 3.8.3（默认不开机启动，填写服务端和 Token 后再启用）
- NTP 自动校时（避免无 RTC 冷启动后 MQTT/HTTPS 证书校验失败）
- SOEM 2.0.0 EtherCAT 主站、结构化扫描、CoE SDO 与周期/WKC 测试
- 1 路 Modbus RTU，默认设备 `/dev/ttyAS5`
- Python CANopen 主站，支持 EDS、节点身份/心跳诊断、NMT、SDO 和 PDO
- `can0` / `can1` 两路经典 CAN / CAN-FD
- 双 EC20 所需的 USB 串口、QMI/WWAN、MBIM 和 PPP 内核/用户态支持
- 原有蓝牙音响及 aptX 支持保持不变

接口配置、启动命令及验收方法见
[工业网关集成说明](./docs/industrial-gateway-integration.md)，本轮新增内容和实物
验收清单见 [2026-07-29 续作记录](./docs/industrial-gateway-development-2026-07-29.md)。
分支所含代码、配置、构建结果及待验项目汇总在
[Gateway CANopen / EtherCAT 交付清单](./docs/gateway-canopen-ethercat-change-set.md)。

串口调试建议使用自带的 serial_agent（独占式串口代理，避免多人/多终端抢占 `/dev/ttyACM0`）：

```sh
cd tools/serial_agent
sudo python3 serial_agent_daemon.py --port /dev/ttyACM0 --baudrate 115200 --tcp-port 23334

# 另开终端实时查看
nc 127.0.0.1 23334
```

## AI Skills

`overlay/skills/` 下提供 5 个用于 Claude / Trae 等 AI Agent 的开发 skill：

| Skill | 用途 |
| --- | --- |
| `system-sdk-ai-default` | T153 SDK 默认 AI 开发闭环：清理配置 → 编译打包 → 烧录 → 串口验证 |
| `t153-flash-serial-debug` | 统一 T153 串口连接与固件烧录流程，含 FEL/USB 恢复步骤 |
| `t153-c906-heterogeneous-dev` | T153 A7 Linux + C906 RTOS 异构开发联调（remoteproc / RPMsg / amp_shell） |
| `t153-lvgl-ui-demo-dev` | 在 T153 上创建 / 交叉编译 / 烧写 / 验证 LVGL 界面示例 |
| `serial-agent-daemon` | T153 串口独占代理（single-owner）使用规范，避免串口抢占冲突 |

每个 skill 目录下的 `SKILL.md` 是触发条件 + 操作流程的完整说明，AI Agent 会按需调用。

## 工具

- **`tools/OpenixCLI/`** — 全志固件烧录 CLI（含 `openixcli` 二进制、deb 安装包、桌面启动器）
- **`tools/serial_agent/`** — Python 串口代理 daemon + client，支持 LangChain / CrewAI 工具集成，提供 TCP 透传端口供 `nc` 接入

## 元数据说明

`meta/` 目录用于记录 overlay 的生成上下文，方便回溯：

- `changed_files.tsv` — 完整 overlay 交付清单；`SYNC` 表示来自当前 SDK，`PKG` 表示补丁独立附带的工具或 skill
- `overlay_manifest.sha256` — overlay 内普通文件的 SHA-256 校验和
- `offline_4g_sources.tsv` — 4G 离线源码包的版本、目标路径、大小和 SHA-256
- `delete_list.txt` — 需要从 SDK 删除的旧文件路径（一行一个，相对 SDK 根）
- `repo_status.txt` — 生成时逐个 SDK 子仓库采集的 `git status` 快照
- `repo_projects.txt` — 生成时的 `repo project -l` 输出
- `summary.json` — overlay 文件数 / 删除条目数 / 排除规则等汇总

## 许可证

见 [LICENSE](./LICENSE)。

## 相关仓库

- 上游 Tina SDK：全志官方 Tina Linux V5.0
- OpenixCLI：<https://github.com/YuzukiTsuru/OpenixCLI>
- ThingsBoard Gateway：<https://github.com/thingsboard/thingsboard-gateway>
- SOEM EtherCAT 主站：<https://github.com/OpenEtherCATsociety/SOEM>
