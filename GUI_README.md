# 串口通信可视化GUI程序 - 使用说明

## 文件清单

1. **radio_gui.py** - 基础版GUI程序（内置命令按钮）
2. **radio_gui_advanced.py** - 高级版GUI程序（支持配置文件加载）
3. **commands_config.json** - 命令配置文件示例
4. **protocol_parser.py** - 协议解析器（已有）
5. **radio_simulator.py** - 串口发送模拟器（已有）

## 架构设计

### 1. 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    主线程 (GUI)                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │  tkinter事件循环                                  │  │
│  │  - 按钮点击处理                                   │  │
│  │  - 文本显示更新                                   │  │
│  │  - 队列消息处理 (每100ms)                        │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                         ↑ ↓
                    Queue (线程安全)
                         ↑ ↓
┌─────────────────────────────────────────────────────────┐
│                 监听线程 (Background)                     │
│  ┌──────────────────────────────────────────────────┐  │
│  │  持续监听串口数据                                 │  │
│  │  - 读取串口数据                                   │  │
│  │  - 协议解析 (ProtocolParser)                     │  │
│  │  - 将结果放入Queue                               │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                         ↑ ↓
                   Serial Port (COM13)
                         ↑ ↓
                    外部设备 (UB/Radio)
```

### 2. 线程安全设计

**问题**: tkinter的GUI更新必须在主线程中执行，但串口监听需要在后台线程中持续运行。

**解决方案**:
- 使用 `queue.Queue` 作为线程间通信桥梁
- 监听线程将接收到的数据放入队列：`msg_queue.put((msg_type, content, tag))`
- 主线程定时检查队列（每100ms）：`root.after(100, self.process_queue)`
- 从队列取出消息后在主线程中更新GUI：`self.append_text(content, tag)`

**线程安全流程**:
```python
# 监听线程 (后台)
def listen_worker(self):
    while self.running:
        data = self.ser.read(...)
        # 不直接更新GUI，而是放入队列
        self.msg_queue.put(("log", f"收到数据: {data}", "info"))

# 主线程 (GUI)
def process_queue(self):
    try:
        msg_type, content, tag = self.msg_queue.get_nowait()
        # 在主线程中安全地更新GUI
        self.append_text(content, tag)
    except queue.Empty:
        pass
    # 定时检查
    self.root.after(100, self.process_queue)
```

### 3. 复用现有模块

#### 3.1 复用 `protocol_parser.py` 的监听逻辑

```python
# 创建ProtocolParser实例
self.parser = ProtocolParser(self.port, self.baudrate)
self.parser.ser = self.ser  # 共享串口对象
self.parser.buffer = bytearray()

# 在监听线程中使用解析逻辑
data = self.ser.read(self.ser.in_waiting)
self.parser.buffer.extend(data)

# 调用现有的解析方法
pos, preamble, direction = self.parser.find_preamble(self.parser.buffer)
packet_info = self.parser.parse_frame(self.parser.buffer, 0)
```

#### 3.2 复用 `radio_simulator.py` 的发送方法

```python
# 创建RadioSimulator实例
self.simulator = RadioSimulator(self.port, self.baudrate)
self.simulator.ser = self.ser  # 共享串口对象

# 直接调用现有的发送方法
self.simulator.send_version_request()
self.simulator.send_gps_status_request()
self.simulator.send_init_sequence()
```

### 4. 关键技术点

#### 4.1 文本框只读与更新

```python
# 设置为只读
self.text_display.config(state=tk.DISABLED)

# 更新时临时解锁
def append_text(self, text, tag="info"):
    self.text_display.config(state=tk.NORMAL)
    self.text_display.insert(tk.END, text + "\n", tag)
    self.text_display.see(tk.END)  # 自动滚动
    self.text_display.config(state=tk.DISABLED)
```

#### 4.2 彩色文本显示

```python
# 配置标签
self.text_display.tag_config("info", foreground="blue")
self.text_display.tag_config("success", foreground="green")
self.text_display.tag_config("error", foreground="red")
self.text_display.tag_config("warning", foreground="orange")
self.text_display.tag_config("data", foreground="purple")

# 使用标签
self.append_text("这是成功消息", "success")
self.append_text("这是错误消息", "error")
```

#### 4.3 线程生命周期管理

```python
# 启动监听线程
self.running = True
self.listen_thread = threading.Thread(target=self.listen_worker, daemon=True)
self.listen_thread.start()

# 停止监听线程
self.running = False  # 标志位通知线程停止
if self.listen_thread and self.listen_thread.is_alive():
    self.listen_thread.join(timeout=1.0)  # 等待线程结束
```

## 使用方法

### 基础版 (radio_gui.py)

```bash
python radio_gui.py
```

**功能**:
- 内置12个预定义命令按钮
- 实时显示接收数据
- 彩色文本区分不同消息类型
- 自动滚动显示

### 高级版 (radio_gui_advanced.py)

```bash
python radio_gui_advanced.py
```

**额外功能**:
- 支持从JSON配置文件加载命令
- 命令按钮可滚动（支持更多命令）
- 保存日志到文件
- 命令按钮工具提示
- 显示/隐藏原始数据选项

### 配置文件格式 (commands_config.json)

```json
{
  "commands": [
    {
      "id": "version",
      "name": "查询版本",
      "method": "send_version_request",
      "description": "发送SU_VERSION_REQUEST查询",
      "confirm": false
    },
    {
      "id": "reset_ub",
      "name": "复位UB",
      "method": "send_reset_ub",
      "description": "发送UB复位命令（危险操作）",
      "confirm": true
    }
  ]
}
```

**字段说明**:
- `id`: 命令唯一标识
- `name`: 按钮显示文本
- `method`: 对应的RadioSimulator方法名
- `description`: 鼠标悬停时显示的描述
- `confirm`: 是否需要确认对话框

## 操作流程

### 1. 连接串口

1. 输入COM端口（默认COM13）
2. 输入波特率（默认38400）
3. 点击"连接"按钮
4. 状态显示为"已连接"（绿色）

### 2. 发送命令

- 点击任意命令按钮即可发送对应的串口命令
- 发送的命令会在监听区显示（橙色）
- 危险命令（如"复位UB"）会弹出确认对话框

### 3. 查看接收数据

- 接收到的原始数据自动显示（紫色）
- 解析后的完整数据包以结构化方式显示（绿色）
- 包含：方向、类型、长度、数据内容、CRC等

### 4. 其他操作

- **清空显示**: 清除监听区的所有文本
- **自动滚动**: 勾选后自动滚动到最新数据
- **显示原始数据**: 显示/隐藏未解析的原始HEX数据
- **保存日志**: 将监听区内容保存到文本文件
- **加载配置**: 从JSON文件加载自定义命令按钮

### 5. 断开连接

- 点击"断开"按钮
- 监听线程自动停止
- 串口关闭

## 线程安全原理详解

### 为什么需要Queue？

tkinter的GUI组件**不是线程安全的**，如果直接在后台线程中调用GUI更新方法（如`text.insert()`），会导致：
- 程序崩溃
- GUI冻结
- 数据丢失

### Queue如何保证线程安全？

1. **后台线程**：只负责读取数据，不触碰GUI
   ```python
   # 监听线程
   data = self.ser.read(...)
   self.msg_queue.put(("log", "收到数据", "info"))  # 放入队列
   ```

2. **主线程定时器**：定期检查队列并更新GUI
   ```python
   # 主线程 (每100ms执行一次)
   def process_queue(self):
       msg = self.msg_queue.get_nowait()  # 非阻塞获取
       self.append_text(msg[1], msg[2])   # 安全更新GUI
       self.root.after(100, self.process_queue)  # 下次定时
   ```

3. **Queue内部机制**：
   - Python的`queue.Queue`是线程安全的
   - 使用锁机制保护内部数据结构
   - `put()`和`get()`操作原子性执行

### 消息类型设计

```python
# 日志消息
self.msg_queue.put(("log", "这是日志内容", "info"))

# 数据包消息
self.msg_queue.put(("packet", packet_info_dict, None))

# 处理时根据类型分发
msg_type, content, tag = self.msg_queue.get_nowait()
if msg_type == "log":
    self.append_text(content, tag)
elif msg_type == "packet":
    self.display_packet(content)
```

## 扩展开发

### 添加新命令

1. 在`radio_simulator.py`中添加新的发送方法：
   ```python
   def send_custom_command(self):
       frame = self.build_frame("  !SU2LS!", b'X', b'custom_data')
       self.ser.write(frame)
   ```

2. 在GUI中添加对应方法：
   ```python
   def send_custom_command(self):
       if not self.check_connection():
           return
       try:
           self.simulator.send_custom_command()
           self.append_text("[发送] > CUSTOM_COMMAND", "warning")
       except Exception as e:
           self.append_text(f"[错误] 发送失败: {e}", "error")
   ```

3. 更新配置文件（高级版）：
   ```json
   {
     "id": "custom",
     "name": "自定义命令",
     "method": "send_custom_command",
     "description": "发送自定义命令",
     "confirm": false
   }
   ```

### 添加数据解析逻辑

在`protocol_parser.py`中添加新的消息类型：
```python
self.MEANINGFUL_TYPES = {
    b'X': 'CUSTOM_TYPE',  # 新增
    # ... 其他类型
}
```

GUI会自动识别并显示新类型的数据包。

## 故障排查

### 问题1: 串口无法打开

**原因**: 端口被占用或不存在

**解决**:
```bash
# Windows: 查看可用端口
mode
# 或使用设备管理器

# 确保其他程序没有占用该端口
```

### 问题2: 收不到数据

**检查**:
1. 串口配置是否正确（波特率、停止位等）
2. 外部设备是否正常工作
3. 线缆是否连接正常
4. 查看监听区是否有"[监听] 监听线程已启动"消息

### 问题3: GUI卡死

**原因**: 可能在后台线程中直接更新了GUI

**检查**:
- 确保所有GUI更新都通过Queue进行
- 不要在`listen_worker`中直接调用`self.append_text()`

### 问题4: 数据解析失败

**调试**:
1. 勾选"显示原始数据"查看接收到的HEX数据
2. 检查PREAMBLE是否正确
3. 查看`protocol_parser.py`的调试输出

## 性能优化

### 1. 队列处理频率

```python
# 默认100ms检查一次队列
self.root.after(100, self.process_queue)

# 如果数据量大，可以缩短间隔
self.root.after(50, self.process_queue)  # 50ms

# 或者批量处理
def process_queue(self):
    count = 0
    while count < 10:  # 一次处理最多10条消息
        try:
            msg = self.msg_queue.get_nowait()
            # 处理消息
            count += 1
        except queue.Empty:
            break
    self.root.after(100, self.process_queue)
```

### 2. 文本框限制

避免文本框内容过多导致卡顿：
```python
def append_text(self, text, tag="info"):
    self.text_display.config(state=tk.NORMAL)

    # 限制行数
    line_count = int(self.text_display.index('end-1c').split('.')[0])
    if line_count > 1000:  # 超过1000行
        self.text_display.delete('1.0', '100.0')  # 删除前100行

    self.text_display.insert(tk.END, text + "\n", tag)
    self.text_display.config(state=tk.DISABLED)
```

## 总结

这个GUI程序完整地解决了串口通信可视化的问题：

1. **架构清晰**: 主线程处理GUI，监听线程处理串口，Queue桥接
2. **线程安全**: 严格遵循tkinter的线程安全规则
3. **复用代码**: 完全复用现有的`protocol_parser.py`和`radio_simulator.py`
4. **功能完整**: 发送、接收、解析、显示一应俱全
5. **易于扩展**: 支持配置文件，方便添加新命令

代码完全可运行，无TODO或省略部分。
