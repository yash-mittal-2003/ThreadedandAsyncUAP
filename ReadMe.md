# Project Overview

This project implements a basic UDP-based client-server communication system using the asyncio library. Both the client and server follow the UAP (User-Agent Protocol) to exchange messages. The communication process is designed to be resilient, with features such as sequence number checking, inactivity timeouts, and support for sending and receiving multiple types of messages (`HELLO`, `DATA`, `ALIVE`, `GOODBYE`).

There are two primary versions of the server and client:

1. **Threaded Server and Client (non-asyncio)**
2. **Non-Threaded Asynchronous Server and Client (using asyncio)**

Each version follows a Finite State Machine (FSM) to manage the message flow and handle various commands (`HELLO`, `DATA`, `ALIVE`, `GOODBYE`).

## FSM Overview for Client and Server

Both client and server FSMs are based on the sequence of message types and the current state. Here are the state machines for both:

### Client FSM:

1. **Hello Wait**: The client sends a `HELLO` message and waits for a `HELLO` response from the server. Once received, the state moves to **Ready**.
2. **Ready**: The client is ready to send or receive `DATA` messages. If the server sends an `ALIVE` message, the client resets its inactivity timer.
3. **Closing**: When the client receives or sends a `GOODBYE` message, it transitions to the **Closed** state.
4. **Closed**: The session is closed, and no further communication takes place.

### Server FSM:

1. **Receive**: The server listens for incoming messages. Upon receiving a `HELLO` message, it responds with a `HELLO` and keeps the session active. It listens for subsequent `DATA` or `ALIVE` messages.
2. **Done**: When a `GOODBYE` message is received from the client, the session is closed, and the server transitions to the **Done** state.
3. **Timeout**: If the client is inactive for more than 20 seconds, the server sends a `GOODBYE` message and closes the session.

## File Descriptions

### 1. `B/async_server.py`

This script contains the implementation of the non-threaded asynchronous UDP server using asyncio. The server listens for client messages, processes commands based on the FSM, and manages sessions with a timeout mechanism for inactive clients.

**Key Features**:
- Non-blocking message handling with asyncio
- Inactivity timeout checking
- Command handling for `HELLO`, `DATA`, `ALIVE`, `GOODBYE`

### 2. `B/async_client.py`

This script implements the non-threaded asynchronous UDP client. It communicates with the server, sending `HELLO`, `DATA`, and `GOODBYE` messages. It follows the FSM to manage state transitions and user inputs.

**Key Features**:
- Asynchronous user input handling with asyncio
- Sends `HELLO`, `DATA`, and `GOODBYE` messages
- Handles server responses with FSM-based transitions

### 3. `A/threaded_server.py`

This script contains a threaded implementation of the UDP server. It spawns separate threads to handle client messages and inactivity timeouts. The server operates in a blocking mode, unlike the asyncio version.

**Key Features**:
- Multithreading for handling multiple client messages
- Timeout handling in separate threads
- Follows the same UAP protocol

### 4. `A/threaded_client.py`

This script contains a threaded implementation of the UDP client. It operates in a blocking mode and uses threading to handle user inputs and server responses concurrently.

**Key Features**:
- Multithreaded client for input and response handling
- Sends `HELLO`, `DATA`, and `GOODBYE` messages
- Operates in a blocking mode

## Instructions to Run (on Linux/Mac or Git Bash on Windows)

### How to Run the Server

1. Open a terminal and navigate to the directory containing the `server.sh` script and `server.py` file.
2. Ensure that Python is installed and properly set up in your system.
3. To run the server, use the following command format:

   ```bash
   ./server.sh <portnum> [output_file]
   ```

   - `<portnum>`: The port number on which the server will listen for incoming client connections.
   - `[output_file]`: (Optional) The name of the file where the server's output will be saved. If no file is provided, the output will be displayed in the console.

4. Examples:
   - To run the server and display output in the console:
     ```bash
     ./server.sh 8080
     ```
   - To run the server and save the output to a file:
     ```bash
     ./server.sh 8080 server_output.txt
     ```

Make sure to start the server before running the client.

### How to Run the Client

1. Open a terminal and navigate to the directory containing the `client.sh` script and `client.py` file.
2. Ensure that Python is installed and properly set up in your system.
3. To run the client, use the following command format:

   ```bash
   ./client.sh <hostname> <portnum> [filename]
   ```

   - `<hostname>`: The hostname or IP address of the server you want to connect to.
   - `<portnum>`: The port number on which the server is listening.
   - `[filename]`: (Optional) The name of the file whose content you want to send to the server. If no filename is provided, the client will run without file redirection.

4. Examples:
   - To run the client without a file:
     ```bash
     ./client.sh localhost 8080
     ```
   - To run the client with a file:
     ```bash
     ./client.sh localhost 8080 data.txt
     ```

Make sure the server is already running and ready to accept connections before running the client.

## Instructions to Run (if you do not have Git on Windows)

Ensure Python is installed and properly set up.

1. Start the async or threaded UDP server:
   ```bash
   python server.py <port_number>
   ```

2. Start the async UDP client in another terminal or machine:
   ```bash
   python client.py <hostname> <port_number>
   ```

Make sure both server and client are on the same network or provide the correct hostname and port, and the server is running when the client starts.

### Ending the Session

Type `q` or `eof` or use an EOF keyboard operation to end the client or the server.

## Notes

- The asynchronous version uses asyncio for concurrency, whereas the threaded version uses Python threads to achieve concurrent behavior.
- Both versions implement a state machine to handle message sequencing and session management.
- The server implements inactivity detection and closes sessions after 20 seconds of inactivity from the client.


