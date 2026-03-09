#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
串口通信可视化GUI程序（高级版本）

特性：
1. 支持从JSON配置文件加载命令列表
2. 线程安全的GUI更新
3. 复用现有的protocol_parser.py和radio_simulator.py
4. 实时监听和显示接收数据
5. 彩色文本显示和自动滚动
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import serial
import threading
import queue
import time
import json
from pathlib import Path
from datetime import datetime
import binascii
from protocol_parser import ProtocolParser
from radio_simulator import RadioSimulator


BASE_DIR = Path(__file__).resolve().parent


class RadioGUIAdvanced:
    """串口通信可视化GUI程序（高级版本）

    架构设计：
    - 主线程：运行tkinter GUI事件循环
    - 监听线程：后台持续监听串口数据
    - 线程安全通信：使用queue.Queue在线程间传递消息
    - 配置驱动：从JSON文件加载命令配置
    """

    def __init__(self, root):
        self.root = root
        self.root.title("串口通信调试工具（高级版）")
        self.root.geometry("1000x750")

        # 串口相关
        self.port = 'COM13'
        self.baudrate = 38400
        self.ser = None
        self.simulator = None
        self.parser = None

        # 线程控制
        self.running = False
        self.listen_thread = None

        # 线程安全的消息队列
        self.msg_queue = queue.Queue()

        # 命令配置
        self.commands = []
        self.command_buttons = []

        # 创建GUI界面
        self.create_widgets()

        # 加载默认配置
        self.load_default_commands()

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

        ttk.Button(config_frame, text="加载配置", command=self.load_commands_from_file).grid(row=0, column=6, padx=5)

        # ========== 上半部分：发送命令区 ==========
        send_frame = ttk.LabelFrame(self.root, text="发送命令区", padding=10)
        send_frame.pack(fill=tk.BOTH, padx=10, pady=5, expand=False)

        # 创建可滚动的命令按钮区域
        canvas = tk.Canvas(send_frame, height=180)
        scrollbar = ttk.Scrollbar(send_frame, orient="vertical", command=canvas.yview)
        self.commands_frame = ttk.Frame(canvas)

        self.commands_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.commands_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # ========== 下半部分：监听显示区 ==========
        display_frame = ttk.LabelFrame(self.root, text="接收数据监听区", padding=10)
        display_frame.pack(fill=tk.BOTH, padx=10, pady=5, expand=True)

        # 文本显示框
        self.text_display = scrolledtext.ScrolledText(
            display_frame,
            wrap=tk.WORD,
            width=120,
            height=25,
            font=("Consolas", 9),
            state=tk.DISABLED
        )
        self.text_display.pack(fill=tk.BOTH, expand=True)

        # 配置文本标签
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

        self.show_raw_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(control_frame, text="显示原始数据", variable=self.show_raw_var).pack(side=tk.LEFT, padx=5)

        ttk.Button(control_frame, text="保存日志", command=self.save_log).pack(side=tk.RIGHT, padx=5)

    def load_default_commands(self):
        """加载默认命令配置"""
        default_commands = [
            {
                "id": "init",
                "name": "发送初始化序列",
                "method": "send_init_sequence",
                "description": "发送完整初始化序列",
                "confirm": False
            },
            {
                "id": "status",
                "name": "发送STATUS",
                "method": "send_status",
                "description": "发送SU_STATUS消息",
                "confirm": False
            },
            {
                "id": "rebooted",
                "name": "发送REBOOTED",
                "method": "send_rebooted",
                "description": "发送SU_REBOOTED消息",
                "confirm": False
            },
            {
                "id": "network",
                "name": "发送网络状态",
                "method": "send_network_status",
                "description": "发送网络连接建立消息",
                "confirm": False
            },
            {
                "id": "version",
                "name": "查询版本",
                "method": "send_version_request",
                "description": "查询设备版本",
                "confirm": False
            },
            {
                "id": "gps_status",
                "name": "查询GPS状态",
                "method": "send_gps_status_request",
                "description": "查询GPS状态",
                "confirm": False
            },
            {
                "id": "gps_position",
                "name": "查询GPS位置",
                "method": "send_gps_position_request",
                "description": "查询GPS位置",
                "confirm": False
            },
            {
                "id": "gps_time",
                "name": "查询GPS时间",
                "method": "send_gps_time_request",
                "description": "查询GPS时间",
                "confirm": False
            },
            {
                "id": "station_id",
                "name": "查询站点ID",
                "method": "send_station_id_request",
                "description": "查询站点ID",
                "confirm": False
            },
            {
                "id": "echo",
                "name": "发送ECHO测试",
                "method": "send_echo",
                "description": "发送回显测试",
                "confirm": False
            },
            {
                "id": "data_ack",
                "name": "发送数据确认",
                "method": "send_data_ack",
                "description": "发送数据确认消息",
                "confirm": False
            },
            {
                "id": "reset_ub",
                "name": "复位UB",
                "method": "send_reset_ub",
                "description": "发送UB复位命令",
                "confirm": True
            }
        ]

        self.commands = default_commands
        self.create_command_buttons()

    def load_commands_from_file(self):
        """从JSON文件加载命令配置"""
        filename = filedialog.askopenfilename(
            title="选择命令配置文件",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")],
            initialdir=str(BASE_DIR),
            initialfile="commands_config.json"
        )

        if not filename:
            return

        try:
            with open(filename, 'r', encoding='utf-8') as f:
                config = json.load(f)

            if 'commands' not in config:
                messagebox.showerror("配置错误", "配置文件格式错误：缺少'commands'字段")
                return

            self.commands = config['commands']
            self.create_command_buttons()

            self.append_text(f"[系统] 成功加载配置文件: {filename}", "success")
            self.append_text(f"[系统] 加载了 {len(self.commands)} 个命令", "info")

        except Exception as e:
            messagebox.showerror("加载失败", f"无法加载配置文件: {e}")
            self.append_text(f"[错误] 加载配置失败: {e}", "error")

    def create_command_buttons(self):
        """根据配置创建命令按钮"""
        # 清除现有按钮
        for widget in self.commands_frame.winfo_children():
            widget.destroy()
        self.command_buttons.clear()

        # 创建新按钮（每行4个）
        for idx, cmd in enumerate(self.commands):
            row = idx // 4
            col = idx % 4

            # 创建按钮点击回调
            def make_callback(command):
                def callback():
                    self.execute_command(command)
                return callback

            btn = ttk.Button(
                self.commands_frame,
                text=cmd['name'],
                command=make_callback(cmd),
                width=22
            )
            btn.grid(row=row, column=col, padx=5, pady=5)

            # 添加工具提示（如果有描述）
            if 'description' in cmd:
                self.create_tooltip(btn, cmd['description'])

            self.command_buttons.append(btn)

    def create_tooltip(self, widget, text):
        """创建工具提示"""
        def on_enter(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")

            label = tk.Label(
                tooltip,
                text=text,
                background="yellow",
                relief="solid",
                borderwidth=1,
                font=("Arial", 9)
            )
            label.pack()

            widget.tooltip = tooltip

        def on_leave(event):
            if hasattr(widget, 'tooltip'):
                widget.tooltip.destroy()
                del widget.tooltip

        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)

    def execute_command(self, command):
        """执行命令"""
        if not self.check_connection():
            return

        # 如果需要确认
        if command.get('confirm', False):
            if not messagebox.askyesno("确认", f"确定要执行命令：{command['name']}？"):
                return

        # 执行对应的方法
        method_name = command['method']
        if hasattr(self, method_name):
            method = getattr(self, method_name)
            try:
                method()
            except Exception as e:
                self.append_text(f"[错误] 执行命令失败: {e}", "error")
        else:
            self.append_text(f"[错误] 未找到方法: {method_name}", "error")

    def append_text(self, text, tag="info"):
        """线程安全地向文本框追加内容"""
        self.text_display.config(state=tk.NORMAL)
        self.text_display.insert(tk.END, text + "\n", tag)

        if self.auto_scroll_var.get():
            self.text_display.see(tk.END)

        self.text_display.config(state=tk.DISABLED)

    def clear_display(self):
        """清空显示区"""
        self.text_display.config(state=tk.NORMAL)
        self.text_display.delete(1.0, tk.END)
        self.text_display.config(state=tk.DISABLED)

    def save_log(self):
        """保存日志到文件"""
        filename = filedialog.asksaveasfilename(
            title="保存日志",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            initialfile=f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        if filename:
            try:
                content = self.text_display.get(1.0, tk.END)
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                messagebox.showinfo("成功", f"日志已保存到: {filename}")
            except Exception as e:
                messagebox.showerror("保存失败", f"无法保存日志: {e}")

    def toggle_connection(self):
        """切换连接状态"""
        if not self.running:
            self.connect_serial()
        else:
            self.disconnect_serial()

    def connect_serial(self):
        """连接串口并启动监听线程"""
        try:
            self.port = self.port_var.get()
            self.baudrate = int(self.baudrate_var.get())

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

            self.simulator = RadioSimulator(self.port, self.baudrate)
            self.simulator.ser = self.ser

            self.parser = ProtocolParser(self.port, self.baudrate)
            self.parser.ser = self.ser
            self.parser.buffer = bytearray()

            self.running = True
            self.status_label.config(text=f"状态: 已连接 ({self.port})", foreground="green")
            self.connect_btn.config(text="断开")

            self.append_text(f"[系统] 成功连接到 {self.port}, 波特率 {self.baudrate}", "success")

            self.listen_thread = threading.Thread(target=self.listen_worker, daemon=True)
            self.listen_thread.start()

        except Exception as e:
            messagebox.showerror("连接错误", f"无法打开串口: {e}")
            self.append_text(f"[错误] 连接失败: {e}", "error")

    def disconnect_serial(self):
        """断开串口连接"""
        self.running = False

        if self.listen_thread and self.listen_thread.is_alive():
            self.listen_thread.join(timeout=1.0)

        if self.ser and self.ser.is_open:
            self.ser.close()

        self.status_label.config(text="状态: 未连接", foreground="red")
        self.connect_btn.config(text="连接")

        self.append_text("[系统] 串口已断开", "info")

    def listen_worker(self):
        """监听线程工作函数"""
        self.msg_queue.put(("log", "[监听] 监听线程已启动", "info"))

        while self.running:
            try:
                if self.ser and self.ser.in_waiting > 0:
                    data = self.ser.read(self.ser.in_waiting)

                    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

                    if self.show_raw_var.get():
                        self.msg_queue.put(("log", f"[{timestamp}] 接收 {len(data)} 字节", "info"))
                        self.msg_queue.put(("log", f"  HEX: {binascii.hexlify(data).decode()}", "data"))

                        try:
                            ascii_str = data.decode('ascii', errors='replace')
                            if any(c.isprintable() or c in '\n\r' for c in ascii_str):
                                self.msg_queue.put(("log", f"  ASCII: {repr(ascii_str)}", "data"))
                        except:
                            pass

                    self.parser.buffer.extend(data)
                    self.process_buffer()

                time.sleep(0.01)

            except Exception as e:
                if self.running:
                    self.msg_queue.put(("log", f"[错误] 监听异常: {e}", "error"))

        self.msg_queue.put(("log", "[监听] 监听线程已停止", "info"))

    def process_buffer(self):
        """处理解析器缓冲区"""
        while len(self.parser.buffer) > 0:
            pos, preamble, direction = self.parser.find_preamble(self.parser.buffer)

            if pos == -1:
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

            if pos > 0:
                self.parser.buffer = self.parser.buffer[pos:]

            packet_info = self.parser.parse_frame(self.parser.buffer, 0)

            if packet_info:
                self.msg_queue.put(("packet", packet_info, None))
                self.parser.buffer = self.parser.buffer[packet_info['frame_len']:]
            else:
                if len(self.parser.buffer) > 1000:
                    self.parser.buffer = self.parser.buffer[1:]
                else:
                    break

    def display_packet(self, packet_info):
        """显示解析后的数据包"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        self.append_text(f"\n{'='*80}", "success")
        self.append_text(f"[{timestamp}] 收到完整数据包", "success")
        self.append_text(f"  方向: {packet_info['direction']}", "success")
        self.append_text(f"  类型: {packet_info['type_name']} ({packet_info['type']})", "success")
        self.append_text(f"  长度: {packet_info['length']} 字节", "success")
        self.append_text(f"  帧长: {packet_info['frame_len']} 字节", "success")

        if len(packet_info['data']) > 0:
            self.append_text(f"  数据: {binascii.hexlify(packet_info['data']).decode()}", "data")

        self.append_text(f"  CRC: {binascii.hexlify(packet_info['crc']).decode()}", "info")
        self.append_text(f"  完整帧: {binascii.hexlify(packet_info['frame']).decode()}", "info")
        self.append_text(f"{'='*80}", "success")

    def process_queue(self):
        """处理消息队列"""
        try:
            while True:
                msg_type, content, tag = self.msg_queue.get_nowait()

                if msg_type == "log":
                    self.append_text(content, tag)
                elif msg_type == "packet":
                    self.display_packet(content)

        except queue.Empty:
            pass

        self.root.after(100, self.process_queue)

    def check_connection(self):
        """检查连接状态"""
        if not self.running or not self.simulator:
            messagebox.showwarning("未连接", "请先连接串口")
            return False
        return True

    # ========== 发送命令方法 ==========

    def send_init_sequence(self):
        """发送初始化序列"""
        if not self.check_connection():
            return

        self.append_text("\n[发送] ========== 初始化序列 ==========", "warning")

        try:
            self.simulator.send_status(0x53)
            self.append_text("[发送] > SU_STATUS (软件复位)", "warning")
            time.sleep(0.5)

            self.simulator.send_rebooted(0x0001)
            self.append_text("[发送] > SU_REBOOTED (Station ID: 0x0001)", "warning")
            time.sleep(0.5)

            self.simulator.send_network_status(0)
            self.append_text("[发送] > SU_NETWORK_REPLY (尝试加入)", "warning")
            time.sleep(1)

            self.simulator.send_network_status(1)
            self.append_text("[发送] > SU_NETWORK_REPLY (发现网络)", "warning")
            time.sleep(1)

            self.simulator.send_network_status(2)
            self.append_text("[发送] > SU_NETWORK_REPLY (连接建立)", "warning")

            self.append_text("[发送] ========== 初始化序列完成 ==========\n", "warning")

        except Exception as e:
            self.append_text(f"[错误] 发送失败: {e}", "error")

    def send_status(self):
        if not self.check_connection():
            return
        try:
            self.simulator.send_status(0x53)
            self.append_text("[发送] > SU_STATUS (软件复位)", "warning")
        except Exception as e:
            self.append_text(f"[错误] 发送失败: {e}", "error")

    def send_rebooted(self):
        if not self.check_connection():
            return
        try:
            self.simulator.send_rebooted(0x0001)
            self.append_text("[发送] > SU_REBOOTED (Station ID: 0x0001)", "warning")
        except Exception as e:
            self.append_text(f"[错误] 发送失败: {e}", "error")

    def send_network_status(self):
        if not self.check_connection():
            return
        try:
            self.simulator.send_network_status(2)
            self.append_text("[发送] > SU_NETWORK_REPLY (连接建立)", "warning")
        except Exception as e:
            self.append_text(f"[错误] 发送失败: {e}", "error")

    def send_version_request(self):
        if not self.check_connection():
            return
        try:
            self.simulator.send_version_request()
            self.append_text("[发送] > SU_VERSION_REQUEST", "warning")
        except Exception as e:
            self.append_text(f"[错误] 发送失败: {e}", "error")

    def send_gps_status_request(self):
        if not self.check_connection():
            return
        try:
            self.simulator.send_gps_status_request()
            self.append_text("[发送] > SU_GPS_STATUS_REQUEST", "warning")
        except Exception as e:
            self.append_text(f"[错误] 发送失败: {e}", "error")

    def send_gps_position_request(self):
        if not self.check_connection():
            return
        try:
            self.simulator.send_gps_position_request()
            self.append_text("[发送] > SU_GPS_POSITION_REQUEST", "warning")
        except Exception as e:
            self.append_text(f"[错误] 发送失败: {e}", "error")

    def send_gps_time_request(self):
        if not self.check_connection():
            return
        try:
            self.simulator.send_gps_time_request()
            self.append_text("[发送] > SU_GPS_TIME_REQUEST", "warning")
        except Exception as e:
            self.append_text(f"[错误] 发送失败: {e}", "error")

    def send_station_id_request(self):
        if not self.check_connection():
            return
        try:
            self.simulator.send_station_id_request()
            self.append_text("[发送] > SU_STATION_ID_REQUEST", "warning")
        except Exception as e:
            self.append_text(f"[错误] 发送失败: {e}", "error")

    def send_echo(self):
        if not self.check_connection():
            return
        try:
            self.simulator.send_echo(b"TEST")
            self.append_text("[发送] > SU_ECHO (数据: TEST)", "warning")
        except Exception as e:
            self.append_text(f"[错误] 发送失败: {e}", "error")

    def send_data_ack(self):
        if not self.check_connection():
            return
        try:
            self.simulator.send_data_ack(0x0001, 0x01)
            self.append_text("[发送] > SU_DATA_ACK (ID: 0x0001, Pack: 1)", "warning")
        except Exception as e:
            self.append_text(f"[错误] 发送失败: {e}", "error")

    def send_reset_ub(self):
        if not self.check_connection():
            return
        try:
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
    app = RadioGUIAdvanced(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
