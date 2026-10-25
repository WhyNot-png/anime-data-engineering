import io
import json
import logging

import pytest

from research_graph.logging_setup import JsonFormatter, setup_logging


def test_logging_goes_to_stderr_and_does_not_duplicate(capsys: pytest.CaptureFixture[str]) -> None:
    setup_logging("DEBUG")
    first_handler = logging.getLogger().handlers[0]
    setup_logging("INFO")
    assert first_handler not in logging.getLogger().handlers
    assert len(logging.getLogger().handlers) == 1
    logging.getLogger("research.test").info("hello-once")
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err.count("hello-once") == 1
    assert "INFO research.test" in out.err
    assert len(out.err.split()[0]) == 10  # Date precedes the level and message.
    assert logging.getLogger("urllib3").level == logging.WARNING


def test_json_logging(capsys: pytest.CaptureFixture[str]) -> None:
    setup_logging("INFO", "json")
    logging.getLogger("research.test").info("Строка %s", "данных")
    out = capsys.readouterr()
    assert out.out == ""
    assert len(out.err.splitlines()) == 1
    record = json.loads(out.err)
    assert record["message"] == "Строка данных"
    assert record["level"] == "INFO"
    assert record["logger"] == "research.test"
    assert record["time"].endswith("+00:00")


def test_json_exception_is_one_line(capsys: pytest.CaptureFixture[str]) -> None:
    setup_logging("INFO", "json")
    try:
        raise RuntimeError("expected failure")
    except RuntimeError:
        logging.getLogger("research.test").exception("computation failed")
    output = capsys.readouterr().err
    assert len(output.splitlines()) == 1
    assert "RuntimeError: expected failure" in json.loads(output)["exception"]


def test_reject_unknown_level() -> None:
    with pytest.raises(ValueError, match="level"):
        setup_logging("not-a-level")


def test_json_formatter_preserves_arguments() -> None:
    record = logging.LogRecord("demo", logging.WARNING, "test.py", 1, "value=%d", (7,), None)
    assert json.loads(JsonFormatter().format(record))["message"] == "value=7"


def test_replaces_existing_handler() -> None:
    old = logging.StreamHandler(io.StringIO())
    logging.getLogger().addHandler(old)
    setup_logging("INFO")
    assert old not in logging.getLogger().handlers
