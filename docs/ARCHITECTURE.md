# 串口通信GUI程序 - 架构设计文档

## 整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                          用户界面层 (GUI Layer)                      │
│                                                                     │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐      │
│  │  串口配置区     │  │  命令按钮区     │  │  数据显示区     │      │
│  │  - 端口选择     │  │  - 12个按钮     │  │  - 彩色文本     │      │
│  │  - 波特率设置   │  │  - 可配置       │  │  - 自动滚动     │      │
│  │  - 连接/断开    │  │  - 点击发送     │  │  - 实时更新     │      │
│  └────────────────┘  └────────────────┘  └────────────────┘      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 │ tkinter GUI主循环
                                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│                       业务逻辑层 (Business Logic)                    │
│                                                                     │
│  ┌──────────────────────────────────────────────────────┐         │
│  │           RadioGUI / RadioGUIAdvanced                │         │
│  │                                                      │         │
│  │  [主线程]                        [监听线程]          │         │
│  │    │                                │                │         │
│  │    │ 按钮点击                        │ 串口读取       │         │
│  │    ↓                                ↓                │         │
│  │  send_xxx()                    listen_worker()       │         │
│  │    │                                │                │         │
│  │    │                                │ 数据接收        │         │
│  │    │                                ↓                │         │
│  │    │                          process_buffer()       │         │
│  │    │                                │                │         │
│  │    │                                │ msg_queue.put()│         │
│  │    │                                ↓                │         │
│  │    │         ┌──────────────────────────┐           │         │
│  │    │         │   queue.Queue (线程安全) │           │         │
│  │    │         └──────────────────────────┘           │         │
│  │    │                     ↑                           │         │
│  │    │                     │ msg_queue.get()          │         │
│  │    ↓                     ↓                           │         │
│  │  process_queue() → append_text()                    │         │
│  │         │                                            │         │
│  │         └─→ GUI更新 (每100ms定时检查)                │         │
│  │                                                      │         │
│  └──────────────────────────────────────────────────────┘         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ↓                         ↓
┌──────────────────────────────┐  ┌──────────────────────────────┐
│   串口发送模块 (Sender)       │  │   串口接收模块 (Receiver)     │
│                              │  │                              │
│  RadioSimulator              │  │  ProtocolParser              │
│  - build_frame()             │  │  - find_preamble()           │
│  - calculate_crc32()         │  │  - parse_frame()             │
│  - send_status()             │  │  - PREAMBLES定义             │
│  - send_version_request()    │  │  - MEANINGFUL_TYPES定义      │
│  - send_gps_xxx()            │  │  - 缓冲区管理                │
│  - send_init_sequence()      │  │  - 数据包提取                │
│  - ...                       │  │  - CRC校验                   │
│                              │  │                              │
└──────────────────────────────┘  └──────────────────────────────┘
                    │                         │
                    └────────────┬────────────┘
                                 ↓
                    ┌────────────────────────────┐
                    │   串口层 (Serial Layer)     │
                    │                            │
                    │   serial.Serial            │
                    │   - port: COM13            │
                    │   - baudrate: 38400        │
                    │   - read() / write()       │
                    │                            │
                    └────────────────────────────┘
                                 │
                                 ↓
                    ┌────────────────────────────┐
                    │   外部设备 (UB/Radio)       │
                    └────────────────────────────┘
```

## 线程交互时序图

### 发送命令流程

```
用户          主线程           RadioSimulator    串口        外部设备
 │               │                    │            │            │
 │ 点击按钮       │                    │            │            │
 ├──────────────>│                    │            │            │
 │               │ send_xxx()         │            │            │
 │               ├───────────────────>│            │            │
 │               │                    │ build_frame()           │
 │               │                    ├───┐        │            │
 │               │                    │<──┘        │            │
 │               │                    │ write()    │            │
 │               │                    ├───────────>│            │
 │               │                    │            │ 串口数据     │
 │               │                    │            ├───────────>│
 │               │ append_text()      │            │            │
 │               │<───────────────────┤            │            │
 │               │ 更新GUI            │            │            │
 │               ├───┐                │            │            │
 │ 显示发送日志   │<──┘                │            │            │
 │<──────────────┤                    │            │            │
 │               │                    │            │            │
```

### 接收数据流程

```
外部设备      串口         监听线程        Queue       主线程         GUI
 │            │              │             │           │             │
 │ 发送数据    │              │             │           │             │
 ├───────────>│              │             │           │             │
 │            │ in_waiting>0 │             │           │             │
 │            ├─────────────>│             │           │             │
 │            │ read()       │             │           │             │
 │            ├─────────────>│             │           │             │
 │            │ 原始数据      │             │           │             │
 │            │<─────────────┤             │           │             │
 │            │              │ 添加到buffer │           │             │
 │            │              ├───┐         │           │             │
 │            │              │<──┘         │           │             │
 │            │              │ find_preamble()         │             │
 │            │              ├───┐         │           │             │
 │            │              │<──┘         │           │             │
 │            │              │ parse_frame()           │             │
 │            │              ├───┐         │           │             │
 │            │              │<──┘         │           │             │
 │            │              │ msg_queue.put()         │             │
 │            │              ├────────────>│           │             │
 │            │              │             │           │             │
 │            │              │             │ 定时器触发 │             │
 │            │              │             │ (100ms)   │             │
 │            │              │             │<──────────┤             │
 │            │              │             │ get()     │             │
 │            │              │             ├──────────>│             │
 │            │              │             │ 消息数据   │             │
 │            │              │             │<──────────┤             │
 │            │              │             │           │ append_text()
 │            │              │             │           ├────────────>│
 │            │              │             │           │             │ 显示
 │            │              │             │           │             ├──┐
 │            │              │             │           │             │<─┘
 │            │              │             │           │             │
```

## 核心类设计

### 1. RadioGUI / RadioGUIAdvanced

**职责**: GUI主控制器

```python
class RadioGUI:
    # 属性
    - root: tkinter根窗口
    - ser: 串口对象
    - simulator: RadioSimulator实例（发送）
    - parser: ProtocolParser实例（接收）
    - running: 线程运行标志
    - listen_thread: 监听线程对象
    - msg_queue: 消息队列（线程间通信）
    - text_display: 文本显示组件

    # 方法
    + __init__(root)
    + create_widgets()           # 创建GUI组件
    + connect_serial()            # 连接串口
    + disconnect_serial()         # 断开串口
    + listen_worker()             # 监听线程工作函数
    + process_buffer()            # 处理接收缓冲区
    + process_queue()             # 处理消息队列
    + append_text(text, tag)     # 追加文本（线程安全）
    + send_xxx()                  # 各种发送命令方法
```

### 2. RadioSimulator (复用)

**职责**: 串口数据发送

```python
class RadioSimulator:
    # 属性
    - ser: 串口对象
    - port: 端口号
    - baudrate: 波特率

    # 方法
    + build_frame(preamble, msg_type, data)  # 构建帧
    + calculate_crc32(data)                   # 计算CRC
    + send_status(reset_source)               # 发送状态
    + send_version_request()                  # 查询版本
    + send_gps_status_request()               # 查询GPS
    + send_init_sequence()                    # 初始化序列
    + ... (其他发送方法)
```

### 3. ProtocolParser (复用)

**职责**: 串口数据接收和解析

```python
class ProtocolParser:
    # 属性
    - ser: 串口对象
    - buffer: 接收缓冲区
    - PREAMBLES: 协议头字典
    - MEANINGFUL_TYPES: 有意义的消息类型

    # 方法
    + find_preamble(data)          # 查找协议头
    + parse_frame(data, start_pos) # 解析帧
    + save_packet(packet_info)     # 保存数据包
```

## 线程安全机制

### 问题

tkinter不是线程安全的，GUI更新必须在主线程中执行。

### 解决方案

使用**生产者-消费者模式** + **Queue**：

```python
# 生产者：监听线程
def listen_worker(self):
    while self.running:
        data = self.ser.read(...)
        # 不直接更新GUI！
        self.msg_queue.put(("log", "数据内容", "info"))  # 放入队列

# 消费者：主线程定时器
def process_queue(self):
    try:
        msg_type, content, tag = self.msg_queue.get_nowait()  # 非阻塞
        # 安全地更新GUI
        self.append_text(content, tag)
    except queue.Empty:
        pass
    # 定时检查（100ms后再次调用）
    self.root.after(100, self.process_queue)
```

### 为什么安全？

1. **Queue内部使用锁**: Python的`queue.Queue`是线程安全的
2. **数据隔离**: 两个线程不直接共享GUI对象
3. **单线程更新**: 所有GUI更新都在主线程中执行
4. **非阻塞**: `get_nowait()`不会阻塞主线程

## 数据流向

### 发送路径

```
用户点击 → GUI按钮 → send_xxx() → RadioSimulator.send_xxx()
→ build_frame() → calculate_crc32() → serial.write()
→ 串口 → 外部设备
```

### 接收路径

```
外部设备 → 串口 → serial.read() → 监听线程 → buffer.extend()
→ ProtocolParser.find_preamble() → ProtocolParser.parse_frame()
→ msg_queue.put() → Queue → msg_queue.get() → 主线程
→ append_text() → GUI更新
```

## 配置驱动设计（高级版）

### 配置文件结构

```json
{
  "commands": [
    {
      "id": "unique_id",          // 唯一标识
      "name": "按钮显示文本",       // GUI显示
      "method": "方法名",          // 对应的方法
      "description": "工具提示",   // 鼠标悬停显示
      "confirm": false            // 是否需要确认
    }
  ]
}
```

### 动态加载流程

```python
# 1. 读取JSON文件
with open('commands_config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

# 2. 解析命令列表
self.commands = config['commands']

# 3. 动态创建按钮
for cmd in self.commands:
    btn = ttk.Button(
        frame,
        text=cmd['name'],
        command=lambda c=cmd: self.execute_command(c)
    )
    btn.grid(...)

# 4. 执行命令
def execute_command(self, command):
    method = getattr(self, command['method'])
    method()
```

## 模块依赖关系

```
radio_gui.py / radio_gui_advanced.py
    │
    ├──> tkinter (GUI框架)
    ├──> queue (线程安全队列)
    ├──> threading (多线程)
    ├──> serial (串口通信)
    ├──> protocol_parser.py (协议解析)
    └──> radio_simulator.py (数据发送)
            │
            └──> protocol_parser.py (协议定义)
```

## 性能考虑

### 1. 队列处理频率

- **默认**: 100ms检查一次
- **高频场景**: 可缩短到50ms
- **批量处理**: 一次处理多条消息

### 2. 文本框限制

```python
# 防止文本框过大
if line_count > 1000:
    self.text_display.delete('1.0', '100.0')  # 删除前100行
```

### 3. 缓冲区管理

```python
# 防止缓冲区无限增长
if len(self.parser.buffer) > 1000:
    self.parser.buffer = self.parser.buffer[1:]
```

## 错误处理

### 串口错误

```python
try:
    self.ser = serial.Serial(...)
except serial.SerialException as e:
    messagebox.showerror("错误", f"无法打开串口: {e}")
```

### 线程错误

```python
def listen_worker(self):
    try:
        while self.running:
            # 监听逻辑
            ...
    except Exception as e:
        if self.running:  # 只在非主动断开时报错
            self.msg_queue.put(("log", f"监听异常: {e}", "error"))
```

### GUI错误

```python
def send_xxx(self):
    if not self.check_connection():
        return
    try:
        self.simulator.send_xxx()
    except Exception as e:
        self.append_text(f"发送失败: {e}", "error")
```

## 扩展指南

### 添加新命令

1. **在RadioSimulator中添加发送方法**:
```python
def send_new_command(self):
    frame = self.build_frame("  !SU2LS!", b'N', b'data')
    self.ser.write(frame)
```

2. **在GUI中添加对应方法**:
```python
def send_new_command(self):
    if not self.check_connection():
        return
    try:
        self.simulator.send_new_command()
        self.append_text("[发送] > NEW_COMMAND", "warning")
    except Exception as e:
        self.append_text(f"[错误] {e}", "error")
```

3. **更新配置文件（高级版）**:
```json
{
  "id": "new_cmd",
  "name": "新命令",
  "method": "send_new_command",
  "description": "这是新命令",
  "confirm": false
}
```

### 添加新消息类型

在`protocol_parser.py`中：
```python
self.MEANINGFUL_TYPES = {
    b'N': 'NEW_TYPE',  # 新增
    # ... 其他类型
}
```

GUI会自动识别并显示。

## 总结

这个架构设计的核心优势：

1. **清晰的分层**: GUI层、业务逻辑层、串口层
2. **线程安全**: Queue桥接，单线程更新GUI
3. **代码复用**: 完全复用现有模块
4. **易于扩展**: 配置驱动，方法映射
5. **健壮性**: 完善的错误处理
6. **可维护性**: 清晰的模块划分

这是一个**生产级别**的设计，可以直接用于实际项目。
