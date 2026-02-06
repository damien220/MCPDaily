# PNS - Personal Note Taking and Search

A simple note-taking and search application built on the mcplearn_mcp-0.1.0 framework.

## Features

- **NoteTool**: Create, read, update, delete, and list notes
- **SearchTool**: Full-text search across notes with tag filtering
- **File-based storage**: Notes stored as Markdown files with YAML frontmatter

## Installation

### Prerequisites

- Python 3.10+
- mcplearn_mcp-0.1.0 framework installed

### Dependencies

```bash
pip install pyyaml>=6.0 python-slugify>=8.0 python-dotenv
```

## Configuration

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` to customize settings:
   ```bash
   PNS_HOST=127.0.0.1
   PNS_PORT=8081
   NOTES_DIRECTORY=./notes
   ```

## Usage

### Start the Server

```bash
cd /workspaces/Learning-prj/EasyMCP
source .venv/bin/activate
python -m PNS.main
```

Server will start at `http://127.0.0.1:8081`

### API Endpoints

All requests are sent to `POST /invoke` with JSON payload.

#### NoteTool

**Create a note:**
```bash
curl -X POST http://127.0.0.1:8081/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "id": "1",
    "tool": "notetool",
    "payload": {
      "action": "create",
      "title": "My First Note",
      "content": "This is the content of my note.",
      "tags": ["personal", "example"]
    }
  }'
```

**List notes:**
```bash
curl -X POST http://127.0.0.1:8081/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "id": "2",
    "tool": "notetool",
    "payload": {
      "action": "list",
      "limit": 10
    }
  }'
```

**Read a note:**
```bash
curl -X POST http://127.0.0.1:8081/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "id": "3",
    "tool": "notetool",
    "payload": {
      "action": "read",
      "note_id": "2025-01-29-my-first-note"
    }
  }'
```

**Update a note:**
```bash
curl -X POST http://127.0.0.1:8081/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "id": "4",
    "tool": "notetool",
    "payload": {
      "action": "update",
      "note_id": "2025-01-29-my-first-note",
      "content": "Updated content here."
    }
  }'
```

**Delete a note:**
```bash
curl -X POST http://127.0.0.1:8081/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "id": "5",
    "tool": "notetool",
    "payload": {
      "action": "delete",
      "note_id": "2025-01-29-my-first-note"
    }
  }'
```

#### SearchTool

**Search notes:**
```bash
curl -X POST http://127.0.0.1:8081/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "id": "6",
    "tool": "searchtool",
    "payload": {
      "query": "search term",
      "tag": "personal",
      "limit": 20
    }
  }'
```

## Note Storage Format

Notes are stored as Markdown files with YAML frontmatter:

```markdown
---
id: 2025-01-29-my-note
title: My Note
tags:
  - personal
created_at: 2025-01-29T10:30:00Z
updated_at: 2025-01-29T10:30:00Z
---

Note content here...
```

**Filename format:** `{date}-{slug}.md` (e.g., `2025-01-29-my-note.md`)

## Project Structure

```
PNS/
├── __init__.py
├── main.py                 # Application entry point
├── config.py               # Configuration management
├── README.md
├── .env.example
├── tools/
│   ├── __init__.py
│   ├── note_tool.py        # CRUD operations
│   └── search_tool.py      # Full-text search
├── storage/
│   ├── __init__.py
│   └── file_storage.py     # File-based storage
└── notes/                  # Default storage directory
```

## Implementation Status

- [x] Phase 1: Foundation (config, storage, main.py)
- [ ] Phase 2: NoteTool implementation
- [ ] Phase 3: SearchTool implementation

## License

MIT
