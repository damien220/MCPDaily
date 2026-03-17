"""LocalFileHandler — MCP server entry point.

Usage:
    python -m LocalFileHandler                       # default: CLI mode
    python -m LocalFileHandler --mode cli            # explicit CLI mode
    python -m LocalFileHandler --mode http           # HTTP API only (port 8080)
    python -m LocalFileHandler --mode web            # HTTP + web dashboard
    python -m LocalFileHandler --mode web --port 9000
"""

import argparse
import sys
from pathlib import Path

from core.application import MCPApplication
from transports.cli_server import CLIServer

from .config import Config, load_config
from .history import OperationLog
from .naming import CategoryMap, NameFormatter
from .tools import (
    ConfigTool,
    CreateDirTool,
    CreateFileTool,
    DeleteTool,
    DuplicatesTool,
    HistoryTool,
    InfoTool,
    ListContentsTool,
    MoveTool,
    NLCommandTool,
    OrganizeTool,
    PreviewTool,
    RenameTool,
    SearchTool,
    SmartCategorizeTool,
    SuggestionsTool,
    UndoTool,
    VoiceTool,
    WatchdogTool,
)


def build_app(config: Config, mode: str = "cli") -> MCPApplication:
    """Build the MCP application with all tools registered."""
    workspace = Path(config.workspace_path).resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    # Operation history log
    log_path = workspace / ".history" / "operations.jsonl"
    operation_log = OperationLog(log_path=log_path)

    # Naming engine
    category_map = CategoryMap()
    formatter = NameFormatter(
        workspace=workspace,
        category_map=category_map,
        date_format=config.naming.date_format,
        date_prefix=config.naming.date_prefix,
        auto_categorize=config.naming.auto_categorize,
        normalize_extensions=config.naming.normalize_extensions,
    )

    # Select transport
    if mode == "http":
        from transports.http_server import HTTPServer
        server = HTTPServer(host=config.server_host, port=config.server_port)
    elif mode == "web":
        from .web.server import WebServer
        server = WebServer(
            host=config.server_host,
            port=config.server_port,
            workspace=workspace,
            auth_username=config.auth_username,
            auth_password=config.auth_password,
        )
    else:
        server = CLIServer()

    app = MCPApplication(server=server)

    # Phase 1 tools
    app.register_tool(CreateFileTool(workspace=workspace, formatter=formatter, operation_log=operation_log))
    app.register_tool(CreateDirTool(workspace=workspace, formatter=formatter, operation_log=operation_log))
    app.register_tool(ListContentsTool(workspace=workspace))
    app.register_tool(RenameTool(workspace=workspace, formatter=formatter, operation_log=operation_log))
    app.register_tool(MoveTool(workspace=workspace, formatter=formatter, operation_log=operation_log))
    app.register_tool(DeleteTool(
        workspace=workspace,
        trash_enabled=config.trash_enabled,
        trash_dir=config.trash_dir,
        operation_log=operation_log,
    ))

    # Phase 2 tools
    app.register_tool(SearchTool(workspace=workspace))
    app.register_tool(OrganizeTool(workspace=workspace, formatter=formatter, operation_log=operation_log))
    app.register_tool(InfoTool(workspace=workspace))
    app.register_tool(HistoryTool(operation_log=operation_log))
    app.register_tool(UndoTool(workspace=workspace, operation_log=operation_log))
    app.register_tool(ConfigTool(config=config, formatter=formatter, category_map=category_map))

    # Phase 3 tools (web UI support)
    app.register_tool(PreviewTool(workspace=workspace, formatter=formatter))

    # Phase 4 tools (AI-enhanced features)
    from .ai import create_client
    ai_client = create_client(config.ai)
    app.register_tool(SmartCategorizeTool(workspace=workspace, client=ai_client))
    app.register_tool(NLCommandTool(client=ai_client))
    app.register_tool(DuplicatesTool(workspace=workspace))
    app.register_tool(SuggestionsTool(workspace=workspace, client=ai_client))

    # Phase 5 tools (voice control)
    from .stt import create_stt_client
    stt_client = create_stt_client(config.speech)
    app.register_tool(VoiceTool(stt_client=stt_client, wake_word=config.speech.wake_word))

    # Phase 6 tools (IoT / deployment)
    app.register_tool(WatchdogTool(workspace=workspace, formatter=formatter, operation_log=operation_log))

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="LocalFileHandler MCP Server")
    parser.add_argument(
        "--mode",
        choices=["cli", "http", "web"],
        default="cli",
        help="Server transport mode (default: cli)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port for HTTP/web mode (overrides config)",
    )
    args = parser.parse_args()

    config = load_config()
    if args.port is not None:
        config.server_port = args.port

    print(f"LocalFileHandler starting in {args.mode.upper()} mode...", file=sys.stderr)
    print(f"Workspace: {Path(config.workspace_path).resolve()}", file=sys.stderr)
    if args.mode in ("http", "web"):
        print(f"API:  http://{config.server_host}:{config.server_port}/invoke", file=sys.stderr)
    if args.mode == "web":
        print(f"Dashboard: http://{config.server_host}:{config.server_port}/", file=sys.stderr)
        print(f"WebSocket: ws://{config.server_host}:{config.server_port}/ws", file=sys.stderr)
    ai_backend = config.ai.backend
    print(f"AI backend: {ai_backend or 'none'} "
          f"({'model: ' + config.ai.model if ai_backend != 'none' else 'set ANTHROPIC_API_KEY, AI_BACKEND=ollama, or AI_BACKEND=llamacpp to enable'})",
          file=sys.stderr)
    if args.mode == "web" and config.auth_username:
        print(f"Auth: Basic Auth enabled (user: {config.auth_username})", file=sys.stderr)
    elif args.mode == "web":
        print("Auth: disabled (set AUTH_USERNAME + AUTH_PASSWORD to enable)", file=sys.stderr)
    stt_backend = config.speech.backend
    print(f"STT backend: {stt_backend or 'none'} "
          f"({'model: ' + config.speech.model if stt_backend != 'none' else 'set STT_BACKEND=faster_whisper (or whisper/vosk/whisper_cpp) to enable voice'})",
          file=sys.stderr)

    app = build_app(config, mode=args.mode)
    app.run()


if __name__ == "__main__":
    main()
