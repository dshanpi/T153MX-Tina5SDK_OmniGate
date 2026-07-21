---
name: "openixcli-install-build"
description: "Installs dependencies and builds OpenixCLI on Linux. Invoke when setting up a new machine, fixing build environment issues, or reproducing local compilation."
---

# OpenixCLI 安装编译配置说明

用于在 Linux 环境完成 OpenixCLI 的依赖安装、Rust 工具链配置、编译与运行验证，并处理常见环境问题。

## 何时使用

- 新机器首次搭建 OpenixCLI 开发环境
- 本地执行 `cargo build --release` 失败需要排障
- 需要给团队输出标准化安装编译步骤

## 目标环境

- 操作系统：Ubuntu / Debian 系
- 项目目录：`/home/ubuntu/OpenixCLI`（可替换为实际路径）
- 需要 sudo 权限用于安装系统依赖

## 标准步骤

### 1) 安装系统依赖

```bash
sudo apt-get update
sudo apt-get install -y cargo rustc libusb-1.0-0-dev pkg-config curl
```

说明：
- `libusb-1.0-0-dev` 是底层 USB 通信编译依赖
- 系统自带 `cargo/rustc` 可能过旧，仅作为兜底

### 2) 安装新版 Rust（推荐）

项目依赖可能要求新版 Cargo（例如支持 `edition2024`）。

```bash
cd /home/ubuntu/OpenixCLI
export CARGO_HOME=$PWD/.cargo-home
export RUSTUP_HOME=$PWD/.rustup-home
export RUSTUP_INIT_SKIP_PATH_CHECK=yes
curl https://sh.rustup.rs -sSf | sh -s -- -y --default-toolchain stable --no-modify-path
export PATH=$PWD/.cargo-home/bin:$PATH
cargo --version
rustc --version
```

### 3) 编译 release

```bash
cd /home/ubuntu/OpenixCLI
export CARGO_HOME=$PWD/.cargo-home
export RUSTUP_HOME=$PWD/.rustup-home
export PATH=$PWD/.cargo-home/bin:$PATH
export CARGO_TARGET_DIR=$PWD/target
cargo build --release
```

成功后产物：
- `target/release/openixcli`

### 4) 运行验证

```bash
./target/release/openixcli --help
./target/release/openixcli scan
```

说明：
- `scan` 在未连接设备时返回 `Device not found` 属正常现象

## 常见问题与处理

### 问题 1：`cargo: command not found`

原因：未安装 Rust 或 PATH 未包含 Cargo。

处理：
- 按“安装新版 Rust”步骤执行
- 确认 `export PATH=$PWD/.cargo-home/bin:$PATH`

### 问题 2：`feature 'edition2024' is required`

原因：Cargo 版本过低（如 1.75）。

处理：
- 使用 rustup 安装 stable 最新版后重新编译

### 问题 3：`Read-only file system` 写入 `~/.cargo` 或 `~/.profile` 失败

原因：HOME 目录或 shell profile 不可写。

处理：
- 使用项目内路径承载 Rust 环境：`.cargo-home`、`.rustup-home`
- rustup 安装时加 `--no-modify-path`
- 每次会话手动 `export` 相关环境变量

## 最小可复用命令集

```bash
cd /home/ubuntu/OpenixCLI
sudo apt-get update
sudo apt-get install -y cargo rustc libusb-1.0-0-dev pkg-config curl
export CARGO_HOME=$PWD/.cargo-home RUSTUP_HOME=$PWD/.rustup-home RUSTUP_INIT_SKIP_PATH_CHECK=yes
curl https://sh.rustup.rs -sSf | sh -s -- -y --default-toolchain stable --no-modify-path
export PATH=$PWD/.cargo-home/bin:$PATH CARGO_TARGET_DIR=$PWD/target
cargo build --release
./target/release/openixcli --help
```

