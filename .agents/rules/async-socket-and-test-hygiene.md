# Rule: Async Socket Lifecycle, Process Isolation & Test Hygiene

## 1. Asynchronous Socket & Stream Lifecycle
- **Mandatory `finally` Disconnect**: Any long-lived connection handler (WebSocket, SSE, streaming generator) MUST invoke its disconnect/cleanup routine inside an outermost `finally` block:
  ```python
  await manager.connect(socket, user_id)
  try:
      while True:
          msg = await socket.receive()
          ...
  finally:
      manager.disconnect(socket, user_id)
  ```
  Never rely solely on `except Exception` or `except WebSocketDisconnect`, as `asyncio.CancelledError` inherits from `BaseException` in Python 3.8+.
- **Bounded Broadcasts**: Connection managers (`ws_manager.send()`) must never execute unbounded writes to client sockets. Wrap client writes in `asyncio.wait_for(ws.send_text(data), timeout=2.0)` and discard dead sockets upon failure or timeout.
- **Copy Before Iteration**: Always iterate over an immutable snapshot of active connections (`list(connections)`), never the live set directly.

## 2. Filesystem & Encoding Invariants
- **Explicit UTF-8 Everywhere**: Never use bare `Path.read_text()` or `Path.write_text()` without `encoding="utf-8"`. Windows defaults to CP1252 and will raise `UnicodeDecodeError` on UTF-8 characters, emojis, or accents.
- **Node ESM Windows File URIs**: When passing filesystem paths to Node.js ESM dynamic imports on Windows, convert them via `path.as_uri()` (e.g. `file:///C:/path/file.js`), as bare Windows drive paths like `C:\...` fail Node ESM specifier resolution.
- **Byte Accuracy on Subtitle Boundaries**: When asserting or generating subtitle files (VTT/SRT) on Windows, write raw byte sequences (e.g., `b"WEBVTT\n\n"`) to avoid platform-dependent CRLF translation (`\r\n`) altering byte floors.

## 3. Test Runner & Application Lifespan Invariants
- **No Package Mutation During Lifespan/Test**: Application startup or test suites must NEVER execute `pip install`, package upgrades, or network dependency syncs.
- **Explicit Directory Invocation**: Full repository test runs must be invoked with the explicit directory argument: `python -m pytest tests/ -q`.
- **No Aggressive WMI Polling During High-I/O Tests**: Never query `Get-CimInstance Win32_Process` in rapid loops during test runs that spawn high volumes of ephemeral ffmpeg or SQLite worker processes, as it induces lock contention in the Windows instrumentation provider.
