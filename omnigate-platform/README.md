# OmniGate Industrial Control Desktop

OmniGate 是面向工业网关、边缘控制器和带屏控制终端的通用开源桌面运行层。本目录
只保存与 SoC 无关的产品契约；Tina、Buildroot、内核 DTS 和厂商固件继续留在板级
集成目录中。

## 稳定接口

- `components.json`：可发布组件及许可证边界。
- `profiles/*.json`：Lite/Enhanced 运行时组成和资源策略。
- `boards/*.json`：板卡适配描述，不承载应用逻辑。
- `/etc/omnigate/platform.json`：设备运行时硬件 Manifest。
- `contracts/`：版本化 `/api/v1` 与 MQTT 数据契约。
- `schemas/`：板卡、profile、遥测和命令的机器可读 Schema。
- `gates/system-gates.json`：开发版、候选版和生产版的机器可读发布门禁。

应用必须按 Manifest 中的逻辑通道和角色查找硬件，禁止直接写死 `can0`、`eth0`、
`/dev/ttyAS5` 等板级设备名。

## 运行配置

- `lite`：原生 Web、Qt HMI、supervisor、SQLite 和工业协议适配器；不安装
  Node-RED，适合 T153/RK3506 一类资源受限设备。
- `enhanced`：在通用核心上增加受限容器和 Node-RED，面向 RK3568、T536 等设备。
  当前只有主机侧配置验证，必须在对应实板通过资源、掉电和负载测试后才能发布。

架构、移植和门禁入口分别见 `docs/architecture.md`、`docs/porting-guide.md`、
`docs/system-gate-requirements.md`。可复用应用层按
GPL-3.0-only 发布；完整 T153 镜像仍包含 Allwinner BSP 和厂商固件，不能整体宣称为
纯开源软件。
