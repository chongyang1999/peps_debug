#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import serial
import struct
import time
from datetime import datetime
import os
import binascii

class ProtocolParser:
    def __init__(self, port='COM4', baudrate=38400):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.buffer = bytearray()
        
        # 协议常量
        self.PREAMBLES = {
            b'  !LS2SU!': 'UB_TO_RADIO',
            b'  !SU2LS!': 'RADIO_TO_UB', 
            b' !BS2PC!': 'BSU_TO_CDAS',
            b'  !PC2BS!': 'CDAS_TO_BSU'
        }
        self.PREAMBLE_LEN = 9
        self.ETX = 0xFF
        
        # 有意义的消息类型（过滤掉无意义的）
        self.MEANINGFUL_TYPES = {
            b'D': 'DATA',           # 数据包
            b'C': 'CONTROL',        # 控制数据
            b'S': 'STATUS',         # 状态信息
            b'V': 'VERSION',        # 版本信息
            b'G': 'GPS',            # GPS状态
            b'P': 'GPS_POS',        # GPS位置
            b'M': 'GPS_DATE',       # GPS时间
            b'U': 'STATION_ID',     # 站点ID
            b'T': 'RESET_UB',       # UB复位
            b'E': 'ECHO',           # 回显
            b'N': 'NETWORK',        # 网络状态
        }
        
    def open_serial(self):
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=8,
                parity=serial.PARITY_NONE,
                stopbits=1,
                timeout=1,
                rtscts=False,      # 禁用RTS/CTS硬件流控制
                dsrdtr=False,      # 禁用DSR/DTR硬件流控制
                xonxoff=False      # 禁用软件流控制
            )
            print(f"已打开串口 {self.port}, 波特率 {self.baudrate}")
            return True
        except Exception as e:
            print(f"无法打开串口 {self.port}: {e}")
            return False
            
    def close_serial(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("串口已关闭")
            
    def find_preamble(self, data):
        """查找有效的PREAMBLE"""
        for preamble, direction in self.PREAMBLES.items():
            pos = data.find(preamble)
            if pos != -1:
                return pos, preamble, direction
        return -1, None, None
        
    def parse_frame(self, data, start_pos):
        """解析协议帧"""
        if len(data) < start_pos + self.PREAMBLE_LEN + 1:
            return None
            
        # 检查LENGTH字段
        length_pos = start_pos + self.PREAMBLE_LEN
        if length_pos >= len(data):
            return None
            
        print(f"[调试] PREAMBLE长度: {self.PREAMBLE_LEN}, start_pos: {start_pos}")
        print(f"[调试] LENGTH字段位置: {length_pos}")
        print(f"[调试] 缓冲区数据: {binascii.hexlify(data[:32]).decode()}")
        
        length = data[length_pos]
        print(f"[调试] LENGTH字段值: 0x{length:02X} = {length}")
        
        # 根据实际数据验证：2020214c5332535521064e86e7d9eeff
        # 位置8应该是0x06，不是0x21
        if length_pos == 8:
            expected_byte = data[8] if len(data) > 8 else None
            print(f"[调试] 位置8的字节: 0x{expected_byte:02X} = {expected_byte}")
            
        # 手动检查正确的LENGTH位置
        if len(data) >= 9:
            manual_length = data[8]  # 手动检查位置8
            print(f"[调试] 手动检查位置8的LENGTH: 0x{manual_length:02X} = {manual_length}")
        
        # 检查是否有足够的数据
        total_frame_len = self.PREAMBLE_LEN + 1 + length
        print(f"[调试] 计算帧长: {self.PREAMBLE_LEN} + 1 + {length} = {total_frame_len}")
        
        if len(data) < start_pos + total_frame_len:
            print(f"[调试] 数据不足: 需要 {total_frame_len} 字节，实际 {len(data)} 字节")
            return None
            
        # 提取完整帧
        frame = data[start_pos:start_pos + total_frame_len]
        
        # 检查ETX
        if frame[-1] != self.ETX:
            print(f"[调试] ETX错误: 期望 0xFF，实际 0x{frame[-1]:02X}")
            return None
            
        # 解析字段
        preamble = frame[:self.PREAMBLE_LEN]
        length_field = frame[self.PREAMBLE_LEN]
        type_field = bytes([frame[self.PREAMBLE_LEN + 1]])
        
        print(f"[调试] 解析帧: LENGTH={length_field}, TYPE={type_field}, 帧长={total_frame_len}")
        
        # 检查是否是有意义的消息类型
        if type_field not in self.MEANINGFUL_TYPES:
            print(f"[调试] 无意义的消息类型: {type_field}")
            return None
            
        # 数据部分（TYPE之后到CRC之前）
        # LENGTH包含TYPE(1)+DATA(?)+CRC(4)+ETX(1)
        data_start = self.PREAMBLE_LEN + 1 + 1  # PREAMBLE + LENGTH + TYPE
        data_end = start_pos + total_frame_len - 5  # 减去CRC(4)+ETX(1)
        data_part = frame[data_start:data_end]
        
        # CRC部分（最后4字节，不包括ETX）
        crc_part = frame[-5:-1]
        
        print(f"[调试] 数据部分长度: {len(data_part)}, CRC: {binascii.hexlify(crc_part).decode()}")
        
        return {
            'frame': frame,
            'preamble': preamble,
            'direction': self.PREAMBLES[bytes(preamble)],
            'length': length_field,
            'type': type_field,
            'type_name': self.MEANINGFUL_TYPES[bytes(type_field)],
            'data': data_part,
            'crc': crc_part,
            'frame_len': total_frame_len
        }
        
    def save_packet(self, packet_info):
        """保存数据包到文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"packet_{timestamp}.bin"
        
        try:
            with open(filename, 'wb') as f:
                f.write(packet_info['frame'])
            
            # 同时保存可读的信息
            info_filename = f"packet_{timestamp}.txt"
            with open(info_filename, 'w', encoding='utf-8') as f:
                f.write(f"时间: {timestamp}\n")
                f.write(f"方向: {packet_info['direction']}\n")
                f.write(f"类型: {packet_info['type_name']} ({packet_info['type']})\n")
                f.write(f"长度: {packet_info['length']}\n")
                f.write(f"帧长度: {packet_info['frame_len']}\n")
                f.write(f"原始数据 (hex): {binascii.hexlify(packet_info['frame']).decode()}\n")
                f.write(f"CRC: {binascii.hexlify(packet_info['crc']).decode()}\n")
                
            print(f"数据包已保存: {filename}, 信息: {info_filename}")
            
        except Exception as e:
            print(f"保存文件失败: {e}")
            
    def run(self):
        """主循环"""
        if not self.open_serial():
            return
            
        print("开始监听串口数据...")
        print("调试模式：显示所有接收到的原始数据")
        
        last_debug_time = time.time()
        
        try:
            while True:
                # 读取数据
                if self.ser.in_waiting > 0:
                    data = self.ser.read(self.ser.in_waiting)
                    
                    # 调试：显示原始数据
                    print(f"[原始数据] 收到 {len(data)} 字节: {data}")
                    print(f"[原始数据] 十六进制: {binascii.hexlify(data).decode()}")
                    print(f"[原始数据] ASCII: {data.decode('ascii', errors='replace')}")
                    
                    self.buffer.extend(data)
                    
                    # 处理缓冲区中的数据
                    while len(self.buffer) > 0:
                        # 查找PREAMBLE
                        pos, preamble, direction = self.find_preamble(self.buffer)
                        
                        if pos == -1:
                            # 没有找到有效的PREAMBLE，但保留可能的部分PREAMBLE
                            print(f"[调试] 缓冲区 {len(self.buffer)} 字节，未找到有效PREAMBLE")
                            print(f"[调试] 缓冲区内容: {self.buffer[:50]}...")  # 只显示前50字节
                            
                            # 检查是否有部分PREAMBLE，如果有就保留
                            keep_buffer = False
                            for preamble in self.PREAMBLES.keys():
                                for i in range(1, len(preamble)):
                                    if self.buffer.endswith(preamble[:i]):
                                        print(f"[调试] 保留部分PREAMBLE: {preamble[:i]}")
                                        keep_buffer = True
                                        break
                                if keep_buffer:
                                    break
                            
                            if not keep_buffer:
                                self.buffer.clear()
                            break
                            
                        # 移除PREAMBLE之前的无效数据
                        if pos > 0:
                            removed = self.buffer[:pos]
                            print(f"[调试] 移除PREAMBLE前的无效数据: {removed}")
                            self.buffer = self.buffer[pos:]
                            
                        print(f"[调试] 找到PREAMBLE: {preamble} at position {pos}, 方向: {direction}")
                        
                        # 尝试解析帧
                        packet_info = self.parse_frame(self.buffer, 0)
                        
                        if packet_info:
                            # 找到完整的有意义的包
                            print(f"✓ 收到包: {packet_info['type_name']} ({packet_info['direction']})")
                            self.save_packet(packet_info)
                            
                            # 从缓冲区移除已处理的帧
                            self.buffer = self.buffer[packet_info['frame_len']:]
                        else:
                            # 帧不完整或无效，等待更多数据
                            print(f"[调试] 帧不完整或无效，缓冲区长度: {len(self.buffer)}")
                            if len(self.buffer) > 1000:  # 防止缓冲区过大
                                self.buffer = self.buffer[1:]
                            else:
                                break
                else:
                    # 没有数据时的状态显示
                    current_time = time.time()
                    if current_time - last_debug_time > 5:  # 每5秒显示一次状态
                        print(f"[状态] 等待数据中... 串口开启: {self.ser.is_open}")
                        last_debug_time = current_time
                        
                time.sleep(0.01)  # 短暂休眠避免过度占用CPU
                
        except KeyboardInterrupt:
            print("\n用户中断，正在退出...")
        except Exception as e:
            print(f"运行错误: {e}")
        finally:
            self.close_serial()

if __name__ == "__main__":
    parser = ProtocolParser()
    parser.run()