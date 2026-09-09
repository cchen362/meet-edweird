<p align="center">
  <img src="frontend/public/favicon.svg" width="100" height="100" alt="Edward" />
</p>

<h1 align="center">Edward</h1>

<p align="center">
  <strong>A personal companion who remembers you.</strong>
</p>

<p align="center">
  Long-term memory &nbsp;·&nbsp; Light ops &nbsp;·&nbsp; WhatsApp &nbsp;·&nbsp; Phone PWA
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="Apache 2.0 License" /></a>
  <img src="https://img.shields.io/badge/platform-Windows%2011-blue.svg" alt="Windows 11" />
  <img src="https://img.shields.io/badge/python-3.11%2B-blue.svg" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/Next.js-14-black.svg" alt="Next.js" />
</p>

<p align="center">
  <a href="docs/ENGINEERING.md">Engineering guide</a> &nbsp;·&nbsp;
  <a href="#quick-start">Quick Start</a> &nbsp;·&nbsp;
  <a href="https://youtu.be/uewYlQma1QY">Historical Walkthrough</a>
</p>

---

## Demo

The upstream walkthrough below predates the September 2026 cleanup and includes features that have since been removed.

<p align="center">
  <a href="https://youtu.be/uewYlQma1QY">
    <img src="https://img.youtube.com/vi/uewYlQma1QY/maxresdefault.jpg" width="700" alt="Watch the Edward walkthrough" />
  </a>
</p>

## Screenshots

These are historical screenshots, not verification of the current interface. The current feature list is below.

<p align="center">
  <img src="docs/screenshots/chat-welcome-desktop.png" width="700" alt="Edward chat interface" />
</p>

<p align="center">
  <img src="docs/screenshots/settings-desktop.png" width="700" alt="Edward settings dashboard" />
</p>

<details>
<summary><strong>Mobile</strong></summary>

<p align="center">
  <img src="docs/screenshots/chat-welcome-mobile.png" width="300" alt="Edward chat - mobile" />
  &nbsp;&nbsp;
  <img src="docs/screenshots/settings-mobile.png" width="300" alt="Edward settings - mobile" />
</p>

</details>

## What is Edward?

Edward is a single-user personal companion with long-term memory, reached from a phone PWA, a desktop browser and WhatsApp. He recalls past conversations, keeps notes, schedules reminders, looks things up and answers GitHub questions through MCP.

Chat uses **GPT via Codex OAuth** and the owner's ChatGPT subscription. **Claude Haiku 4.5** handles background intelligence such as memory extraction, reflection and WhatsApp triage. The app runs on Windows with Next.js, FastAPI and PostgreSQL with pgvector. Cleanup and verification progress are recorded in [Plan 001](docs/plans/001_REVIVAL_CLEANUP.md).

## Features

| Feature | What it does |
|:--|:--|
| Long-term memory | Extracts useful memories and recalls them through vector and keyword search |
| Documents | Saves notes and retrieves relevant documents |
| Scheduled events | One-time reminders and cron-based recurring check-ins |
| WhatsApp | Reads and sends through the Baileys bridge; inbound mentions default to @edward |
| Web search | Brave Search and page extraction |
| GitHub and custom MCP | Connects running MCP servers and exposes their tools in chat |
| Phone PWA | Browser-based access with a chat activity feed |

Web Push support remains in the app, but delivery is currently broken and awaits the separate Plan 002 fix. Chat turns are still tied to the open connection; returning to a completed answer after disconnect is future Plan 006 work.

## Quick Start

```powershell
git clone https://github.com/cchen362/meet-edweird.git
cd meet-edweird
.\setup.ps1                    # Installs Python & Node deps, starts PostgreSQL in Docker
.\restart.ps1                  # Starts backend (:8000) + frontend (:3001)
```

Add your Anthropic API key to `.env` before starting the backend — that's the only required environment variable. Open [localhost:3001](http://localhost:3001), set a password on first visit, and sign in to Codex OAuth from Settings for chat. The Anthropic key pays only for Haiku background calls; chat requires the OAuth connection.

> **Prerequisites:** Windows 11, PowerShell, Docker (PostgreSQL with pgvector runs in the `edward-pg` container), Node.js 18+, Python 3.11+, [Anthropic API key](https://console.anthropic.com/)

## Architecture

```
Phone PWA / Desktop browser ──HTTP + SSE──> FastAPI (:8000) ──> PostgreSQL + pgvector
       Next.js (:3001)                         │                  Docker (:5432)
WhatsApp (Node / Baileys) ─────webhook───────────┤
                                              ├─ GPT via Codex OAuth: chat + tools
                                              ├─ Claude Haiku 4.5: background intelligence
                                              └─ Local sentence-transformers: embeddings
```

Each chat turn loads conversation state, retrieves memories and document references, calls GPT and runs any requested tools. The browser receives activity and content over SSE; the backend saves messages before the completion event and starts post-turn memory work. Provider text is collected before it is emitted to the browser.

The runtime is in `backend/services/graph/streaming.py`, with prompt assembly, events, message conversion, provider calls and tool execution in neighbouring modules. Tools live in `backend/services/graph/tools/`, `backend/services/whatsapp_bridge_tools.py` and `backend/services/custom_mcp_tools.py`. See the [engineering guide](docs/ENGINEERING.md#current-architecture) for startup order, tool gates and data ownership.

<details>
<summary><strong>Background Systems</strong></summary>

| System | Description |
|--------|-------------|
| Heartbeat | Monitors WhatsApp; triages by urgency |
| Memory Reflection | Post-turn enrichment via related memory queries |
| Deep Retrieval | Pre-turn multi-query search for complex conversations |
| Search Tags | Auto-generated keywords for conversation search |

</details>

<details>
<summary><strong>Configuration</strong></summary>

Copy [`.env.example`](.env.example) to `.env` and configure:

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude Haiku key for background jobs |
| `BRAVE_SEARCH_API_KEY` | No | Enables web search |
| `MCP_WHATSAPP_ENABLED` | No | WhatsApp via the Baileys bridge |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` | No | Web Push configuration; delivery fix pending |
| `JWT_SECRET_KEY` | No | Auth secret (auto-generates if unset) |
| `GITHUB_TOKEN` | No | MCP server search via GitHub API |
| `GITHUB_MCP_TOKEN` / `GITHUB_PERSONAL_ACCESS_TOKEN` | No | Matching PAT values for the configured GitHub MCP binary |

See [`.env.example`](.env.example) for the full list.

</details>

<details>
<summary><strong>Skills</strong></summary>

Each skill is toggled from the settings page. Tools are dynamically bound to the LLM based on what's enabled.

| Skill | Description |
|-------|-------------|
| Brave Search | Web search + page extraction |
| WhatsApp MCP | WhatsApp via the Baileys bridge |
| Push Notifications | VAPID-backed Web Push; delivery fix pending |

Memory, documents, scheduled events, heartbeat review and custom-server management tools are always bound. Push additionally needs VAPID configuration, WhatsApp needs an available bridge, and custom MCP tools come from running servers. Settings contains General, Skills, Edward's Servers, Heartbeat, Memories, Documents and Events.

</details>

## Scripts

```powershell
.\setup.ps1                    # First-time setup (Docker Postgres, dependencies, .env)
.\restart.ps1                  # Restart both frontend and backend
.\restart.ps1 frontend         # Restart only frontend
.\restart.ps1 backend          # Restart only backend
```

## Contributing

Open an issue first to discuss what you'd like to change. Read the [engineering guide](docs/ENGINEERING.md) and [settled decisions](docs/DECISIONS.md) before implementing changes, then fork, branch and open a PR.

## License

[Apache 2.0](LICENSE)
