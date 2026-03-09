import binascii
import time

import board
import busio


# XIAO ESP32C3: D0=TX, D1=RX
uart = busio.UART(tx=board.D0, rx=board.D1, baudrate=38400, receiver_buffer_size=4096)

# Preamble + Length(06) + Type(V) + CRC + ETX
CMD_VERSION_QUERY = "20 20 21 53 55 32 4C 53 21 06 56 95 8B 41 B8 FF"

print("UART Initialized: 38400, 8N1")
print("---------------------------------------------")
print("Function 1: rx()            -> passive listen mode")
print("Function 2: query_version() -> send version query and wait for reply")
print("Function 3: tx_wait('hex')  -> send arbitrary hex and wait for reply")
print("---------------------------------------------")


def clean_hex(hex_str):
    return binascii.unhexlify(hex_str.replace(" ", ""))


def rx():
    print("\n[Mode] Listening... (Press Ctrl+C to stop)")
    try:
        while True:
            if uart.in_waiting > 0:
                data = uart.read(uart.in_waiting)
                if data:
                    hex_s = binascii.hexlify(data, " ").decode().upper()
                    ascii_s = "".join(chr(b) if 32 <= b <= 126 else "." for b in data)
                    print(f"[RX] LEN:{len(data)} | HEX: {hex_s} | ASCII: {ascii_s}")
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\n[Stopped]")


def tx_wait(hex_str, timeout=3.0):
    try:
        data = clean_hex(hex_str)
        uart.write(data)
        print(f"\n[TX] {hex_str}")

        start_time = time.monotonic()
        print(f"[Wait] Listening for {timeout}s...")

        has_received = False
        while (time.monotonic() - start_time) < timeout:
            if uart.in_waiting > 0:
                resp = uart.read(uart.in_waiting)
                if resp:
                    hex_s = binascii.hexlify(resp, " ").decode().upper()
                    ascii_s = "".join(chr(b) if 32 <= b <= 126 else "." for b in resp)
                    print(f"[RX_ACK] LEN:{len(resp)} | HEX: {hex_s}")
                    print(f"         ASCII: {ascii_s}")
                    has_received = True
                    start_time = time.monotonic()
            time.sleep(0.005)

        if not has_received:
            print("[Timeout] No response received.")
        else:
            print("[Done] Transaction complete.")

    except Exception as exc:
        print(f"[Error] {exc}")


def query_version():
    print("--- Sending Query Version (V) ---")
    tx_wait(CMD_VERSION_QUERY, timeout=2.0)


# Uncomment to auto-start listening on boot.
# rx()
