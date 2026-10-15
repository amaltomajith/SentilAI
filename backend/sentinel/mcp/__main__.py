import sys

from sentinel.mcp.server import build_server

if __name__ == "__main__":
    server = build_server()
    server.run(transport="streamable-http" if "--http" in sys.argv else "stdio")