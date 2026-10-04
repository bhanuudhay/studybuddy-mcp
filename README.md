# StudyBuddy MCP

A study assistant built as an **MCP server and client in Python**. I made it to learn the Model Context Protocol and Claude tool use hands-on while working through a course on Claude tool design and MCP (lessons 32–49).

You chat with Claude ("quiz me on lesson 38", "save a note: never retry a 404"), and Claude uses this server to read lessons, save notes, run flashcard quizzes and track progress, all stored in a local SQLite database.

Each feature exists to practise one concept: tools, resources, prompts, input schemas, enums and limits, useful errors, retries, partial success, and MCP clients.

---

## How it fits together

```
                         ┌──────────────────────────────┐
  Claude Code / Inspector│        MCP SERVER            │
  or client/chat.py ────▶│  server/main.py  (FastMCP)   │
        (MCP client)     │   ├─ tools.py      9 tools   │──▶ data/studybuddy.db (SQLite)
          stdio          │   ├─ resources.py  2         │        ▲ seeded from data/seed.json
        JSON-RPC         │   └─ prompts.py    3         │
                         └──────────────────────────────┘──▶ dictionaryapi.dev (define_term)
         │
         └──▶ Claude API (client/chat.py agent loop)
```

## The three MCP primitives

| Primitive | Who controls it | In this project |
|---|---|---|
| **Tools** | The **model** decides when to call them | `get_lesson`, `add_note`, `search_notes`, `start_quiz`, `grade_answer`, `create_flashcard`, `log_progress`, `bulk_import_flashcards`, `define_term` |
| **Resources** | The **application** decides when to attach them (read-only) | `course://syllabus`, `notes://{lesson_id}` (template) |
| **Prompts** | The **user** picks them, like slash commands | `explain_like_im_new(lesson_id)`, `make_quiz(topic, difficulty)`, `weekly_review()` |

## Project structure

```
studybuddy-mcp/
├── server/
│   ├── main.py        # creates the FastMCP server and registers everything
│   ├── db.py          # SQLite layer: tables, seeding, query helpers
│   ├── tools.py       # 9 tools
│   ├── resources.py   # syllabus + per-lesson notes
│   └── prompts.py     # 3 reusable prompt templates
├── client/
│   ├── client.py      # MCP client: connect, discover, call each primitive
│   ├── chat.py        # MCP client + Claude API agent loop
│   └── agents.py      # (planned) per-agent tool scoping
└── data/
    └── seed.json      # 18 lessons + 38 flashcards loaded on first run
```

---

## Setup

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/). The MCP Inspector also needs Node.js.

```bash
git clone https://github.com/bhanuudhay/studybuddy-mcp.git
cd studybuddy-mcp
uv sync
```

The database is created and seeded automatically the first time the server starts. To reset it, delete `data/studybuddy.db`.

## Running it

**1. Test the server in the MCP Inspector** (no API key needed)
```bash
npx @modelcontextprotocol/inspector uv run python -m server.main
```

**2. Run the discovery client** (no API key needed): lists the tools, resources and prompts, and calls one of each.
```bash
uv run python -m client.client
```

**3. Use it inside Claude Code** (runs on your Claude subscription)
```bash
claude mcp add studybuddy -- uv --directory /path/to/studybuddy-mcp run python -m server.main
claude mcp list
```

**4. Chat through the Claude API agent loop** (needs an API key with credit from console.anthropic.com)
```bash
echo 'ANTHROPIC_API_KEY=your-key-here' > .env    # .env is git-ignored
uv run --env-file .env python -m client.chat
```

Try:
- `what is lesson 41 about?`
- `save a note for lesson 38: never retry a 404`
- `quiz me on lesson 36, 2 hard questions`
- `tell me about lesson 99` (shows error recovery)

---

## What I learned

### Tool design (lessons 32–42)

- **Claude picks tools only from their name, description and schema.** It never sees the code. Writing "Use this when… / Do not use this for… (use X instead)" in each docstring is what routes requests correctly.
- **Type hints become the schema.** With FastMCP, `Literal["easy","medium","hard"]` becomes an `enum`, `Annotated[int, Field(ge=1, le=20)]` becomes `minimum`/`maximum`, and parameters with defaults become optional. I never wrote JSON Schema by hand.
- **There are two layers of validation.** The schema rejects bad shapes before my code runs (`num_questions=50`, `difficulty="expert"`). Business rules ("lesson exists", "score ≤ total") still have to be checked in code. That's also why strict mode doesn't replace validation.
- **Errors are instructions for the model.** `ToolError("Lesson 99 not found. Valid IDs are 32-49.")` comes back with `isError: true`, and Claude uses the message to correct itself. A bare `"error"` gives it nothing to work with.
- **Partial success beats all-or-nothing.** `bulk_import_flashcards` takes `list[dict]` instead of a pydantic model on purpose: a model would reject the whole batch at the first bad card. It saves the good cards and returns `{"imported": n, "failed": [{index, reason}]}`.
- **Retry only temporary failures.** `define_term` retries timeouts and 5xx errors with backoff (1s, then 2s) but fails a 404 immediately. A simulated 30% failure rate makes the retries visible.
- **Hide what the model shouldn't see.** `start_quiz` returns questions without answers; `grade_answer` reveals the answer only after the user responds.

### MCP (lessons 43–49)

- **MCP turns M×N integrations into M+N.** The same server ran unchanged in the MCP Inspector, my own Python client and Claude Code.
- **The client lifecycle** is: start the server over stdio → `initialize()` handshake → `list_tools` / `list_resources` / `list_resource_templates` / `list_prompts` → `call_tool` / `read_resource` / `get_prompt`.
- **Connecting MCP to the Claude API is mostly a rename**: MCP's `inputSchema` becomes Claude's `input_schema`. The agent loop sends tools, runs every `tool_use` block through `session.call_tool`, and returns all results in **one** user message with `is_error` set from `isError`.
- **Resources have fixed URIs or URI templates.** `course://syllabus` is fixed; `notes://{lesson_id}` is a template whose `{lesson_id}` becomes the function argument.
- **Prompts don't call the model.** They return message text that the client sends.

### Gotchas I ran into

| Problem | Cause / fix |
|---|---|
| Server output corrupting the connection | In a stdio server, **stdout is the protocol channel**. Never `print()`; log to `sys.stderr`. |
| `AttributeError: module has no attribute 'register'` | `main.py` calls `register()` in every module, so even empty modules need a placeholder `def register(mcp): pass`. |
| A tool silently missing | Two functions named `get_lesson`. FastMCP keeps the first one and logs `Tool already exists`. |
| `text: string` accepted any value | `string` is the Python module, not the type. Use `str`. |
| `ImportError` when running a file directly | Run as a package from the repo root: `python -m server.main`, not `python server/main.py`. |
| `401 API key is invalid` even with a good `.env` | An older `export ANTHROPIC_API_KEY=...` in the shell **wins over** `uv --env-file`. Run `unset ANTHROPIC_API_KEY` first. |
| A subscription token (`claude setup-token`) doesn't work in my own app | Subscription OAuth tokens are for Claude Code. Custom apps need a Console API key with credit, or you can plug the server into Claude Code instead. |
| `FastMCP` not found with the latest SDK | `mcp` v2 renamed things (`FastMCP` → `MCPServer`, `ClientSession` → `Client`). This repo pins `mcp>=1.30,<2` to match the course. |
| Forced `tool_choice` returns 400 | Claude Opus 5.5 rejects `{"type": "any"}` / `{"type": "tool"}`. Use `auto` plus a prompt instruction and `strict: true`, or a model that supports forcing (e.g. Haiku 4.5). |
| Strict mode with `minimum`/`maximum` | Strict tool use doesn't support numeric limits. Strip them from the schema sent to Claude and keep enforcing them on the server. |

---

## Roadmap

Experiments still to run through the Claude API:

- [ ] **Strict tool use** (lesson 36): `strict: true` plus `additionalProperties: false`, comparing invalid-input rates with it on and off
- [ ] **Tool scoping** (lesson 39): a Librarian agent (note tools) and a Quizmaster agent (quiz tools) in `client/agents.py`
- [ ] **Routing experiments** (lessons 32–33, 40): degrade a description, watch Claude pick the wrong tool, fix it
- [ ] **`tool_choice`** (lesson 41): `auto` / `any` / `tool` / `none`
- [ ] **Tool search** (lesson 42): about 30 tools marked `defer_loading: true` plus the BM25 tool search tool
- [ ] Graceful API error handling in `chat.py`

## Tech

Python 3.13 · [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) v1 (FastMCP) · [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) · SQLite · httpx · uv
