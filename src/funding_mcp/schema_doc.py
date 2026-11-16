"""Generate docs/TOOL_SCHEMAS.md from the running server's tool list, so the documented schemas cannot drift.

uv run python -m funding_mcp.schema_doc          # rewrite docs/TOOL_SCHEMAS.md
(tests/test_schema_doc.py fails if the committed file is out of date)
"""

import asyncio
import json
from pathlib import Path

from mcp import Client

from .server import FundingServer

DOC_PATH = Path(__file__).resolve().parents[2] / "docs" / "TOOL_SCHEMAS.md"

HEADER = """# MCP Tool Schemas (generated)

Generated from the running server by `uv run python -m funding_mcp.schema_doc`; `tests/test_schema_doc.py` fails if
this file differs from the code. Business meaning, roles and errors: [SPEC.md](SPEC.md) §5. Every tool can also return
the error envelope of SPEC §5.3 with `isError: true` (not covered by `outputSchema`, per MCP).
"""


async def render() -> str:
    # Listing tools needs no database or identity; the server is constructed but never started.
    async with Client(FundingServer(db_path=Path("unused.db"), staff_id=None)) as client:
        tools = (await client.list_tools()).tools
    parts = [HEADER]
    for tool in tools:
        hints = tool.annotations
        flags = (
            f"readOnly={hints.read_only_hint}, idempotent={hints.idempotent_hint}, destructive={hints.destructive_hint}"
        )
        parts.append(f"\n## `{tool.name}`\n\n{tool.description}\n\nAnnotations: {flags}\n")
        parts.append("\n**Input schema**\n\n```json\n" + json.dumps(tool.input_schema, indent=2) + "\n```\n")
        parts.append("\n**Output schema**\n\n```json\n" + json.dumps(tool.output_schema, indent=2) + "\n```\n")
    return "".join(parts)


def main() -> None:
    DOC_PATH.write_text(asyncio.run(render()), encoding="utf-8", newline="\n")
    print(f"wrote {DOC_PATH}")


if __name__ == "__main__":
    main()
