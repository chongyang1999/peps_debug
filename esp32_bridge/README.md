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
- `ubradio_web.py`: minimal Wi-Fi HTTP wrapper around `ubradio_decode.py`
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

Current first web build:
- `ubradio_decode.py` remains the UART/protocol core used in REPL
- `ubradio_web.py` reuses that module and serves a small HTTP page with:
  - fixed buttons for `V/G/P/M/U`
  - an Echo payload input
  - manual refresh and text log display with TX/RX, raw hex, parsed data, CRC, and timestamps
- the web layer now uses `adafruit_httpserver` instead of a hand-written socket server
- currently verified in browser:
  - `Version` -> `V02.01`
  - `GPS Status` -> `00`

Board-local setup for web mode:
- put Wi-Fi credentials in `settings.toml`
- required keys:
  - `CIRCUITPY_WIFI_SSID="your-ssid"`
  - `CIRCUITPY_WIFI_PASSWORD="your-password"`
- install the official HTTP library:
  - `py -m pip install circup`
  - `circup install adafruit_httpserver`
- or manually copy `adafruit_httpserver` from the matching CircuitPython Bundle into `CIRCUITPY/lib/`
- then run `ubradio_web.py` as the main script, or import it in REPL and call:
  - `serve_forever()`
