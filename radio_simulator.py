#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import serial
import struct
import time
import threading
from protocol_parser import ProtocolParser

class RadioSimulator:
    """模拟Radio端，主动发送命令诱导UB响应"""

    def __init__(self, port='COM13', baudrate=38400):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.parser = None
        self.running = False

    def calculate_crc32(self, data):
        """计算CRC32校验码"""
        import zlib
        crc = zlib.crc32(data) & 0xFFFFFFFF
        return struct.pack('<I', crc)  # 小端序

    def build_frame(self, preamble, msg_type, data=b''):
        """构建协议帧
        Args:
            preamble: PREAMBLE字符串，如"  !SU2LS!"
            msg_type: 消息类型，单字节，如b'S'
            data: 数据部分（可选）
        """
        # LENGTH = TYPE(1) + DATA(n) + CRC(4) + ETX(1)
        length = 1 + len(data) + 4 + 1

        # 构建用于CRC计算的部分：PREAMBLE + LENGTH + TYPE + DATA
        crc_data = preamble.encode('ascii') + bytes([length]) + msg_type + data
        crc = self.calculate_crc32(crc_data)

        # 完整帧：PREAMBLE + LENGTH + TYPE + DATA + CRC + ETX
        frame = crc_data + crc + b'\xff'
        return frame

    def send_status(self, reset_source=0x53):
        """发送SU_STATUS消息 (Radio→UB方向)
        reset_source: 0x48=硬件复位, 0x53=软件复位
        """
        frame = self.build_frame("  !SU2LS!", b'S', bytes([reset_source]))
        self.ser.write(frame)
        print(f"[发送] SU_STATUS (复位源: 0x{reset_source:02X})")
        print(f"       原始帧: {frame.hex()}")
        print(f"       PREAMBLE: Radio→UB")

    def send_rebooted(self, station_id=0x0001):
        """发送SU_REBOOTED消息
        station_id: 2字节站点ID
        """
        data = struct.pack('>H', station_id)  # 大端序
        frame = self.build_frame("  !SU2LS!", b'z', data)
        self.ser.write(frame)
        print(f"[发送] SU_REBOOTED (Station ID: 0x{station_id:04X})")
        print(f"       原始帧: {frame.hex()}")

    def send_network_status(self, status=2):
        """发送SU_NETWORK_REPLY消息
        status: 0=尝试加入, 1=发现网络, 2=连接建立, 3=丢失连接
        """
        frame = self.build_frame("  !SU2LS!", b'n', bytes([status]))
        self.ser.write(frame)
        print(f"[发送] SU_NETWORK_REPLY (状态: {status})")
        print(f"       原始帧: {frame.hex()}")

    def send_version_request(self):
        """发送版本查询命令"""
        frame = self.build_frame("  !SU2LS!", b'V')
        self.ser.write(frame)
        print(f"[发送] SU_VERSION_REQUEST")
        print(f"       原始帧: {frame.hex()}")

    def send_gps_status_request(self):
        """发送GPS状态查询"""
        frame = self.build_frame("  !SU2LS!", b'G')
        self.ser.write(frame)
        print(f"[发送] SU_GPS_STATUS_REQUEST")
        print(f"       原始帧: {frame.hex()}")

    def send_gps_position_request(self):
        """发送GPS位置查询"""
        frame = self.build_frame("  !SU2LS!", b'P')
        self.ser.write(frame)
        print(f"[发送] SU_GPS_POSITION_REQUEST")
        print(f"       原始帧: {frame.hex()}")

    def send_gps_time_request(self):
        """发送GPS时间查询"""
        frame = self.build_frame("  !SU2LS!", b'M')
        self.ser.write(frame)
        print(f"[发送] SU_GPS_TIME_REQUEST")
        print(f"       原始帧: {frame.hex()}")

    def send_station_id_request(self):
        """发送站点ID查询"""
        frame = self.build_frame("  !SU2LS!", b'U')
        self.ser.write(frame)
        print(f"[发送] SU_STATION_ID_REQUEST")
        print(f"       原始帧: {frame.hex()}")

    def send_data_ack(self, station_id=0x0001, pack_number=0x01):
        """发送数据确认"""
        data = struct.pack('>HB', station_id, pack_number)
        frame = self.build_frame("  !SU2LS!", b'd', data)
        self.ser.write(frame)
        print(f"[发送] SU_DATA_ACK (ID: 0x{station_id:04X}, Pack: {pack_number})")
        print(f"       原始帧: {frame.hex()}")

    def send_echo(self, echo_data=b"TEST"):
        """发送回显测试"""
        frame = self.build_frame("  !SU2LS!", b'E', echo_data)
        self.ser.write(frame)
        print(f"[发送] SU_ECHO (数据: {echo_data})")
        print(f"       原始帧: {frame.hex()}")

    def send_reset_ub(self):
        """发送UB复位命令"""
        frame = self.build_frame("  !SU2LS!", b'T')
        self.ser.write(frame)
        print(f"[发送] SU_RESET_UB")
        print(f"       原始帧: {frame.hex()}")

    def send_init_sequence(self):
        """发送初始化序列（模拟Radio上电）"""
        print("\n========== 发送初始化序列 ==========")

        # 1. 发送STATUS
        self.send_status(0x53)
        time.sleep(0.5)

        # 2. 发送REBOOTED
        self.send_rebooted(0x0001)
        time.sleep(0.5)

        # 3. 发送网络状态：尝试加入
        self.send_network_status(0)
        time.sleep(1)

        # 4. 发送网络状态：发现网络
        self.send_network_status(1)
        time.sleep(1)

        # 5. 发送网络状态：连接建立（这应该触发UB发送数据）
        self.send_network_status(2)
        print("========== 初始化序列完成 ==========\n")

    def start_listener(self):
        """在独立线程中启动监听器"""
        self.parser = ProtocolParser(self.port, self.baudrate)
        self.parser.ser = self.ser  # 共享串口

        def listen_thread():
            print("\n[监听线程] 开始监听UB响应...")
            print("[监听线程] 等待数据中...\n")
            self.parser.buffer = bytearray()
            last_status = time.time()

            while self.running:
                # 每5秒显示一次状态
                if time.time() - last_status > 5:
                    print(f"[监听] 仍在监听... 缓冲区: {len(self.parser.buffer)} 字节")
                    last_status = time.time()

                if self.ser.in_waiting > 0:
                    data = self.ser.read(self.ser.in_waiting)
                    print(f"\n[接收] 收到 {len(data)} 字节")
                    print(f"       十六进制: {data.hex()}")
                    print(f"       ASCII: {data.decode('ascii', errors='replace')}")

                    self.parser.buffer.extend(data)

                    # 处理缓冲区
                    while len(self.parser.buffer) > 0:
                        pos, preamble, direction = self.parser.find_preamble(self.parser.buffer)

                        if pos == -1:
                            self.parser.buffer.clear()
                            break

                        if pos > 0:
                            self.parser.buffer = self.parser.buffer[pos:]

                        packet_info = self.parser.parse_frame(self.parser.buffer, 0)

                        if packet_info:
                            print(f"\n✓ 收到完整包: {packet_info['type_name']} ({packet_info['direction']})")
                            self.parser.save_packet(packet_info)
                            self.parser.buffer = self.parser.buffer[packet_info['frame_len']:]
                        else:
                            break

                time.sleep(0.01)

        listener = threading.Thread(target=listen_thread, daemon=True)
        listener.start()

    def open_serial(self):
        """打开串口"""
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=8,
                parity=serial.PARITY_NONE,
                stopbits=1,
                timeout=1,
                rtscts=False,
                dsrdtr=False,
                xonxoff=False
            )
            print(f"已打开串口 {self.port}, 波特率 {self.baudrate}")
            return True
        except Exception as e:
            print(f"无法打开串口 {self.port}: {e}")
            return False

    def close_serial(self):
        """关闭串口"""
        self.running = False
        time.sleep(0.1)
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("串口已关闭")

    def interactive_mode(self):
        """交互模式"""
        print("\n========== Radio模拟器交互模式 ==========")
        print("可用命令：")
        print("  1  - 发送完整初始化序列")
        print("  S  - 发送STATUS")
        print("  z  - 发送REBOOTED")
        print("  n  - 发送NETWORK_STATUS (状态2)")
        print("  V  - 发送VERSION请求")
        print("  G  - 发送GPS状态请求")
        print("  P  - 发送GPS位置请求")
        print("  M  - 发送GPS时间请求")
        print("  U  - 发送站点ID请求")
        print("  E  - 发送ECHO测试")
        print("  d  - 发送DATA_ACK")
        print("  T  - 发送RESET_UB")
        print("  q  - 退出")
        print("=========================================\n")

        while self.running:
            try:
                cmd = input("输入命令: ").strip()

                if cmd == 'q':
                    break
                elif cmd == '1':
                    self.send_init_sequence()
                elif cmd == 'S':
                    self.send_status()
                elif cmd == 'z':
                    self.send_rebooted()
                elif cmd == 'n':
                    self.send_network_status(2)
                elif cmd == 'V':
                    self.send_version_request()
                elif cmd == 'G':
                    self.send_gps_status_request()
                elif cmd == 'P':
                    self.send_gps_position_request()
                elif cmd == 'M':
                    self.send_gps_time_request()
                elif cmd == 'U':
                    self.send_station_id_request()
                elif cmd == 'E':
                    self.send_echo()
                elif cmd == 'd':
                    self.send_data_ack()
                elif cmd == 'T':
                    self.send_reset_ub()
                else:
                    print("未知命令")

                time.sleep(0.1)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"错误: {e}")

    def run(self):
        """主函数"""
        if not self.open_serial():
            return

        self.running = True

        # 启动监听线程
        self.start_listener()

        # 自动发送初始化序列
        time.sleep(1)
        self.send_init_sequence()

        # 进入交互模式
        try:
            self.interactive_mode()
        except KeyboardInterrupt:
            print("\n用户中断")
        finally:
            self.close_serial()

if __name__ == "__main__":
    simulator = RadioSimulator()
    simulator.run()
