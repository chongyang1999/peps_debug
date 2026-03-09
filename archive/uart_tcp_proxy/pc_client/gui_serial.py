import threading
import time
import zlib
from datetime import datetime
from tkinter import BOTH, END, LEFT, RIGHT, TOP, Button, Entry, Frame, Label, Scrollbar, Text, Tk, ttk, StringVar

import serial  # pyserial


PREAMBLE_SU2LS = bytes.fromhex("20 20 21 53 55 32 4C 53 21")  # "  !SU2LS!"
ETX = 0xFF

COMMON_COMMANDS = [
    ("ID request (U)", b"U"),
    ("Reset UB (T)", b"T"),
    ("Radio reset (R)", b"R"),
    ("Version query (V)", b"V"),
    ("GPS status (G)", b"G"),
    ("GPS position (P)", b"P"),
    ("GPS time (M)", b"M"),
    ("Echo test (E) with text 'PING'", b"E" + b"PING"),
    ("Network status (N)", b"N"),
    ("Buffer status (B)", b"B"),
    ("Control (C) <no data>", b"C"),
]


def bytes_to_hex(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data)


def bytes_to_printable(data: bytes) -> str:
    return "".join(chr(b) if 32 <= b <= 126 else "." for b in data)


def pack_frame(type_and_data: bytes) -> bytes:
    """Build Radio->UB frame: PREAMBLE + LENGTH + TYPE+DATA + CRC32 + ETX."""
    # LENGTH counts TYPE+DATA + CRC32 (4B) + ETX (1B)
    length = len(type_and_data) + 4 + 1
    length_byte = length.to_bytes(1, "big", signed=False)
    crc_input = length_byte + type_and_data
    crc_val = zlib.crc32(crc_input) & 0xFFFFFFFF
    crc_bytes = crc_val.to_bytes(4, "big")
    return PREAMBLE_SU2LS + length_byte + type_and_data + crc_bytes + bytes([ETX])


class SerialGUI:
    def __init__(self, master: Tk):
        self.master = master
        master.title("RS-232 Bridge Helper")

        self.port_var = StringVar(value="COM5")
        self.baud_var = StringVar(value="38400")
        self.send_mode = StringVar(value="ascii")
        self.cmd_choice = StringVar(value=COMMON_COMMANDS[0][0])

        self.ser = None
        self.reader_thread = None
        self.stop_event = threading.Event()

        self._build_ui()

    def _build_ui(self):
        top_frame = Frame(self.master)
        top_frame.pack(fill=BOTH, padx=8, pady=4)

        Label(top_frame, text="Port").pack(side=LEFT)
        Entry(top_frame, width=10, textvariable=self.port_var).pack(side=LEFT, padx=4)

        Label(top_frame, text="Baud").pack(side=LEFT)
        Entry(top_frame, width=10, textvariable=self.baud_var).pack(side=LEFT, padx=4)

        self.connect_btn = Button(top_frame, text="Connect", command=self.toggle_connect, width=12)
        self.connect_btn.pack(side=LEFT, padx=6)

        clear_btn = Button(top_frame, text="Clear Log", command=self.clear_log, width=10)
        clear_btn.pack(side=LEFT, padx=6)

        # Send controls
        send_frame = Frame(self.master)
        send_frame.pack(fill=BOTH, padx=8, pady=4)

        Label(send_frame, text="Command:").pack(side=LEFT)
        self.cmd_menu = ttk.OptionMenu(
            send_frame,
            self.cmd_choice,
            self.cmd_choice.get(),
            *[c[0] for c in COMMON_COMMANDS],
        )
        self.cmd_menu.pack(side=LEFT, padx=4)

        send_btn = Button(send_frame, text="Send", command=self.send_common, width=12)
        send_btn.pack(side=LEFT, padx=4)

        # Raw send controls (optional manual override)
        Label(send_frame, text="Raw:").pack(side=LEFT, padx=(16, 2))
        self.send_entry = Entry(send_frame, width=40)
        self.send_entry.pack(side=LEFT, padx=4, fill=BOTH, expand=True)

        mode_menu = ttk.OptionMenu(send_frame, self.send_mode, self.send_mode.get(), "ascii", "hex")
        mode_menu.pack(side=LEFT, padx=4)

        raw_btn = Button(send_frame, text="Send Raw", command=self.send_data, width=10)
        raw_btn.pack(side=LEFT, padx=4)

        # Log area
        log_frame = Frame(self.master)
        log_frame.pack(fill=BOTH, expand=True, padx=8, pady=4)

        self.log_text = Text(log_frame, wrap="none", height=24)
        self.log_text.pack(side=LEFT, fill=BOTH, expand=True)

        scroll_y = Scrollbar(log_frame, command=self.log_text.yview)
        scroll_y.pack(side=RIGHT, fill="y")
        self.log_text.configure(yscrollcommand=scroll_y.set)

        scroll_x = Scrollbar(log_frame, orient="horizontal", command=self.log_text.xview)
        scroll_x.pack(side=TOP, fill="x")
        self.log_text.configure(xscrollcommand=scroll_x.set)

    def log(self, msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        line = f"[{timestamp}] {msg}\n"
        self.log_text.insert(END, line)
        self.log_text.see(END)

    def clear_log(self):
        self.log_text.delete("1.0", END)

    def toggle_connect(self):
        if self.ser and self.ser.is_open:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        port = self.port_var.get().strip()
        try:
            baud = int(self.baud_var.get().strip())
        except ValueError:
            self.log("Invalid baud rate")
            return

        try:
            self.ser = serial.Serial(port=port, baudrate=baud, timeout=0.1)
        except Exception as e:
            self.log(f"Open failed: {e}")
            return

        self.stop_event.clear()
        self.reader_thread = threading.Thread(target=self.read_loop, daemon=True)
        self.reader_thread.start()
        self.connect_btn.configure(text="Disconnect")
        self.log(f"Connected to {port} @ {baud}")

    def disconnect(self):
        self.stop_event.set()
        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=1)

        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
        self.ser = None
        self.connect_btn.configure(text="Connect")
        self.log("Disconnected")

    def read_loop(self):
        while not self.stop_event.is_set():
            try:
                data = self.ser.read(1024)
            except Exception as e:
                self.log(f"Read error: {e}")
                self.stop_event.set()
                break

            if data:
                hex_repr = bytes_to_hex(data)
                ascii_repr = bytes_to_printable(data)
                self.log(f"RX {len(data)} bytes | HEX: {hex_repr} | ASCII: {ascii_repr}")
            else:
                time.sleep(0.02)

    def send_data(self):
        if not self.ser or not self.ser.is_open:
            self.log("Not connected")
            return

        raw = self.send_entry.get()
        if not raw:
            return

        mode = self.send_mode.get()
        try:
            if mode == "hex":
                payload = bytes.fromhex(raw)
            else:
                payload = raw.encode()
        except Exception as e:
            self.log(f"Send parse error: {e}")
            return

        try:
            self.ser.write(payload)
            self.log(f"TX (raw) {len(payload)} bytes | MODE={mode} | {bytes_to_hex(payload)}")
        except Exception as e:
            self.log(f"Send error: {e}")

    def send_common(self):
        """Send a pre-defined command using protocol framing."""
        if not self.ser or not self.ser.is_open:
            self.log("Not connected")
            return

        label = self.cmd_choice.get()
        cmd = next((cmd for lbl, cmd in COMMON_COMMANDS if lbl == label), None)
        if cmd is None:
            self.log("Command not found")
            return

        frame = pack_frame(cmd)
        try:
            self.ser.write(frame)
            self.log(
                f"TX (framed) {len(frame)} bytes | {label} | HEX: {bytes_to_hex(frame)}"
            )
        except Exception as e:
            self.log(f"Send error: {e}")


def main():
    root = Tk()
    app = SerialGUI(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.disconnect(), root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    main()
