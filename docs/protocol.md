# 通信协议文档重点总结

本文档对 `comms_protocol.pdf` 中 UB ↔ Radio ↔ CDAS/BSU 的 RS‑232 通信协议要点进行了提炼，方便复制和二次编辑。

---

## 1. 文档目的与背景

- 针对 Pierre Auger 项目，补充 UB（Unit Board）与 Radio 以及 CDAS/BSU 之间的差异与扩展  
- “Station Id request” 命令由原来 `'T'` 改为 `'U'`，响应由 `'t'` 改为 `'u'`  
- 新增 UB 复位命令 `'T'`，收到后 UB 会重启  

---

## 2. 物理与电气连接（DB-9）

| 引脚 | UB 端           | Radio 端         | 说明                        |
|------|-----------------|------------------|-----------------------------|
| 1    | 12 V            | 12 V             | 电源                        |
| 2    | Rx (RS‑232)     | Rx (RS‑232)      | 接收数据                    |
| 3    | Tx (RS‑232)     | Tx (RS‑232)      | 发送数据                    |
| 4    | PPS (3.3 V TTL) | Reset (3.3 V TTL)| GPS 同步 vs 收发机复位      |
| 5    | GND             | GND              | 地                          |
| 6    | Reset (3.3 V TTL)| PPS (3.3 V TTL) | 收发机复位 vs GPS 同步      |
| 7    | RTS (RS‑232)    | RTS (RS‑232)     | 请求发送                    |
| 8    | CTS (RS‑232)    | CTS (RS‑232)     | 清除发送                    |
| 9    | Reset UB (TTL)  | Reset Radio      | 复位控制                    |

- 交叉连线：2↔3、3↔2、4↔6、6↔4、7↔8、8↔7  
- UART 参数：38400 bps、8 数据位、无校验、1 起始 + 1 停止位  

---

## 3. 通信帧格式


- **PREAMBLE**：  
  - `"  !LS2SU!"`：UB→Radio  
  - `"  !SU2LS!"`：Radio→UB  
  - `" !BS2PC!"`：BSU→CDAS  
  - `"  !PC2BS!"`：CDAS→BSU  
- **LENGTH**：后续字段总长度（TYPE+DATA+CRC+ETX）  
- **TYPE**：1 字节消息类型（如 `D` 表示数据包）  
- **DATA**：有效载荷  
- **CRC4**：4 字节 CRC32 校验  
- **ETX**：结束标志 `0xFF`  

---

## 4. 初始握手与网络状态

1. 上电/复位后，Radio 发送一系列 SU2ATE 预编程报文，UB 忽略之  
2. 接着 Radio 发送：
   - `SU_STATUS`（软件复位，0x53）
   - `SU_REBOOTE` + ID（2 字节）
   - `SU_NETWORK_STATUS`（状态码：0=尝试加入，1=发现网络，2=连接中，3=丢失连接）
3. UB 仅在收到 `SU_NETWORK_STATUS=2` 且 GPS 可用时，才开始发送数据  

---

## 5. UB 数据封装细节

- **消息 TYPE=D 时**，DATA 部分结构：
  1. 4 字节保留区  
  2. Station Id（2 字节）  
  3. 包内消息数量（1 字节）  
  4. 若干消息，每条包含：
     - 长度（1 字节，不含自身）
     - 分片标识：completion（2 bit） + slice（6 bit）
     - 子类型（1 字节）
     - 消息号（6 bit） + 版本（2 bit）
     - 数据（可变）
  5. 分片机制：ALL/FIRST/NEXT/LAST，序号 0–63  

---

## 6. 命令与响应总览

| 命令名               | TYPE | 长度范围 (bytes) | 数据说明                   |
|----------------------|------|------------------|----------------------------|
| SU_DATA / ACK        | D / d| 9–156 / 9        | Id + 包号 +…               |
| SU_LENGTH_EXCEEDED   | x    | 9                |                            |
| SU_ECHO / ACK        | E / e| 6–255            | 回显数据                   |
| SU_CONTROL / ACK     | C / c| 6–255 / 6        | 控制数据                   |
| SU_RESET / ACK       | R / r| 6 / 6            |                            |
| SU_STATUS            | S    | 7                | 复位源（0x48 硬件，0x53 软件）|
| SU_VERSION / ACK     | V / v| 6 / 12           | 版本字符串                 |
| SU_GPS / ACK         | G / g| 6 / 7            | GPS 状态（0=无效，1=有效）  |
| SU_GPS_POS_REQ / ACK | P / p| 6 / 19           | GPS 坐标                   |
| SU_GPS_DATE_REQ/ACK  | M / m| 6 / 11           | UTC 秒数                   |
| SU_ID / SU_ID_REPLY  | U / u| 6 / 8            | Station Id                 |
| SU_RESET_UB / REBOOT | T / z| 6 / 8            | UB 复位                    |
| SU_NETWORK / ACK     | N / n| — / 7            | 网络状态                   |
| SU_INVALID           | I    | 6                | 无效命令                   |
| SU_BUFF_REQ / ACK    | B / b| 6 / 7            | 缓冲区状态                 |

---

## 7. 示例报文解析

文档末尾提供了完整字节流示例并按字段逐字节注释，有助于调试与回放。  

---

## 8. 实测备注

- “PC 直接连接 UB” 在本项目语境下，实际通常指 **PC -> MM232R USB-UART -> MAX3232 -> UB Radio RS-232**，并非 PC 直接以 TTL 或裸串口方式接入 UB。
- 引入 ESP32 后，硬件链路变化为 **PC -> ESP32 -> MAX3232 -> UB**；可以理解为 ESP32 替换了原有的 MM232R 主机适配部分。
- 历史抓包表明，UB 在启动后或空闲状态下会自发发送 `TYPE='N'` 的状态包；当前保存的样本显示该周期约为 **10 分钟**。
- 上述“10 分钟”是根据样本时间点推得的经验值，而非本协议文档中明示的固定配置。

---

> **总结**：  
> 本文档详细定义了 UB↔Radio↔CDAS 三方通过非标准 DB‑9 接口的 RS‑232 通信，包括物理接线、电气参数、帧结构、握手流程、数据封装、分片机制及命令集，是实现该链路的关键参考。
