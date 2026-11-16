"""R-21: the documented tool schemas (docs/TOOL_SCHEMAS.md) must match what the server actually publishes."""

import asyncio

from funding_mcp.schema_doc import DOC_PATH, render


def test_tool_schema_doc_is_up_to_date():
    expected = asyncio.run(render())
    actual = DOC_PATH.read_text(encoding="utf-8")
    assert actual == expected, "docs/TOOL_SCHEMAS.md is stale: run `uv run python -m funding_mcp.schema_doc`"
