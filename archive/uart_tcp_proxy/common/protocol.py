import crcmod
import struct
import logging

# Configure basic logging for the protocol module if needed, or rely on application-level logging
# logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - protocol - %(message)s')

FRAME_HEADER = b'\xAA\x55'
HEADER_LENGTH = len(FRAME_HEADER)
LENGTH_FIELD_SIZE = 2  # 2 bytes for length
CRC_FIELD_SIZE = 2  # 2 bytes for CRC16

# CRC-16/MODBUS: poly=0x8005, init=0xFFFF, refin=True, refout=True, xorout=0x0000
# This is a common CRC16 variant.
crc16_func = crcmod.mkCrcFun(0x18005, rev=True, initCrc=0xFFFF, xorOut=0x0000)

def bytes_to_hex_string_protocol(data): # Renamed to avoid conflict if imported elsewhere
    if data is None:
        return ""
    return ' '.join(f'{b:02x}' for b in data)

def pack_data(payload: bytes) -> bytes:
    """
    Packs the payload into a network packet with header, length, and CRC16.
    - Frame Header: 2 bytes (0xAA55)
    - Length: 2 bytes (big-endian, length of payload only)
    - Payload: N bytes
    - CRC16: 2 bytes (calculated over header, length, and payload)
    """
    if payload is None:
        # Or raise an error, depending on desired handling for None payloads
        logging.warning("Attempted to pack None payload. Returning empty bytes.")
        return b''

    payload_len = len(payload)

    # Pack header and length (big-endian for length)
    # The length in the packet is the length of the payload part.
    header_and_length = FRAME_HEADER + struct.pack('>H', payload_len)

    # Data to be CRCed: Header + Length field + Payload
    data_for_crc = header_and_length + payload

    # Calculate CRC16
    crc_val = crc16_func(data_for_crc)
    crc_bytes = struct.pack('>H', crc_val) # CRC is typically sent big-endian as well

    packed_frame = data_for_crc + crc_bytes
    logging.debug(f"Packed data: {bytes_to_hex_string_protocol(packed_frame)}")
    return packed_frame

def unpack_data(stream: bytes) -> tuple[list[bytes], bytes]:
    """
    Unpacks network packets from a byte stream. Handles multiple packets, partial packets, and CRC validation.

    Args:
        stream: The incoming byte stream.

    Returns:
        A tuple containing:
            - A list of successfully unpacked payloads (bytes).
            - The remaining unprocessed part of the stream (bytes).
    """
    payloads = []
    remaining_stream = stream

    while len(remaining_stream) >= HEADER_LENGTH + LENGTH_FIELD_SIZE: # Minimum length for header + length field
        # Find the frame header
        header_index = remaining_stream.find(FRAME_HEADER)

        if header_index == -1:
            # No header found. If there's data, it's unrecognized.
            if remaining_stream: # Only log if there's actually data being discarded
                logging.debug(f"No frame header found in remaining stream of len {len(remaining_stream)}. Discarding: {bytes_to_hex_string_protocol(remaining_stream)}")
            return payloads, b'' # Discard unrecognized data

        if header_index > 0:
            # Data before header is garbage, discard it
            discarded_data = remaining_stream[:header_index]
            logging.warning(f"Discarding {header_index} bytes of unrecognized data before frame header: {bytes_to_hex_string_protocol(discarded_data)}")
            remaining_stream = remaining_stream[header_index:]

        # We have a potential frame starting with FRAME_HEADER
        # Check if we have enough data for header and length field
        if len(remaining_stream) < HEADER_LENGTH + LENGTH_FIELD_SIZE:
            # Not enough data for header and length field, wait for more data
            logging.debug(f"Partial frame (header but not enough for length): {bytes_to_hex_string_protocol(remaining_stream)}")
            break

        # Extract payload length
        length_bytes = remaining_stream[HEADER_LENGTH : HEADER_LENGTH + LENGTH_FIELD_SIZE]
        payload_len = struct.unpack('>H', length_bytes)[0]

        # Calculate total frame length: Header + Length Field + Payload + CRC Field
        expected_frame_len = HEADER_LENGTH + LENGTH_FIELD_SIZE + payload_len + CRC_FIELD_SIZE

        if len(remaining_stream) < expected_frame_len:
            # Not enough data for the full frame, wait for more data
            logging.debug(f"Partial frame (not enough for full payload + CRC). Expected: {expected_frame_len}, Have: {len(remaining_stream)}, Current buffer: {bytes_to_hex_string_protocol(remaining_stream)}")
            break

        # We potentially have a full frame
        current_frame = remaining_stream[:expected_frame_len]

        # Extract components
        # header = current_frame[:HEADER_LENGTH] # is FRAME_HEADER
        # length_field = current_frame[HEADER_LENGTH : HEADER_LENGTH + LENGTH_FIELD_SIZE] # is length_bytes
        payload = current_frame[HEADER_LENGTH + LENGTH_FIELD_SIZE : HEADER_LENGTH + LENGTH_FIELD_SIZE + payload_len]
        received_crc_bytes = current_frame[HEADER_LENGTH + LENGTH_FIELD_SIZE + payload_len : expected_frame_len]
        received_crc = struct.unpack('>H', received_crc_bytes)[0]

        # Verify CRC
        # CRC is calculated over Header + Length field + Payload
        data_for_crc_check = current_frame[:HEADER_LENGTH + LENGTH_FIELD_SIZE + payload_len]
        calculated_crc = crc16_func(data_for_crc_check)

        if calculated_crc == received_crc:
            payloads.append(payload)
            logging.debug(f"Successfully unpacked payload: {bytes_to_hex_string_protocol(payload)}")
        else:
            logging.warning(f"CRC mismatch! Expected: {calculated_crc:04X}, Received: {received_crc:04X}. Frame: {bytes_to_hex_string_protocol(current_frame)}")
            # Frame is corrupt. What to do?
            # Option 1: Discard this frame and continue searching for the next AA55 from the byte after the current AA55.
            # This prevents a single bad CRC from stalling processing if multiple frames are packed closely.
            # If we discard only this frame and advance, we might find subsequent valid frames.
            # We must advance past the current FRAME_HEADER to avoid reprocessing it.
            # So, we advance by 1 byte from the start of this failed frame to look for a new header.
            # This is a simple strategy. More complex ones could try to find the *next* AA55.
            # For now, advancing by 1 effectively means we'll re-scan from remaining_stream[1:].
            # If we just `remaining_stream = remaining_stream[expected_frame_len:]` and there was a valid frame immediately after,
            # but this one had a bad CRC, we'd miss it.
            # The current loop structure with `find(FRAME_HEADER)` handles finding the next valid header,
            # so simply advancing `remaining_stream` past this corrupted frame is correct.
            # No, if header_index was 0, and CRC fails, we must advance past this frame's header to avoid an infinite loop.
            # `remaining_stream = remaining_stream[1:]` would be wrong if header_index was > 0.
            # Correct is to advance beyond this processed (but failed) frame's header.
            # The outer loop will then re-search from `remaining_stream[header_index+1:]` effectively.
            # The current logic: if header_index is 0, and it fails, we need to make sure we don't re-evaluate the same header.
            # The `remaining_stream = remaining_stream[expected_frame_len:]` below will advance past the current frame.
            # If CRC fails, we discard this frame and then we consume it from the stream.
            # The next iteration will look for the *next* header.
            pass # Data is discarded by not adding to payloads.

        # Move the stream past the processed (or discarded) frame
        remaining_stream = remaining_stream[expected_frame_len:]

    if not payloads and remaining_stream: # If loop finished but still data left (must be partial)
        logging.debug(f"Unpacking loop finished. No full payloads extracted in last pass. Remaining partial stream: {bytes_to_hex_string_protocol(remaining_stream)}")
    elif not payloads and not remaining_stream:
        logging.debug(f"Unpacking loop finished. No payloads extracted and no remaining stream.")
    else:
        logging.debug(f"Unpacking finished. Payloads: {len(payloads)}, Remaining stream len: {len(remaining_stream)}")
    return payloads, remaining_stream

if __name__ == '__main__':
    # Basic test cases for pack and unpack
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - protocol - %(message)s')

    payload1 = b"Hello"
    payload2 = b"World"

    packed1 = pack_data(payload1)
    packed2 = pack_data(payload2)

    logging.info(f"Packed 1 ({bytes_to_hex_string_protocol(payload1)}): {bytes_to_hex_string_protocol(packed1)}")
    logging.info(f"Packed 2 ({bytes_to_hex_string_protocol(payload2)}): {bytes_to_hex_string_protocol(packed2)}")

    # Test unpacking single packet
    payloads, remainder = unpack_data(packed1)
    assert len(payloads) == 1
    assert payloads[0] == payload1
    assert remainder == b''
    logging.info("Unpack single: PASS")

    # Test unpacking multiple packets
    stream = packed1 + packed2
    payloads, remainder = unpack_data(stream)
    assert len(payloads) == 2
    assert payloads[0] == payload1
    assert payloads[1] == payload2
    assert remainder == b''
    logging.info("Unpack multiple: PASS")

    # Test unpacking partial packet (header only)
    partial_stream = packed1[:1] # AA
    payloads, remainder = unpack_data(partial_stream)
    assert len(payloads) == 0
    assert remainder == partial_stream # Should remain as it's too short to be processed
    logging.info(f"Unpack partial (header only): remaining: {bytes_to_hex_string_protocol(remainder)}")

    # Test unpacking partial packet (header + partial length)
    partial_stream = packed1[:HEADER_LENGTH + 1] # AA 55 00 (missing one byte of length)
    payloads, remainder = unpack_data(partial_stream)
    assert len(payloads) == 0
    assert remainder == partial_stream
    logging.info(f"Unpack partial (header + partial length): remaining: {bytes_to_hex_string_protocol(remainder)}")

    # Test unpacking partial packet (header + length + partial payload)
    partial_stream = packed1[:HEADER_LENGTH + LENGTH_FIELD_SIZE + 2] # AA 55 00 05 He
    payloads, remainder = unpack_data(partial_stream)
    assert len(payloads) == 0
    assert remainder == partial_stream
    logging.info(f"Unpack partial (header + length + partial payload): remaining: {bytes_to_hex_string_protocol(remainder)}")

    # Test unpacking with garbage data at the beginning
    garbage_stream = b'\x01\x02\x03' + packed1 + packed2
    payloads, remainder = unpack_data(garbage_stream)
    assert len(payloads) == 2
    assert payloads[0] == payload1
    assert payloads[1] == payload2
    assert remainder == b''
    logging.info("Unpack with garbage prefix: PASS")

    # Test unpacking with garbage data in between packets
    # AA 55 00 05 H e l l o CRC1 CRC2 GARBAGE AA 55 00 05 W o r l d CRC3 CRC4
    # unpack_data should find the first, then find the second, discarding GARBAGE.
    garbage_between_stream = packed1 + b'\xDE\xAD\xBE\xEF' + packed2
    payloads, remainder = unpack_data(garbage_between_stream)
    assert len(payloads) == 2
    assert payloads[0] == payload1
    assert payloads[1] == payload2 # This assertion will fail with current simple discard logic
    # The current logic will see DEADBEEF as part of remaining_stream after packed1,
    # then find AA55 of packed2 within it.
    assert remainder == b''
    logging.info(f"Unpack with garbage between: Found {len(payloads)} payloads. Payloads: {[bytes_to_hex_string_protocol(p) for p in payloads]}. Remainder: {bytes_to_hex_string_protocol(remainder)}")
    # This test passes because `find(FRAME_HEADER)` will skip DEADBEEF.

    # Test CRC error
    corrupted_packed1 = list(packed1)
    corrupted_packed1[-1] = corrupted_packed1[-1] ^ 0xFF # Flip last byte of CRC
    corrupted_stream = bytes(corrupted_packed1) + packed2

    payloads, remainder = unpack_data(corrupted_stream)
    assert len(payloads) == 1 # Only packed2 should be valid
    assert payloads[0] == payload2
    assert remainder == b''
    logging.info("Unpack with CRC error: PASS")

    # Test empty stream
    payloads, remainder = unpack_data(b'')
    assert len(payloads) == 0
    assert remainder == b''
    logging.info("Unpack empty stream: PASS")

    # Test stream that is just a header
    payloads, remainder = unpack_data(FRAME_HEADER)
    assert len(payloads) == 0
    assert remainder == FRAME_HEADER
    logging.info("Unpack header-only stream: PASS")

    # Test stream with valid header but not enough for length
    payloads, remainder = unpack_data(FRAME_HEADER + b'\x00') # AA 55 00
    assert len(payloads) == 0
    assert remainder == FRAME_HEADER + b'\x00'
    logging.info("Unpack header + 1 byte length: PASS")

    # Test a frame with payload_len = 0
    empty_payload = b""
    packed_empty = pack_data(empty_payload)
    logging.info(f"Packed empty payload: {bytes_to_hex_string_protocol(packed_empty)}")
    payloads, remainder = unpack_data(packed_empty)
    assert len(payloads) == 1
    assert payloads[0] == empty_payload
    assert remainder == b''
    logging.info("Unpack empty payload frame: PASS")

    # Test case: AA 55 (header) 00 01 (len=1) XX (payload) YY YY (CRC) AA (start of next, incomplete)
    # This should parse the first frame and leave AA as remainder.
    payload_A = b"A" # len 1
    packed_A = pack_data(payload_A) # AA 55 00 01 41 CRC_A
    test_stream_incomplete_next = packed_A + FRAME_HEADER[:1] # ... CRC_A AA
    payloads, remainder = unpack_data(test_stream_incomplete_next)
    assert len(payloads) == 1
    assert payloads[0] == payload_A
    assert remainder == FRAME_HEADER[:1] # Should be b'\xAA'
    logging.info(f"Unpack frame followed by partial header of next: PASS. Remainder: {bytes_to_hex_string_protocol(remainder)}")

    # Test case: Junk data, then a valid frame, then junk data
    # 01 02 AA 55 00 01 42 CRC 03 04
    payload_B = b"B"
    packed_B = pack_data(payload_B)
    test_stream_junk_around = b'\x01\x02' + packed_B + b'\x03\x04'
    payloads, remainder = unpack_data(test_stream_junk_around)
    assert len(payloads) == 1
    assert payloads[0] == payload_B
    assert remainder == b'\x03\x04' # Junk after valid frame should remain if no new header is found
    logging.info(f"Unpack frame with junk around: PASS. Remainder: {bytes_to_hex_string_protocol(remainder)}")

    logging.info("All basic protocol tests completed.")
