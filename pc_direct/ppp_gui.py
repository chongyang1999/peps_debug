#!/usr/bin/env python3
import argparse
import queue
import struct
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

import serial

# PPP constants
FLAG = 0x7E
ESC = 0x7D
ESC_MASK = 0x20
PPP_ADDRESS = 0xFF
PPP_CONTROL = 0x03
PPP_PROTO_LCP = 0xC021
PPP_PROTO_IPCP = 0x8021
PPP_PROTO_IP = 0x0021
PPP_GOOD_FCS = 0xF0B8

FCS16TAB = (
    0x0000, 0x1189, 0x2312, 0x329b, 0x4624, 0x57ad, 0x6536, 0x74bf,
    0x8c48, 0x9dc1, 0xaf5a, 0xbed3, 0xca6c, 0xdbe5, 0xe97e, 0xf8f7,
    0x1081, 0x0108, 0x3393, 0x221a, 0x56a5, 0x472c, 0x75b7, 0x643e,
    0x9cc9, 0x8d40, 0xbfdb, 0xae52, 0xdaed, 0xcb64, 0xf9ff, 0xe876,
    0x2102, 0x308b, 0x0210, 0x1399, 0x6726, 0x76af, 0x4434, 0x55bd,
    0xad4a, 0xbcc3, 0x8e58, 0x9fd1, 0xeb6e, 0xfae7, 0xc87c, 0xd9f5,
    0x3183, 0x200a, 0x1291, 0x0318, 0x77a7, 0x662e, 0x54b5, 0x453c,
    0xbdcb, 0xac42, 0x9ed9, 0x8f50, 0xfbef, 0xea66, 0xd8fd, 0xc974,
    0x4204, 0x538d, 0x6116, 0x709f, 0x0420, 0x15a9, 0x2732, 0x36bb,
    0xce4c, 0xdfc5, 0xed5e, 0xfcd7, 0x8868, 0x99e1, 0xab7a, 0xbaf3,
    0x5285, 0x430c, 0x7197, 0x601e, 0x14a1, 0x0528, 0x37b3, 0x263a,
    0xdecd, 0xcf44, 0xfddf, 0xec56, 0x98e9, 0x8960, 0xbbfb, 0xaa72,
    0x6306, 0x728f, 0x4014, 0x519d, 0x2522, 0x34ab, 0x0630, 0x17b9,
    0xef4e, 0xfec7, 0xcc5c, 0xddd5, 0xa96a, 0xb8e3, 0x8a78, 0x9bf1,
    0x7387, 0x620e, 0x5095, 0x411c, 0x35a3, 0x242a, 0x16b1, 0x0738,
    0xffcf, 0xee46, 0xdcdd, 0xcd54, 0xb9eb, 0xa862, 0x9af9, 0x8b70,
    0x8408, 0x9581, 0xa71a, 0xb693, 0xc22c, 0xd3a5, 0xe13e, 0xf0b7,
    0x0840, 0x19c9, 0x2b52, 0x3adb, 0x4e64, 0x5fed, 0x6d76, 0x7cff,
    0x9489, 0x8500, 0xb79b, 0xa612, 0xd2ad, 0xc324, 0xf1bf, 0xe036,
    0x18c1, 0x0948, 0x3bd3, 0x2a5a, 0x5ee5, 0x4f6c, 0x7df7, 0x6c7e,
    0xa50a, 0xb483, 0x8618, 0x9791, 0xe32e, 0xf2a7, 0xc03c, 0xd1b5,
    0x2942, 0x38cb, 0x0a50, 0x1bd9, 0x6f66, 0x7eef, 0x4c74, 0x5dfd,
    0xb58b, 0xa402, 0x9699, 0x8710, 0xf3af, 0xe226, 0xd0bd, 0xc134,
    0x39c3, 0x284a, 0x1ad1, 0x0b58, 0x7fe7, 0x6e6e, 0x5cf5, 0x4d7c,
    0xc60c, 0xd785, 0xe51e, 0xf497, 0x8028, 0x91a1, 0xa33a, 0xb2b3,
    0x4a44, 0x5bcd, 0x6956, 0x78df, 0x0c60, 0x1de9, 0x2f72, 0x3efb,
    0xd68d, 0xc704, 0xf59f, 0xe416, 0x90a9, 0x8120, 0xb3bb, 0xa232,
    0x5ac5, 0x4b4c, 0x79d7, 0x685e, 0x1ce1, 0x0d68, 0x3ff3, 0x2e7a,
    0xe70e, 0xf687, 0xc41c, 0xd595, 0xa12a, 0xb0a3, 0x8238, 0x93b1,
    0x6b46, 0x7acf, 0x4854, 0x59dd, 0x2d62, 0x3ceb, 0x0e70, 0x1ff9,
    0xf78f, 0xe606, 0xd49d, 0xc514, 0xb1ab, 0xa022, 0x92b9, 0x8330,
    0x7bc7, 0x6a4e, 0x58d5, 0x495c, 0x3de3, 0x2c6a, 0x1ef1, 0x0f78,
)


def calc_fcs(payload: bytes) -> int:
    fcs = 0xFFFF
    for byte in payload:
        fcs = (fcs >> 8) ^ FCS16TAB[(fcs ^ byte) & 0xFF]
    return fcs


def escape_bytes(data: bytes) -> bytes:
    out = bytearray()
    for b in data:
        if b in (FLAG, ESC, 0x11, 0x13):
            out.append(ESC)
            out.append(b ^ ESC_MASK)
        else:
            out.append(b)
    return bytes(out)


def decode_bytes(data: bytes) -> bytes:
    out = bytearray()
    escape = False
    for b in data:
        if escape:
            out.append(b ^ ESC_MASK)
            escape = False
            continue
        if b == ESC:
            escape = True
            continue
        out.append(b)
    return bytes(out)


class PPPWorker(threading.Thread):
    def __init__(self, port, baud, local_ip, peer_ip, log_queue):
        super().__init__(daemon=True)
        self.port = port
        self.baud = baud
        self.local_ip = local_ip
        self.peer_ip = peer_ip
        self.log_queue = log_queue
        self.stop_event = threading.Event()
        self.ser = None
        self.lcp_id = 1
        self.ipcp_id = 1
        self.lcp_remote_open = False
        self.lcp_local_open = False
        self.ipcp_remote_open = False
        self.ipcp_local_open = False

    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.log_queue.put(f"[{timestamp}] {message}")

    def stop(self):
        self.stop_event.set()

    def close_serial(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

    def run(self):
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baud,
                timeout=0.2,
            )
        except serial.SerialException as exc:
            self.log(f"串口打开失败: {exc}")
            return

        self.log(f"串口 {self.port} @ {self.baud} 已打开，等待 UB ...")
        try:
            self.negotiate()
        except Exception as exc:
            self.log(f"PPP 过程异常: {exc}")
        finally:
            self.close_serial()
            self.log("串口已关闭")

    def send_frame(self, protocol: int, payload: bytes):
        header = bytes([PPP_ADDRESS, PPP_CONTROL]) + struct.pack("!H", protocol)
        core = header + payload
        fcs = calc_fcs(core)
        fcs = (~fcs) & 0xFFFF
        frame = bytearray([FLAG])
        frame += escape_bytes(core + struct.pack("<H", fcs))
        frame.append(FLAG)
        self.ser.write(frame)
        self.log(f"TX proto=0x{protocol:04X} len={len(payload)}")

    def read_frame(self, deadline: float = 5.0):
        buf = bytearray()
        start = time.time()
        inside = False
        while not self.stop_event.is_set():
            if deadline and (time.time() - start) > deadline:
                return None
            chunk = self.ser.read(1)
            if not chunk:
                continue
            b = chunk[0]
            if b == FLAG:
                if inside and buf:
                    raw = decode_bytes(buf)
                    buf.clear()
                    inside = False
                    if not raw:
                        continue
                    fcs = calc_fcs(raw)
                    if fcs != PPP_GOOD_FCS:
                        self.log("收到帧 FCS 错误")
                        continue
                    return raw
                inside = True
                buf.clear()
                continue
            if inside:
                buf.append(b)
        return None

    def negotiate(self):
        self.log("发送 LCP Configure-Request")
        self._send_lcp_request()
        last_tx = time.time()

        while not self.stop_event.is_set():
            frame = self.read_frame()
            if frame is None:
                if not self.lcp_local_open and (time.time() - last_tx) > 2:
                    self.lcp_id = (self.lcp_id + 1) & 0xFF or 1
                    self.log("重发 LCP Configure-Request")
                    self._send_lcp_request()
                    last_tx = time.time()
                continue

            protocol = struct.unpack("!H", frame[2:4])[0]
            payload = frame[4:-2]
            if protocol == PPP_PROTO_LCP:
                self._handle_lcp(payload)
            elif protocol == PPP_PROTO_IPCP:
                self._handle_ipcp(payload)
            elif protocol == PPP_PROTO_IP:
                self.log(f"RX IP 数据 len={len(payload)} 前32字节={payload[:16].hex()}")
            else:
                self.log(f"RX 未处理协议 0x{protocol:04X}")

            if self.ipcp_local_open and self.ipcp_remote_open:
                self.log(f"PPP 链路建立，Local={self.local_ip}, Peer={self.peer_ip}")
                self._stream_frames()
                break

    def _stream_frames(self):
        while not self.stop_event.is_set():
            frame = self.read_frame(deadline=0)
            if frame is None:
                continue
            protocol = struct.unpack("!H", frame[2:4])[0]
            payload = frame[4:-2]
            direction = "RX"
            if protocol == PPP_PROTO_IP:
                self.log(f"{direction} IP len={len(payload)} data={payload[:16].hex()}")
            else:
                self.log(f"{direction} proto=0x{protocol:04X} len={len(payload)}")

    def _send_lcp_request(self):
        opts = bytearray()
        opts += bytes([0x01, 0x04, 0x05, 0xDC])  # MRU=1500
        opts += bytes([0x02, 0x06, 0x00, 0x00, 0x00, 0x00])  # ACCM=0
        length = len(opts) + 4
        payload = bytes([0x01, self.lcp_id]) + struct.pack("!H", length) + opts
        self.send_frame(PPP_PROTO_LCP, payload)

    def _send_ipcp_request(self):
        req_ip = bytes(map(int, self.local_ip.split(".")))
        opts = bytes([0x03, 0x06]) + req_ip
        length = len(opts) + 4
        payload = bytes([0x01, self.ipcp_id]) + struct.pack("!H", length) + opts
        self.send_frame(PPP_PROTO_IPCP, payload)

    def _send_config_ack(self, protocol: int, ident: int, data: bytes):
        payload = bytes([0x02, ident]) + struct.pack("!H", len(data) + 4) + data
        self.send_frame(protocol, payload)

    def _handle_lcp(self, payload: bytes):
        if len(payload) < 4:
            return
        code = payload[0]
        ident = payload[1]
        length = struct.unpack("!H", payload[2:4])[0]
        data = payload[4:length]
        if code == 0x01:
            self.log(f"RX LCP Configure-Request id={ident}")
            self._send_config_ack(PPP_PROTO_LCP, ident, data)
            self.lcp_remote_open = True
        elif code == 0x02:
            self.log(f"RX LCP Configure-Ack id={ident}")
            self.lcp_local_open = True
            if not self.ipcp_local_open:
                self.log("发送 IPCP Configure-Request")
                self._send_ipcp_request()
        elif code == 0x05:
            self.log("RX LCP Terminate-Request")
            payload = bytes([0x06, ident, 0x00, 0x04])
            self.send_frame(PPP_PROTO_LCP, payload)
            self.lcp_local_open = False
        else:
            self.log(f"RX LCP 未处理 code={code}")

    def _handle_ipcp(self, payload: bytes):
        if len(payload) < 4:
            return
        code = payload[0]
        ident = payload[1]
        length = struct.unpack("!H", payload[2:4])[0]
        data = payload[4:length]
        if code == 0x01:
            self.log(f"RX IPCP Configure-Request id={ident}")
            self._parse_peer_ip(data)
            self._send_config_ack(PPP_PROTO_IPCP, ident, data)
            self.ipcp_remote_open = True
        elif code == 0x02:
            self.log(f"RX IPCP Configure-Ack id={ident}")
            self.ipcp_local_open = True
        elif code == 0x03:
            self.log(f"RX IPCP Configure-Nak id={ident}")
            if len(data) >= 6 and data[0] == 0x03:
                self.local_ip = ".".join(str(b) for b in data[2:6])
                self.log(f"UB 请求使用本地 IP {self.local_ip}")
                self.ipcp_id = (self.ipcp_id + 1) & 0xFF or 1
                self._send_ipcp_request()
        else:
            self.log(f"RX IPCP 未处理 code={code}")

    def _parse_peer_ip(self, data: bytes):
        idx = 0
        while idx < len(data):
            opt = data[idx]
            opt_len = data[idx + 1]
            if opt == 0x03 and opt_len == 6:
                self.peer_ip = ".".join(str(b) for b in data[idx + 2:idx + 6])
                self.log(f"UB 提供对端 IP: {self.peer_ip}")
            idx += opt_len


class PPPGui:
    def __init__(self, root):
        self.root = root
        self.root.title("UB Test Port PPP Monitor")
        self.log_queue = queue.Queue()
        self.worker = None

        self._build_widgets()
        self._poll_log_queue()

    def _build_widgets(self):
        frm = ttk.Frame(self.root, padding=10)
        frm.grid(row=0, column=0, sticky="nsew")

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        frm.columnconfigure(1, weight=1)
        frm.rowconfigure(4, weight=1)

        ttk.Label(frm, text="串口:").grid(row=0, column=0, sticky="w")
        self.port_var = tk.StringVar(value="COM4")
        ttk.Entry(frm, textvariable=self.port_var, width=12).grid(row=0, column=1, sticky="w")

        ttk.Label(frm, text="波特率:").grid(row=1, column=0, sticky="w")
        self.baud_var = tk.StringVar(value="115200")
        ttk.Entry(frm, textvariable=self.baud_var, width=12).grid(row=1, column=1, sticky="w")

        ttk.Label(frm, text="本地 IP:").grid(row=0, column=2, sticky="w")
        self.local_ip_var = tk.StringVar(value="192.168.200.10")
        ttk.Entry(frm, textvariable=self.local_ip_var, width=15).grid(row=0, column=3, sticky="w")

        ttk.Label(frm, text="对端 IP:").grid(row=1, column=2, sticky="w")
        self.peer_ip_var = tk.StringVar(value="192.168.200.1")
        ttk.Entry(frm, textvariable=self.peer_ip_var, width=15).grid(row=1, column=3, sticky="w")

        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=2, column=0, columnspan=4, pady=(5, 5), sticky="w")
        ttk.Button(btn_frame, text="连接", command=self.start_connection).grid(row=0, column=0, padx=5)
        ttk.Button(btn_frame, text="断开", command=self.stop_connection).grid(row=0, column=1, padx=5)

        self.text = tk.Text(frm, height=20)
        self.text.grid(row=4, column=0, columnspan=4, sticky="nsew")
        scrollbar = ttk.Scrollbar(frm, orient="vertical", command=self.text.yview)
        scrollbar.grid(row=4, column=4, sticky="ns")
        self.text["yscrollcommand"] = scrollbar.set

    def start_connection(self):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("提示", "连接已在运行")
            return
        port = self.port_var.get().strip()
        try:
            baud = int(self.baud_var.get().strip())
        except ValueError:
            messagebox.showerror("错误", "波特率必须为数字")
            return
        local_ip = self.local_ip_var.get().strip()
        peer_ip = self.peer_ip_var.get().strip()
        self.worker = PPPWorker(port, baud, local_ip, peer_ip, self.log_queue)
        self.worker.start()
        self.append_log("=== PPP 任务启动 ===")

    def stop_connection(self):
        if self.worker:
            self.worker.stop()
            self.worker = None
            self.append_log("=== PPP 任务请求停止 ===")

    def append_log(self, message: str):
        self.text.insert("end", message + "\n")
        self.text.see("end")

    def _poll_log_queue(self):
        while True:
            try:
                msg = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self.append_log(msg)
        self.root.after(100, self._poll_log_queue)


def main():
    parser = argparse.ArgumentParser(description="UB PPP monitor GUI")
    parser.add_argument("--no-gui", action="store_true", help="仅验证依赖")
    args = parser.parse_args()
    if args.no_gui:
        print("GUI mode disabled via --no-gui")
        return
    root = tk.Tk()
    PPPGui(root)
    root.mainloop()


if __name__ == "__main__":
    main()
