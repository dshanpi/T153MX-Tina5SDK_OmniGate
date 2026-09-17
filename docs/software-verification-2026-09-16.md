# OmniGate 软件验证记录（2026-09-16）

## 本轮结论

当前结论为 **PASS WITH PERIPHERAL LIMITATIONS**。主机自动化测试、SDK overlay
一致性、完整构建、打包和短时实板功能回归通过。本轮按要求暂停 24 小时
老化，因此本结论不包含长期稳定性。

## 已通过项目

- 5 项平台核心测试：设备/点位 CRUD、版本递增、审计和 Manifest。
- 3 项 Web/HMI 测试：健康端点、HTTP 错误语义和默认非演示模式。
- Python 编译、Shell 语法、Node-RED JSON/JavaScript 静态检查。
- Node-RED 4.1.7 主机临时运行时：登录保护、30 分钟会话、禁用在线安装、
  MQTT telemetry/规则/受控命令、加密凭据和重启持久化。
- 162 个 overlay 交付项与 SDK 内容一致；8 个离线 4G 源码归档校验通过。
- 对 `omnigate-core`、`omnigate-hmi` 定向清理后完整重建并打包成功，避免
  Buildroot 本地包旧 stamp 复用历史产物。
- 新镜像成功传入 Lynx 缓存，远端 SHA-256 与本地一致；`IMAGEWTY` v3、46 个
  内嵌对象、Boot0/Boot1、双 boot、双 rootfs 均可解析，未加密。
- 此前全擦写尝试已建立 12 分区布局；最终采用 `partition + verify + reboot` 完成更新，
  Boot0、Boot1 和全部写入数据校验通过，`verifyState=success`、
  `verifyErrorCode=0`，Linux 在 120 秒门槛内启动。不得将其表述为同一任务内
  `full_erase` 成功。
- 实板统一 API 通过未登录拒绝、登录、平台/通道/系统、设备 CRUD、点位 CRUD、
  CSRF、只读角色和审计检查；连续错误登录第 9 次返回 429。
- 临时自签名 HTTPS 在 8443 验证通过：默认证书校验拒绝自签名证书，显式信任后
  可登录且 Cookie 带 `Secure`；测试后恢复 HTTP 80。
- Web 故障注入后约 33 秒恢复，supervisor 只增加 1 次恢复记录，未形成重启风暴；
  硬件看门狗保持关闭。
- 真实 framebuffer 为 1024×768：顶部 CPU/内存/温度/存储完整，底部无重复指标，
  深灰主题和状态色线条一致，无明显文字截断或布局重叠。
- 最终 `#69` 冷启动已消除缺失 powerkey 工具和 NFS server 的启动告警；未见
  panic、Oops 或 OOM。
- CAN0/1、RS485、双以太网、Wi-Fi、显示、ModemManager 和蜂窝内核驱动完成安全
  枚举；未连接外部从站或网线时不发送控制帧。

## 构建产物

- 镜像：`out/t153_linux_omnigate_bootclean_20260916.img`
- 大小：`604371968` bytes
- SHA-256：`84914b6b79c59c5dd5221ba9aa59ae107c06d4826d193c10260ed7ce5cc87f17`
- 分区：12 个 MBR 分区：`boot-resource`、`env`、`env-redund`、`bootA`、
  `bootB`、`dtbo`、`dtbo-r`、`rootfsA`、`rootfsB`、`private`、
  `rootfs_data`、`UDISK`。

## 明确未完成或受条件限制

- 24 小时老化按用户要求暂不执行；此前中止数据不计作有效老化。
- Goodix 已恢复最初板级配置并在 `0x14` 成功识别为 ID 967，注册为
  `Goodix Capacitive TouchScreen` 和 `/dev/input/event1`；物理触摸已由现场用户
  实际操作确认可用。无 CANopen、Modbus、EtherCAT 外部从站，
  只验证组件、枚举和安全空载行为，不声明协议互操作通过。
- RK3568/T536 的 OCI 资源限制、掉电恢复和硬件负载仍待对应实板。
- ADB、空 root 密码、防火墙、安全启动、签名 OTA 和自动回滚尚未达到
  IEC 62443 生产基线；本结果不是生产安全认证。

## 证据目录

原软件功能证据位于 `acceptance-results/final-software-20260916/`；最终 `#69` 冷启动、
Goodix 状态和当前启动截图位于 `acceptance-results/bootclean-20260916/`。当前真实
framebuffer SHA-256 为
`4a99cdb02598c8fa4e21329968302588da87997fdc70d0c0bd6d0837b07a0949`。
