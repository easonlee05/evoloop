"""Evoloop 3.0 MCP Server Entrypoint."""
import sys
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("mcp package is not installed. Please install mcp to run this server.", file=sys.stderr)
    sys.exit(1)

from app.mcp.tools import register_tools

# Instantiate the FastMCP server
mcp = FastMCP("Evoloop_3.0_PM_Control_Plane")

# Register all capabilities
register_tools(mcp)

def main():
    """Start the stdio MCP server."""
    mcp.run()

if __name__ == "__main__":
    main()
