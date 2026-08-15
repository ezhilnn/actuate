import pytest

from actuate.graphs.agent import parse_tool_call
from actuate.graphs.tools import run_tool


def test_parse_tool_call() -> None:
    parsed = parse_tool_call('{"tool": "calculator", "args": {"expression": "1+2"}}')
    assert parsed == {"name": "calculator", "args": {"expression": "1+2"}}
    assert parse_tool_call("just a specialist paragraph") is None


@pytest.mark.asyncio
async def test_calculator_tool() -> None:
    out = await run_tool("calculator", {"expression": "(10+2)/4"}, {})
    assert out == "3.0"


@pytest.mark.asyncio
async def test_http_get_blocks_localhost() -> None:
    out = await run_tool("http_get", {"url": "https://127.0.0.1/"}, {})
    assert "NEED DATA" in out
    out2 = await run_tool("http_get", {"url": "file:///etc/passwd"}, {})
    assert "NEED DATA" in out2
