"""Entry point for DailyTaskReminder MCP server."""

import argparse

from core.application import MCPApplication
from core.router import ToolRouter
from transports.cli_server import CLIServer

from .interactive_cli import InteractiveCLI
from .notifier import Notifier
from .storage import TaskStorage
from .tools import (
    AddTaskTool,
    CheckRemindersTool,
    CompleteTaskTool,
    DeleteTaskTool,
    ListTasksTool,
)


def _build_tools(storage: TaskStorage) -> list:
    """Create all tool instances sharing a single storage."""
    return [
        AddTaskTool(storage),
        ListTasksTool(storage),
        CompleteTaskTool(storage),
        DeleteTaskTool(storage),
        CheckRemindersTool(storage),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="DailyTaskReminder",
        description="CLI-based task reminder built on the mcplearn MCP framework.",
    )
    parser.add_argument(
        "--mode",
        choices=["interactive", "mcp"],
        default="interactive",
        help="Run mode: 'interactive' (default) for REPL, 'mcp' for raw JSON MCP server.",
    )
    args = parser.parse_args()

    storage = TaskStorage()
    tools = _build_tools(storage)

    if args.mode == "mcp":
        server = CLIServer()
        app = MCPApplication(server=server)
        for tool in tools:
            app.register_tool(tool)
        app.run()
    else:
        # Interactive mode — build a ToolRouter directly and hand it to the REPL
        router = ToolRouter()
        for tool in tools:
            router.register(tool)

        notifier = Notifier()
        cli = InteractiveCLI(router, notifier)
        cli.run()


if __name__ == "__main__":
    main()
