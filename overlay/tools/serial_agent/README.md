# Serial AI Agent 套件 (A133)

面向 Linux 串口设备的 AI Agent 工具集，基于 `PySerial + LangChain/CrewAI`，并提供 `pexpect` 交互能力。适配 **Allwinner A133 (sun50iw10p1)** 平台。

## 目录说明

- `serial_core.py`: 串口底层读写会话（打开/关闭/发送命令/读取输出）
- `langchain_tools.py`: LangChain `StructuredTool` 封装
- `crewai_tools.py`: CrewAI `Tool` 封装
- `serial_pexpect.py`: 交互式串口终端封装（依赖 `picocom` + `pexpect`）
- `trae_serial_terminal.py`: 面向 Trae AI 终端的串口 CLI（扫描/参数化连接/输入输出）
- `example_langchain_agent.py`: LangChain Agent 示例
- `example_crewai_agent.py`: CrewAI Agent 示例
- `example_bt_wifi_provision.py`: 串口一键执行 WiFi 配网 + 蓝牙配对示例

## 安装依赖

```bash
cd /home/ubuntu/A133-Tina5.0-v0.9/tools/serial_agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## A133 设备信息

- 芯片: Allwinner A133 (sun50iw10p1)
- 串口: /dev/ttyACM1 (USB Quad Serial, VID:PID=1a86:55d5)
- 波特率: 115200 8N1
- 烧录: efex 模式 (U-Boot 进入), ADB sideload
- SDK 路径: /home/ubuntu/A133-Tina5.0-v0.9

## 基础用法（直接调用）

```python
from serial_core import SerialSession, make_serial_config

cfg = make_serial_config(
    port="/dev/ttyACM0",
    baudrate=115200,
    bytesize="8",
    parity="N",
    stopbits="1",
    xonxoff=False,
    rtscts=False,
    dsrdtr=False,
)
sess = SerialSession(cfg)
sess.open()
print(sess.run_command("uname -a"))
sess.close()
```

## Trae 终端一键调用

扫描串口：

```bash
cd /home/ubuntu/A133-Tina5.0-v0.9/tools/serial_agent
python3 trae_serial_terminal.py scan
```

带参数打开并发送一次命令：

```bash
python3 trae_serial_terminal.py io \
  --auto-select --vid 1a86 --pid 55d5 \
  --baudrate 115200 \
  --bytesize 8 \
  --parity N \
  --stopbits 1 \
  --xonxoff false \
  --rtscts false \
  --dsrdtr false \
  --send "help"
```

进入交互模式（连续输入输出，默认透传，支持 Tab 补齐）：

```bash
python3 trae_serial_terminal.py terminal --auto-select --vid 1a86 --pid 55d5 --baudrate 115200
```

纯透传模式（字符级，不等回车，行为更接近 putty）：

```bash
python3 trae_serial_terminal.py terminal-raw --auto-select --vid 1a86 --pid 55d5 --baudrate 115200
```

纯透传并落盘日志（收发双向）：

```bash
python3 trae_serial_terminal.py terminal-raw \
  --auto-select --vid 1a86 --pid 55d5 \
  --baudrate 115200 \
  --log-file /tmp/serial_a133.log
```

说明：
- `terminal` 与 `terminal-raw` 都是长连接透传模式，串口输出会持续实时显示（类似 putty）。
- 按键会实时发送到串口，`Tab` 会直接送到设备端用于命令补齐。
- 两个模式都仅支持 `Ctrl+]` 本地退出，不再使用 `:quit`，可避免误退出终端。
- 透传模式下 `Ctrl+C/Backspace` 不由本地终端拦截，行为更接近原生串口终端。
- `--log-file` 仅在 `terminal-raw` 模式下记录串口收发日志（`[RX]/[TX]`）。
- `scan --json` 可输出结构化 JSON，便于 AI 终端解析。
- 自动选口优先顺序：`sn -> vid/pid -> product/description -> ttyACM/ttyUSB`。
- 指定 `vid/pid/sn/product/description` 但未命中时会直接报错，不会回退到无关串口。

## Go 版本（新增）

目录内新增 Go 实现：
- `main.go`: Go 版本串口 CLI（`scan/io/terminal/terminal-raw`）
- `go.mod`: Go 依赖定义

编译：

```bash
cd /home/ubuntu/A133-Tina5.0-v0.9/tools/serial_agent
go mod tidy
go build -o trae_serial_terminal_go main.go
```

示例：

```bash
./trae_serial_terminal_go scan --json
./trae_serial_terminal_go terminal --auto-select --vid 1a86 --pid 55d5 --baudrate 115200
```

说明：
- Go 版本同样是长连接透传，支持 `Tab` 直通补齐。
- `terminal` 与 `terminal-raw` 都仅通过 `Ctrl+]` 退出。
- 当前 Go 串口库不支持 `xonxoff/rtscts/dsrdtr`，传参会提示并忽略。

## LangChain 用法

```bash
export OPENAI_API_KEY=your_key
python3 example_langchain_agent.py
```

## CrewAI 用法

```bash
export OPENAI_API_KEY=your_key
python3 example_crewai_agent.py
```

## 交互场景（登录、密码、确认框）

```python
from serial_pexpect import PexpectSerialTerminal

t = PexpectSerialTerminal("/dev/ttyUSB0", 115200)
t.open()
t.login("root", "123456")
print(t.run("dmesg | tail -n 20"))
t.close()
```

## 注意事项

- 运行用户需要串口权限（通常加入 `dialout` 组）。
- `serial_pexpect.py` 依赖系统安装 `picocom`。
- 默认串口参数是 `115200 8N1`，并支持 `xonxoff/rtscts/dsrdtr` 流控配置。
