# Architecture

OmniGate 把工业控制桌面拆成四层，板级差异只能向下收敛。

1. **应用层**：Qt HMI、Web、Node-RED 和后续第三方应用，只调用 `/api/v1` 或 MQTT。
2. **平台服务层**：认证、设备/点位模型、SQLite、审计、健康检查和 supervisor。
3. **协议适配层**：CANopen、Modbus RTU、EtherCAT、蜂窝和网络适配器，把厂商数据
   转换成统一设备与点位模型。
4. **板级支持层**：内核、DTS、启动、设备节点、显示和厂商固件，通过
   `/etc/omnigate/platform.json` 暴露逻辑能力。

依赖方向固定为“应用 → 平台 → 协议 → 板级”。应用层禁止导入板级脚本，容器禁止
获得硬件设备权限。Lite 使用本机进程；Enhanced 可增加 OCI 应用，但二者共享相同 API、
数据模型和硬件 Manifest。

持久数据默认位于 `/var/lib/omnigate`。配置采用临时文件加原子替换，设备和审计数据
使用 SQLite。所有服务必须提供健康状态，supervisor 只负责有限次数恢复，不代替启动
系统、硬件看门狗或 A/B 回滚。
