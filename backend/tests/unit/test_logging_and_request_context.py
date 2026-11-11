import json
import logging

from app.core.logging import JsonFormatter
from app.core.request_context import new_request_id, set_request_id


def test_request_id_accepts_safe_caller_value() -> None:
    assert new_request_id("abc-12345678") == "abc-12345678"


def test_request_id_replaces_unsafe_or_missing_value() -> None:
    for candidate in (None, "", "short", "has spaces and \n newline", "x" * 200):
        generated = new_request_id(candidate)
        assert generated != candidate
        assert len(generated) == 32


def test_json_formatter_includes_request_id_and_extras() -> None:
    set_request_id("req-logging-1")
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "hello %s", ("world",), None)
    record.status_code = 200
    payload = json.loads(JsonFormatter().format(record))
    assert payload["message"] == "hello world"
    assert payload["request_id"] == "req-logging-1"
    assert payload["status_code"] == 200
    assert payload["level"] == "INFO"


def test_json_formatter_logs_error_type_without_traceback() -> None:
    try:
        raise ValueError("secret detail")
    except ValueError:
        import sys

        record = logging.LogRecord("t", logging.ERROR, __file__, 1, "failed", (), sys.exc_info())
    output = JsonFormatter().format(record)
    assert json.loads(output)["error_type"] == "ValueError"
    assert "secret detail" not in output
