"""Pandapower MCP server entry point."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import analysis, build, io, power_flow, topology

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Initializing Pandapower Analysis Server")
mcp = FastMCP("Pandapower Analysis Server")

io.register_tools(mcp)
power_flow.register_tools(mcp)
analysis.register_tools(mcp)
topology.register_tools(mcp)
build.register_tools(mcp)

if __name__ == "__main__":
    mcp.run(transport="stdio")
