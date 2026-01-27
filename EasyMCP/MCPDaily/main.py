"""MCPDaily Application Entry Point.

This module initializes the MCPDaily application, registers all tools,
and starts the HTTP server for handling requests.
"""

import sys
from pathlib import Path

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.application import MCPApplication
from transports.http_server import HTTPServer
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from MCPDaily.config import load_config
from MCPDaily.tools.time_tool import TimeTool
from MCPDaily.tools.weather_tool import WeatherTool
from MCPDaily.tools.news_tool import NewsTool


def create_app() -> MCPApplication:
    """Create and configure the MCPDaily application.

    Returns:
        Configured MCPApplication instance.
    """
    # Load configuration
    print("[MCPDaily] Loading configuration...")
    config = load_config()

    # Initialize HTTP server
    print(f"[MCPDaily] Initializing HTTP server on {config.host}:{config.port}")
    server = HTTPServer(host=config.host, port=config.port)

    # Create application
    app = MCPApplication(server=server)

    # Register Time Tool
    print("[MCPDaily] Registering Time Tool...")
    time_tool = TimeTool(
        default_timezone=config.default_timezone,
        description="Get current time and timezone information"
    )
    app.register_tool(time_tool)

    # Register Weather Tool
    print("[MCPDaily] Registering Weather Tool...")
    weather_tool = WeatherTool(
        api_key=config.weather_api_key,
        api_base_url=config.weather_api_base_url,
        cache_duration=config.cache_duration,
        description="Get weather forecast for a location"
    )
    app.register_tool(weather_tool)

    # Register News Tool
    print("[MCPDaily] Registering News Tool...")
    news_tool = NewsTool(
        api_key=config.news_api_key,
        api_base_url=config.news_api_base_url,
        cache_duration=config.cache_duration,
        description="Get news headlines from various sources"
    )
    app.register_tool(news_tool)

    print("[MCPDaily] All tools registered successfully!")

    # Configure static files and web dashboard
    print("[MCPDaily] Configuring web dashboard...")
    static_dir = Path(__file__).parent / "web" / "static"

    # Mount static files
    server.app.mount("/static/", StaticFiles(directory=str(static_dir)), name="static")

    # Add root route to serve dashboard
    @server.app.get("/")
    async def serve_dashboard():
        """Serve the main dashboard HTML page."""
        index_path = static_dir / "index.html"
        response = FileResponse(index_path)
        # Prevent browser caching of the HTML file
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    print(f"[MCPDaily] Web dashboard configured at http://{config.host}:{config.port}")

    return app


def main():
    """Main entry point for the MCPDaily application."""
    print("=" * 60)
    print("MCPDaily - Daily Data Visualization Platform")
    print("=" * 60)

    try:
        # Create and configure application
        app = create_app()

        # Display available tools
        print("\n[MCPDaily] Available Tools:")
        print("  • timetool     - Get current time and timezone information")
        print("  • weathertool  - Get weather forecast for a location")
        print("  • newstool     - Get news headlines from various sources")

        print("\n[MCPDaily] Web Dashboard:")
        config = load_config()
        print(f"  • Dashboard URL: http://{config.host}:{config.port}")
        print(f"  • API Endpoint:  http://{config.host}:{config.port}/invoke")

        print("\n[MCPDaily] Starting server...")
        print("=" * 60)

        # Start the server
        app.run()

    except KeyboardInterrupt:
        print("\n\n[MCPDaily] Server stopped by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[MCPDaily] Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
