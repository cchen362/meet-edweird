<p align="center">
  <img src="frontend/public/favicon.svg" width="100" height="100" alt="Edward" />
</p>

<h1 align="center">Edward</h1>

<p align="center">
  <strong>Your AI assistant that remembers everything.</strong>
</p>

<p align="center">
  Long-term memory &nbsp;·&nbsp; Multi-agent orchestration &nbsp;·&nbsp; Self-evolution &nbsp;·&nbsp; Code execution
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="Apache 2.0 License" /></a>
  <img src="https://img.shields.io/badge/platform-Windows%2011-blue.svg" alt="Windows 11" />
  <img src="https://img.shields.io/badge/python-3.11%2B-blue.svg" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/Next.js-15-black.svg" alt="Next.js" />
</p>

<p align="center">
  <a href="https://meet-edward.com">Website</a> &nbsp;·&nbsp;
  <a href="https://meet-edward.com/docs">Docs</a> &nbsp;·&nbsp;
  <a href="#quick-start">Quick Start</a> &nbsp;·&nbsp;
  <a href="https://youtu.be/uewYlQma1QY">Video Walkthrough</a>
</p>

---

## Demo

<p align="center">
  <a href="https://youtu.be/uewYlQma1QY">
    <img src="https://img.youtube.com/vi/uewYlQma1QY/maxresdefault.jpg" width="700" alt="Watch the Edward walkthrough" />
  </a>
</p>

## Screenshots

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

Edward is a full-stack AI assistant built on **Next.js**, **FastAPI**, and **PostgreSQL with pgvector**. He extracts memories from every conversation, schedules his own reminders, sends messages over WhatsApp, and runs code — reached from a phone PWA, a desktop browser, and WhatsApp.

Unlike chat wrappers, Edward has persistent memory, background autonomy, a multi-agent orchestrator that spawns worker agents for parallel tasks, and a self-evolution engine that lets him propose, test, and deploy improvements to his own codebase.

## Features

| | | | |
|:--|:--|:--|:--|
| 🧠 **Long-Term Memory** | Hybrid vector + keyword recall | 📅 **Scheduled Events** | One-time & cron recurring |
| 💬 **WhatsApp** | Send/receive via a Baileys bridge | 🐍 **Code Execution** | Python, JS, SQL, Shell sandboxes |
| 🔍 **Web Search** | Brave Search + page extraction | 📄 **Document Store** | Semantic search over saved docs |
| 🔌 **Custom MCP Servers** | Self-serve install at runtime | 🤖 **Multi-Agent Orchestrator** | Spawns parallel worker agents |
| 🧬 **Self-Evolution** | Proposes, tests, and deploys its own upgrades | 🔔 **Push Notifications** | Web Push via VAPID |

## Quick Start

```powershell
git clone https://github.com/ben4mn/meet-edward.git; cd meet-edward
.\setup.ps1                    # Installs Python & Node deps, starts PostgreSQL in Docker
.\restart.ps1                  # Starts backend (:8000) + frontend (:3001)
```

Add your Anthropic API key to `.env` — that's the only required variable. Open [localhost:3001](http://localhost:3001) and set a password on first visit.

> **Prerequisites:** Windows 11, PowerShell, Docker (PostgreSQL with pgvector runs in the `edward-pg` container), Node.js 18+, Python 3.11+, [Anthropic API key](https://console.anthropic.com/)

## Architecture

```
Frontend (Next.js :3001)  →  Backend (FastAPI :8000)  →  PostgreSQL (:5432, Docker)
                                      ↓
                              Chat turn loop
                           (retrieve memory →
                            LLM call → tools →
                            stream → extract memory)
                                      ↓
                     Codex OAuth (chat) · Claude Haiku (background)
```

<details>
<summary><strong>Background Systems</strong></summary>

| System | Description |
|--------|-------------|
| Heartbeat | Monitors WhatsApp; triages by urgency |
| Memory Reflection | Post-turn enrichment via related memory queries |
| Deep Retrieval | Pre-turn multi-query search for complex conversations |
| Memory Consolidation | Hourly clustering of related memories |
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
| `VAPID_PUBLIC_KEY` / `PRIVATE_KEY` | No | Browser push notifications |
| `JWT_SECRET_KEY` | No | Auth secret (auto-generates if unset) |
| `GITHUB_TOKEN` | No | MCP server search via GitHub API |

See [`.env.example`](.env.example) for the full list.

</details>

<details>
<summary><strong>Skills</strong></summary>

Each skill is toggled from the settings page. Tools are dynamically bound to the LLM based on what's enabled.

| Skill | Description |
|-------|-------------|
| Code Interpreter | Sandboxed Python with numpy/pandas/matplotlib |
| JavaScript Interpreter | Node.js sandbox |
| SQL Database | Per-conversation SQLite + persistent PostgreSQL schemas |
| Shell/Bash | Sandboxed shell commands |
| Brave Search | Web search + page extraction |
| WhatsApp MCP | WhatsApp via the Baileys bridge |
| Scheduled Events | Reminders, messages, and recurring tasks |

Memory, documents, scheduled events, push notifications, and contacts are always available.

</details>

## Scripts

```powershell
.\setup.ps1                    # First-time setup (Docker Postgres, dependencies, .env)
.\restart.ps1                  # Restart both frontend and backend
.\restart.ps1 frontend         # Restart only frontend
.\restart.ps1 backend          # Restart only backend
```

## Contributing

Contributions welcome — open an issue first to discuss what you'd like to change. Fork, branch, and open a PR. See the [docs site](https://meet-edward.com/docs) for architecture details.

## License

[Apache 2.0](LICENSE)
