import asyncio
import logging
import random
import time

# Configure basic logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # For more specific logging control if needed

def bytes_to_hex_string(data):
    if data is None:
        return ""
    return ' '.join(f'{b:02x}' for b in data)

class UARTManager:
    def __init__(self, port="COM1", baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.is_connected = False
        # In a real scenario, this would be a serial.Serial object
        self.serial_conn = None
        logging.info(f"UARTManager initialized for port {self.port} (placeholder).")

    async def connect(self):
        # Placeholder: Simulate connection
        logging.info(f"Attempting to connect to UART {self.port}...")
        await asyncio.sleep(0.5) # Simulate connection delay
        self.is_connected = True
        logging.info(f"UART {self.port} connected (placeholder).")
        return True

    async def read_uart(self) -> bytes | None:
        if not self.is_connected:
            logging.warning("UART not connected. Cannot read.")
            return None
        # Placeholder: Simulate reading data from UART
        await asyncio.sleep(random.uniform(0.1, 0.5)) # Simulate variable read delay
        if random.random() < 0.1: # Simulate occasional no data
            return None
        if random.random() < 0.05: # Simulate read error
            logging.error("UART read error (simulated).")
            self.is_connected = False # Simulate disconnect on error
            return None

        simulated_data = f"UART_DATA_{time.time_ns()}".encode()
        logging.info(f"UART RX: {bytes_to_hex_string(simulated_data)}")
        return simulated_data

    async def write_uart(self, data: bytes) -> bool:
        if not self.is_connected:
            logging.warning("UART not connected. Cannot write.")
            return False
        if data is None:
            logging.warning("Attempted to write None to UART.")
            return False
        # Placeholder: Simulate writing data to UART
        logging.info(f"UART TX: {bytes_to_hex_string(data)}")
        await asyncio.sleep(random.uniform(0.05, 0.2)) # Simulate write delay
        if random.random() < 0.05: # Simulate write error
            logging.error("UART write error (simulated).")
            self.is_connected = False # Simulate disconnect on error
            return False
        return True

    async def close(self):
        if self.is_connected:
            logging.info(f"Closing UART {self.port} (placeholder).")
            self.is_connected = False
            # In a real scenario: self.serial_conn.close()

class NetworkManager:
    def __init__(self, host="127.0.0.1", port=8888):
        self.host = host
        self.port = port
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.is_connected = False
        self.reconnect_attempts = 5
        self.reconnect_delay = 5 # seconds

    async def connect(self) -> bool:
        for attempt in range(self.reconnect_attempts):
            try:
                logging.info(f"Attempting to connect to network {self.host}:{self.port} (Attempt {attempt + 1}/{self.reconnect_attempts})...")
                self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
                self.is_connected = True
                logging.info(f"Network connection established to {self.host}:{self.port}.")
                return True
            except ConnectionRefusedError:
                logging.error(f"Connection to {self.host}:{self.port} refused.")
                if attempt < self.reconnect_attempts - 1:
                    logging.info(f"Retrying in {self.reconnect_delay} seconds...")
                    await asyncio.sleep(self.reconnect_delay)
                else:
                    logging.error("Max reconnection attempts reached. Could not connect to server.")
                    return False
            except Exception as e:
                logging.error(f"Network connection failed: {e}")
                if attempt < self.reconnect_attempts - 1:
                    logging.info(f"Retrying in {self.reconnect_delay} seconds...")
                    await asyncio.sleep(self.reconnect_delay)
                else:
                    logging.error("Max reconnection attempts reached due to an unexpected error.")
                    return False
        return False


from common.protocol import pack_data, unpack_data # Added import

class NetworkManager:
    def __init__(self, host="127.0.0.1", port=8888):
        self.host = host
        self.port = port
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.is_connected = False
        self.reconnect_attempts = 5
        self.reconnect_delay = 5 # seconds
        self._receive_buffer = b'' # Buffer for handling partial packets

    async def connect(self) -> bool:
        for attempt in range(self.reconnect_attempts):
            try:
                logging.info(f"Attempting to connect to network {self.host}:{self.port} (Attempt {attempt + 1}/{self.reconnect_attempts})...")
                self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
                self.is_connected = True
                self._receive_buffer = b'' # Reset buffer on new connection
                logging.info(f"Network connection established to {self.host}:{self.port}.")
                return True
            except ConnectionRefusedError:
                logging.error(f"Connection to {self.host}:{self.port} refused.")
                if attempt < self.reconnect_attempts - 1:
                    logging.info(f"Retrying in {self.reconnect_delay} seconds...")
                    await asyncio.sleep(self.reconnect_delay)
                else:
                    logging.error("Max reconnection attempts reached. Could not connect to server.")
                    return False
            except Exception as e:
                logging.error(f"Network connection failed: {e}")
                if attempt < self.reconnect_attempts - 1:
                    logging.info(f"Retrying in {self.reconnect_delay} seconds...")
                    await asyncio.sleep(self.reconnect_delay)
                else:
                    logging.error("Max reconnection attempts reached due to an unexpected error.")
                    return False
        return False


    async def send(self, payload_data: bytes) -> bool:
        if not self.is_connected or not self.writer:
            logging.warning("Network not connected. Cannot send.")
            return False
        try:
            packed_frame = pack_data(payload_data)
            if not packed_frame:
                logging.error("Failed to pack data (pack_data returned empty bytes).")
                return False

            logging.info(f"NET TX (payload): {bytes_to_hex_string(payload_data)}")
            logging.debug(f"NET TX (packed frame): {bytes_to_hex_string(packed_frame)}")
            self.writer.write(packed_frame)
            await self.writer.drain()
            return True
        except ConnectionResetError:
            logging.error("Network connection reset by peer during send.")
            self.is_connected = False
            return False
        except Exception as e:
            logging.error(f"Network send error: {e}", exc_info=True)
            self.is_connected = False # Assume connection is lost on error
            return False

    async def receive_payloads(self) -> list[bytes]:
        """
        Receives data from the network, unpacks it, and returns a list of payloads.
        Manages an internal buffer for partial packets.
        """
        if not self.is_connected or not self.reader:
            logging.warning("Network not connected. Cannot receive.")
            return []
        try:
            # Read available data, up to a reasonable chunk size
            # This read is non-blocking in the sense that it won't wait forever for 4096 bytes
            # if less is available or connection closes.
            chunk = await self.reader.read(4096)

            if chunk == b'': # Connection closed by server
                logging.warning("Network connection closed by server (EOF received).")
                self.is_connected = False
                return []

            self._receive_buffer += chunk
            logging.debug(f"NET RX (chunk): {bytes_to_hex_string(chunk)}, Buffer now: {bytes_to_hex_string(self._receive_buffer)}")

            payloads, remaining_buffer = unpack_data(self._receive_buffer)
            self._receive_buffer = remaining_buffer

            if payloads:
                for i, p_load in enumerate(payloads):
                    logging.info(f"NET RX (unpacked payload {i+1}/{len(payloads)}): {bytes_to_hex_string(p_load)}")
            if self._receive_buffer:
                logging.debug(f"NET RX (remaining buffer after unpack): {bytes_to_hex_string(self._receive_buffer)}")

            return payloads

        except ConnectionResetError:
            logging.error("Network connection reset by peer during receive.")
            self.is_connected = False
            self._receive_buffer = b'' # Clear buffer on connection error
            return []
        except asyncio.IncompleteReadError as e:
            # This error typically means the stream ended before the specified number of bytes (n in read(n)) was read.
            # For read(4096), it's more about the stream ending unexpectedly.
            logging.error(f"Incomplete read from network: {bytes_to_hex_string(e.partial)}. Connection may be closed.")
            self.is_connected = False
            self._receive_buffer = b''
            return []
        except Exception as e:
            logging.error(f"Network receive error: {e}", exc_info=True)
            self.is_connected = False # Assume connection is lost on error
            self._receive_buffer = b''
            return []

    async def close(self):
        if self.writer:
            logging.info("Closing network writer.")
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except Exception as e:
                logging.warning(f"Error while closing network writer: {e}")
        self.is_connected = False
        self.reader = None
        self.writer = None
        logging.info("Network connection closed.")

async def uart_to_network_flow(uart_manager: UARTManager, network_manager: NetworkManager):
    while True:
        if not uart_manager.is_connected:
            logging.info("UART disconnected in uart_to_network_flow. Attempting to reconnect...")
            await uart_manager.connect() # Placeholder connect
            if not uart_manager.is_connected:
                await asyncio.sleep(5) # Wait before retrying UART connection
                continue

        if not network_manager.is_connected:
            logging.info("Network disconnected in uart_to_network_flow. Attempting to reconnect network...")
            if not await network_manager.connect(): # Try to reconnect
                logging.warning("uart_to_network_flow: Network reconnection failed. Waiting before retry...")
                await asyncio.sleep(network_manager.reconnect_delay)
                continue # Skip to next iteration to try connecting again

        uart_data = await uart_manager.read_uart()
        if uart_data:
            success = await network_manager.send(uart_data)
            if not success:
                logging.error("Failed to send UART data to network. Network might be down (send indicated failure).")
                # network_manager.send already sets is_connected to False if critical error.
                # The loop will attempt to reconnect at the start of the next iteration.
                await asyncio.sleep(1) # Brief pause before attempting reconnect via loop
        await asyncio.sleep(0.01) # Small delay to prevent busy loop if read_uart is too fast

async def network_to_uart_flow(uart_manager: UARTManager, network_manager: NetworkManager):
    while True:
        if not network_manager.is_connected:
            logging.info("Network disconnected in network_to_uart_flow. Attempting to reconnect network...")
            if not await network_manager.connect(): # Try to reconnect
                logging.warning("network_to_uart_flow: Network reconnection failed. Waiting before retry...")
                await asyncio.sleep(network_manager.reconnect_delay)
                continue # Skip to next iteration to try connecting again

        if not uart_manager.is_connected:
            logging.info("UART disconnected in network_to_uart_flow. Attempting to reconnect...")
            await uart_manager.connect() # Placeholder connect
            if not uart_manager.is_connected:
                await asyncio.sleep(5) # Wait before retrying UART connection
                continue

        # network_manager.receive() was changed to network_manager.receive_payloads()
        # which returns a list of payloads.
        net_payloads = await network_manager.receive_payloads()
        if net_payloads:
            for payload in net_payloads:
                if not uart_manager.is_connected: # Check UART connection before each write
                    logging.warning("UART disconnected before writing all network payloads. Breaking.")
                    break
                success = await uart_manager.write_uart(payload)
                if not success:
                    logging.error("Failed to write network data to UART. UART might be down.")
                    # If write fails, uart_manager.is_connected should be false
                    # The uart_manager.connect() at the start of the loop will try to recover
                    break # Stop processing further payloads in this batch if UART write fails

        # If no data or processing done, small sleep to prevent tight loop
        if not net_payloads:
             await asyncio.sleep(0.01)

async def main_pc_client():
    # Configuration (can be moved to a config file later)
    SERIAL_PORT = "COM_PLACEHOLDER" # e.g., "COM3" on Windows, "/dev/ttyUSB0" on Linux
    BAUD_RATE = 115200
    SERVER_HOST = "127.0.0.1"
    SERVER_PORT = 65432 # Using a different port than default 8888 to avoid conflicts

    uart = UARTManager(port=SERIAL_PORT, baudrate=BAUD_RATE)
    network = NetworkManager(host=SERVER_HOST, port=SERVER_PORT)

    # Initial connection attempts
    if not await uart.connect(): # Placeholder connect
        logging.error("Failed to connect to UART initially. Exiting.")
        return

    if not await network.connect():
        logging.error("Failed to connect to Network initially. Exiting.")
        # Clean up UART if network fails to connect initially
        await uart.close()
        return

    logging.info("PC Client started. Initial connections successful.")
    logging.info("Starting UART <-> Network data forwarding tasks...")

    try:
        task_uart_to_net = asyncio.create_task(uart_to_network_flow(uart, network))
        task_net_to_uart = asyncio.create_task(network_to_uart_flow(uart, network))

        # Keep main running, or handle termination gracefully
        # For this placeholder, we'll just let them run until an unhandled exception or Ctrl+C
        await asyncio.gather(task_uart_to_net, task_net_to_uart)

    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt received. Shutting down PC client...")
    except Exception as e:
        logging.error(f"An unexpected error occurred in main_pc_client: {e}", exc_info=True)
    finally:
        logging.info("Cleaning up resources...")
        if task_uart_to_net and not task_uart_to_net.done():
            task_uart_to_net.cancel()
        if task_net_to_uart and not task_net_to_uart.done():
            task_net_to_uart.cancel()

        # Wait for tasks to cancel
        # Note: gather with return_exceptions=True can be used if you want to inspect cancellation results
        try:
            await asyncio.gather(task_uart_to_net, task_net_to_uart, return_exceptions=True)
        except asyncio.CancelledError:
            logging.info("Data forwarding tasks cancelled.")

        await network.close()
        await uart.close()
        logging.info("PC Client shut down.")

if __name__ == "__main__":
    # This is mainly for standalone testing.
    # The server needs to be running for the network part to work.
    # To run this, you'd typically run the server first, then this client.
    # Since UART is placeholder, it doesn't need a real serial port yet.

    # Example of how to run (conceptual, as server is not yet implemented)
    # loop = asyncio.get_event_loop()
    # try:
    #     loop.run_until_complete(main_pc_client())
    # except KeyboardInterrupt:
    #     logging.info("Application interrupted. Closing...")
    # finally:
    #     # Additional cleanup if necessary, though main_pc_client handles its own.
    #     loop.close()
    asyncio.run(main_pc_client())
