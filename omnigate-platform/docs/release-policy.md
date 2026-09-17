# Release policy

发布状态和证据要求以
[系统发布门禁要求](./system-gate-requirements.md)及机器可读的
`../gates/system-gates.json` 为准。硬件缺失、人工触摸未执行或老化未完成必须列为
限制或 `not-run`，不能改写为通过。

- 平台源码包只包含可复用 GPL 应用、契约、测试和构建接入示例。
- 板卡集成包可包含 BSP、固件和厂商工具，但保留各自许可证，不冠以“全开源”。
- 每个二进制镜像记录版本、大小、SHA-256、分区表、工具版本和板卡描述 ID。
- `release-status.json` 是当前验证状态，不是营销声明；每次发布必须随证据更新。
- `-dev` 版本不允许标记为生产安全或现场协议互操作认证通过。
- 发布前运行 `python3 scripts/check_release_gates.py`；其结果必须与人工证据审查一起归档。
