"""Bridge CommunicationMod to a host-only Unix socket for setup and scoring."""

import json
import socket
import sys
import threading
import time

SOCKET = "/tmp/sts-observer.sock"


class Observer:
    """Serialize read-only state requests and the initial run setup command."""

    def __init__(self) -> None:
        """Initialize synchronization for the game's line-oriented protocol."""
        self.condition = threading.Condition()
        self.latest = None
        self.sequence = 0
        self.started = False

    def read_game(self) -> None:
        """Continuously consume complete state lines without select/readline buffering races."""
        for line in sys.stdin:
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue
            with self.condition:
                self.latest = raw
                self.sequence += 1
                self.condition.notify_all()

    def command(self, command: str) -> dict:
        """Send one permitted command and wait for a fresh game response."""
        if command != "STATE":
            if not command.startswith("START ") or self.started:
                raise ValueError(
                    "Only STATE and one initial START command are permitted"
                )
            self.started = True
        with self.condition:
            previous = self.sequence
            print(command, flush=True)
            deadline = time.monotonic() + 25
            while self.sequence <= previous:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("CommunicationMod did not return a fresh state")
                self.condition.wait(remaining)
            return self.latest

    def run(self) -> None:
        """Expose a local socket after the CommunicationMod handshake completes."""
        threading.Thread(target=self.read_game, daemon=True).start()
        print("ready", flush=True)
        with self.condition:
            if not self.condition.wait_for(lambda: self.latest is not None, timeout=60):
                raise TimeoutError("No initial CommunicationMod state")
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(SOCKET)
            server.listen(4)
            while True:
                conn, _ = server.accept()
                with conn:
                    conn.settimeout(30)
                    try:
                        command = conn.makefile("r").readline(4096).strip()
                        response = self.command(command)
                    except (ValueError, OSError, TimeoutError) as exc:
                        response = {"error": f"{type(exc).__name__}: {exc}"}
                    conn.sendall(json.dumps(response).encode() + b"\n")


def client(command: str) -> None:
    """Print the observer's response for a trusted controller-side request."""
    with socket.socket(socket.AF_UNIX) as conn:
        conn.settimeout(28)
        conn.connect(SOCKET)
        conn.sendall(command.encode() + b"\n")
        response = conn.makefile("r").readline()
        if not response:
            raise RuntimeError("Observer closed without a response")
        print(response, end="")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "client":
        client(sys.argv[2])
    else:
        Observer().run()
