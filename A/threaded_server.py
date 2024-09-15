import socket
import threading
import struct
import time
import sys
import select

HEADER_FORMAT = "!HBBIIQ"  # Header format with 8-byte logical clock
MAGIC_NUMBER = 0xC461
VERSION = 1
HELLO, DATA, ALIVE, GOODBYE = 0, 1, 2, 3
INACTIVITY_TIMEOUT = 1000  # 20 seconds of inactivity

class ThreadedUDPServer:
    def __init__(self, port):
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.bind(("", port))
        self.sessions = {}
        self.shutdown_flag = False
        self.logical_clock = 0  # Global logical clock

    def update_logical_clock(self):
        self.logical_clock += 1
        return self.logical_clock

    def handle_client(self, data, address):
        try:
            # Unpack the data from the message, including the logical clock
            magic, version, command, sequence, session_id, counter = struct.unpack(HEADER_FORMAT, data[:20])
            session_key = (session_id, address)

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

            self.sessions[session_key]["last_activity"] = time.time()
            session_state = self.sessions[session_key]["state"]

            # Update local logical clock based on received message's counter
            self.logical_clock = max(self.logical_clock, counter) + 1

            if session_state == "Receive":
                self.handle_receive_state(command, sequence, session_key, data)

            elif session_state == "Done":
                if command == HELLO:
                    print(f"[Session {session_id}] Protocol error: HELLO received in Done state.")
                    self.send_goodbye(address, session_id)
                    del self.sessions[session_key]
                else:
                    print(f"[Session {session_id}] Protocol error in Done state. Ignoring messages.")
                    self.send_goodbye(address, session_id)
                    del self.sessions[session_key]
        except ConnectionResetError:
            print(f"[Session {session_id}] Connection reset by client.")
            self.handle_session_cleanup(session_key)
        except Exception as e:
            print(f"Error handling client data: {e}")

    def handle_receive_state(self, command, sequence, session_key, data):
        try:
            session_id, address = session_key
            expected_sequence = self.sessions[session_key]["expected_sequence"]

            if sequence > expected_sequence:
                for i in range(expected_sequence, sequence):
                    print(f"{session_id} [{i}] Lost packet!")
                self.sessions[session_key]["expected_sequence"] = sequence + 1
            elif sequence == expected_sequence:
                self.sessions[session_key]["expected_sequence"] += 1
            elif sequence < expected_sequence:
                if sequence in self.sessions[session_key]["isFound"]:
                    print(f"{session_id} [{sequence}] Duplicate packet")
                else:
                    print(f"{session_id} [{sequence}] Protocol error!")
                    self.send_goodbye(address, session_id)
                    self.handle_session_cleanup(session_key)
                    return

            self.sessions[session_key]["isFound"].append(sequence)

            if command == HELLO:
                self.handle_hello(address, session_id)
            elif command == DATA:
                message = data[20:].decode('utf-16', errors='replace')  # Adjusted offset to 20 bytes
                print(f"{session_id} [{sequence}] {message}")
                self.send_alive(address, session_id)
            elif command == GOODBYE:
                print(f"{session_id} [{sequence}] Goodbye from client")
                self.handle_session_cleanup(session_key)
        except Exception as e:
            print(f"Error handling receive state: {e}")

    def handle_hello(self, address, session_id):
        print(f"{session_id} [0] Session created")
        self.send_message(address, HELLO, session_id)

    def send_alive(self, address, session_id):
        self.send_message(address, ALIVE, session_id)

    def send_goodbye(self, address, session_id):
        print(f"{session_id} Session closed")
        self.send_message(address, GOODBYE, session_id)

    def send_message(self, address, command, session_id):
        try:
            # Find the session using the tuple (session_id, address)
            session_key = (session_id, address)
            sequence_number = self.sessions[session_key]["expected_sequence"] if session_key in self.sessions else 0
            clock_value = self.update_logical_clock()  # Update and get the global logical clock value
            message = struct.pack(HEADER_FORMAT, MAGIC_NUMBER, VERSION, command, sequence_number, session_id, clock_value)
            self.server_socket.sendto(message, address)
        except Exception as e:
            print(f"Error sending message: {e}")

    def handle_session_cleanup(self, session_key):
        if session_key in self.sessions:
            address = session_key[1]
            session_id = session_key[0]
            self.sessions[session_key]["state"] = "Done"
            self.send_goodbye(address, session_id)

    def check_inactivity(self):
        while not self.shutdown_flag:
            try:
                current_time = time.time()
                inactive_sessions = [
                    session_key for session_key, data in self.sessions.items()
                    if current_time - data["last_activity"] > INACTIVITY_TIMEOUT and self.sessions[session_key]["state"] != "Done"
                ]
                for session_key in inactive_sessions:
                    session_id, address = session_key
                    print(f"[Session {session_id}] timed out due to inactivity")
                    self.handle_session_cleanup(session_key)

                time.sleep(1)  # Check inactivity every 1 second
            except Exception as e:
                print(f"Error in inactivity check: {e}")

    def shutdown(self):
        for session_key in list(self.sessions.keys()):
            self.handle_session_cleanup(session_key)

        self.shutdown_flag = True
        print("Server shutting down...")
        self.server_socket.close()

    def start(self):
        print(f"Waiting on port {self.port}")
        try:
            inactivity_thread = threading.Thread(target=self.check_inactivity)
            inactivity_thread.daemon = True
            inactivity_thread.start()

            input_thread = threading.Thread(target=self.wait_for_input)
            input_thread.daemon = True
            input_thread.start()

            while not self.shutdown_flag:
                try:
                    ready_sockets, _, _ = select.select([self.server_socket], [], [], 1)
                    if ready_sockets:
                        data, addr = self.server_socket.recvfrom(1024)
                        client_thread = threading.Thread(target=self.handle_client, args=(data, addr))
                        client_thread.start()
                except ConnectionResetError:
                    print("")
                except Exception as e:
                    if not self.shutdown_flag:
                        print(f"Error receiving data: {e}")

        except Exception as e:
            print(f"Server encountered an error: {e}")
        finally:
            self.shutdown()

    def wait_for_input(self):
        while not self.shutdown_flag:
            try:
                user_input = input()
                if user_input.lower() == "q" or user_input.lower() == "eof":
                    self.shutdown_flag = True
            except EOFError:
                print("EOF encountered. Shutting down server...")
                self.shutdown_flag = True


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <portnum>")
        sys.exit(1)

    port = int(sys.argv[1])
    server = ThreadedUDPServer(port)
    server.start()