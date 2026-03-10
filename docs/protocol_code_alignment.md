# UB Radio 协议与当前代码对照

本文档用于对照 `docs/protocol.md` 与当前 ESP32 实现 `esp32_bridge/ubradio_decode.py`，明确哪些地方已经严格对上，哪些地方只是当前主线场景下够用，哪些地方仍未覆盖。

适用范围：
- 当前文档只针对 **UB <-> Radio** 这条链路
- 不覆盖 `BSU <-> PC` 那部分前导符和业务
- 当前主要实现文件：
  - `esp32_bridge/ubradio_decode.py`
  - `esp32_bridge/ubradio_web.py`

---

## 1. 当前结论

当前这套 ESP32 代码对 **UB <-> Radio** 协议的核心字段已经基本对应，尤其是：

- `PREAMBLE` 处理正确
- 前导空格算作有效字节
- `LENGTH` 定义与代码一致
- `CRC32` 输入范围与实测一致
- `ETX=0xFF` 处理正确

你之前担心的“前面的空格算不算字节”这个点，当前代码是按正确方式实现的：

- 空格 **算进 PREAMBLE**
- 但 **不算进 LENGTH**

---

## 2. PREAMBLE 对照

`docs/protocol.md` 中定义：

- `"  !LS2SU!"`：UB -> Radio
- `"  !SU2LS!"`：Radio -> UB

注意：
- 这两个字符串前面都有 **两个空格**
- 整个 `PREAMBLE` 长度是 **9 字节**

按字节展开：

```text
0x20 0x20 0x21 0x4c 0x53 0x32 0x53 0x55 0x21   -> "  !LS2SU!"
0x20 0x20 0x21 0x53 0x55 0x32 0x4c 0x53 0x21   -> "  !SU2LS!"
```

当前代码：

```python
PREAMBLE_TX = b"  !SU2LS!"
PREAMBLE_RX = b"  !LS2SU!"
```

这说明：

- 代码把前导空格算进了协议字段
- `PREAMBLE` 被当作固定 9 字节处理
- 后续 `LENGTH` 的读取位置用的是 `buffer[9]`

所以这一点是 **正确的**。

---

## 3. LENGTH 对照

协议文档定义：

- `LENGTH` 表示后续字段总长度
- 覆盖范围是：
  - `TYPE`
  - `DATA`
  - `CRC`
  - `ETX`

换句话说：

```text
LENGTH = 1 + len(DATA) + 4 + 1
       = len(DATA) + 6
```

关键点：

- `LENGTH` **不包括 PREAMBLE**
- `LENGTH` **不包括自身这个字节**

当前发包代码：

```python
length_int = 1 + len(payload) + 4 + 1
```

当前收包代码：

```python
pkt_len = buffer[9]
data_len = pkt_len - 6
```

这与协议定义完全一致。

---

## 4. CRC32 对照

协议文档只写了“CRC32，4 字节”，没有在摘要里详细展开输入范围。  
当前实现依据实测样本采用的是：

```text
CRC32(LENGTH + TYPE + DATA)
```

当前代码发包：

```python
crc_input = length_byte + type_byte + payload
crc_bytes = calculate_crc(crc_input)
```

当前代码收包：

```python
crc_input_data = frame[9 : 9 + 1 + 1 + data_len]
calculated_crc = calculate_crc(crc_input_data)
```

即：

- `frame[9]` 是 `LENGTH`
- `frame[10]` 是 `TYPE`
- 后面跟 `DATA`

也就是按：

```text
LENGTH + TYPE + DATA
```

进行 CRC32 计算。

### 为什么认为这是对的

这不是纯猜测，而是已经被真实帧验证过。

例如空闲状态包：

```text
2020214c5332535521064e86e7d9eeff
```

拆开后：

- PREAMBLE = `2020214c5332535521` = `"  !LS2SU!"`
- LENGTH = `06`
- TYPE = `4e` = `N`
- DATA = 空
- CRC = `86e7d9ee`
- ETX = `ff`

对 `06 4e` 做 CRC32，结果正好是：

```text
86e7d9ee
```

因此当前 CRC 方案与实测相符。

---

## 5. ETX 对照

协议中：

- `ETX = 0xFF`

当前代码：

```python
ETX = 0xFF
```

收包时：

```python
expected_etx = frame[-1]
if expected_etx != ETX:
    ...
```

发包时：

```python
+ bytes([ETX])
```

这一点也是正确的。

---

## 6. 当前已验证命令

目前通过 REPL 和网页都已经实测成功的命令：

### `V -> v`

请求：

- `TYPE='V'`

响应：

- `TYPE='v'`
- 返回 ASCII：`V02.01`

说明：

- 发包格式正确
- 收包格式正确
- `LENGTH/CRC/ETX` 都已通过真实交互验证

### `G -> g`

请求：

- `TYPE='G'`

响应：

- `TYPE='g'`
- 数据：`00`

当前解释：

- GPS invalid

### `E -> e`

请求：

- `TYPE='E'`
- 例如 payload=`PING`

响应：

- `TYPE='e'`
- 当前实测一般只回 ACK，不回显 payload

这说明：

- 协议表写的是 Echo
- 但当前 UB 固件行为更接近“收到即确认”

---

## 7. 当前代码没有完整覆盖的部分

虽然当前实现对 **UB <-> Radio** 主线已经基本对上，但还不是对 `protocol.md` 的“全覆盖实现”。

### 7.1 只覆盖了 UB <-> Radio

协议文档还列了：

- `" !BS2PC!"`
- `"  !PC2BS!"`

当前代码没有处理这两类前导符。  
这不算当前主线 bug，因为现阶段我们只做 `UB <-> Radio`。

### 7.2 未做严格 TYPE 输入校验

协议要求：

- `TYPE` 必须是 1 字节

当前代码里：

```python
if isinstance(cmd_type_char, str):
    type_byte = cmd_type_char.encode()
```

如果误传 `"AB"`，理论上会生成 2 字节 `TYPE`，这是非法帧。  
当前按钮和 REPL 调用都只传单字符，所以暂时没出问题，但这是一个代码边界问题。

### 7.3 还没有覆盖所有协议命令

协议表里有：

- `C/R/T/N/B/U/P/M/...`

当前已重点验证的是：

- `V`
- `G`
- `E`

其他命令虽然可以发，但不是全部都已经被实际确认。

---

## 8. 关于“空格算不算字节”的最终结论

这个问题最容易误导人，单独写清楚：

### 算进 PREAMBLE

前导两个空格是协议字符串的一部分，所以：

```text
"  !LS2SU!"
"  !SU2LS!"
```

都必须按 **9 字节** 看待。

### 不算进 LENGTH

虽然空格属于 `PREAMBLE`，但 `LENGTH` 的定义从来不是“整帧总长”，而是：

```text
TYPE + DATA + CRC + ETX
```

因此：

- 空格算进前导符
- 但不参与 `LENGTH`
- 也不参与当前 CRC 输入

这正是当前代码的实现方式。

---

## 9. 当前建议

如果以后还要继续对照协议与代码，建议优先盯这四个点：

1. `PREAMBLE` 是否仍按 9 字节处理  
2. `LENGTH` 是否始终等于 `len(DATA)+6`  
3. `CRC32` 是否始终只覆盖 `LENGTH + TYPE + DATA`  
4. `TYPE` 是否被限制为单字节

前 3 项当前已经基本稳定；第 4 项后续可以再补输入校验。

---

## 10. 总结

当前结论可以简化成一句话：

> 对当前正在使用的 `UB <-> Radio` 主线协议来说，`esp32_bridge/ubradio_decode.py` 在 `PREAMBLE`、`LENGTH`、`CRC32`、`ETX` 这几个核心字段上已经与协议和实测数据基本对应；“前导空格是否计入字节”的问题，当前实现是正确处理的。
