import socket
import struct
import random
import time
import threading
import sys

HEADER_FORMAT = "!HBBIIQ"  # Updated format to include 8-byte logical clock
MAGIC_NUMBER = 0xC461
VERSION = 1
HELLO, DATA, ALIVE, GOODBYE = 0, 1, 2, 3
TIMEOUT = 1000  # seconds

class ThreadedUDPClient:
    def __init__(self, host, port):
        self.server_address = (host, port)
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.client_socket.settimeout(TIMEOUT)  # Set a timeout for receiving data
        self.session_id = random.randint(1, 1_000_000)
        self.sequence = 0
        self.state = "Hello Wait"  # Initial state is 'Hello Wait'
        self.last_activity_time = time.time()
        self.stop_client = False  # To signal threads to stop
        self.logical_clock = 0  # Initialize logical clock

    def send_message(self, command, message=""):
        self.logical_clock += 1  # Increment the logical clock before sending a message
        header = struct.pack(HEADER_FORMAT, MAGIC_NUMBER, VERSION, command, self.sequence, self.session_id, self.logical_clock)
        if message:
            header += message.encode('utf-16', errors='ignore')

        self.client_socket.sendto(header, self.server_address)
        self.sequence += 1
        

    def receive_message(self):
        try:
            data, addr = self.client_socket.recvfrom(1024)
            magic, version, command, sequence, session_id, received_clock = struct.unpack(HEADER_FORMAT, data[:20])
            if magic != MAGIC_NUMBER or version != VERSION or session_id != self.session_id:
                print("Received invalid message. Ignoring...")
                return None, None
            self.logical_clock = max(self.logical_clock, received_clock) + 1  # Update logical clock based on received message
            return command, data[20:]
        except socket.timeout:
            print("Socket timeout. No response from server.")
            return None, None
        except Exception as e:
            print(f"Error receiving message: {e}")
            return None, None

    def update_state(self, command):
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
        elif self.state == "Closing" and command == ALIVE:
            print("Received ALIVE while closing. Moving to 'Closed' state.")
            self.state = "Closed"
            self.stop_client = True
        elif command == GOODBYE:
            print("Received GOODBYE. Moving to 'Closed' state.")
            self.state = "Closed"
            self.stop_client = True

    def listen_for_responses(self):
        while not self.stop_client:
            command, _ = self.receive_message()
            if command is not None:
                self.update_state(command)

            if time.time() - self.last_activity_time > TIMEOUT and self.state != "Closed":
                self.send_message(GOODBYE)
                print("Inactivity timeout. Moving to 'Closing' state.")
                self.state = "Closing"

            if self.state == "Closed":
                self.stop_client = True
                print("Connection closed due to inactivity timeout.")
                break

    def handle_user_input(self):
        while not self.stop_client:
            if self.state == "Ready":
                if self.stop_client:
                    break

                try:
                    user_input = input("> ")
                except EOFError:
                    user_input = "eof"

                if user_input == 'q' or user_input == "eof":
                    if user_input == "eof":
                        print("Received EOF. Moving to 'Closing' state.")
                    self.send_message(GOODBYE)
                    print("GOODBYE sent. Moving to 'Closing' state.")
                    self.state = "Closing"
                    self.stop_client = True
                else:
                    self.send_message(DATA, user_input)
                    print(f"Sent: {user_input}")
                    self.last_activity_time = time.time()

            if self.state == "Closed" or self.stop_client:
                break

    def start(self):
        try:
            self.send_message(HELLO)
            print("HELLO sent. Starting conversation...")
            self.state = "Hello Wait"
            self.last_activity_time = time.time()

            response_thread = threading.Thread(target=self.listen_for_responses)
            input_thread = threading.Thread(target=self.handle_user_input)

            response_thread.daemon = True
            input_thread.daemon = True
            response_thread.start()
            input_thread.start()

            input_thread.join()
            response_thread.join()
        finally:
            try:
                self.client_socket.close()
                print("Client socket closed.")
            except Exception as e:
                print(f"Error closing client socket: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <hostname> <portnum>")
        sys.exit(1)
    hostname = sys.argv[1]
    port = int(sys.argv[2])
    client = ThreadedUDPClient(hostname, port)
    client.start()
