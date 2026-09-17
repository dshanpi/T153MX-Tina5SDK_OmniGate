# OmniGate MQTT contract

Enhanced 应用只通过私有 MQTT 网络与硬件适配器交换规范化数据，容器不得直接挂载
CAN、串口、GPIO 或原始 EtherCAT 网卡。

- 遥测：`devices/{device_id}/telemetry`
- 受控命令：`devices/{device_id}/commands/request`
- 命令结果：`devices/{device_id}/commands/result`
- 在线状态：`devices/{device_id}/state`

遥测和命令分别必须符合 `schemas/telemetry.schema.json`、
`schemas/command.schema.json`。命令消费者必须拒绝过期、重复 `command_id`、未知动作
和越权请求，并把执行者、结果及失败原因写入审计。代理不得暴露到非管理网络；生产
部署必须启用独立凭据、ACL 和 TLS。
