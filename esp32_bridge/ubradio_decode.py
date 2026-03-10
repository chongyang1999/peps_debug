import binascii
import time

import board
import busio


# XIAO ESP32C3: D0=TX, D1=RX
uart = busio.UART(tx=board.D0, rx=board.D1, baudrate=38400, receiver_buffer_size=4096)

PREAMBLE_TX = b"  !SU2LS!"
PREAMBLE_RX = b"  !LS2SU!"
ETX = 0xFF
MAX_LOGS = 32

rx_buffer = bytearray()
logs = []

print("UART Protocol Stack Loaded.")


def calculate_crc(data_bytes):
    crc_int = binascii.crc32(data_bytes) & 0xFFFFFFFF
    return crc_int.to_bytes(4, "big")


def pack_frame(cmd_type_char, payload=b""):
    if isinstance(cmd_type_char, str):
        type_byte = cmd_type_char.encode()
    else:
        type_byte = bytes([cmd_type_char])

    length_int = 1 + len(payload) + 4 + 1
    length_byte = bytes([length_int])
    crc_input = length_byte + type_byte + payload
    crc_bytes = calculate_crc(crc_input)
    return PREAMBLE_TX + length_byte + type_byte + payload + crc_bytes + bytes([ETX])


def _ascii_repr(data):
    return "".join(chr(b) if 32 <= b <= 126 else "." for b in data)


def _add_log(entry):
    logs.append(entry)
    if len(logs) > MAX_LOGS:
        del logs[0]


def parse_frame(buffer):
    start_idx = buffer.find(PREAMBLE_RX)
    if start_idx == -1:
        keep_len = len(PREAMBLE_RX) - 1
        if len(buffer) > keep_len:
            return False, "Waiting for Preamble", buffer[-keep_len:]
        return False, "Waiting for Preamble", buffer

    buffer = buffer[start_idx:]

    if len(buffer) < 10:
        return False, "Waiting for Length", buffer

    pkt_len = buffer[9]
    total_frame_len = 9 + 1 + pkt_len
    if len(buffer) < total_frame_len:
        return False, f"Receiving... ({len(buffer)}/{total_frame_len})", buffer

    frame = buffer[:total_frame_len]
    remaining = buffer[total_frame_len:]

    # LENGTH covers TYPE(1) + DATA(n) + CRC(4) + ETX(1)
    # So payload length is pkt_len - 6.
    data_len = pkt_len - 6
    received_crc = frame[-5:-1]
    expected_etx = frame[-1]

    if expected_etx != ETX:
        print("[Error] ETX mismatch!")
        return False, "ETX Error", buffer[1:]

    # CRC is computed over LENGTH + TYPE + DATA.
    crc_input_data = frame[9 : 9 + 1 + 1 + data_len]
    calculated_crc = calculate_crc(crc_input_data)
    if received_crc != calculated_crc:
        print("[Error] CRC Fail! Recv:%s Calc:%s Frame:%s" % (
            received_crc.hex(),
            calculated_crc.hex(),
            binascii.hexlify(frame).decode()
        ))
        return False, "CRC Fail", buffer[1:]

    cmd_type = chr(frame[10])
    payload_data = frame[11 : 11 + data_len]
    result = {
        "raw_hex": binascii.hexlify(frame).decode(),
        "length": pkt_len,
        "type": cmd_type,
        "data_hex": binascii.hexlify(payload_data, " ").decode(),
        "data_ascii": _ascii_repr(payload_data),
        "recv_crc": received_crc.hex(),
        "calc_crc": calculated_crc.hex(),
        "crc_ok": True,
    }
    return True, result, remaining


def send_command(cmd_type_char, payload=b""):
    frame = pack_frame(cmd_type_char, payload)
    uart.write(frame)
    entry = {
        "dir": "tx",
        "raw_hex": binascii.hexlify(frame).decode(),
        "length": frame[9],
        "type": chr(frame[10]),
        "data_hex": binascii.hexlify(payload, " ").decode(),
        "data_ascii": _ascii_repr(payload),
        "recv_crc": "",
        "calc_crc": frame[-5:-1].hex(),
        "crc_ok": True,
    }
    _add_log(entry)
    print("[TX] Type: %s" % entry["type"])
    print("   Data: %s (%s)" % (entry["data_ascii"], entry["data_hex"]))
    return frame


def q(cmd_type_char, payload=b""):
    return send_command(cmd_type_char, payload)


def poll_uart_once():
    global rx_buffer
    frames = []

    if not uart.in_waiting:
        return frames

    chunk = uart.read(uart.in_waiting)
    if not chunk:
        return frames

    rx_buffer.extend(chunk)

    while True:
        success, res, remaining = parse_frame(rx_buffer)
        if success:
            res["dir"] = "rx"
            _add_log(res)
            frames.append(res)
            rx_buffer = bytearray(remaining)
            continue
        if res in ("ETX Error", "CRC Fail"):
            rx_buffer = bytearray(remaining)
            continue
        break

    return frames


def read_frames(timeout_ms=1000, verbose=True):
    deadline = time.monotonic() + (timeout_ms / 1000.0)
    collected = []

    while time.monotonic() < deadline:
        frames = poll_uart_once()
        if frames:
            collected.extend(frames)
            if verbose:
                for res in frames:
                    print("[VALID FRAME] Type: %s" % res["type"])
                    print("   Data: %s (%s)" % (res["data_ascii"], res["data_hex"]))
        time.sleep(0.01)

    return collected


def get_logs():
    return list(logs)


def clear_logs():
    global rx_buffer
    logs.clear()
    rx_buffer = bytearray()


def rx_loop():
    print("Listening for valid frames...")

    try:
        while True:
            read_frames(100, verbose=True)
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("Stopped.")


def send_query():
    print("Sending Query Version (V)...")
    send_command("V")
    rx_loop()
