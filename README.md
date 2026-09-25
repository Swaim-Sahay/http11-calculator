# HTTP/1.1 calculator assignment

This is a socket-only HTTP/1.1 server—no framework or HTTP server library.

## Run

In VS Code, open this folder and start the server:

```sh
python3 server.py
```

It listens on port `8080`. Keep this terminal running. In a second terminal,
run the marking-style keep-alive test:

```sh
python3 test_keep_alive.py
```

The test sends all required calculator requests through one TCP connection.
Each response includes `Content-Length`, and the server consumes exactly the
request body length before parsing the next request.

## Browser testing

The server is an HTTP calculator API, not a visual calculator website. Port
`8080` is only the server's door number; the URL must also include an operation
and its two numbers. Paste one complete URL into the browser:

```text
http://127.0.0.1:8080/add?a=2&b=3
http://127.0.0.1:8080/sub?a=10&b=4
http://127.0.0.1:8080/mul?a=6&b=7
http://127.0.0.1:8080/div?a=9&b=3
```

Opening only `http://127.0.0.1:8080/` correctly returns 404 because `/` is
not one of the assignment's calculator routes. A 404 for `/favicon.ico` in the
browser console is also harmless.

## Required behaviour

| Request | Status | Body |
|---|---:|---|
| `GET /add?a=2&b=3` | 200 | `5` |
| `GET /sub?a=10&b=4` | 200 | `6` |
| `GET /mul?a=6&b=7` | 200 | `42` |
| `GET /div?a=9&b=3` | 200 | `3` |
| divide by zero or invalid `a`/`b` | 400 | error message |
| unsupported path, such as `/pow` | 404 | error message |
| non-GET method | 405 | error message |
| no `Host` header | 400 | error message |
# http11-calculator
