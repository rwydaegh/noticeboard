"""Exercise the actual stdio protocol against a running local application."""

import asyncio
import json
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    root = Path(__file__).resolve().parents[1]
    parameters = StdioServerParameters(
        command=str(root / ".venv/bin/python"), args=["-m", "procurement.mcp_server"], cwd=str(root)
    )
    async with stdio_client(parameters) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = (await session.list_tools()).tools
        assert len(tools) == 4 and all(tool.annotations.readOnlyHint for tool in tools)
        result = await session.call_tool("search_notices", {"query": "software", "limit": 2})
        assert not result.isError
        items = json.loads(result.content[0].text)["items"]
        assert items
        detail = await session.call_tool("read_notice", {"opportunity_id": items[0]["id"]})
        assert not detail.isError
        assert json.loads(detail.content[0].text)["source_url"].startswith("https://ted.europa.eu/")
        print("MCP: tool discovery, read-only annotations, search and source detail passed.")


if __name__ == "__main__":
    asyncio.run(main())
