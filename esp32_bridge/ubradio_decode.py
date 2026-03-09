import binascii
import time

import board
import busio


# XIAO ESP32C3: D0=TX, D1=RX
uart = busio.UART(tx=board.D0, rx=board.D1, baudrate=38400, receiver_buffer_size=4096)

PREAMBLE_TX = b"  !SU2LS!"
PREAMBLE_RX = b"  !LS2SU!"
ETX = 0xFF

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

    data_len = pkt_len - 5
    received_crc = frame[-5:-1]
    expected_etx = frame[-1]

    if expected_etx != ETX:
        print("[Error] ETX mismatch!")
        return False, "ETX Error", buffer[1:]

    crc_input_data = frame[9 : 9 + 1 + 1 + data_len]
    calculated_crc = calculate_crc(crc_input_data)
    if received_crc != calculated_crc:
        print(f"[Error] CRC Fail! Recv:{received_crc.hex()} Calc:{calculated_crc.hex()}")
        return False, "CRC Fail", buffer[1:]

    cmd_type = chr(frame[10])
    payload_data = frame[11 : 11 + data_len]
    result = {
        "type": cmd_type,
        "data_hex": binascii.hexlify(payload_data, " ").decode(),
        "data_ascii": "".join(chr(b) if 32 <= b <= 126 else "." for b in payload_data),
    }
    return True, result, remaining


def rx_loop():
    print("Listening for valid frames...")
    buf = bytearray()

    try:
        while True:
            if uart.in_waiting:
                chunk = uart.read(uart.in_waiting)
                buf.extend(chunk)

                while True:
                    success, res, buf = parse_frame(buf)
                    if success:
                        print(f"[VALID FRAME] Type: {res['type']}")
                        print(f"   Data: {res['data_ascii']} ({res['data_hex']})")
                    else:
                        break
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("Stopped.")


def send_query():
    print("Sending Query Version (V)...")
    frame = pack_frame("V")
    uart.write(frame)
    rx_loop()
