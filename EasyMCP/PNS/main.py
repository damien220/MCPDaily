"""
PNS - Personal Note Taking and Search

Main entry point for the PNS application.
"""

from core.application import MCPApplication
from transports.http_server import HTTPServer

from config import load_config
from tools import NoteTool, SearchTool


def main():
    """Main entry point for PNS application."""
    # Load configuration from .env file
    config = load_config()

    print(f"[PNS] Starting server...")
    print(f"[PNS] Host: {config.host}")
    print(f"[PNS] Port: {config.port}")
    print(f"[PNS] Notes directory: {config.notes_directory}")

    # Initialize HTTP server
    server = HTTPServer(host=config.host, port=config.port)

    # Create application
    app = MCPApplication(server=server)

    # Register tools
    app.register_tool(NoteTool(storage_path=config.notes_directory))
    app.register_tool(SearchTool(storage_path=config.notes_directory))

    print(f"[PNS] Server running at http://{config.host}:{config.port}")
    print("[PNS] Press Ctrl+C to stop")

    # Start the application
    app.run()


if __name__ == "__main__":
    main()
