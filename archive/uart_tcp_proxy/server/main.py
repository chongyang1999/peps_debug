import asyncio
import logging

# Configure basic logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # For more specific logging control if needed


def bytes_to_hex_string(data):
    if data is None:
        return ""
    return ' '.join(f'{b:02x}' for b in data)

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
from common.protocol import pack_data, unpack_data # Added import

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    client_address = writer.get_extra_info('peername')
    logging.info(f"Accepted connection from {client_address}")
    receive_buffer = b''

    try:
        while True:
            chunk = await reader.read(4096) # Read a chunk of data
            if not chunk:
                logging.info(f"Client {client_address} disconnected (EOF).")
                break

            receive_buffer += chunk
            logging.debug(f"SERVER RX (chunk) from {client_address}: {bytes_to_hex_string(chunk)}, Buffer now: {bytes_to_hex_string(receive_buffer)}")

            payloads, remaining_buffer = unpack_data(receive_buffer)
            receive_buffer = remaining_buffer

            if not payloads and receive_buffer:
                 logging.debug(f"SERVER RX from {client_address}: No complete payloads yet, buffer: {bytes_to_hex_string(receive_buffer)}")

            for i, payload in enumerate(payloads):
                logging.info(f"SERVER RX (unpacked payload {i+1}/{len(payloads)}) from {client_address}: {bytes_to_hex_string(payload)}")

                # Placeholder: Echo payload back
                # In a real scenario, 'payload' would be processed by the business logic
                # and a response payload would be generated.
                response_payload = payload # Simple echo for now

                packed_response = pack_data(response_payload)
                if not packed_response:
                    logging.error(f"SERVER TX to {client_address}: Failed to pack response payload: {bytes_to_hex_string(response_payload)}")
                    continue

                writer.write(packed_response)
                await writer.drain()
                logging.info(f"SERVER TX (payload) to {client_address}: {bytes_to_hex_string(response_payload)}")
                logging.debug(f"SERVER TX (packed frame) to {client_address}: {bytes_to_hex_string(packed_response)}")

    except ConnectionResetError:
        logging.warning(f"Connection reset by client {client_address}.")
    except asyncio.IncompleteReadError as e:
        logging.error(f"Incomplete read from client {client_address}: {bytes_to_hex_string(e.partial)}. Connection may be closed.")
    except asyncio.CancelledError:
        logging.info(f"Client handler for {client_address} cancelled.")
        # Propagate cancellation if necessary, or just clean up.
        raise
    except Exception as e:
        logging.error(f"Error handling client {client_address}: {e}", exc_info=True)
    finally:
        logging.info(f"Closing connection for {client_address}.")
        writer.close()
        try:
            await writer.wait_closed()
        except Exception as e:
            logging.warning(f"Error while closing writer for {client_address}: {e}")

async def main_server(host="0.0.0.0", port=65432): # Using 0.0.0.0 to listen on all available interfaces
    server = await asyncio.start_server(handle_client, host, port)

    addr = server.sockets[0].getsockname()
    logging.info(f"Server listening on {addr}")

    async with server:
        try:
            await server.serve_forever()
        except KeyboardInterrupt:
            logging.info("Server shutting down due to KeyboardInterrupt...")
        except asyncio.CancelledError:
            logging.info("Server main task cancelled.") # Should not happen in normal operation unless externally cancelled
        finally:
            logging.info("Server shutting down.")
            # Server.close() is called automatically by async with server
            # await server.wait_closed() # also handled by async with

if __name__ == "__main__":
    try:
        asyncio.run(main_server())
    except KeyboardInterrupt:
        logging.info("Server application terminated by KeyboardInterrupt.")
    except Exception as e:
        logging.error(f"Unhandled exception in server startup: {e}", exc_info=True)

# Note: The client (pc_client/main.py) is configured to connect to 127.0.0.1:65432.
# This server listens on 0.0.0.0:65432, which means it will accept connections
# to any of its IP addresses on that port, including 127.0.0.1.
