#!/usr/bin/env python3
"""Socket-only HTTP/1.1 calculator with persistent connections."""

import argparse
import socket
import threading
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlsplit

MAX_HEADER_BYTES = 16 * 1024
MAX_BODY_BYTES = 1024 * 1024
STATUS_TEXT = {
    200: "OK",
    400: "Bad Request",
    404: "Not Found",
    405: "Method Not Allowed",
}


class BadRequest(Exception):
    """An HTTP request cannot be processed safely."""


@dataclass
class Request:
    method: str
    target: str
    version: str
    headers: dict[str, list[str]]
    body: bytes


class ConnectionReader:
    """Keeps unread TCP bytes between HTTP requests on the same socket."""

    def __init__(self, conn: socket.socket) -> None:
        self.conn = conn
        self.buffer = b""

    def _read_headers(self) -> bytes | None:
        while b"\r\n\r\n" not in self.buffer:
            if len(self.buffer) > MAX_HEADER_BYTES:
                raise BadRequest("headers are too large")
            received = self.conn.recv(4096)
            if not received:
                if self.buffer:
                    raise BadRequest("connection ended inside headers")
                return None
            self.buffer += received
        head, self.buffer = self.buffer.split(b"\r\n\r\n", 1)
        if len(head) > MAX_HEADER_BYTES:
            raise BadRequest("headers are too large")
        return head

    def _read_exact(self, amount: int) -> bytes:
        while len(self.buffer) < amount:
            received = self.conn.recv(min(4096, amount - len(self.buffer)))
            if not received:
                raise BadRequest("connection ended inside body")
            self.buffer += received
        body, self.buffer = self.buffer[:amount], self.buffer[amount:]
        return body

    def read_request(self) -> Request | None:
        raw_headers = self._read_headers()
        if raw_headers is None:
            return None
        try:
            lines = raw_headers.decode("iso-8859-1").split("\r\n")
        except UnicodeDecodeError as exc:
            raise BadRequest("headers are not text") from exc
        parts = lines[0].split(" ")
        if len(parts) != 3 or not all(parts):
            raise BadRequest("bad request line")
        method, target, version = parts
        if version != "HTTP/1.1":
            raise BadRequest("only HTTP/1.1 is supported")

        headers: dict[str, list[str]] = {}
        for line in lines[1:]:
            if ":" not in line:
                raise BadRequest("bad header line")
            name, value = line.split(":", 1)
            name = name.strip().lower()
            if not name:
                raise BadRequest("empty header name")
            headers.setdefault(name, []).append(value.strip())

        lengths = headers.get("content-length", [])
        if not lengths:
            content_length = 0
        elif len(lengths) != 1 or not lengths[0].isdigit():
            raise BadRequest("invalid Content-Length")
        else:
            content_length = int(lengths[0])
            if content_length > MAX_BODY_BYTES:
                raise BadRequest("body is too large")

        # This is the important HTTP/1.1 boundary: consume exactly this many
        # bytes, leaving byte n+1 in buffer for the next request.
        body = self._read_exact(content_length)
        return Request(method, target, version, headers, body)


def make_response(status: int, body: str, close: bool = False) -> bytes:
    body_bytes = body.encode("utf-8")
    headers = [
        f"HTTP/1.1 {status} {STATUS_TEXT[status]}",
        "Content-Type: text/plain; charset=utf-8",
        f"Content-Length: {len(body_bytes)}",
        "Connection: close" if close else "Connection: keep-alive",
        "",
        "",
    ]
    return "\r\n".join(headers).encode("ascii") + body_bytes


def calculate(request: Request) -> tuple[int, str]:
    host_values = request.headers.get("host", [])
    if len(host_values) != 1 or not host_values[0]:
        return 400, "Host header required"

    if request.method != "GET":
        return 405, "Only GET is allowed"

    parsed = urlsplit(request.target)
    if parsed.scheme or parsed.netloc or parsed.path not in {"/add", "/sub", "/mul", "/div"}:
        return 404, "Not Found"

    try:
        pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        return 400, "Bad query"
    if len(pairs) != 2 or {name for name, _ in pairs} != {"a", "b"}:
        return 400, "Query must contain one a and one b"

    values = dict(pairs)
    try:
        a, b = int(values["a"]), int(values["b"])
    except ValueError:
        return 400, "a and b must be integers"

    if parsed.path == "/add":
        return 200, str(a + b)
    if parsed.path == "/sub":
        return 200, str(a - b)
    if parsed.path == "/mul":
        return 200, str(a * b)
    if b == 0:
        return 400, "Cannot divide by zero"
    return 200, str(a // b)


def serve_connection(conn: socket.socket) -> None:
    reader = ConnectionReader(conn)
    while True:
        try:
            request = reader.read_request()
        except BadRequest as error:
            conn.sendall(make_response(400, str(error), close=True))
            return
        if request is None:
            return

        status, body = calculate(request)
        connection_values = request.headers.get("connection", [])
        close = any(value.lower() == "close" for value in connection_values)
        conn.sendall(make_response(status, body, close=close))
        if close:
            return


def serve_client(conn: socket.socket) -> None:
    """Keep one client alive without preventing the listener accepting another."""
    with conn:
        serve_connection(conn)


def main() -> None:
    parser = argparse.ArgumentParser(description="persistent HTTP/1.1 calculator")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((args.host, args.port))
        listener.listen()
        print(f"Listening on http://{args.host}:{args.port}")
        while True:
            conn, _ = listener.accept()
            threading.Thread(target=serve_client, args=(conn,), daemon=True).start()


if __name__ == "__main__":
    main()
