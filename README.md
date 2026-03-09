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
