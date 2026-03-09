# PC-side RS-232↔TCP bridge helper and UB protocol probing

## GUI helper design (pc_client/gui_serial.py)
- Tkinter + pyserial GUI to talk to UB radio RS-232 port.
- Configurable port/baud (defaults COM5 @ 38400), connect/disconnect buttons.
- RX view shows timestamped HEX + ASCII (non-printable as ".").
- TX options:
  - Dropdown of common protocol commands (auto-frame with “  !SU2LS!” + LENGTH + CRC32 + ETX): ID request, Reset UB, Radio reset, Version, GPS status/position/time, Echo PING, Network status, Buffer status, Control.
  - Raw send box (ASCII or HEX) for manual bytes.
- Frame packing follows protocol: LENGTH counts TYPE+DATA+CRC32+ETX; CRC32 over LENGTH+TYPE+DATA; ETX=0xFF.

## On-wire protocol recap
- Preamble UB→Radio: `20 20 21 4C 53 32 53 55 21` (“  !LS2SU!”).
- Preamble Radio→UB (our sends): `20 20 21 53 55 32 4C 53 21` (“  !SU2LS!”).
- LENGTH: 1 byte, counts TYPE+DATA+CRC32(4)+ETX.
- CRC: CRC32 over LENGTH+TYPE+DATA. ETX=0xFF terminator.

## Live test results with UB (RS-232 via MAX3232/MM232R, 38400 8N1)
- Version query (V): UB replies `v` with ASCII `V02.01` (CRC OK).
- GPS status (G): UB replies `g` status=0x00 (GPS invalid).
- GPS position (P): UB replies `p`, status=0x00, north=0x0000FD54, east=0x20000000, height=0x00000000 (status invalid, values not trusted).
- Echo test (E + “PING”): UB replies `e` ACK without payload (no echo content).
- ID request (U): UB echoes request back instead of returning `u` with ID (no proper ID reply observed).
- Network status (N): UB responds `I` (Invalid command).
- Buffer status (B): UB responds `I` (Invalid command).
- Reset UB (T): UB responds `I` (Invalid command).
- UB spontaneous/periodic: observed `N` (comm status) frames from UB on startup/idle.

## Notes
- Working commands: V, G, P, E (ACK-only), observed N from UB.
- Unsupported/ignored in current firmware: T, B, N (as query), U (no proper reply).
- Use HEX RX log to inspect full frames; raw send remains available for custom payloads.
