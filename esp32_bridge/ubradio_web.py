import json
import os
import time

import socketpool
import wifi
from adafruit_httpserver import JSONResponse, Request, Response, Server

import ubradio_decode as bridge


HOST = "0.0.0.0"
PORT = 80
POLL_DELAY = 0.05
COMMANDS = ("V", "G", "P", "M", "U")

HTML_PAGE = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>UB Radio Bridge</title>
  <style>
    :root {
      --bg: #f3efe4;
      --panel: #fffaf0;
      --ink: #1f2a2a;
      --muted: #6d746d;
      --line: #cbbfa7;
      --accent: #9f4a23;
      --accent-2: #294b53;
    }
    body {
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      background: linear-gradient(180deg, #efe5d0 0%, var(--bg) 100%);
      color: var(--ink);
    }
    main {
      max-width: 980px;
      margin: 0 auto;
      padding: 20px;
    }
    h1 {
      margin: 0 0 16px;
      font-size: 28px;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 16px;
      margin-bottom: 16px;
      box-shadow: 0 10px 24px rgba(0, 0, 0, 0.06);
    }
    .row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 12px;
    }
    button {
      border: 0;
      border-radius: 999px;
      background: var(--accent);
      color: white;
      padding: 10px 16px;
      font-size: 15px;
      cursor: pointer;
    }
    button.secondary {
      background: var(--accent-2);
    }
    input {
      flex: 1 1 220px;
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 10px 14px;
      font-size: 15px;
      background: #fff;
    }
    #status {
      margin: 0;
      padding: 12px 14px;
      background: #f7f1e4;
      border: 1px solid #e0d3ba;
      border-radius: 12px;
      color: var(--ink);
      font-size: 14px;
    }
    #logOutput {
      min-height: 360px;
      max-height: 60vh;
      overflow: auto;
      background: #fffdf8;
      border: 1px solid #e0d3ba;
      border-radius: 12px;
      padding: 14px;
      margin: 0;
      white-space: pre-wrap;
      line-height: 1.45;
      font-size: 13px;
    }
    .mono {
      font-family: "Courier New", monospace;
    }
    .hint {
      color: var(--muted);
      margin-top: 8px;
      font-size: 13px;
    }
  </style>
</head>
<body>
  <main>
    <h1>UB Radio Bridge</h1>
    <div class="panel">
      <div class="row">
        <button onclick="sendCommand('V')">Version</button>
        <button onclick="sendCommand('G')">GPS Status</button>
        <button onclick="sendCommand('P')">GPS Position</button>
        <button onclick="sendCommand('M')">GPS Time</button>
        <button onclick="sendCommand('U')">Station ID</button>
        <button class="secondary" onclick="refreshLogs()">Refresh</button>
        <button class="secondary" onclick="clearLogs()">Clear Logs</button>
      </div>
      <div class="row">
        <input id="echoPayload" placeholder="Echo payload (ASCII)">
        <button onclick="sendEcho()">Send Echo</button>
      </div>
      <p id="status">Ready. Manual refresh only.</p>
      <p class="hint">Click a command, then inspect the log below for TX/RX details.</p>
    </div>
    <div class="panel">
      <pre id="logOutput" class="mono">No logs yet.</pre>
    </div>
  </main>
  <script>
    async function fetchJson(url) {
      const response = await fetch(url, {cache: "no-store"});
      const data = await response.json();
      if (!response.ok || data.ok === false) {
        throw new Error(data.error || ("HTTP " + response.status));
      }
      return data;
    }

    function fmtTs(ts) {
      return Number(ts || 0).toFixed(3);
    }

    function formatLine(item) {
      const parts = [];
      parts.push("[" + fmtTs(item.ts) + "]");
      parts.push((item.dir || "").toUpperCase());
      parts.push("type=" + (item.type || ""));
      if (item.length !== undefined) {
        parts.push("len=" + item.length);
      }
      if (item.crc_ok !== undefined) {
        parts.push("crc=" + (item.crc_ok ? "ok" : "bad"));
      }
      if (item.recv_crc || item.calc_crc) {
        parts.push("crc32=" + (item.recv_crc ? item.recv_crc + "/" : "") + (item.calc_crc || ""));
      }
      if (item.data_ascii) {
        parts.push("ascii=" + JSON.stringify(item.data_ascii));
      }
      if (item.data_hex) {
        parts.push("hex=" + item.data_hex);
      }
      if (item.raw_hex) {
        parts.push("raw=" + item.raw_hex);
      }
      return parts.join(" | ");
    }

    function renderLogs(items) {
      const logOutput = document.getElementById("logOutput");
      if (!items || !items.length) {
        logOutput.textContent = "No logs yet.";
        return;
      }
      logOutput.textContent = items.map(formatLine).join("\\n");
      logOutput.scrollTop = logOutput.scrollHeight;
    }

    async function refreshLogs() {
      try {
        const data = await fetchJson("/api/logs");
        renderLogs(data.logs || []);
        document.getElementById("status").textContent = "Logs updated. Entries: " + (data.logs || []).length;
      } catch (error) {
        document.getElementById("status").textContent = "Refresh failed: " + error.message;
      }
    }

    async function sendCommand(cmd, payload="") {
      try {
        document.getElementById("status").textContent = "Sending " + cmd + "...";
        const url = "/api/send?cmd=" + encodeURIComponent(cmd) + "&payload=" + encodeURIComponent(payload);
        const data = await fetchJson(url);
        renderLogs(data.logs || []);
        document.getElementById("status").textContent = "Sent " + cmd + ". Frames received: " + (data.frames || 0);
      } catch (error) {
        document.getElementById("status").textContent = "Send failed: " + error.message;
      }
    }

    function sendEcho() {
      const payload = document.getElementById("echoPayload").value || "";
      sendCommand("E", payload);
    }

    async function clearLogs() {
      try {
        const data = await fetchJson("/api/clear");
        renderLogs(data.logs || []);
        document.getElementById("status").textContent = "Logs cleared.";
      } catch (error) {
        document.getElementById("status").textContent = "Clear failed: " + error.message;
      }
    }
  </script>
</body>
</html>
"""


def _get_setting(name):
    value = os.getenv(name)
    if value:
        return value
    raise RuntimeError("Missing setting: %s" % name)


def _decode_query_component(text):
    text = text.replace("+", " ")
    parts = text.split("%")
    if len(parts) == 1:
        return text
    out = parts[0]
    for item in parts[1:]:
        if len(item) >= 2:
            out += chr(int(item[:2], 16)) + item[2:]
        else:
            out += "%" + item
    return out


def _parse_query(path):
    params = {}
    if "?" not in path:
        return path, params
    path, query = path.split("?", 1)
    for pair in query.split("&"):
        if not pair:
            continue
        if "=" in pair:
            key, value = pair.split("=", 1)
        else:
            key, value = pair, ""
        params[_decode_query_component(key)] = _decode_query_component(value)
    return path, params


def _json_payload(**kwargs):
    return kwargs


def connect_wifi():
    ssid = _get_setting("CIRCUITPY_WIFI_SSID")
    password = _get_setting("CIRCUITPY_WIFI_PASSWORD")
    print("Connecting Wi-Fi...")
    wifi.radio.connect(ssid, password)
    print("Wi-Fi connected:", str(wifi.radio.ipv4_address))


def make_server():
    pool = socketpool.SocketPool(wifi.radio)
    server = Server(pool, debug=True)

    @server.route("/")
    def index(request: Request):
        bridge.poll_uart_once()
        return Response(request, HTML_PAGE, content_type="text/html")

    @server.route("/api/logs")
    def api_logs(request: Request):
        bridge.poll_uart_once()
        return JSONResponse(request, _json_payload(ok=True, logs=bridge.get_logs()))

    @server.route("/api/clear")
    def api_clear(request: Request):
        bridge.clear_logs()
        return JSONResponse(request, _json_payload(ok=True, logs=bridge.get_logs()))

    @server.route("/api/send")
    def api_send(request: Request):
        cmd = request.query_params.get("cmd", "") or ""
        payload = request.query_params.get("payload", "") or ""
        cmd = cmd.strip().upper()

        if cmd not in COMMANDS and cmd != "E":
            return JSONResponse(
                request,
                _json_payload(ok=False, error="Unsupported cmd"),
                status=(400, "Bad Request"),
            )

        bridge.send_command(cmd, payload.encode("ascii", "ignore"))
        frames = bridge.read_frames(600, verbose=False)
        return JSONResponse(
            request,
            _json_payload(
                ok=True,
                cmd=cmd,
                frames=len(frames),
                logs=bridge.get_logs(),
            ),
        )

    return server


def serve_forever():
    connect_wifi()
    server = make_server()
    server.start(str(wifi.radio.ipv4_address), port=PORT)
    print("HTTP server ready at http://%s:%d/" % (wifi.radio.ipv4_address, PORT))

    while True:
        bridge.poll_uart_once()
        try:
            server.poll()
        except OSError as exc:
            print("HTTP poll error:", exc)
        time.sleep(POLL_DELAY)


if __name__ == "__main__":
    serve_forever()
