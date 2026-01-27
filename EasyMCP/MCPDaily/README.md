# MCPDaily - Daily Data Visualization Platform

A Model-Centric Platform (MCP) application providing daily and routine data visualization for local network users. Built on the mcplearn framework, MCPDaily exposes tools for time, weather, and news information through a simple HTTP API.

## Implementation Status

**Version:** 0.1.0
**Status:** ✅ Core Backend Complete | 🔄 Web Frontend In Progress

## Features

### Available Tools

1. **Time Tool** (`timetool`)
   - Display current time in any timezone
   - UTC and local time conversion
   - Unix timestamp generation
   - No external API required

2. **Weather Tool** (`weathertool`)
   - Current weather conditions
   - Temperature, humidity, wind speed
   - Sunrise/sunset times
   - Powered by OpenWeatherMap API
   - Built-in caching (5-minute default)

3. **News Tool** (`newstool`)
   - Latest news headlines
   - Filter by category and source
   - Multiple news categories supported
   - Powered by NewsAPI
   - Built-in caching (5-minute default)

## Project Structure

```
MCPDaily/
├── __init__.py          # Package initialization
├── main.py              # Application entry point
├── config.py            # Configuration management
├── tools/               # Tool implementations
│   ├── __init__.py
│   ├── time_tool.py    # Time tool (extends BaseTool)
│   ├── weather_tool.py # Weather tool (extends BaseTool)
│   └── news_tool.py    # News tool (extends BaseTool)
└── web/                 # Web interface (future)
    ├── static/
    └── templates/
```

## Installation

### Prerequisites

- Python 3.10 or higher
- Virtual environment (recommended)
- API keys (for Weather and News tools)

### Setup

1. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

   The mcplearn framework is already installed from the .whl file.

2. **Configure environment variables:**

   Copy the example environment file and fill in your API keys:

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and add your API keys:
   - Get OpenWeatherMap API key: https://openweathermap.org/api
   - Get NewsAPI key: https://newsapi.org/

3. **Run the application:**

   ```bash
   python -m MCPDaily.main
   ```

   The server will start on `http://127.0.0.1:8080` by default.

## Usage

### API Endpoint

All tools are accessed via the `/invoke` endpoint using POST requests with JSON payloads.

**Endpoint:** `POST http://127.0.0.1:8080/invoke`

**Request Format:**

```json
{
  "id": "unique-request-id",
  "tool": "tool-name",
  "payload": {
    // tool-specific parameters
  }
}
```

### Example Requests

#### 1. Time Tool

Get current time in a specific timezone:

```bash
curl -X POST http://127.0.0.1:8080/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "id": "1",
    "tool": "timetool",
    "payload": {
      "timezone": "America/New_York"
    }
  }'
```

**Response:**

```json
{
  "id": "1",
  "status": "success",
  "result": {
    "current_time": "2026-01-01 10:30:45",
    "timezone": "America/New_York",
    "timezone_abbr": "EST",
    "utc_time": "2026-01-01 15:30:45",
    "timestamp": 1735742445,
    "iso_format": "2026-01-01T10:30:45-05:00",
    "day_of_week": "Wednesday",
    "date": "2026-01-01",
    "time_12hr": "10:30:45 AM"
  }
}
```

#### 2. Weather Tool

Get current weather for a location:

```bash
curl -X POST http://127.0.0.1:8080/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "id": "2",
    "tool": "weathertool",
    "payload": {
      "location": "London"
    }
  }'
```

**Response:**

```json
{
  "id": "2",
  "status": "success",
  "result": {
    "location": "London, GB",
    "temperature": {
      "current": 15.5,
      "feels_like": 14.2,
      "min": 13.0,
      "max": 17.0,
      "unit": "celsius"
    },
    "conditions": {
      "main": "Clouds",
      "description": "Partly cloudy",
      "icon": "02d"
    },
    "humidity": 65,
    "pressure": 1013,
    "wind": {
      "speed": 10.5,
      "direction": 180
    },
    "cached": false
  }
}
```

#### 3. News Tool

Get latest technology news:

```bash
curl -X POST http://127.0.0.1:8080/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "id": "3",
    "tool": "newstool",
    "payload": {
      "category": "technology",
      "limit": 5
    }
  }'
```

**Response:**

```json
{
  "id": "3",
  "status": "success",
  "result": {
    "category": "technology",
    "source": null,
    "count": 5,
    "headlines": [
      {
        "title": "Example Tech News Headline",
        "description": "Description of the news article...",
        "url": "https://example.com/article",
        "source": "TechNews",
        "published_at": "2026-01-01T10:00:00Z",
        "author": "John Doe",
        "image_url": "https://example.com/image.jpg"
      }
    ],
    "cached": false
  }
}
```

## Tool Details

### Time Tool Parameters

- `timezone` (optional): IANA timezone name (e.g., "America/New_York", "Europe/London")
  - Default: UTC

### Weather Tool Parameters

- `location` (required): City name or location query
  - Examples: "London", "New York", "Paris, FR"

### News Tool Parameters

- `category` (optional): News category
  - Valid values: `general`, `business`, `entertainment`, `health`, `science`, `sports`, `technology`
  - Default: `general`
- `source` (optional): Specific news source ID
- `limit` (optional): Number of headlines to return (1-100)
  - Default: 10

## Configuration

Configuration is managed through environment variables in the `.env` file:

| Variable           | Description                    | Default           |
| ------------------ | ------------------------------ | ----------------- |
| `MCP_DAILY_HOST`   | Server host address            | `127.0.0.1`       |
| `MCP_DAILY_PORT`   | Server port                    | `8080`            |
| `WEATHER_API_KEY`  | OpenWeatherMap API key         | _(required)_      |
| `NEWS_API_KEY`     | NewsAPI key                    | _(required)_      |
| `DEFAULT_TIMEZONE` | Default timezone for time tool | `UTC`             |
| `CACHE_DURATION`   | Cache duration in seconds      | `300` (5 minutes) |

## Architecture

MCPDaily is built on the mcplearn MCP framework, which provides:

- **Base Classes**: All tools extend `BaseTool` from `core.tool_base`
- **Data Models**: Request/response handling via `MCPRequest` and `MCPResponse`
- **Transport Layer**: HTTP server using FastAPI
- **Application Harness**: Tool registration and lifecycle management

### Tool Implementation Pattern

Each tool follows this pattern:

```python
from core.tool_base import BaseTool
from core.models import MCPRequest, MCPResponse

class CustomTool(BaseTool):
    """Tool description."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize tool-specific attributes

    def validate(self, request: MCPRequest) -> None:
        """Validate incoming request."""
        # Validation logic

    def handle(self, request: MCPRequest) -> MCPResponse:
        """Handle the request and return response."""
        # Tool logic
        return MCPResponse.success(request, result_data)
```

## Future Enhancements

- [ ] Web interface for data visualization
- [ ] Additional tools (calendar, tasks, etc.)
- [ ] WebSocket support for real-time updates
- [ ] User authentication
- [ ] Persistent caching (Redis, SQLite)
- [ ] Custom news sources via RSS
- [ ] Multi-day weather forecast

## Troubleshooting

### API Key Issues

If you see warnings about missing API keys:

- Ensure your `.env` file exists and contains valid API keys
- Check that environment variables are loaded properly
- Verify API keys are active at the provider's website

### Import Errors

If you encounter import errors:

- Ensure you're running from the project root directory
- Verify the mcplearn framework is installed: `pip list | grep mcplearn`
- Check Python version is 3.10 or higher

### Network Issues

If the server won't start:

- Verify port 8080 is not already in use
- Try changing the port in `.env`
- Check firewall settings if accessing from local network

## Next Steps - Phase 4: Web Dashboard Development

The core backend is complete and all tools are operational. The next phase focuses on creating a user-friendly web interface.

### Immediate Actions

1. **Configure API Keys** (Recommended)

   ```bash
   # Copy the example environment file
   cp .env.example .env

   # Edit .env and add your API keys:
   # - Get WEATHER_API_KEY from: https://openweathermap.org/api
   # - Get NEWS_API_KEY from: https://newsapi.org/
   ```

2. **Test with Real Data**
   - Start the server with configured API keys
   - Test Weather Tool with actual weather data
   - Test News Tool with real headlines

### Web Dashboard Development

**Goal:** Create a responsive web dashboard that displays all tool data in real-time.

**Planned Features:**

- Live time display with timezone selection
- Current weather conditions with location search
- Latest news headlines with category filters
- Auto-refresh functionality (configurable interval)
- Manual refresh buttons
- Error handling and status indicators
- Mobile-responsive design

**Implementation Approach:**

**Option A: Static HTML + JavaScript (Recommended)**

```
MCPDaily/web/static/
├── index.html          # Main dashboard page
├── css/
│   └── dashboard.css   # Styling
└── js/
    └── dashboard.js    # API calls and UI updates
```

Advantages:

- Simple to implement
- No backend changes needed
- Easy to customize and extend
- Lightweight and fast

**Option B: FastAPI Templates**

- Use Jinja2 templates for server-side rendering
- Add new routes to serve HTML pages
- Integrated with existing FastAPI server

### Dashboard Layout

```
┌─────────────────────────────────────────────────┐
│          MCPDaily Dashboard                      │
├──────────────────────┬──────────────────────────┤
│                      │                          │
│   Time & Date        │    Weather               │
│                      │                          │
│   🕐 10:30:45 AM     │   ☁️ 15°C               │
│   📅 Thursday        │   Partly Cloudy          │
│   🌍 New York (EST)  │   💨 Wind: 10 km/h      │
│                      │   💧 Humidity: 65%       │
│                      │                          │
├──────────────────────┴──────────────────────────┤
│                                                  │
│   📰 Latest News                                │
│                                                  │
│   • Tech: New AI breakthrough announced...       │
│   • Science: Climate study reveals...           │
│   • Business: Markets show growth...            │
│                                                  │
└──────────────────────────────────────────────────┘
```

### Local Network Access

For accessing the dashboard from other devices on your network:

1. **Update Configuration**

   ```bash
   # In .env file, change:
   MCP_DAILY_HOST=0.0.0.0  # Listen on all interfaces
   ```

2. **Configure Firewall** (if needed)

   ```bash
   # Allow incoming connections on port 8080
   sudo ufw allow 8080
   ```

3. **Access Dashboard**
   - Find your server's local IP: `hostname -I`
   - Access from other devices: `http://<server-ip>:8080`

### Future Enhancements

**Phase 5: Advanced Features**

- User authentication and preferences
- Multiple timezone displays
- Extended weather forecasts (multi-day)
- Customizable news sources
- Dark mode toggle
- Data history and charts

**Phase 6: Additional Tools**

- Calendar integration
- Task/reminder management
- System monitoring
- Custom RSS feeds
- Local event notifications

## Contributing

Contributions are welcome! Areas for contribution:

- Web dashboard implementation
- Additional tools
- UI/UX improvements
- Documentation
- Testing

## License

This project is part of the EasyMCP learning platform.

## Support

For issues or questions, refer to the main EasyMCP documentation.
