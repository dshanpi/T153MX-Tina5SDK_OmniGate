# OmniGate `/api/v1` contract

`/api/v1` 是桌面、Web、自动化应用与板级实现之间的稳定边界。响应使用 JSON；修改
请求必须通过登录、角色检查和 CSRF 校验。未知资源返回 404，校验失败返回 400/422，
权限不足返回 403，内部异常不得向客户端泄露调用栈。

| Resource | Methods | Purpose |
| --- | --- | --- |
| `/api/v1/platform` | GET | 板型、SoC、运行 profile 和能力 |
| `/api/v1/system` | GET | CPU、内存、温度、存储及服务状态 |
| `/api/v1/channels` | GET | 逻辑通道及板级绑定，只读 |
| `/api/v1/devices` | GET, POST | 设备列表和创建 |
| `/api/v1/devices/{id}` | GET, PUT, DELETE | 设备配置、乐观版本和删除 |
| `/api/v1/points` | GET | 数据点列表，可按设备过滤 |
| `/api/v1/points/{id}` | GET, PUT, DELETE | 点位配置和版本递增 |
| `/api/v1/audit` | GET | 有界审计记录 |

应用不得根据板卡 ID 分支访问 Linux 设备；所有硬件解析必须经过 `platform` 和
`channels`。破坏性现场总线写操作不属于通用 CRUD，必须由协议适配器进行范围校验、
权限控制、确认和审计。
