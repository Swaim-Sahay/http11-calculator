#!/usr/bin/env python3
"""Manual marking-style test: six requests, exactly one TCP connection."""

import socket


def read_response(sock: socket.socket, buffered: bytes) -> tuple[int, bytes, bytes]:
    while b"\r\n\r\n" not in buffered:
        buffered += sock.recv(4096)
    raw_headers, buffered = buffered.split(b"\r\n\r\n", 1)
    lines = raw_headers.decode("iso-8859-1").split("\r\n")
    status = int(lines[0].split()[1])
    headers = {}
    for line in lines[1:]:
        name, value = line.split(":", 1)
        headers[name.lower()] = value.strip()
    size = int(headers["content-length"])
    while len(buffered) < size:
        buffered += sock.recv(4096)
    return status, buffered[:size], buffered[size:]


tests = [
    ("GET", "/add?a=2&b=3", 200, b"5"),
    ("GET", "/sub?a=10&b=4", 200, b"6"),
    ("GET", "/mul?a=6&b=7", 200, b"42"),
    ("GET", "/div?a=1&b=0", 400, None),
    ("GET", "/pow?a=2&b=8", 404, None),
    ("POST", "/add", 405, None),
]

with socket.create_connection(("localhost", 8080)) as sock:
    leftover = b""
    for method, path, expected_status, expected_body in tests:
        request = (
            f"{method} {path} HTTP/1.1\r\n"
            "Host: localhost\r\n"
            "Content-Length: 0\r\n"
            "\r\n"
        ).encode("ascii")
        sock.sendall(request)
        status, body, leftover = read_response(sock, leftover)
        assert status == expected_status, (path, status, expected_status)
        if expected_body is not None:
            assert body == expected_body, (path, body, expected_body)
        print(f"{method:4} {path:20} -> {status} {body.decode()}")

    print("socket still open:", sock.fileno() != -1)
    print(f"1 TCP connection, {len(tests)} responses")
