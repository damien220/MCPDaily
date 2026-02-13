# DailyTaskReminder

A CLI-based task reminder application built on the [mcplearn](./mcplearn_mcp-0.1.0-py3-none-any.whl) MCP (Model Context Protocol) framework. Create tasks with due dates and reminder times, and get notified via terminal alerts and desktop notifications when reminders come due.

## Purpose

DailyTaskReminder demonstrates how to build a practical, self-contained application on top of the mcplearn MCP server framework. The app exposes all task management operations as discrete MCP **tools**, making it easy to extend with new capabilities without modifying existing code.

It operates in two modes:
- **Interactive mode** (default) — a user-friendly command-line REPL with a background reminder thread
- **MCP mode** — a raw JSON-in/JSON-out server for programmatic integration with MCP clients

## How It Works

```
              ┌─────────────────────┐
              │      main.py        │
              │   (entry point)     │
              └─────────┬───────────┘
                        │
             ┌──────────┴──────────┐
             │                     │
    --mode interactive      --mode mcp
             │                     │
  ┌──────────▼──────────┐  ┌──────▼────────┐
  │  interactive_cli.py  │  │  CLIServer    │
  │  (REPL + reminders)  │  │  (JSON stdio) │
  └──────────┬──────────┘  └──────┬────────┘
             │                     │
             └──────────┬──────────┘
                        │
                 ┌──────▼──────┐
                 │  ToolRouter  │
                 └──────┬──────┘
                        │
          ┌─────┬───────┼────────┬──────────┐
       AddTask List  Complete  Delete  CheckReminders
          └─────┴───────┼────────┴──────────┘
                        │
                 ┌──────▼──────┐
                 │  TaskStorage │
                 │ (tasks.json) │
                 └─────────────┘
```

Both modes share the same `ToolRouter` and tools. The interactive CLI translates human-friendly commands into `MCPRequest` objects and dispatches them through the same pipeline as the raw MCP server.

A **background thread** runs alongside the interactive REPL, polling every 60 seconds (configurable) for tasks whose reminder time has passed. When a reminder fires, it prints a colored `[REMINDER]` alert in the terminal and attempts a desktop notification via `notify-send`.

## Installation

### Prerequisites

- Python 3.10 or later
- Linux (for desktop notifications via `notify-send` — optional, the app works without it)

### Steps

```bash
# 1. Navigate to the project directory
cd DailyTaskReminder

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install the MCP framework and dependencies
pip install mcplearn_mcp-0.1.0-py3-none-any.whl
```

That's it. There are no additional pip dependencies beyond the framework and the Python standard library.

## Usage

### Starting the app

```bash
# From the parent directory of DailyTaskReminder/
source DailyTaskReminder/.venv/bin/activate

# Interactive mode (default)
python -m DailyTaskReminder

# Raw MCP JSON mode
python -m DailyTaskReminder --mode mcp
```

### Interactive mode commands

```
  add <title> [--desc "..."] [--due "YYYY-MM-DD HH:MM"] [--remind "YYYY-MM-DD HH:MM"]
      Add a new task.

  list [--filter pending|completed|overdue|all]
      List tasks (default: pending).

  complete <task_id>
      Mark a task as completed. Accepts partial IDs (first 4+ characters).

  delete <task_id>
      Delete a task. Accepts partial IDs.

  help
      Show available commands.

  quit / exit
      Exit the application.
```

### Example session

```
$ python -m DailyTaskReminder
DailyTaskReminder v0.1.0 — type 'help' for commands

> add Buy groceries --due "2026-02-14 09:00" --remind "2026-02-14 08:30"
Task created: [4c3afd81] Buy groceries  due: 2026-02-14T09:00:00

> add Finish report --desc "Q4 financial summary" --due "2026-02-15 17:00"
Task created: [685973a7] Finish report  due: 2026-02-15T17:00:00

> list
Pending tasks (2):
  [4c3afd81] Buy groceries  Due: 2026-02-14T09:00:00  Remind: 2026-02-14T08:30:00
  [685973a7] Finish report  Due: 2026-02-15T17:00:00

> complete 4c3a
Completed: [4c3afd81] Buy groceries

> list --filter all
All tasks (2):
  [4c3afd81] Buy groceries  Due: 2026-02-14T09:00:00  [COMPLETED]
  [685973a7] Finish report  Due: 2026-02-15T17:00:00  [PENDING]

> quit
Goodbye!
```

### Raw MCP mode

For programmatic integration, the MCP mode accepts one JSON request per line on stdin and writes JSON responses to stdout:

```bash
$ echo '{"id": "1", "tool": "addtask", "payload": {"title": "Test task"}}' \
  | python -m DailyTaskReminder --mode mcp
```

Available tools: `addtask`, `listtasks`, `completetask`, `deletetask`, `checkreminders`.

### Notifications

When a task's `remind_at` time is reached:
- A colored **[REMINDER]** alert appears in the terminal
- A **desktop notification** pops up via `notify-send` (Linux only; silently skipped if unavailable)

Reminders fire once and are marked as notified so they don't repeat.

## Configuration

All settings are controlled via environment variables:

| Variable | Default | Description |
|---|---|---|
| `DTR_STORAGE_DIR` | `~/.dailytaskreminder` | Directory for the `tasks.json` file |
| `DTR_POLL_INTERVAL` | `60` | Seconds between reminder checks |
| `DTR_TIMEZONE` | `UTC` | Default timezone for display |

## Project Structure

```
DailyTaskReminder/
├── __init__.py                 # Package marker
├── __main__.py                 # python -m entry point
├── main.py                     # App entry point with --mode selection
├── config.py                   # Configuration via environment variables
├── storage.py                  # JSON file CRUD with file locking
├── notifier.py                 # Terminal + desktop notification delivery
├── interactive_cli.py          # REPL, command parser, background reminder thread
├── requirements.txt            # Python dependencies
├── plan.md                     # Implementation plan and architecture
├── README.md                   # This file
├── mcplearn_mcp-0.1.0-py3-none-any.whl  # MCP framework
├── tools/
│   ├── __init__.py             # Exports all tool classes
│   ├── add_task_tool.py        # AddTaskTool — create tasks
│   ├── list_tasks_tool.py      # ListTasksTool — query tasks with filters
│   ├── complete_task_tool.py   # CompleteTaskTool — mark tasks done
│   ├── delete_task_tool.py     # DeleteTaskTool — remove tasks
│   └── check_reminders_tool.py # CheckRemindersTool — find due reminders
└── tests/
    ├── __init__.py
    ├── test_storage.py         # Storage layer tests
    ├── test_tools.py           # MCP tool tests
    └── test_interactive.py     # Interactive CLI and notification tests
```

## Running Tests

```bash
# From the parent directory of DailyTaskReminder/
source DailyTaskReminder/.venv/bin/activate

# Run all test suites
python -m DailyTaskReminder.tests.test_storage
python -m DailyTaskReminder.tests.test_tools
python -m DailyTaskReminder.tests.test_interactive
```

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `mcplearn_mcp-0.1.0` (`.whl`) | Python package | MCP framework — `BaseTool`, `CLIServer`, `MCPApplication`, `ToolRouter` |
| Python 3.10+ standard library | Built-in | `json`, `uuid`, `datetime`, `threading`, `subprocess`, `argparse`, `shlex`, `fcntl` |
| `notify-send` | System (Linux) | Desktop notifications — optional, gracefully skipped if unavailable |

No additional pip packages are required.

## Prototype Status and Future Enhancements

This project is a **prototype** demonstrating MCP-based tool architecture for task management. It is designed as a foundation for further development. The modular tool system means new capabilities can be added without modifying existing code — create a `BaseTool` subclass, implement `handle()`, and register it.

Planned enhancements for future iterations:

- **Recurring tasks** — tasks that repeat on a daily, weekly, or custom schedule
- **Task priorities** — low, medium, high priority levels with sorted display
- **Task editing** — modify title, description, due date, or reminder of existing tasks
- **Web dashboard** — HTTP mode with a browser-based UI using the framework's `HTTPServer`
- **Database storage** — migrate from JSON file to SQLite for better performance and querying
- **Multi-user support** — separate task stores per user with optional authentication
- **Remote notifications** — email, Slack, or webhook integrations for reminders
- **Task categories and tags** — organize tasks with labels and filter by them
- **Extended date formats** — natural language parsing ("tomorrow at 3pm", "next Monday")
- **Task history and analytics** — track completion rates, overdue patterns
- **WebSocket real-time updates** — push notifications via the framework's `WSServer`
- **Export/import** — backup and restore tasks in standard formats (CSV, iCal)
