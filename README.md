# PEPS Workspace

这个仓库现在按两条主线整理：

- `pc_direct/`
  PC 直接连接 UB 的工具与调试脚本。包括 `radio_gui.py`、`radio_gui_advanced.py`、`protocol_parser.py`、`radio_simulator.py`、`ppp_gui.py`、`simple_ppp_client.py`。
- `esp32_bridge/`
  PC -> ESP32 -> UB 方向的 CircuitPython 实验代码。这是后续更重要的开发方向。

辅助内容：

- `docs/`
  协议说明、开发日志、GUI 文档、`comms_protocol.pdf`、`softtestub.pdf`。
- `samples/radio_packets/`
  历史抓包样本 `packet_*.bin/.txt`。
- `archive/uart_tcp_proxy/`
  从 `peps` 仓库并入的旧 UART-TCP 原型与草稿代码，暂时归档，不作为当前主线。

常用启动方式：

```bash
python pc_direct/radio_gui.py
python pc_direct/radio_gui_advanced.py
python pc_direct/ppp_gui.py
```

当前建议：

- 日常调试 `radio` 口时使用 `pc_direct/`。
- 新开发优先放在 `esp32_bridge/`，围绕 PC -> ESP32 -> UB 这条链路推进。

## ESP32 当前状态

- 当前已经验证 `esp32_bridge/ubradio_decode.py` 可在 CircuitPython REPL 下完成：
  - 发送命令帧 `send_command("V")`
  - 非阻塞轮询接收 `read_frames(...)`
  - 获取结构化日志 `get_logs()`
- 已确认的实测结果：
  - `V -> v`，返回版本字符串 `V02.01`
  - `G -> g`，当前实测返回 `00`，表示 GPS 无效
  - `E -> e`，当前固件仅返回 ACK，不回显 payload
- 当前 `logs` 已包含网页展示所需的大部分字段：
  - `dir`、`type`、`raw_hex`、`data_hex`、`data_ascii`
  - `recv_crc`、`calc_crc`、`crc_ok`、`length`

## 第一版网页方案

- 第一版目标不是重写协议栈，而是在 `esp32_bridge/ubradio_decode.py` 现有接口外包一层极简网页。
- ESP32 端保留现有协议/串口逻辑，只补少量展示需要的信息，例如时间戳。
- 网页端只做固定功能：
  - 固定命令按钮，例如 `V/G/P/M/E/U`
  - 手动刷新日志
  - 显示 TX/RX、原始 hex、解析结果和 CRC
- 第一版网页已切换到 `adafruit_httpserver`，不再使用手写 socket HTTP 服务器。
- 当前网页实测已经验证：
  - `Version` 可返回 `V02.01`
  - `GPS Status` 可返回 `00`
  - 页面可显示带时间戳的 TX/RX 文本日志
- 第一版保持“纯手动调试页”定位，不在页面内做自动轮询；若要近似持续采集，应由 PC 侧单独脚本定时访问接口。
