## ESP32 CircuitPython UB UART Experiments

This directory tracks the current ESP32-side UART experiments that are closer to the real hardware path than the `pc_client/` and `server/` prototype bridge.

Scope:
- Talk to the UB board over UART at `38400 8N1`
- Capture raw frames for protocol study
- Pack outbound UB query frames
- Parse inbound UB frames with preamble, length, CRC32, and ETX checks

Out of scope:
- No complete `PC <-> ESP32 <-> UB` bridge yet
- No TCP forwarding
- No Azure / Wi-Fi / IoT state machine code
- No secrets or board-local config files

Files:
- `ubradio.py`: early raw UART monitor and one-shot version query helper
- `ubradio_decode.py`: current protocol-oriented experiment with frame pack/unpack and CRC validation
- `peps.py`: frame boundary sniffer for preamble/length debugging

Hardware notes:
- `ubradio.py` and `ubradio_decode.py` use `D0/D1`
- `peps.py` uses `D6/D7`

Board-local files intentionally not included:
- `config.py`
- Azure IoT Hub credentials
- Wi-Fi credentials
- unrelated `code.py` / IoT state-machine experiments

Suggested next step:
- consolidate pin mapping
- choose one script as the canonical `code.py`
- add a host-side command channel so ESP32 can bridge PC commands to UB and return parsed responses
