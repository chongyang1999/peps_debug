# UB板通信协议解析器开发日志

## 项目目标

实现一个智能的UART-over-TCP透明代理系统：
- **上行**：UB板 → UART数据 → 解析分包 → TCP网络 → 远端服务器
- **下行**：远端服务器 → TCP网络 → UART命令 → UB板
- **核心**：智能分包，识别事件边界，过滤无意义数据

## 协议分析要点

### 通信架构
- UB板通过RS-232连接到Radio端口
- 物理连接：DB-9接口，只使用RX/TX线（2↔3交叉）
- UART参数：38400 bps、8数据位、无校验、1起始+1停止位
- **关键**：无硬件流控制（RTS/CTS/DTR/DSR都禁用）

### 协议帧格式
```
PREAMBLE (9字节) + LENGTH (1字节) + TYPE (1字节) + DATA (可变) + CRC32 (4字节) + ETX (1字节)
```

- **PREAMBLE**：`  !LS2SU!` (UB→Radio)、`  !SU2LS!` (Radio→UB)
- **LENGTH**：后续字段总长度（TYPE+DATA+CRC+ETX）
- **TYPE**：消息类型（D=数据，N=网络状态，等）
- **ETX**：结束标志 `0xFF`

### 数据发送条件
**关键发现**：UB仅在收到`SU_NETWORK_STATUS=2`且GPS可用时，才开始发送数据

## 开发过程记录

### 第一阶段：环境搭建
1. **硬件连接**：USB转UART电缆连接PC和UB板Radio口
2. **初步测试**：Putty能收到`!LS2SU!N`后跟不可见字符
3. **问题确认**：需要解析完整的协议帧结构

### 第二阶段：协议解析器实现
#### 关键技术问题及解决方案

**问题1：串口参数设置**
```python
# 解决方案：禁用所有流控制
serial.Serial(
    port='COM13',
    baudrate=38400,
    bytesize=8,
    parity=serial.PARITY_NONE,
    stopbits=1,
    rtscts=False,      # 禁用RTS/CTS
    dsrdtr=False,      # 禁用DSR/DTR  
    xonxoff=False      # 禁用软件流控制
)
```

**问题2：PREAMBLE长度误判**
- 初始错误：认为PREAMBLE是8字节
- 实际数据分析：`2020214c5332535521064e86e7d9eeff`
- 正确解析：PREAMBLE是9字节（`  !LS2SU!`）

**问题3：分段数据接收**
- 数据可能分多次到达：先收到`b'  '`，后收到`b'!LS2SU!...'`
- 解决方案：实现智能缓冲区管理，保留部分PREAMBLE

**问题4：数据类型转换**
- 错误：`bytearray`无法作为字典键
- 解决方案：使用`bytes()`转换

### 第三阶段：成功解析首个数据包
**实际收到的网络状态包**：
```
原始数据: 2020214c5332535521064e86e7d9eeff
解析结果:
- PREAMBLE: "  !LS2SU!" (9字节)
- LENGTH: 0x06 = 6
- TYPE: 'N' (网络状态)
- DATA: 无 (长度0)
- CRC: 86e7d9ee
- ETX: 0xFF
```

## 当前实现状态

### 已完成功能
1. ✅ 串口连接和配置
2. ✅ 协议帧完整解析
3. ✅ 分段数据处理
4. ✅ 有意义包类型过滤
5. ✅ 数据包保存（二进制+可读信息）
6. ✅ 详细调试日志

### 核心代码结构
```python
class ProtocolParser:
    def __init__(self):
        # 协议常量定义
        self.PREAMBLES = {
            b'  !LS2SU!': 'UB_TO_RADIO',
            b'  !SU2LS!': 'RADIO_TO_UB'
        }
        self.MEANINGFUL_TYPES = {
            b'D': 'DATA', b'N': 'NETWORK', ...
        }
    
    def parse_frame(self, data, start_pos):
        # 完整的协议帧解析逻辑
        
    def run(self):
        # 主循环：接收、解析、保存
```

## 下一步开发计划

### 优先级1：主动触发数据发送
**目标**：让UB板按需发送数据包，加速调试
**方案**：
1. 实现发送功能（模拟Radio）
2. 发送`SU_NETWORK_STATUS=2`让UB认为网络已连接
3. 测试查询命令：版本查询(V)、GPS状态(G)、Station ID(U)

### 优先级2：完善协议支持
1. 添加更多消息类型支持
2. 实现数据包分片重组机制
3. 可选的CRC32校验验证

### 优先级3：智能分包逻辑
1. 定义"完整事件"的边界识别
2. 过滤重复心跳和状态查询
3. 实现事件序列的批量打包

### 优先级4：网络代理实现
1. 设计TCP包格式
2. 实现双向透明代理
3. 多线程架构（接收/发送/网络）

## 技术难点和解决思路

### 发送接收并行处理
**架构选择**：
- 调试阶段：交互式单线程（按键触发发送）
- 生产阶段：多线程（接收线程+发送线程+网络线程）

### 事件边界识别
**待解决**：如何判断一个完整的"事件"结束
- 需要收到真实的TYPE=D数据包进行分析
- 可能需要基于时间窗口+消息类型的组合逻辑

### CRC校验
**当前状态**：记录但不验证
**原因**：不确定具体的CRC算法和字节序
**计划**：收集足够数据后实验验证

## 文件结构
```
peps/
├── protocol.md              # 协议文档（中文总结）
├── protocol_parser.py       # 主程序
├── development_log.md       # 本文档
├── packet_YYYYMMDD_HHMMSS.bin  # 保存的数据包
└── packet_YYYYMMDD_HHMMSS.txt  # 可读的包信息
```

## 经验总结

### 串口调试技巧
1. 先用Putty确认硬件连接正常
2. 添加详细的原始数据打印（十六进制+ASCII）
3. 分段接收是常态，需要缓冲区管理
4. 流控制设置对通信成功至关重要

### 协议解析要点
1. 严格按照文档定义解析每个字段
2. 注意字节序和数据类型转换
3. 预留调试信息便于问题定位
4. 分步验证：先解析再功能扩展

### 开发方法论
1. 最小可行版本优先
2. 实际数据驱动的调试方式
3. 保持代码结构清晰，便于扩展
4. 详细记录问题和解决方案

---

## 补充实测结论（后续整理补记）

### 实际硬件链路说明
- 之前文档里写的“PC 直接连接 UB Radio 口”，实际调试链路并不是 PC 直接接 RS-232 裸线。
- 实际可工作的链路是：**PC -> MM232R USB-UART -> MAX3232 电平转换 -> UB Radio RS-232 口**。
- 后续引入 ESP32 时，本质上是用 **ESP32 + MAX3232** 去替换原来 PC 侧的 **MM232R + MAX3232** 串口适配路径，而不是改变 UB 侧协议。
- 这一点与 `archive/uart_tcp_proxy/TEST_NOTES.md` 中的记录一致：`RS-232 via MAX3232/MM232R, 38400 8N1`。

### 空闲状态周期包
- 历史抓包样本显示，UB 在空闲/启动后会周期性发出 `TYPE='N'` 的网络状态包。
- 已保存的样本时间点分别为：
  - `2025-07-08 14:54:19`
  - `2025-07-08 15:04:19`
  - `2025-07-08 15:14:20`
  - `2025-07-08 15:24:20`
- 因此当前可认为：**默认 idle/周期性 `N` 包的发送周期约为 10 分钟**。
- 该结论来自实测抓包，不是协议文档中明确写死的配置项；后续若抓到更多样本，应继续校正。

### ESP32 串口协议脚本当前状态
- 当前主线脚本为 `esp32_bridge/ubradio_decode.py`。
- 该脚本已经整理为“协议核心 + REPL 可调用接口”的形式，保留了原有协议实现：
  - `calculate_crc()`
  - `pack_frame()`
  - `parse_frame()`
- 在此基础上新增并验证了以下接口：
  - `send_command(cmd, payload=b"")`
  - `q(cmd, payload=b"")`
  - `poll_uart_once()`
  - `read_frames(timeout_ms=...)`
  - `get_logs()`
  - `clear_logs()`
- 当前接收侧已是“非阻塞轮询”模式：
  - `poll_uart_once()` 无数据时立即返回
  - 有数据时读取 UART、解析完整帧并写入 `logs`
  - 这为后续网页轮询提供了直接复用点

### 当前 REPL 实测结果
- `send_command("V") + read_frames(1000)` 已验证成功：
  - 发送 `TYPE='V'`
  - 收到 `TYPE='v'`
  - 返回内容：`V02.01`
- `q("G") + rx_loop()` 已验证成功：
  - 收到 `TYPE='g'`
  - 数据 `00`
  - 当前解释为 GPS invalid
- `q("E", b"PING") + rx_loop()` 已验证成功：
  - 收到 `TYPE='e'`
  - 当前固件行为是仅回 ACK，不回显 payload

### 当前日志结构
- `get_logs()` 现已返回结构化日志项，字段包括：
  - `dir`
  - `type`
  - `raw_hex`
  - `length`
  - `data_hex`
  - `data_ascii`
  - `recv_crc`
  - `calc_crc`
  - `crc_ok`
- 这些字段已经足够支撑第一版网页日志展示；后续只需补充 `ts` 时间戳即可。

### CircuitPython 兼容性补记
- 在 ESP32 / CircuitPython 上，`bytearray` 的切片删除能力与桌面 Python 不完全一致。
- 曾在重构 `poll_uart_once()` 时使用 `del rx_buffer[:]`，在板子上触发：
  - `TypeError: 'bytearray' object doesn't support item deletion`
- 当前已改为直接重建缓冲区：
  - `rx_buffer = bytearray(remaining)`
- 结论：后续写 CircuitPython 代码时，应优先使用“整体重建对象”的方式，而不是依赖 CPython 风格的原地切片删除。

### 第一版网页方案边界
- 第一版网页方案不重写串口协议栈，也不在网页端重复实现 CRC/解包。
- 设计原则是：
  - ESP32 继续使用 `ubradio_decode.py` 作为协议与 UART 核心
  - 网页层只调用已有接口发送命令、轮询日志并展示结果
- 第一版网页仅实现固定调试功能：
  - 固定命令按钮：`V/G/P/M/E/U`
  - 自动刷新日志
  - 显示 TX/RX、原始 hex、CRC、解析内容
- 第一版允许使用“PC/网页端高频轮询”来近似持续采集：
  - 只要网页持续访问，效果上接近后台采集
  - 暂不要求 ESP32 在无人访问时也持续常驻采集
- 若后续确有需要，再增加常驻后台轮询与更完整的服务模式。

*最后更新：2025-07-10*
