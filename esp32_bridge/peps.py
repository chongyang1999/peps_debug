import binascii
import time

import board
import busio


UART_TX = board.D6
UART_RX = board.D7

PREAMBLES = (
    b"  !LS2SU!",
    b"  !SU2LS!",
    b" !BS2PC!",
    b"  !PC2BS!",
)

uart = busio.UART(
    UART_TX,
    UART_RX,
    baudrate=38400,
    bits=8,
    parity=None,
    stop=1,
    timeout=0.1,
    receiver_buffer_size=2048,
)

rx_buffer = bytearray()
last_rx = time.monotonic()
print("UART ready @38400 8N1, waiting for UB packets...")


def dump(label: str, data: bytes) -> None:
    print(f"{label} len={len(data)} hex={binascii.hexlify(data).decode()}")
    print(f"{label} ascii={data.decode('ascii', errors='replace')}")


try:
    while True:
        chunk = uart.read(256)
        now = time.monotonic()

        if chunk:
            last_rx = now
            dump(f"[{now:8.3f}] +", chunk)
            rx_buffer.extend(chunk)

            while True:
                pre_pos = -1
                for pre in PREAMBLES:
                    pos = rx_buffer.find(pre)
                    if 0 <= pos < pre_pos or pre_pos == -1:
                        pre_pos = pos

                if pre_pos == -1:
                    if len(rx_buffer) > len(PREAMBLES[0]):
                        rx_buffer[:] = rx_buffer[-len(PREAMBLES[0]) :]
                    break

                if pre_pos > 0:
                    print(f"[{now:8.3f}] drop {pre_pos} bytes before preamble")
                    del rx_buffer[:pre_pos]

                if len(rx_buffer) < 10:
                    break

                frame_len = rx_buffer[9] + 9 + 1
                if len(rx_buffer) < frame_len:
                    break

                frame = bytes(rx_buffer[:frame_len])
                dump(f"[{now:8.3f}] frame", frame)
                del rx_buffer[:frame_len]
        else:
            if now - last_rx >= 5.0:
                print(f"[{now:8.3f}] idle... buffer={len(rx_buffer)}")
                last_rx = now

except KeyboardInterrupt:
    pass
finally:
    uart.deinit()
    print("UART deinit, exiting.")
