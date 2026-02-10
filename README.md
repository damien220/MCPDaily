# EasyMCP

A collection of simple apps built on top of the MCP (Model Context Protocol) pattern. Each app uses the `mcplearn` installer package (included as a `.whl` file) which provides a lightweight MCP server for developing and running these tools.

## Apps

- **MCPDaily** - Everyday data at a glance: time, weather, and news headlines served over HTTP.
- **PNS** - A personal note-taking app for quick capture and retrieval of notes.

## Getting Started

1. Install the framework:
   ```bash
   pip install mcplearn_mcp-0.1.0-py3-none-any.whl
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Pick an app directory (`MCPDaily/` or `PNS/`) and follow its own `README.md` for usage.

## Structure

```
EasyMCP/
├── mcplearn_mcp-0.1.0-py3-none-any.whl   # MCP server framework
├── MCPDaily/                               # Daily info dashboard app
├── PNS/                                    # Personal notes app
└── requirements.txt
```

## Extending

To build a new app, create a directory, install the `mcplearn` package, implement your tools using the `BaseTool` class, and register them with the MCP application. See the existing apps for reference.
