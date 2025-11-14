#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import serial
import threading
import queue
import time
from datetime import datetime
import binascii
from protocol_parser import ProtocolParser
from radio_simulator import RadioSimulator


class RadioGUI:
    """串口通信可视化GUI程序

    架构设计：
    1. 主线程：运行tkinter GUI事件循环
    2. 监听线程：后台持续监听串口数据
    3. 线程安全通信：使用queue.Queue在线程间传递消息
    """

    def __init__(self, root):
        self.root = root
        self.root.title("串口通信调试工具")
        self.root.geometry("900x700")

        # 串口相关
        self.port = 'COM13'
        self.baudrate = 38400
        self.ser = None
        self.simulator = None
        self.parser = None

        # 线程控制
        self.running = False
        self.listen_thread = None

        # 线程安全的消息队列（从监听线程到GUI主线程）
        self.msg_queue = queue.Queue()

        # 原始字节流模式（默认关闭，只显示解析后的协议数据）
        self.raw_mode = False

        # 创建GUI界面
        self.create_widgets()

        # 启动队列处理定时器
        self.process_queue()

    def create_widgets(self):
        """创建GUI组件"""

        # ========== 顶部：串口配置区 ==========
        config_frame = ttk.LabelFrame(self.root, text="串口配置", padding=10)
        config_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(config_frame, text="端口:").grid(row=0, column=0, padx=5)
        self.port_var = tk.StringVar(value=self.port)
        port_entry = ttk.Entry(config_frame, textvariable=self.port_var, width=10)
        port_entry.grid(row=0, column=1, padx=5)

        ttk.Label(config_frame, text="波特率:").grid(row=0, column=2, padx=5)
        self.baudrate_var = tk.StringVar(value=str(self.baudrate))
        baudrate_entry = ttk.Entry(config_frame, textvariable=self.baudrate_var, width=10)
        baudrate_entry.grid(row=0, column=3, padx=5)

        self.connect_btn = ttk.Button(config_frame, text="连接", command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=4, padx=10)

        self.status_label = ttk.Label(config_frame, text="状态: 未连接", foreground="red")
        self.status_label.grid(row=0, column=5, padx=10)

        # ========== 上半部分：发送命令区 ==========
        send_frame = ttk.LabelFrame(self.root, text="发送命令区", padding=10)
        send_frame.pack(fill=tk.BOTH, padx=10, pady=5, expand=False)

        # 定义命令按钮配置（命令名称、显示文本、对应的发送方法）
        self.commands = [
            ("init", "发送初始化序列", self.send_init_sequence),
            ("status", "发送STATUS", self.send_status),
            ("rebooted", "发送REBOOTED", self.send_rebooted),
            ("network", "发送网络状态(连接建立)", self.send_network_status),
            ("version", "查询版本", self.send_version_request),
            ("gps_status", "查询GPS状态", self.send_gps_status_request),
            ("gps_position", "查询GPS位置", self.send_gps_position_request),
            ("gps_time", "查询GPS时间", self.send_gps_time_request),
            ("station_id", "查询站点ID", self.send_station_id_request),
            ("echo", "发送ECHO测试", self.send_echo),
            ("data_ack", "发送数据确认", self.send_data_ack),
            ("reset_ub", "复位UB", self.send_reset_ub),
        ]

        # 创建按钮网格（每行4个按钮）
        for idx, (cmd_name, btn_text, cmd_func) in enumerate(self.commands):
            row = idx // 4
            col = idx % 4
            btn = ttk.Button(send_frame, text=btn_text, command=cmd_func, width=20)
            btn.grid(row=row, column=col, padx=5, pady=5)

        # ========== 下半部分：监听显示区 ==========
        display_frame = ttk.LabelFrame(self.root, text="接收数据监听区", padding=10)
        display_frame.pack(fill=tk.BOTH, padx=10, pady=5, expand=True)

        # 文本显示框（带滚动条）
        self.text_display = scrolledtext.ScrolledText(
            display_frame,
            wrap=tk.WORD,
            width=100,
            height=25,
            font=("Consolas", 9),
            state=tk.DISABLED  # 只读模式
        )
        self.text_display.pack(fill=tk.BOTH, expand=True)

        # 配置文本标签（用于彩色显示）
        self.text_display.tag_config("info", foreground="blue")
        self.text_display.tag_config("success", foreground="green")
        self.text_display.tag_config("error", foreground="red")
        self.text_display.tag_config("warning", foreground="orange")
        self.text_display.tag_config("data", foreground="purple")

        # 底部控制按钮
        control_frame = ttk.Frame(display_frame)
        control_frame.pack(fill=tk.X, pady=5)

        ttk.Button(control_frame, text="清空显示", command=self.clear_display).pack(side=tk.LEFT, padx=5)

        self.auto_scroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(control_frame, text="自动滚动", variable=self.auto_scroll_var).pack(side=tk.LEFT, padx=5)

        # 原始字节流模式切换按钮
        self.raw_mode_btn = ttk.Button(control_frame, text="切换到原始字节模式", command=self.toggle_raw_mode)
        self.raw_mode_btn.pack(side=tk.LEFT, padx=5)

    def append_text(self, text, tag="info"):
        """线程安全地向文本框追加内容

        Args:
            text: 要显示的文本
            tag: 文本标签（用于颜色）
        """
        self.text_display.config(state=tk.NORMAL)
        self.text_display.insert(tk.END, text + "\n", tag)

        # 自动滚动到底部
        if self.auto_scroll_var.get():
            self.text_display.see(tk.END)

        self.text_display.config(state=tk.DISABLED)

    def clear_display(self):
        """清空显示区"""
        self.text_display.config(state=tk.NORMAL)
        self.text_display.delete(1.0, tk.END)
        self.text_display.config(state=tk.DISABLED)

    def toggle_raw_mode(self):
        """切换原始字节流模式"""
        self.raw_mode = not self.raw_mode
        if self.raw_mode:
            self.raw_mode_btn.config(text="切换到协议解析模式")
            self.append_text("=" * 60, "warning")
            self.append_text("已切换到原始字节流模式", "warning")
            self.append_text("将显示所有接收到的原始字节，不进行协议解析", "warning")
            self.append_text("=" * 60, "warning")
        else:
            self.raw_mode_btn.config(text="切换到原始字节模式")
            self.append_text("=" * 60, "info")
            self.append_text("已切换到协议解析模式", "info")
            self.append_text("将只显示符合协议的完整数据包", "info")
            self.append_text("=" * 60, "info")

    def toggle_connection(self):
        """切换连接状态"""
        if not self.running:
            self.connect_serial()
        else:
            self.disconnect_serial()

    def connect_serial(self):
        """连接串口并启动监听线程"""
        try:
            # 获取配置
            self.port = self.port_var.get()
            self.baudrate = int(self.baudrate_var.get())

            # 打开串口
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

            # 创建RadioSimulator实例（用于发送）
            self.simulator = RadioSimulator(self.port, self.baudrate)
            self.simulator.ser = self.ser  # 共享串口

            # 创建ProtocolParser实例（用于接收解析）
            self.parser = ProtocolParser(self.port, self.baudrate)
            self.parser.ser = self.ser  # 共享串口
            self.parser.buffer = bytearray()

            # 更新状态
            self.running = True
            self.status_label.config(text=f"状态: 已连接 ({self.port})", foreground="green")
            self.connect_btn.config(text="断开")

            self.append_text(f"[系统] 成功连接到 {self.port}, 波特率 {self.baudrate}", "success")

            # 启动监听线程
            self.listen_thread = threading.Thread(target=self.listen_worker, daemon=True)
            self.listen_thread.start()

        except Exception as e:
            messagebox.showerror("连接错误", f"无法打开串口: {e}")
            self.append_text(f"[错误] 连接失败: {e}", "error")

    def disconnect_serial(self):
        """断开串口连接"""
        self.running = False

        # 等待监听线程结束
        if self.listen_thread and self.listen_thread.is_alive():
            self.listen_thread.join(timeout=1.0)

        # 关闭串口
        if self.ser and self.ser.is_open:
            self.ser.close()

        # 更新状态
        self.status_label.config(text="状态: 未连接", foreground="red")
        self.connect_btn.config(text="连接")

        self.append_text("[系统] 串口已断开", "info")

    def listen_worker(self):
        """监听线程工作函数（后台持续监听串口数据）"""
        self.msg_queue.put(("log", "[监听] 监听线程已启动", "info"))

        while self.running:
            try:
                if self.ser and self.ser.in_waiting > 0:
                    # 读取数据
                    data = self.ser.read(self.ser.in_waiting)

                    # 发送到GUI显示
                    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    self.msg_queue.put(("log", f"[{timestamp}] 接收 {len(data)} 字节", "info"))
                    self.msg_queue.put(("log", f"  HEX: {binascii.hexlify(data).decode()}", "data"))

                    # 尝试ASCII显示（如果可读）
                    try:
                        ascii_str = data.decode('ascii', errors='replace')
                        if ascii_str.isprintable() or '\n' in ascii_str or '\r' in ascii_str:
                            self.msg_queue.put(("log", f"  ASCII: {repr(ascii_str)}", "data"))
                    except:
                        pass

                    # 根据模式决定是否解析协议
                    if self.raw_mode:
                        # 原始字节流模式：只显示字节，不解析
                        self.msg_queue.put(("log", "  [原始模式] 跳过协议解析", "warning"))
                    else:
                        # 协议解析模式：尝试解析协议帧
                        # 添加到解析器缓冲区
                        self.parser.buffer.extend(data)
                        # 尝试解析协议帧
                        self.process_buffer()

                time.sleep(0.01)  # 避免过度占用CPU

            except Exception as e:
                if self.running:  # 只在非主动断开时报错
                    self.msg_queue.put(("log", f"[错误] 监听异常: {e}", "error"))

        self.msg_queue.put(("log", "[监听] 监听线程已停止", "info"))

    def process_buffer(self):
        """处理解析器缓冲区中的数据"""
        while len(self.parser.buffer) > 0:
            # 查找PREAMBLE
            pos, preamble, direction = self.parser.find_preamble(self.parser.buffer)

            if pos == -1:
                # 没有找到有效的PREAMBLE
                # 检查是否有部分PREAMBLE需要保留
                keep_buffer = False
                for preamble_key in self.parser.PREAMBLES.keys():
                    for i in range(1, len(preamble_key)):
                        if self.parser.buffer.endswith(preamble_key[:i]):
                            keep_buffer = True
                            break
                    if keep_buffer:
                        break

                if not keep_buffer:
                    self.parser.buffer.clear()
                break

            # 移除PREAMBLE之前的无效数据
            if pos > 0:
                removed = self.parser.buffer[:pos]
                self.msg_queue.put(("log", f"  [解析] 丢弃 {len(removed)} 字节无效数据", "warning"))
                self.parser.buffer = self.parser.buffer[pos:]

            # 尝试解析帧
            packet_info = self.parser.parse_frame(self.parser.buffer, 0)

            if packet_info:
                # 成功解析到完整的包
                self.msg_queue.put(("packet", packet_info, None))

                # 从缓冲区移除已处理的帧
                self.parser.buffer = self.parser.buffer[packet_info['frame_len']:]
            else:
                # 帧不完整，等待更多数据
                if len(self.parser.buffer) > 1000:  # 防止缓冲区过大
                    self.parser.buffer = self.parser.buffer[1:]
                else:
                    break

    def display_packet(self, packet_info):
        """显示解析后的数据包"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        self.append_text(f"\n{'='*70}", "success")
        self.append_text(f"[{timestamp}] 收到完整数据包", "success")
        self.append_text(f"  方向: {packet_info['direction']}", "success")
        self.append_text(f"  类型: {packet_info['type_name']} ({packet_info['type']})", "success")
        self.append_text(f"  长度: {packet_info['length']} 字节", "success")
        self.append_text(f"  帧长: {packet_info['frame_len']} 字节", "success")
        self.append_text(f"  数据: {binascii.hexlify(packet_info['data']).decode()}", "data")
        self.append_text(f"  CRC: {binascii.hexlify(packet_info['crc']).decode()}", "info")
        self.append_text(f"  完整帧: {binascii.hexlify(packet_info['frame']).decode()}", "info")
        self.append_text(f"{'='*70}", "success")

    def process_queue(self):
        """处理消息队列（定时器，在主线程中执行）"""
        try:
            while True:
                # 非阻塞地获取队列消息
                msg_type, content, tag = self.msg_queue.get_nowait()

                if msg_type == "log":
                    self.append_text(content, tag)
                elif msg_type == "packet":
                    self.display_packet(content)

        except queue.Empty:
            pass

        # 每100ms检查一次队列
        self.root.after(100, self.process_queue)

    # ========== 发送命令方法 ==========

    def check_connection(self):
        """检查连接状态"""
        if not self.running or not self.simulator:
            messagebox.showwarning("未连接", "请先连接串口")
            return False
        return True

    def send_init_sequence(self):
        """发送初始化序列"""
        if not self.check_connection():
            return

        self.append_text("\n[发送] ========== 初始化序列 ==========", "warning")

        try:
            # 1. STATUS
            self.simulator.send_status(0x53)
            self.append_text("[发送] > SU_STATUS (软件复位)", "warning")
            time.sleep(0.5)

            # 2. REBOOTED
            self.simulator.send_rebooted(0x0001)
            self.append_text("[发送] > SU_REBOOTED (Station ID: 0x0001)", "warning")
            time.sleep(0.5)

            # 3. 网络状态：尝试加入
            self.simulator.send_network_status(0)
            self.append_text("[发送] > SU_NETWORK_REPLY (尝试加入)", "warning")
            time.sleep(1)

            # 4. 网络状态：发现网络
            self.simulator.send_network_status(1)
            self.append_text("[发送] > SU_NETWORK_REPLY (发现网络)", "warning")
            time.sleep(1)

            # 5. 网络状态：连接建立
            self.simulator.send_network_status(2)
            self.append_text("[发送] > SU_NETWORK_REPLY (连接建立)", "warning")

            self.append_text("[发送] ========== 初始化序列完成 ==========\n", "warning")

        except Exception as e:
            self.append_text(f"[错误] 发送失败: {e}", "error")

    def send_status(self):
        """发送STATUS"""
        if not self.check_connection():
            return
        try:
            self.simulator.send_status(0x53)
            self.append_text("[发送] > SU_STATUS (软件复位)", "warning")
        except Exception as e:
            self.append_text(f"[错误] 发送失败: {e}", "error")

    def send_rebooted(self):
        """发送REBOOTED"""
        if not self.check_connection():
            return
        try:
            self.simulator.send_rebooted(0x0001)
            self.append_text("[发送] > SU_REBOOTED (Station ID: 0x0001)", "warning")
        except Exception as e:
            self.append_text(f"[错误] 发送失败: {e}", "error")

    def send_network_status(self):
        """发送网络状态"""
        if not self.check_connection():
            return
        try:
            self.simulator.send_network_status(2)
            self.append_text("[发送] > SU_NETWORK_REPLY (连接建立)", "warning")
        except Exception as e:
            self.append_text(f"[错误] 发送失败: {e}", "error")

    def send_version_request(self):
        """发送版本查询"""
        if not self.check_connection():
            return
        try:
            self.simulator.send_version_request()
            self.append_text("[发送] > SU_VERSION_REQUEST", "warning")
        except Exception as e:
            self.append_text(f"[错误] 发送失败: {e}", "error")

    def send_gps_status_request(self):
        """发送GPS状态查询"""
        if not self.check_connection():
            return
        try:
            self.simulator.send_gps_status_request()
            self.append_text("[发送] > SU_GPS_STATUS_REQUEST", "warning")
        except Exception as e:
            self.append_text(f"[错误] 发送失败: {e}", "error")

    def send_gps_position_request(self):
        """发送GPS位置查询"""
        if not self.check_connection():
            return
        try:
            self.simulator.send_gps_position_request()
            self.append_text("[发送] > SU_GPS_POSITION_REQUEST", "warning")
        except Exception as e:
            self.append_text(f"[错误] 发送失败: {e}", "error")

    def send_gps_time_request(self):
        """发送GPS时间查询"""
        if not self.check_connection():
            return
        try:
            self.simulator.send_gps_time_request()
            self.append_text("[发送] > SU_GPS_TIME_REQUEST", "warning")
        except Exception as e:
            self.append_text(f"[错误] 发送失败: {e}", "error")

    def send_station_id_request(self):
        """发送站点ID查询"""
        if not self.check_connection():
            return
        try:
            self.simulator.send_station_id_request()
            self.append_text("[发送] > SU_STATION_ID_REQUEST", "warning")
        except Exception as e:
            self.append_text(f"[错误] 发送失败: {e}", "error")

    def send_echo(self):
        """发送ECHO测试"""
        if not self.check_connection():
            return
        try:
            self.simulator.send_echo(b"TEST")
            self.append_text("[发送] > SU_ECHO (数据: TEST)", "warning")
        except Exception as e:
            self.append_text(f"[错误] 发送失败: {e}", "error")

    def send_data_ack(self):
        """发送数据确认"""
        if not self.check_connection():
            return
        try:
            self.simulator.send_data_ack(0x0001, 0x01)
            self.append_text("[发送] > SU_DATA_ACK (ID: 0x0001, Pack: 1)", "warning")
        except Exception as e:
            self.append_text(f"[错误] 发送失败: {e}", "error")

    def send_reset_ub(self):
        """发送UB复位命令"""
        if not self.check_connection():
            return
        try:
            # 确认操作
            if messagebox.askyesno("确认", "确定要复位UB吗？"):
                self.simulator.send_reset_ub()
                self.append_text("[发送] > SU_RESET_UB (UB复位命令)", "warning")
        except Exception as e:
            self.append_text(f"[错误] 发送失败: {e}", "error")

    def on_closing(self):
        """窗口关闭事件"""
        if self.running:
            self.disconnect_serial()
        self.root.destroy()


def main():
    """主函数"""
    root = tk.Tk()
    app = RadioGUI(root)

    # 绑定窗口关闭事件
    root.protocol("WM_DELETE_WINDOW", app.on_closing)

    # 启动GUI主循环
    root.mainloop()


if __name__ == "__main__":
    main()
