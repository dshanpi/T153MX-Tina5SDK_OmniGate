# T153 OmniGate MIPI DSI 4-Lane 屏调试记录

## 目标

在 T153 OmniGate 板上点亮一款 MIPI DSI 4-lane 1024x768 RGB888 屏。
参考屏参来源：
- RK3576 平台 dtsi: <https://github.com/dshanpi/DshanPi-A1_CM5-BuildrootSDK/blob/master/overlay/kernel-6.1/arch/arm64/boot/dts/rockchip/rk3576-100ask-1024-768-mipi.dtsi>
- A133 平台 sys_config.fex 风格 lcd0 节点（用户提供）

## 硬件信号确认

| 信号 | T153 引脚 | 说明 |
|---|---|---|
| DSI 4-lane 数据/时钟 | PD0-PD9 | sun8iw22p1.dtsi 的 `dsi0_4lane_pins_a` 包含 PD0-PD9+PD17/18/19/21，但 PD17/18/19/21 无 dsi function，只用 PD0-PD9 |
| PWM 背光 | PD22 | = `pwm2` 控制器的 channel 6（`pwm2_6`），25ms 周期 |
| LCD_RESET | PD23 | 低有效（GPIO_ACTIVE_LOW） |
| BL_EN | 不接 | 纯 PWM 调光，背光 IC 常使能 |

## 修改文件清单

### 1. overlay 设备树（git 仓库内）

**`overlay/device/config/chips/t153/configs/omnigate/linux-5.10-origin/board.dts`**（+212 行）

新增内容：
- 根节点下 `backlight0` 节点（pwm-backlight，pwms = `<&pwm2 6 25000 0>`）
- 根节点下 `panel_0` 节点（allwinner,panel-dsi，4-lane RGB888，含完整 panel-init-sequence 从 RK 参考 dtsi 直接复用）
- `&pio` 下新增 `pwm2_6_pins_active/sleep`（PD22 pinmux）
- `&pio` 下新增 `dsi0_4lane_pins_a_fix/b_fix`（只用 PD0-PD9，function="dsi"，绕过 dtsi 的 bug）
- `&pwm2 { status = "okay"; };`（父节点 enable）
- `&pwm2_6` 配置（pinctrl-names = "active","sleep"，status okay）
- `&dsi0` 配置（status okay，pinctrl-0 = <&dsi0_4lane_pins_a_fix>，含 virtual-panel 路由）
- `&dlcd0 { status = "okay"; };`
- `&dsi0combophy { status = "okay"; };`
- `&lvds0 { status = "disabled"; };`（避免 lvds bind 失败拖垮整个 drm）

当前 timing 配置（RK 参考）：
- clock-frequency = 50000000（50MHz）
- hactive=1024, vactive=768
- hfront-porch=10, hsync-len=5, hback-porch=20
- vfront-porch=5, vsync-len=5, vback-porch=10
- dsi,flags = (MIPI_DSI_MODE_VIDEO)（NON-BURST SYNC PULSES）
- dsi,lanes = 4, dsi,format = 0 (RGB888)

### 2. SDK 驱动代码（git 仓库外，需手动同步）

**`bsp/drivers/drm/panel/panel-dsi.c`** - 加调试日志（保留）
- `panel_dsi_prepare` 开头加 `dev_info("panel_dsi_prepare start")`
- `panel_dsi_cmd_seq` 循环里加 `printk(KERN_INFO "DSI_CMD[%d/%d] ...")` 打印每条命令的 data_type/delay/len/payload[0] 和发送结果

**`bsp/drivers/drm/sunxi_device/hardware/lowlevel_lcd/dsi_v1.c`** - DSI H timing 公式修复（NON-BURST 分支）

原始代码：
```c
dsi_hbp = hbp * dsi_pixel_bits[format] / 8 - 10;
dsi_hblk = (ht - hspw) * dsi_pixel_bits[format] / 8 - 10;
dsi_hfp = (ht - hbp - hspw - x) * 3 - 6 - 6;
```

修改后（对齐全志官方 LCD timing 计算器 https://docs.aw-ol.com/docs/tools/lcd_timing_calculator）：
```c
dsi_hact = x * dsi_pixel_bits[format] / 8;
dsi_hbp = hbp * dsi_pixel_bits[format] / 8 - 6;              /* 原 -10，官方工具 -6 */
dsi_hblk = (ht - hspw) * dsi_pixel_bits[format] / 8 - 10;
dsi_hfp = dsi_hblk - (4 + dsi_hact + 2) - (4 + dsi_hbp + 2); /* 官方工具公式 */
dsi->reg->dsi_basic_ctl.bits.hsa_hse_dis = 0;                /* 显式 SYNC PULSES */
dsi->reg->dsi_basic_ctl.bits.hbp_dis = 0;                    /* 启用 HBP */
```

## 调试过程（按时间顺序）

### 阶段 1：基础配置 + pinctrl 修复

1. 参照 `device/config/chips/t153/configs/demo_nand/linux-5.10-origin/board.dts` 的 panel_0/backlight0/&dsi0 范例，在 omnigate board.dts 添加完整 DSI 配置
2. 第一次烧录：dmesg 报 `unsupported function dsi0 on pin PD0` - 发现 sun8iw22p1.dtsi 的 `dsi0_4lane_pins_a` 用 `function="dsi0"`，但 pinctrl 驱动注册的是 `"dsi"`；且 PD17/18/19/21 没有 dsi function
3. 修复：在 board.dts 新增 `dsi0_4lane_pins_a_fix/b_fix`，只用 PD0-PD9，function="dsi"
4. dmesg 还报 lvds0 bind 失败（`Failed to find panel or bridge: -19`）拖垮整个 drm - 修复：`&lvds0 { status = "disabled"; };`

### 阶段 2：PWM 背光修复

5. 背光不亮，dmesg 报 `pinctrl_lookup_state(active) failed` - 发现 `&pwm2_6` 的 `pinctrl-names` 写成 `"default","sleep"`，但 sunxi PWM 驱动查找 `"active"`
6. 修复：pinctrl-names 改成 `"active","sleep"`，并加 `&pwm2 { status = "okay"; };`（父节点也要 enable）

### 阶段 3：reset 极性修复

7. 背光亮但白屏 - 看 panel-dsi.c 代码发现 `reset-on-sequence` 的 level 是 gpiod_set_value 的**逻辑值**：ACTIVE_LOW 下 level=1 = assert reset，level=0 = release reset
8. 原配置 `<0 10>,<1 100>` = release 10ms -> assert 100ms（panel 一直 reset）- 修复：改成 `<1 10>,<0 100>` = assert 10ms -> release 100ms

### 阶段 4：DSI 命令发送验证

9. 加调试日志到 panel-dsi.c，确认 `panel_dsi_prepare` 被调用，32 条 init sequence 命令全部发送成功（DSI_CMD[1-32] OK，含 sleep out 0x11 + display on 0x29）
10. `sunxi_drm_bind ok`，`/dev/fb0` 存在，`card0-DSI-1 enabled` - 软件层面全部就绪

### 阶段 5：条纹问题调试（未解决）

11. 屏幕显示**水平细条纹**（纯色也有），说明 panel 锁定同步但行数据错位
12. 尝试去掉 `MIPI_DSI_MODE_NO_EOT_PACKET` - 条纹不变
13. 尝试去掉 `MIPI_DSI_MODE_VIDEO_BURST`（用 NON-BURST）- 条纹不变
14. 尝试提高 pixel clock 到 70MHz（lane rate 420Mbps 接近 RK 的 480Mbps）- 一半黑屏一半黑白条纹闪烁（panel 失锁）
15. 尝试增大 HBP(40)/HFP(20) - 无显示（panel 无法锁定）
16. 用户提供 A133 参考：lcd_dclk_freq=24MHz, lcd_ht=1050, lcd_hbp=16, lcd_hspw=5, lcd_vt=796, lcd_vbp=22, lcd_vspw=2, lcd_dsi_if=0
17. 尝试 A133 timing + 24MHz - 白屏 + 右边竖条纹闪烁（帧率 28.7Hz 太低）
18. 尝试 A133 timing + 50MHz - 4 个区域（2x2 分割，左白右黑）
19. 尝试 A133 timing + 50MHz + BURST - 雪花点花屏
20. 查全志官方 LCD timing 计算器，发现驱动 dsi_hbp 常数 -10 应为 -6，dsi_hfp 公式不同 - 修改 dsi_v1.c - 条纹不变
21. 在 NON-BURST 分支显式设置 `hsa_hse_dis=0`（SYNC PULSES）- 条纹不变

## 当前状态

- ✅ 背光正常（PWM 调光工作）
- ✅ DSI panel init sequence 32 条命令全部发送成功
- ✅ DRM bind 成功，`/dev/fb0` 存在，`card0-DSI-1 enabled`
- ✅ 屏幕能显示颜色（写 fb0 能看到颜色变化）
- ❌ **水平细条纹未消除**（纯色也有，说明是 DSI 同步/timing 问题，非数据问题）

## 未解决问题的可能原因

1. **T153 DSI PHY 信号完整性问题**（硬件）- T153 的 DSI PHY 跟 A133/RK 不同，HS 信号质量可能不满足 panel 要求，需要示波器测量 DSI HS clock 和 data lane 信号
2. **DSI lane mapping 不匹配** - T153 的 PD0-PD9 到 lane0-3+CLK 的映射可能跟 panel 期望不同（SoC 硬件固定，无法软件配置）
3. **DSI PHY 时序参数** - `bsp/drivers/drm/phy/sunxi_dsi_combophy.c` 的 hs_trail_set/hs_pre_set/lpx_tm_set 可能需要针对此 panel 调整
4. **fb0 stride 跟 DSI HACT 不匹配** - fb0 是 32bpp（stride 4096），DSI 是 RGB888（HACT 3072），DRM 转换可能有微小问题

## 下一步建议

1. **用示波器测量 DSI 信号** - 确认 HS clock 频率、data lane 信号质量、lane 时序
2. **对比 A133 实际工作的 DSI 寄存器配置** - 在 A133 板上 dump DSI 控制器寄存器，跟 T153 对比
3. **调整 PHY 参数** - 尝试增大 hs_trail_set，或调整 hs_pre_set
4. **检查 DSI lane 顺序** - 确认 T153 PD0-PD9 的 lane mapping 跟 panel 一致

## 串口/烧录操作备忘

- 串口 agent: `sudo python3 tools/serial_agent/serial_agent_daemon.py --port /dev/ttyACM0 --baudrate 115200 --tcp-port 23334`
- 查看串口: `nc 127.0.0.1 23334`
- 进 FEL: 系统执行 `reboot efex`（或串口发 `reboot efex`），USB 断开后需重新插拔 OTG 线
- 烧录: `sudo tools/OpenixCLI/openixcli flash -m partition -p boot-resource,env,env-redund,bootA,bootB,dtbo,dtbo-r,rootfsA,rootfsB,private,rootfs_data out/t153_linux_omnigate_uart0.img`
- 编译: `source build/envsetup.sh && ./build.sh kernel && ./build.sh pack`

## 相关 memory 记录

- `t153-dsi0-4lane-pinctrl-bug` - dtsi dsi0_4lane_pins_a 的 function 名字错 + 包含不支持的 pin
- `t153-lvds0-disable-for-dsi` - 配 DSI 屏必须 disable lvds0
- `t153-reboot-efex-fel` - 进 FEL 烧录模式命令
