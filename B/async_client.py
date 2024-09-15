import asyncio
import socket
import struct
import random
import time

HEADER_FORMAT = "!HBBIIQ"  # Updated to include 8-byte logical clock
MAGIC_NUMBER = 0xC461
VERSION = 1
HELLO, DATA, ALIVE, GOODBYE = 0, 1, 2, 3
TIMEOUT = 1000  # seconds

class AsyncUDPClient:
    def __init__(self, host, port):
        self.server_address = (host, port)
        self.session_id = random.randint(1, 1_000_000)
        self.sequence = 0
        self.logical_clock = 0  # Initialize logical clock
        self.state = "Hello Wait"  # Initial state
        self.last_activity_time = time.time()
        self.stop_client = False  # To signal to stop the loop
        self.client_socket = None
        self.loop = asyncio.get_event_loop()

    async def send_message(self, command, message=""):
        self.logical_clock += 1  # Increment logical clock
        header = struct.pack(HEADER_FORMAT, MAGIC_NUMBER, VERSION, command, self.sequence, self.session_id, self.logical_clock)
        if message:
            header += message.encode('utf-16', errors='ignore')

        try:
            self.client_socket.sendto(header, self.server_address)
            print(f"Sent: Command {command}, Message: {message}")
        except OSError as e:
            print(f"Error sending message: {e}")
       
        self.sequence += 1

    async def receive_message(self):
        try:
            # Use recvfrom to receive UDP messages
            data, _ = await self.loop.run_in_executor(None, self.client_socket.recvfrom, 1024)

            # Unpack the header to include the logical clock
            magic, version, command, sequence, session_id, received_clock = struct.unpack(HEADER_FORMAT, data[:20])
            if magic != MAGIC_NUMBER or version != VERSION or session_id != self.session_id:
                print("Received invalid message. Ignoring...")
                return None, None

            # Update logical clock
            self.logical_clock = max(self.logical_clock, received_clock) + 1

            return command, data[20:]
        except Exception as e:
            print(f"Error receiving message: {e}")
            return None, None

    async def update_state(self, command):
        if self.state == "Hello Wait" and command == HELLO:
            print("Received HELLO from server. Moving to 'Ready' state.")
            self.state = "Ready"
        elif self.state == "Ready" and command == ALIVE:
            print("Received ALIVE from server. Resetting timer.")
            self.last_activity_time = time.time()
        elif self.state == "Ready" and command == GOODBYE:
            print("Received GOODBYE from server. Moving to 'Closed' state.")
            self.state = "Closed"
            self.stop_client = True
        elif command == GOODBYE:
            print("Received GOODBYE. Moving to 'Closed' state.")
            self.state = "Closed"
            self.stop_client = True

    async def listen_for_responses(self):
        while not self.stop_client:
            command, _ = await self.receive_message()
            if command is not None:
                await self.update_state(command)

            # Check for inactivity timeout
            if time.time() - self.last_activity_time > TIMEOUT and self.state != "Closed":
                await self.send_message(GOODBYE)
                print("Inactivity timeout. Moving to 'Closing' state.")
                self.state = "Closed"
                self.stop_client = True

    async def handle_user_input(self):
        while not self.stop_client:
            try:
                user_input = await self.loop.run_in_executor(None, input, "> ")
                if user_input.lower() == 'q' or user_input.lower() == 'eof':
                    await self.send_message(GOODBYE)
                    print("GOODBYE sent. Moving to 'Closing' state.")
                    self.state = "Closed"
                    self.stop_client = True
                else:
                    await self.send_message(DATA, user_input)
                    print(f"Sent: {user_input}")
                    self.last_activity_time = time.time()
            except EOFError:
                # Handle the case where Ctrl+D is pressed
                print("EOF encountered. Sending GOODBYE and closing.")
                await self.send_message(GOODBYE)
                self.state = "Closed"
                self.stop_client = True

    async def start(self):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.client_socket.setblocking(True)  # UDP communication in blocking mode

        try:
            await self.send_message(HELLO)
            print("HELLO sent. Starting conversation...")
            self.state = "Hello Wait"
            self.last_activity_time = time.time()

            # Create tasks to listen for server messages and handle user input concurrently
            await asyncio.gather(
                self.listen_for_responses(),
                self.handle_user_input()
            )
        finally:
            try:
                self.client_socket.close()
                print("Client socket closed.")
            except Exception as e:
                print(f"Error closing client socket: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <hostname> <portnum>")
        sys.exit(1)
   
    hostname = sys.argv[1]
    port = int(sys.argv[2])
   
    client = AsyncUDPClient(hostname, port)
   
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(client.start())  # Using loop.run_until_complete instead of asyncio.run
    except KeyboardInterrupt:
        print("Client interrupted.")