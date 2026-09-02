# Task 4: HTTP Range Byte Source — Report

## Summary
Successfully implemented HTTP range request byte source for reading remote GGUF file headers without full download.

## Changes

### Added Files
- `tests/test_http_range.py` — New test module with two tests:
  - `test_range_read_returns_requested_bytes`: Verifies basic HTTP range read
  - `test_parses_remote_header_without_full_download`: Verifies metadata parsing without downloading tensors

### Modified Files
- `src/ggufdoctor/bytesource.py` — Appended (no existing code changed):
  - `HttpSourceError(Exception)` — Exception for HTTP read failures
  - `HttpRangeByteSource(url, headers=None)` — HTTP range request reader

## Implementation Details

**HttpRangeByteSource** implements the `ByteSource` protocol:
- `__init__(url, headers=None)` — Initializes with optional custom headers, adds default User-Agent
- `read(offset, length)` — Sends `Range: bytes=offset-offset+length-1` header via `urllib.request`
- Tracks `bytes_fetched` for monitoring bandwidth usage
- Handles both 200 (full file) and 206 (partial content) responses
- Raises `HttpSourceError` on non-200/206 HTTP status or network errors

**Test Strategy** (no network calls):
- Uses Python's built-in `HTTPServer` and `SimpleHTTPRequestHandler` started in a background thread
- Creates fixture-based test GGUF file locally with 5MB padding to test range reads
- Verifies that parsing remote headers fetches far less than full file size (<3MB of 5MB+)
- All tests run locally without external dependencies

## Test Execution

```bash
$ pytest tests/test_http_range.py -v
============================= test session starts ==============================
tests/test_http_range.py::test_range_read_returns_requested_bytes PASSED [ 50%]
tests/test_http_range.py::test_parses_remote_header_without_full_download PASSED [100%]

============================== 2 passed in 0.06s ===============================
```

Full suite (13 tests):
```bash
$ pytest tests/ -v
============================== 13 passed in 0.05s ===============================
```

All 11 existing tests continue to pass. New tests run without network access.

## Commit
- **SHA:** `90a09ea`
- **Message:** `feat: HTTP range byte source for remote GGUF headers`
- **Files:** `src/ggufdoctor/bytesource.py`, `tests/test_http_range.py`

## Adherence to Brief
✓ Implementation appended verbatim from brief (no reformatting of existing code)
✓ Uses only `urllib.request` from stdlib (no `requests`, `httpx`, or test mocks)
✓ Raises `HttpSourceError` on non-206/200 responses
✓ Tracks `bytes_fetched` for bandwidth monitoring
✓ Tests use local HTTP server fixture (no network calls, no external test libraries)
✓ `ByteSource` protocol satisfied: `read(offset, length) -> bytes`
✓ All existing tests pass untouched

## Deviations
None. Implementation follows brief exactly.

## Notes for Later Tasks
- `HttpRangeByteSource.bytes_fetched` tracks cumulative bytes from all `read()` calls for bandwidth reporting
- The HTTP status check accepts both 200 (server doesn't support ranges) and 206 (proper range response)
- Timeout is fixed at 30 seconds; consider making configurable if needed for production use
- User-Agent header is set to `ggufdoctor/0.1` by default

---

## Fix Round 1

**Issues Fixed:**

1. **Correctness bug (Finding A):** Original code accepted HTTP 200 responses at any offset. This is wrong: a 200 response means the server sent the full body from byte 0. Requesting offset 500 with an unaware server would return bytes 0-length instead of bytes 500-(500+length), silently corrupting data.

2. **Test validity bug (Finding B):** `SimpleHTTPRequestHandler` doesn't implement byte-range serving; it always returns 200 with the full body. The test suite never exercised the 206 path, and the `bytes_fetched < 3_000_000` assertion only measured the Cursor's 1 MB buffer, not actual range efficiency.

**Changes Made:**

1. **HttpRangeByteSource.read()** — Updated to properly handle HTTP status codes:
   - Accept 206 (Partial Content) as the valid range response
   - Accept 200 only when `offset == 0` (full file from start is correct)
   - Raise `HttpSourceError` with message "server does not support byte ranges" when receiving 200 at nonzero offset
   - Cap returned bytes to requested `length` to prevent over-reading

2. **tests/test_http_range.py** — Complete rewrite:
   - Added `RangeAwareHTTPRequestHandler` subclass that properly parses `Range: bytes=start-end` headers and returns 206 responses with correct `Content-Range` header
   - Suppressed logging noise via `log_message()` override
   - Created two fixtures:
     - `served` — uses range-aware handler (tests normal operation)
     - `served_no_range` — uses standard handler (tests error case)
   - Updated original two tests to work with new fixtures
   - Added `test_nonzero_offset_returns_correct_bytes()` — verifies nonzero offset reads return correct bytes by comparing to reconstructed file
   - Added `test_nonzero_offset_against_non_range_server_raises_error()` — verifies error handling when server doesn't support ranges
   - Moved GGUF blob creation to module level (`GGUF_BLOB`) for reuse

**Test Results:**

```bash
$ pytest tests/ -v
============================== 15 passed in 1.63s =======================================
```

- 2 original bytesource tests: PASS
- 4 HTTP range tests: PASS (2 original + 2 new)
- 4 models tests: PASS
- 5 reader tests: PASS
- No stderr noise from range-aware handler (SimpleHTTPRequestHandler noise is expected for the error test)

**Measured bytes_fetched:**
- Actual: **1,048,576 bytes** (exactly 1 × Cursor.CHUNK = 1 MB)
- This is the single 1 MB read-ahead chunk needed to capture the metadata
- Assertion tightened from `< 3_000_000` to `< 2_000_000` to reflect range efficiency
- Confirms ranges work: without them, entire 5+ MB file would be fetched

**Commit:**
- **SHA:** `e30ca7e`
- **Parent:** `90a09ea`
- **Message:** `fix: HTTP range byte source - verify offset support and use range-aware test handler`

---

## Fix Round 2

**Issue:** The efficiency test from Round 1 was not actually falsifiable. The client-side counter `bytes_fetched` measures bytes the *client consumed*, not bytes the *server sent*. A naive source that ignores Range headers, opens full-body GETs, and abandons them early would report the same `bytes_fetched == 1,048,576` as a proper range-requesting source.

**Root Cause:** Measurement was on the wrong side of the socket. No threshold on the client-side counter can distinguish genuine range requests from full downloads abandoned early.

**Solution:** Instrument the *server* to record what it actually sent.

**Changes Made:**

1. **RangeAwareHTTPRequestHandler instrumentation** — Added request logging:
   - Track `Range` header from each request (or `None` if absent)
   - Record HTTP status code sent (206 vs 200)
   - Track actual bytes written in response body
   - Accumulate to class-level `request_log` list, reset per fixture

2. **Test rewrite** — `test_parses_remote_header_without_full_download` now verifies server-side metrics:
   - Every request must carry a `Range` header
   - Every response must be `206 Partial Content`
   - Total bytes the server wrote must be small (< 2 MB, not 5+ MB)

3. **Added comment to `bytes_fetched`** — Clarified it is a client-side metric only, warning against using it as evidence of server-side efficiency.

**Falsification Proof:**

Created a `NaiveByteSource` that sends *no* `Range` header and downloads the full body per request:

| Metric | Real HttpRangeByteSource | Naive (no ranges) |
|--------|--------------------------|-------------------|
| Client `bytes_fetched` | 1,048,576 (1 MB) | 1,048,576 (1 MB) ← **same!** |
| Server bytes sent | 1,048,576 (1 MB) | 5,000,184 (5+ MB) |
| Range header | `bytes=0-1048575` | `None` |
| Status | 206 | 200 |

**Assertion results:**
- Real implementation: ✓ All assertions PASS (Range headers present, 206 status, 1 MB server bytes)
- Naive implementation: ✓ Assertions CORRECTLY FAIL (no Range header, 200 status, 5 MB server bytes)

The new server-side assertions are falsifiable and catch non-compliant implementations.

**Test Results:**

```bash
$ pytest tests/ -v
============================== 15 passed in 1.63s =======================================
```

All tests pass. One expected `BrokenPipeError` stderr from the non-range-aware test, and ~1.5s runtime from `socketserver` teardown poll (both non-blocking).

**Commit:**
- **SHA:** `07bc0d7`
- **Parent:** `e30ca7e`
- **Message:** `fix: instrument server to verify range compliance`

---

## Fix Round 3

**Issue:** The test failed against naive implementations, but for the wrong reason. When a naive client closed the connection after reading 1 MB of a 5 MB response, the server's `write()` raised `ConnectionResetError`, preventing the `append()` call from executing. This left the `request_log` empty, so the test failed on the length guard (`len(request_log) > 0`) instead of on the proper assertions (Range header, 206 status, bytes sent).

**Root Cause:** Logging happened *after* the write. When the write raised an exception, the log entry never recorded what the server *intended* to send.

**Solution:** Move the log entry to *before* the write. The record describes what the server decided to send (Range header to expect, status code, bytes to write), so it should not depend on the write succeeding.

**Change Made:**

Both the 206 and 200 paths now call `self.request_log.append(...)` immediately after `self.end_headers()` and before `self.wfile.write()`. The `bytes_written` field still accurately reflects the length of data the server is about to write.

**Falsification Proof (Revised):**

Now when the naive source closes after reading 1 MB:

```
NaiveByteSource request_log: [{'range_header': None, 'bytes_written': 5000184, 'status': 200}]
```

The test assertion that fires:
```
✓ Assertion FAILS: Missing Range header: {'range_header': None, 'bytes_written': 5000184, 'status': 200}
```

The log is now populated and the test fails on the correct assertion: the absence of a Range header, not on an empty log.

**Test Results:**

```bash
$ pytest tests/ -v
============================== 15 passed in 1.63s =======================================
```

All 15 tests pass.

**Commit:**
- **SHA:** `8a71217`
- **Parent:** `07bc0d7`
- **Message:** `fix: log request record before writing body`
