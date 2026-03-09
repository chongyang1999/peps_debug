#!/usr/bin/env python3
import argparse
import logging
import struct
import sys
import time

import serial

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


class SimplePPPClient:
    def __init__(self, port: str, baud: int, local_ip: str, peer_ip: str, timeout: float = 0.2):
        self.ser = serial.Serial(port=port, baudrate=baud, timeout=timeout)
        self.local_ip = local_ip
        self.peer_ip = peer_ip
        self.lcp_id = 1
        self.ipcp_id = 1
        self.lcp_remote_open = False
        self.lcp_local_open = False
        self.ipcp_remote_open = False
        self.ipcp_local_open = False
        logging.info("Serial %s opened at %d bps", port, baud)

    def close(self):
        if self.ser.is_open:
            self.ser.close()

    def send_frame(self, protocol: int, payload: bytes):
        header = bytes([PPP_ADDRESS, PPP_CONTROL]) + struct.pack("!H", protocol)
        core = header + payload
        fcs = calc_fcs(core)
        fcs = (~fcs) & 0xFFFF
        frame = bytearray([FLAG])
        frame += escape_bytes(core + struct.pack("<H", fcs))
        frame.append(FLAG)
        self.ser.write(frame)
        logging.debug("TX proto=0x%04x len=%d", protocol, len(payload))

    def read_frame(self, deadline: float = 5.0):
        buf = bytearray()
        start = time.time()
        inside = False
        while True:
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
                        logging.debug("Bad FCS 0x%04x", fcs)
                        continue
                    return raw
                inside = True
                buf.clear()
                continue
            if inside:
                buf.append(b)

    def _send_lcp_request(self):
        opts = bytearray()
        opts += bytes([0x01, 0x04, 0x05, 0xDC])  # MRU=1500
        opts += bytes([0x02, 0x06, 0x00, 0x00, 0x00, 0x00])  # ACCM=0
        length = len(opts) + 4
        payload = bytes([0x01, self.lcp_id]) + struct.pack("!H", length) + opts
        logging.info("-> LCP Configure-Request id=%d", self.lcp_id)
        self.send_frame(PPP_PROTO_LCP, payload)

    def _send_ipcp_request(self):
        req_ip = bytes(map(int, self.local_ip.split('.')))
        opts = bytes([0x03, 0x06]) + req_ip  # IP-Address option
        length = len(opts) + 4
        payload = bytes([0x01, self.ipcp_id]) + struct.pack("!H", length) + opts
        logging.info("-> IPCP Configure-Request id=%d (%s)", self.ipcp_id, self.local_ip)
        self.send_frame(PPP_PROTO_IPCP, payload)

    def _send_config_ack(self, protocol: int, ident: int, data: bytes):
        payload = bytes([0x02, ident]) + struct.pack("!H", len(data) + 4) + data
        self.send_frame(protocol, payload)

    def _send_config_nak(self, protocol: int, ident: int, data: bytes):
        payload = bytes([0x03, ident]) + struct.pack("!H", len(data) + 4) + data
        self.send_frame(protocol, payload)

    def negotiate(self):
        self._send_lcp_request()
        last_tx = time.time()
        while True:
            frame = self.read_frame()
            if frame is None:
                if not self.lcp_local_open and (time.time() - last_tx) > 2:
                    self.lcp_id = (self.lcp_id + 1) & 0xFF or 1
                    self._send_lcp_request()
                    last_tx = time.time()
                continue
            if len(frame) < 6:
                continue
            addr, ctrl = frame[0], frame[1]
            protocol = struct.unpack("!H", frame[2:4])[0]
            payload = frame[4:-2]
            if addr != PPP_ADDRESS or ctrl != PPP_CONTROL:
                continue
            if protocol == PPP_PROTO_LCP:
                self._handle_lcp(payload)
            elif protocol == PPP_PROTO_IPCP:
                self._handle_ipcp(payload)
            elif protocol == PPP_PROTO_IP:
                logging.info("IP packet received len=%d", len(payload))
            else:
                logging.debug("Unhandled protocol 0x%04x", protocol)
            if self.ipcp_local_open and self.ipcp_remote_open:
                logging.info("PPP link ready (IP local %s, peer %s)", self.local_ip, self.peer_ip)
                return

    def _handle_lcp(self, payload: bytes):
        if len(payload) < 4:
            return
        code = payload[0]
        ident = payload[1]
        length = struct.unpack("!H", payload[2:4])[0]
        data = payload[4:length]
        if code == 0x01:  # Configure-Request
            logging.info("<- LCP Configure-Request id=%d", ident)
            self._send_config_ack(PPP_PROTO_LCP, ident, data)
            self.lcp_remote_open = True
        elif code == 0x02:  # Configure-Ack
            logging.info("<- LCP Configure-Ack id=%d", ident)
            self.lcp_local_open = True
            if not self.ipcp_local_open:
                self._send_ipcp_request()
        elif code == 0x04:  # Configure-Reject
            logging.warning("<- LCP Configure-Reject id=%d", ident)
        elif code == 0x05:  # Terminate-Request
            logging.warning("<- LCP Terminate-Request")
            payload = bytes([0x06, ident, 0x00, 0x04])
            self.send_frame(PPP_PROTO_LCP, payload)
            self.lcp_local_open = False
        else:
            logging.debug("Unhandled LCP code %d", code)

    def _handle_ipcp(self, payload: bytes):
        if len(payload) < 4:
            return
        code = payload[0]
        ident = payload[1]
        length = struct.unpack("!H", payload[2:4])[0]
        data = payload[4:length]
        if code == 0x01:  # Configure-Request from peer
            logging.info("<- IPCP Configure-Request id=%d", ident)
            # Accept peer's request blindly
            self._send_config_ack(PPP_PROTO_IPCP, ident, data)
            self.ipcp_remote_open = True
            # Extract peer IP if present
            idx = 0
            while idx < len(data):
                opt = data[idx]
                opt_len = data[idx + 1]
                if opt == 0x03 and opt_len == 6:
                    self.peer_ip = '.'.join(str(b) for b in data[idx + 2:idx + 6])
                    logging.info("Peer IP suggested: %s", self.peer_ip)
                idx += opt_len
        elif code == 0x02:  # Configure-Ack
            logging.info("<- IPCP Configure-Ack id=%d", ident)
            self.ipcp_local_open = True
        elif code == 0x03:  # Configure-Nak
            logging.info("<- IPCP Configure-Nak id=%d", ident)
            if len(data) >= 6 and data[0] == 0x03:
                self.local_ip = '.'.join(str(b) for b in data[2:6])
                logging.info("Adjusting local IP to %s", self.local_ip)
                self.ipcp_id = (self.ipcp_id + 1) & 0xFF or 1
                self._send_ipcp_request()
        else:
            logging.debug("Unhandled IPCP code %d", code)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Minimal PPP client for UB test port")
    parser.add_argument("--port", required=True, help="Serial port, e.g. COM7")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--local-ip", default="192.168.200.10", help="Requested local IP")
    parser.add_argument("--peer-ip", default="192.168.200.1", help="Initial peer IP hint")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase logging")
    args = parser.parse_args(argv)

    level = logging.WARNING
    if args.verbose == 1:
        level = logging.INFO
    elif args.verbose >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(message)s")

    client = SimplePPPClient(args.port, args.baud, args.local_ip, args.peer_ip)
    try:
        client.negotiate()
        logging.info("Link is up. Press Ctrl+C to exit.")
        while True:
            frame = client.read_frame(deadline=0)
            if frame is None:
                continue
            protocol = struct.unpack("!H", frame[2:4])[0]
            payload = frame[4:-2]
            if protocol == PPP_PROTO_IP:
                logging.info("IP frame len=%d: %s", len(payload), payload[:32].hex())
    except KeyboardInterrupt:
        logging.info("Stopping PPP client")
    finally:
        client.close()


if __name__ == "__main__":
    main()
