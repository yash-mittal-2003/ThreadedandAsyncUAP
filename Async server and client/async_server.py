import socket
import struct
import time
import asyncio
import sys

HEADER_FORMAT = "!HBBIIQ"  # Include 8-byte logical clock
MAGIC_NUMBER = 0xC461
VERSION = 1
HELLO, DATA, ALIVE, GOODBYE = 0, 1, 2, 3
INACTIVITY_TIMEOUT = 1000  # 20 seconds of inactivity

class AsyncUDPServer:
    def __init__(self, port):
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.bind(("", port))
        self.server_socket.setblocking(False)  # Set to non-blocking for asyncio compatibility
        self.sessions = {}
        self.shutdown_flag = False
        self.tasks = []
        self.logical_clock = 0  # Single logical clock for the entire server

    async def send_message(self, command, session_key, message=""):
        session_id, address = session_key
        sequence = self.sessions[session_key]["expected_sequence"]
        self.logical_clock += 1  # Increment logical clock for each sent message
        header = struct.pack(HEADER_FORMAT, MAGIC_NUMBER, VERSION, command, sequence, session_id, self.logical_clock)
        if message:
            header += message.encode('utf-16')
        
        await asyncio.get_running_loop().sock_sendto(self.server_socket, header, address)

    async def receive_message(self):
        try:
            data, address = await asyncio.get_running_loop().sock_recvfrom(self.server_socket, 1024)
            return data, address
        except asyncio.TimeoutError:
            return None, None

    async def handle_client_message(self, data, address):
        try:
            magic, version, command, sequence, session_id, received_clock = struct.unpack(HEADER_FORMAT, data[:20])
            session_key = (session_id, address)

            # Validate header
            if magic != MAGIC_NUMBER or version != VERSION:
                print("Invalid message. Ignoring...")
                return

            if session_key not in self.sessions:
                self.sessions[session_key] = {
                    "expected_sequence": 0,
                    "last_activity": time.time(),
                    "state": "Receive",
                    "isFound": []
                }
            else:
                self.sessions[session_key]["last_activity"] = time.time()

            # Update logical clock based on received clock
            self.logical_clock = max(self.logical_clock, received_clock) + 1

            session_state = self.sessions[session_key]["state"]

            if session_state == "Receive":
                await self.handle_receive_state(command, sequence, session_key, data)

            elif session_state == "Done":
                if command == HELLO:
                    print(f"[Session {session_id}] Protocol error: HELLO received in Done state.")
                else:
                    print(f"[Session {session_id}] Protocol error in Done state. Ignoring messages.")
                await self.handle_goodbye(session_key)
                del self.sessions[session_key]
                    
        except Exception as e:
            print(f"Error handling client message: {e}")

    async def handle_receive_state(self, command, sequence, session_key, data):
        try:
            session_id, address = session_key
            expected_sequence = self.sessions[session_key]["expected_sequence"]

            if sequence > expected_sequence:
                for i in range(expected_sequence, sequence):
                    print(f"{session_id} [{i}] Lost packet!")
                self.sessions[session_key]["expected_sequence"] = sequence + 1
            elif sequence == expected_sequence:
                if sequence in self.sessions[session_key]["isFound"]:
                    print(f"{session_id} [{sequence}] Duplicate packet")
                    return
                self.sessions[session_key]["expected_sequence"] += 1
            elif sequence < expected_sequence:
                print(f"{session_id} [{sequence}] Protocol error!")
                await self.handle_goodbye(session_key)
                return

            self.sessions[session_key]["isFound"].append(sequence)

            if command == HELLO:
                await self.handle_hello(session_key)
                self.sessions[session_key]["last_activity"] = time.time()
            elif command == DATA:
                message = data[20:].decode('utf-16', errors='replace')
                print(f"{session_id} [{sequence}] {message}")
                await self.send_message(ALIVE, session_key)
                self.sessions[session_key]["last_activity"] = time.time()
            elif command == GOODBYE:
                print(f"{session_id} [{sequence}] Goodbye from client")
                await self.handle_goodbye(session_key)
        except Exception as e:
            print(f"Error handling receive state: {e}")

    async def handle_hello(self, session_key):
        session_id, _ = session_key
        print(f"{session_id} [0] session created")
        await self.send_message(HELLO, session_key)

    async def handle_goodbye(self, session_key):
        if session_key in self.sessions:
            session_id, address = session_key
            self.sessions[session_key]["state"] = "Done"
            await self.send_message(GOODBYE, session_key)
            print(f"[Session {session_id}] Session closed.")

    async def check_inactivity(self):
        while not self.shutdown_flag:
            current_time = time.time()
            inactive_sessions = [
                session_key for session_key, data in self.sessions.items()
                if current_time - data["last_activity"] > INACTIVITY_TIMEOUT and self.sessions[session_key]["state"] != "Done"
            ]
            for session_key in inactive_sessions:
                session_id, _ = session_key
                print(f"[Session {session_id}] timed out due to inactivity")
                await self.handle_goodbye(session_key)
            await asyncio.sleep(1)

    async def listen_for_messages(self):
        while not self.shutdown_flag:
            data, address = await self.receive_message()
            if data:
                await self.handle_client_message(data, address)

    async def handle_user_input(self):
        while not self.shutdown_flag:
            try:
                user_input = await asyncio.get_event_loop().run_in_executor(None, input, "")
                if user_input.lower() in ["q", "quit", "eof"]:
                    print("Shutting down server...")
                    self.shutdown_flag = True
                    for task in self.tasks:
                        task.cancel()
            except EOFError:
                print("EOF encountered. Shutting down server...")
                self.shutdown_flag = True
                for task in self.tasks:
                    task.cancel()

    async def start(self):
        print(f"Waiting on port {self.port}")
        try:
            message_task = asyncio.create_task(self.listen_for_messages())
            inactivity_task = asyncio.create_task(self.check_inactivity())
            input_task = asyncio.create_task(self.handle_user_input())

            self.tasks.extend([message_task, inactivity_task, input_task])

            await asyncio.gather(message_task, inactivity_task, input_task)
        except asyncio.CancelledError:
            pass
        finally:
            await self.shutdown()

    async def shutdown(self):
        print("Server shutdown initiated")
        for task in self.tasks:
            task.cancel()

        await asyncio.gather(*self.tasks, return_exceptions=True)

        for session_key in list(self.sessions.keys()):
            await self.handle_goodbye(session_key)

        if not self.server_socket._closed:
            self.server_socket.close()
        print("Server socket closed.")

if __name__ == "__main__":
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    else:
        loop = asyncio.SelectorEventLoop()
        asyncio.set_event_loop(loop)

    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <portnum>")
        sys.exit(1)

    port = int(sys.argv[1])
    server = AsyncUDPServer(port)

    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("Server interrupted.")
        asyncio.run(server.shutdown())
