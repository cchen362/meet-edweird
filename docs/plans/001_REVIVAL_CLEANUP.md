# Plan 001: Revival — Rebuild Edward In Place

**Status: Approved 2026-09-09. M1, M2, M4, M3, M5 complete (M4 was pulled ahead of M3 on 2026-09-09 because the Codex endpoint stopped serving `gpt-5.4` and chat was silently falling back to the metered API key). M6 next.**

Supersedes the `IMPLEMENTATION_PLANS/` sequence (000–014) and `docs/superpowers/`. Those trees are frozen as archive; nothing in them is authoritative once this plan is approved.

---

## Why

Edward was built as an ambitious autonomous-agent platform (20+ subsystems) but was actually used as a **companion who remembers you, plus an occasional ops helper**. Usage collapsed once the build sprint ended. The unused subsystems now dominate the codebase, the docs, the startup sequence, and the model's own system prompt, and they make every change expensive.

Direction agreed in the 2026-09-09 interview:

1. **Product:** personal companion with memory (primary) + personal ops assistant (secondary).
2. **Approach:** rebuild in place. Keep the proven core, aggressively delete the rest.
3. **Platform:** Windows only. All macOS / Apple code goes.
4. **Models:** chat "brain" on GPT via Codex OAuth (subscription credits). Background jobs stay on Claude Haiku 4.5 (already built, cheapest per call). Anthropic key is retained only for Haiku.
5. **Reach:** phone PWA + Web Push, and Edward may initiate. Push is currently broken and gets its own plan.
6. **WhatsApp** is the channel the owner uses most and becomes a first-class surface. Enhancement (chat/group triage) is its own plan; this plan only keeps the bridge alive.
7. **UI redesign** is welcome and gets its own plan after cleanup. Design commitment is settled now so no agent picks something generic in the meantime.

## Verified facts (do not re-derive)

Measured from the live PostgreSQL database and the repo on 2026-09-09:

| Fact | Value |
|---|---|
| User conversations | 145; monthly count fell from 196 (Mar) to 5 (Jul) |
| Typical user conversation | "Sanity check", "How's your day", lounge / dinner decisions |
| Scheduled-event conversations | 92, nearly all Edward's recurring self-audits |
| Documents | 65, nearly all "weekly self-review" / "memory audit" / "evolution check" |
| Orchestrator tasks | 26, of which 21 failed |
| Evolution cycles | 2 |
| Heartbeat events | 51, all WhatsApp, none since 2026-03-14 |
| External (Twilio) contacts | 0 |
| Push subscriptions | 11; 10 deactivated after 3 failures each (iPhone **and** desktop Chrome), 1 active from 2026-03-03 |
| Memories | 228 (82 context, 59 preference, 51 instruction, 36 fact) |
| Custom MCP servers | 1 (GitHub), used |
| Backend size | ~27.5k lines Python; `graph/tools.py` 4,025 lines, `graph/streaming.py` 2,245 lines |
| Frontend size | ~11.5k lines TS; settings panels alone 5,332 lines |
| Background LLM client | `services/llm_client.py` is hard-wired to Anthropic Haiku; 12 call sites |
| VAPID keys | Public key in `.env` derives correctly from the private key (verified) |
| Push failure cause | Unknown. Errors were printed to stdout only; `backend/logs/` is empty. Requires a live test. |
| Pending recurring self-audit events | 5 (cron: Fri 09:00, Sat 14:00, Sun 19:00, Mon 09:00, 1st 19:30) |
| Fonts | Inter via `next/font/google` (violates design floor) |
| Current palette | Slate scale (#0f172a … #f1f5f9) + green accent #52b788 + stray indigo #6366f1 |

## Target architecture

```
Phone PWA / Desktop browser ──HTTP+SSE──> FastAPI backend ──> PostgreSQL + pgvector
WhatsApp (Baileys bridge, Node) ──webhook─┘      │
                                                 ├─ Chat: GPT via Codex OAuth (Responses API)
                                                 ├─ Background: Claude Haiku 4.5 (extraction, tags, reflection, triage)
                                                 ├─ Embeddings: sentence-transformers, local
                                                 └─ Tools: memory · documents · scheduled events · push ·
                                                           web search · WhatsApp · GitHub MCP · custom MCP
```

Startup order after cleanup: `init_db` → checkpoint store → skills → custom MCP servers (GitHub) → WhatsApp bridge → tool registry → scheduler → WhatsApp heartbeat → done. Ten hooks become six.

## Keep list

| Subsystem | Why |
|---|---|
| Chat runtime (`graph/streaming.py`, checkpoint store, conversations) | The product |
| Memory service (extraction, hybrid retrieval, reflection, deep retrieval) | The one feature that demonstrably worked. Redesign is Plan 005, not this plan. |
| Documents | "Notes Edward keeps for you". Self-audit noise gets deleted from data, not from code. |
| Scheduled events + scheduler | Reminders and check-ins. Core to "Edward may initiate". |
| Push notifications (PWA, service worker, VAPID) | The reach channel. Fix is Plan 002. |
| Auth (JWT cookie, single password) | Required for the tunnel. |
| Web search (Brave) | Explicitly wanted. |
| WhatsApp bridge + tools + heartbeat listener + triage | Explicitly wanted, to be enhanced in Plan 003. |
| Custom MCP service + GitHub server | Explicitly wanted for spontaneous repo questions. |
| Auto-restart, ngrok tunnel, watchdog scripts | Keeps the phone path alive. |
| Codex OAuth service | Becomes the only chat provider. |
| `llm_client.py` (Haiku) | Background jobs. |

## Cut list

Every row is deleted outright: service, router, tools, DB models, frontend panel, API client functions, settings UI, startup/shutdown hooks, system-prompt references, `.env.example` entries, and `requirements.txt` / `package.json` dependencies that become unused. Line counts are backend only.

| Group | Lines | Files (backend) | Frontend |
|---|---|---|---|
| Apple / macOS: iMessage, Contacts, Apple MCP, iMessage + Calendar + Email heartbeat listeners | 1,761 | `imessage_service.py`, `contacts_service.py`, `mcp_client.py`, `heartbeat/listener_{imessage,calendar,email}.py` | HeartbeatPanel loses 3 tracks |
| Twilio SMS / WhatsApp-via-Twilio | 267 + webhook routes | `twilio_service.py`, Twilio routes in `routers/webhooks.py`, `external_contacts` usage | — |
| Orchestrator, Evolution, Claude Code sessions, CC manager | 2,198 | `orchestrator_*.py`, `evolution_*.py`, `claude_code_service.py`, `cc_manager_service.py`, `routers/{orchestrator,evolution}.py` | OrchestratorPanel, EvolutionPanel, CCSessionBlock, PlanBlock (if plan tools go) |
| CASCE governance (Plan 014 Phase 0) | 29 + prompt text | `services/governance/` | — |
| Code execution sandbox (Python, JS, SQL, shell) | 1,005 | `services/execution/`, `code_execution_service.py` | CodeBlock execution events in chat UI |
| NotebookLM (28 tools) | 719 | `notebooklm_service.py` | SkillsPanel entry |
| iOS Scriptable widget | 349 | `widget_service.py`, `routers/widget.py` | — |
| Persistent PostgreSQL DBs, HTML hosting, file storage | 1,301 | `persistent_db_service.py`, `html_hosting_service.py`, `file_storage_service.py`, `routers/{databases,files}.py` | DatabaseBrowser, FileBrowser |
| LangSmith inspector + legacy LangGraph fallback | 570 | `langsmith_service.py`, `graph/{nodes,graph,state}.py`, legacy checkpoint readers, debug trace routes | TraceInspector, Debug Panel graph view |
| Memory consolidation (hourly clustering) | 809 | `consolidation_*.py`, `routers/consolidation.py` | — |
| Anthropic as a **chat** provider (keep SDK for Haiku only) | part of `streaming.py` | Anthropic branch of the chat loop, provider switch UI limited to GPT models | Header model badge lists GPT models only |
| Task-planning tools (`create_plan`, plan events) | ~250 | plan section of `tools.py`, PLAN_* SSE events | PlanBlock |
| `site/` (docs website for the original upstream project) | — | whole directory | — |

Estimated deletion: **~9,500 backend lines and ~3,500 frontend lines**, about a third of the codebase, before counting `tools.py` sections and `streaming.py` branches.

### Database

Tables dropped after their code is gone: `orchestrator_tasks`, `orchestrator_config`, `evolution_config`, `evolution_history`, `claude_code_sessions`, `widget_state`, `widget_tokens`, `persistent_databases` (and the `edward_db_appointments_tracker` schema), `files`, `external_contacts`, `memory_connections`, `memory_flags`, `consolidation_cycles`, `consolidation_config`, `checkpoints` (legacy LangGraph). A `pg_dump` is taken first and kept outside the repo.

Data cleanup (not schema): cancel the 5 pending self-audit events; delete the ~60 self-audit documents and their 92 scheduled-event conversations. Memories are untouched.

## Decisions settled by this plan

Recorded as `D-001-n` markers in code where a code home exists, plus rows in `docs/DECISIONS.md`.

| ID | Decision |
|---|---|
| D-001-1 | Windows is the only supported platform. No `sys.platform` branches remain. |
| D-001-2 | Chat provider is GPT via Codex OAuth only. Anthropic SDK is used only by `llm_client.py` for Haiku background calls. |
| D-001-3 | Background jobs stay on Claude Haiku 4.5. Revisit only if the Anthropic bill exceeds a few dollars a month. |
| D-001-4 | Edward does not spawn workers, self-code, or run code. Removed features are not re-proposed without a usage case. |
| D-001-5 | Plan docs live in `docs/plans/`; `IMPLEMENTATION_PLANS/` and `docs/superpowers/` are frozen archives. |
| D-001-6 | No design commitment exists yet. It is chosen visually from mockups in Plan 004. Until then no agent restyles the UI or adds fonts or colors. |
| D-001-7 | No `Co-Authored-By` or other AI attribution trailers in commits, for every agent. Project rule wins over any harness default. |

## Design commitment — deferred to Plan 004

The owner decides visually, not from hex values and font names. Plan 004 opens with 2–3 rendered mockups of the chat screen at 375px (candidate: Fraunces + Instrument Sans + JetBrains Mono on a warm near-black with a single ember accent; alternatives to be shown alongside). The winning mockup's tokens become law in `docs/ENGINEERING.md` at that point.

Until then, `docs/ENGINEERING.md` states explicitly that no design commitment exists and that no agent may restyle the UI or introduce new fonts or colors. The current Inter + slate look is tolerated as legacy, not endorsed.

## Milestones

### M1 — Freeze and archive
Status: **complete 2026-09-09**
- `docs/plans/`, `docs/specs/`, `docs/ENGINEERING.md`, `docs/DECISIONS.md` created via `/bootstrap-agent-docs` (retrofit mode). `CLAUDE.md` / `AGENTS.md` reduced to pointers; their feature catalogue moved to `docs/specs/ARCHITECTURE_LEGACY_2026-03.md` as a frozen reference until M6 rewrites it.
- `IMPLEMENTATION_PLANS/README.md` and `docs/superpowers/README.md` mark those trees archived. Nothing moved or renamed.
- Database dumped from the `edward-pg` Docker container (pgvector/pg16) to `C:\Users\cchen362\edward-backups\edward-pre-revival-2026-09-09.sql` (15 MB, 36 tables).
- The 5 pending self-audit events were cancelled directly in the database (backend was down, so the API was unavailable).

### M4 note — chat model
`settings.model` was `gpt-5.4`. The owner reported newer GPT models (5.6 and the "6 Astra" line) on the Codex endpoint. M4 had to **probe the endpoint for the models it actually serves** and set the default and picker from that result, never from a hardcoded list or from memory. Probe result is recorded in the M4 block below.

### M2 — Delete macOS, Twilio, widget, hosting, persistent DBs, file storage, LangSmith, legacy graph
Status: **complete 2026-09-09** — backend boots clean, `npm run lint` and `npm run build` pass. Browser-verified after the owner signed in: Settings tiles (Databases/Files gone), Heartbeat panel with a single WhatsApp listener, Skills (9 skills), Events browser, and a full chat turn that streamed a reply, saved to `conversation_messages`, and ran memory extraction; chat and settings checked at 375px. Two pre-existing issues surfaced, neither caused by M2: (1) the Codex endpoint now rejects `gpt-5.4` ("not supported when using Codex with a ChatGPT account"), so every turn silently falls through to the pay-per-token `OPENAI_API_KEY` path — this is the M4 probe item and should be done next; (2) a React hydration mismatch in the header (`ClientLayout.tsx`, the `isAuthenticated && <ModelBadge />` branch) from commit 0e80767, visible only as a dev-overlay error.
- Deleted in full: iMessage, Contacts, Apple MCP, the iMessage/Calendar/Email heartbeat listeners and their triage rules, Twilio (service, webhooks, auth allow-list), iOS widget, persistent DBs, HTML hosting, file storage, LangSmith debug routes, legacy LangGraph (`graph/{graph,nodes,state}.py`, the boot-time `AsyncPostgresSaver`, the conversations-router fallback), `_build_platform_context()`, all `.sh` scripts, `site/` plus its Cloudflare Pages workflow, and the `opengraph-image` / `twitter-image` routes (social cards for the deleted public site; they also failed to prerender on Windows and were the only thing keeping `npm run build` red).
- D-001-1 stamped in `backend/main.py`. Every `sys.platform` branch in kept code is now unconditional Windows code; the only remaining branches are in M3-cut files (`claude_code_service.py`, `services/execution/`).
- Deviations from the design: (1) `nlm_push_file` (NotebookLM, an M3 item) went now because it imported file storage. (2) `delivery_channel` vocabulary for scheduled events changed from `sms`/`imessage` to `whatsapp`/`push`; the live table held only `chat`/null, so no rows were affected. (3) Chat uploads no longer get a `file_id`; the database showed zero uploads ever persisted, so the history-preview path never worked and nothing regressed.
- Verified from the live DB before deleting the legacy fallback: only 2 one-message conversations from 2026-03-04 were readable solely through it.
- Kept for M5: the `HeartbeatConfigModel` iMessage/Calendar/Email columns and every model on the drop list stay defined in `database.py`; stale `skills` rows are hidden because listing iterates `SKILL_DEFINITIONS`.

### M3 — Delete orchestrator, evolution, Claude Code, CASCE, code execution, NotebookLM, consolidation, plan tools
Status: **complete 2026-09-09** — backend boots with zero tracebacks in the uvicorn err log (registry, scheduler, heartbeat, GitHub MCP all start); `npm run lint` and `npm run build` pass. Browser-verified signed in: Settings shows seven tiles (Evolution and Orchestrator gone); Skills lists the three surviving skills (WhatsApp, Web Search, Push) all connected; a chat turn asking for a web search streamed via `gpt-6-astra`, the activity feed showed `web_search`, `remember_search`, `save_document`, `fetch_page_content`, the reply rendered, one `conversation_messages` row was saved with a `tool_calls` list and no `plan_steps` key, and memory extraction stored a new `context` memory. Chat and Settings checked at 375px with no horizontal overflow.
- **Deleted in full:** `orchestrator_{service,models}.py`, `evolution_{service,models}.py`, `claude_code_service.py`, `cc_manager_service.py`, `code_execution_service.py`, `services/execution/`, `services/governance/`, `notebooklm_service.py`, `consolidation_{service,models}.py`, `routers/{orchestrator,evolution,consolidation}.py`, the `governance.jsonl` file handler in `main.py` (and the `backend/logs/` directory it kept recreating), the NotebookLM / consolidation / evolution / orchestrator lifespan hooks, six skills (`code_interpreter`, `javascript_interpreter`, `sql_interpreter`, `shell_interpreter`, `orchestrator`, `notebooklm`), the plan tools and their `plan_*` events, the `code` / `execution_*` / `cc_*` SSE events, `_stream_cc_session_inline`, the legacy string-only `stream_with_memory`, `chat_with_memory`'s `skip_memory` / `is_worker` parameters and orchestrator briefing, `get_worker_tools`, `SKILL_TOOL_MAPPING` (unread), `get_all_tools_description` (uncalled), the `cc_sessions` field on the conversation response, the consolidation "spreading activation" and flag-annotation blocks in `memory_service.retrieve_memories`, the six NotebookLM seed memories in `scripts/seed_memories.py`, and `claude-agent-sdk` / `notebooklm-mcp-cli` from `requirements.txt`. Frontend: `CodeBlock`, `PlanBlock`, `CCSessionBlock`, `EvolutionPanel`, `OrchestratorPanel`, the Evolution and Orchestrator API sections in `api.ts`, the `orchestrator_worker` conversation source (sidebar icon and "Workers" filter). No `sys.platform` branch remains anywhere.
- **Prompt and loop changes.** `EDWARD_CHARACTER` lost the `create_plan` / `spawn_cc_worker` / `spawn_worker` paragraph and the "notebook" mention; the heartbeat inner-mind prompt and the memory/search tool descriptions lost theirs. Both tool loops now use fixed `MAX_TOOL_ITERATIONS = 30` and `MAX_CONSECUTIVE_ERROR_ITERATIONS = 3` (the plan-aware 100-iteration / 6-error scaling and the "you still have N incomplete steps" nudge went with the plan tools).
- **Module split.** `services/graph/streaming.py` (1,876 lines) is now `prompt.py` (character + memory context), `events.py` (the SSE `EventType` contract and tool labels), `messages.py` (checkpoint message dicts and Responses-API conversion), `codex.py` (`call_llm` / `call_codex`, carrying the D-001-2 marker), `tool_execution.py`, and `streaming.py` (the two turn loops, 651 lines). `services/graph/tools.py` (2,774 lines) is the package `services/graph/tools/` with `context.py`, `memory.py`, `documents.py`, `scheduled_events.py`, `heartbeat.py`, `push.py`, `search.py`; the registry imports from the concrete modules and there are no re-exports. WhatsApp and custom-MCP tools already had their own modules (`services/whatsapp_bridge_tools.py`, `services/custom_mcp_tools.py`) and stayed there. Largest file is now `streaming.py`; nothing above 651 lines.
- **Deviations.** (1) `aiohttp` stays: the Codex OAuth callback server uses it. `langsmith`, `twilio`, `phonenumbers` were already gone after M2. (2) The deletion pass removed `get_memory_tools_description` and `get_search_tools_description`, which the registry imports lazily on every turn; an import-only boot check did not catch it and the split pass restored them. The chat turn above is the proof they are back. (3) `scripts/seed_memories.py` kept its four non-notebook entries with their wording trimmed to memories and documents only.
- D-001-4 stamped above `get_available_tools` in `tool_registry.py`; the D-001-2 marker moved with `call_llm` into `codex.py` and its `docs/DECISIONS.md` pointer was updated.
- **Left for M5** (data, not code): live `memories` of type `instruction` that still tell Edward to build notebooks (seeded from the deleted entries), any `conversations` rows with `source = 'orchestrator_worker'`, and stale `skills` rows for the six deleted skills (hidden today because listing iterates `SKILL_DEFINITIONS`). `database.py` still defines every model on the drop list.

### M4 — Provider simplification
Status: **complete 2026-09-09** — backend boots with zero tracebacks in the uvicorn err log; startup logged the served list and rewrote `settings.model` from `gpt-5.4` to `gpt-6-astra`; starting without `ANTHROPIC_API_KEY` raises the named `RuntimeError`; `npm run lint` and `npm run build` pass. Browser-verified signed in: the header picker lists the five served models with descriptions; a chat turn asking for a web search logged `[LLM] Calling Codex OAuth (gpt-6-astra)` twice (tool call, then reply), streamed the answer, saved to `conversation_messages`, and memory extraction stored a new `context` memory; no hydration error in the console; chat and Settings → General checked at 375px with no horizontal overflow.
- **Probe (2026-09-09).** `GET https://chatgpt.com/backend-api/codex/models?client_version=<v>` with the same auth headers as the responses call returns the served catalogue. `client_version` is required, and the server hides models whose `minimal_client_version` is newer than the value given, so Edward asks with `99.0.0`. Served that day, by priority: `gpt-6-astra` (1, "GPT-6-Astra"), `gpt-5.6-sol` (6), `gpt-5.6-terra` (7), `gpt-5.6-luna` (8), `gpt-5.5` (12); hidden entries `gpt-reserve` (an alias that answers as `gpt-5.6-luna`) and `codex-auto-review`. Every listed slug answered a real POST. Rejected with HTTP 400 "not supported when using Codex with a ChatGPT account": `gpt-5.4`, `gpt-5.6`, `gpt-5.4-mini`, `gpt-5.3-codex`, `gpt-5.5-codex`, `gpt-5.6-codex`, `gpt-5-codex`, `gpt-6`, `codex-mini-latest`.
- **Model resolution.** `codex_oauth_service.list_served_models()` fetches the listing (10-minute cache, `visibility == "list"` only, sorted by priority) and `resolve_chat_model()` keeps `settings.model` if it is served, else picks the highest-priority served model and logs it. Startup runs the probe once, logs the list, and rewrites a stale `settings.model` (`gpt-5.4` → `gpt-6-astra`). `_call_llm` resolves again on every turn from the cache, so a model retired mid-run surfaces as a log line and a served model, never as spend.
- **Deleted in full:** the Anthropic chat branch in `streaming.py` (`_call_anthropic`, `_build_api_kwargs`, effort handling, the Anthropic streaming fallback), the metered `_call_openai` path and its "OpenAI Auth Fallback" push, `_is_openai_model`, `tools_to_anthropic_schemas`, the hardcoded `ANTHROPIC_MODELS` / `OPENAI_MODELS` lists, the `openai` package, and `OPENAI_API_KEY` from `.env.example`. `GET /api/settings/models` now returns the served list; the header badge and the Settings select are one flat list with no provider grouping.
- **Startup credential checks.** `ANTHROPIC_API_KEY` missing → `RuntimeError` naming the variable before `init_db`. Codex OAuth tokens missing → a loud console banner, and the app still boots so the owner can sign in from Settings → OpenAI (the sign-in flow lives inside the app, so a hard fail here would lock the owner out). A listing failure with tokens present raises and stops startup.
- **Hydration fix.** `AuthContext` seeded `isAuthenticated` from `localStorage` inside the state initializer, so the server rendered "logged out" and the client "logged in" and the header badge mismatched. It now reads the hint through `useSyncExternalStore` with a `false` server snapshot.
- D-001-2 stamped above `_call_llm` in `streaming.py`; D-001-3 stamped in `llm_client.py`.
- Verify: a chat turn streams, a tool call round-trips, memory extraction runs after the turn.

### M5 — Data cleanup and schema drop
Status: **complete 2026-09-09** — backend booted twice with zero tracebacks in the uvicorn err log (the second boot proves `create_all` plus the idempotent block converge on the reduced schema); `npm run lint` and `npm run build` pass. Browser-verified signed in: a chat turn streamed via `gpt-6-astra` with one tool call and five retrieved memories, saved a 4-entry `conversation_messages` row, and ran memory extraction (which correctly found nothing new to store for a question); Skills (3, all connected), Memories (227), Documents (11), Events (no pending) and Settings render at desktop and 375px with no horizontal overflow. `information_schema.tables` now lists 14 public tables and the `edward_db_appointments_tracker` schema is gone.
- **Backup first:** `C:\Users\cchen362\edward-backups\edward-pre-m5-2026-09-09.sql` (15 MB, 35 tables incl. the 3 in the appointments schema), taken with `docker exec edward-pg pg_dump` before any `DELETE` or `DROP`.
- **Data deleted** (one transaction, counts before → after): `documents` 66 → 11 (55 self-audit notes: every "weekly self-review", "memory audit", "evolution check" and "Weekly insights audit" title; all were authored from `scheduled_event` conversations); `conversations` 276 → 194 (70 `scheduled_event` self-audit runs matched by title prefix plus all 12 `orchestrator_worker` `[CC]` smoke tests; the 22 `scheduled_event` conversations that are real reminders and pushes were kept, as were all 149 `user` and 23 `heartbeat` rows); `conversation_messages` 266 → 197 (the 69 rows belonging to those conversations); `memories` 230 → 227 (the 3 `instruction` memories that mention notebooks / `nlm_`); `skills` 16 → 3 (every row not in `SKILL_DEFINITIONS`: 13, not the 7 estimated, because the M2 deletions had never been pruned either). No `scheduled_events` row was `pending` (24 completed, 10 cancelled, 1 failed); none were deleted.
- **Schema.** `database.py` (796 → 458 lines) no longer defines `ExternalContactModel`, `FileModel`, `WidgetStateModel`, `WidgetTokenModel`, `PersistentDatabaseModel`, `MemoryConnectionModel`, `MemoryFlagModel`, `ConsolidationCycleModel`, `ConsolidationConfigModel`, `ClaudeCodeSessionModel`, `EvolutionConfigModel`, `EvolutionHistoryModel`, `OrchestratorTaskModel`, `OrchestratorConfigModel`, nor their `ALTER` / `CREATE INDEX` lines or default-row seeding; `HeartbeatConfigModel` lost the iMessage/Calendar/Email columns. Because there is no migration tool, the drop itself lives in `init_db` as an idempotent block right after `create_all`: `DROP TABLE IF EXISTS … CASCADE` for the 14 model tables plus the four legacy LangGraph tables (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations` — the cut list named one; there were four), `DROP SCHEMA IF EXISTS edward_db_appointments_tracker CASCADE`, and `DROP COLUMN IF EXISTS` for the seven heartbeat columns. It stays in the file so a fresh clone and the live database converge on the same shape.
- **Deviations.** (1) The document delete pattern gained `Weekly insights audit%`: 16 such notes (from the "Surface insights from Edward's data" self-audit) were not caught by the three handoff patterns but are the same noise. (2) Two of the three deleted notebook memories also carried non-notebook guidance ("use web search proactively", "maintain memory hygiene"). They were deleted as decided; the text survives in both dumps if the owner wants them re-added without the notebook clause in Plan 005. (3) The `edward_db_appointments_tracker` schema was dropped along with `persistent_databases`, as the Database section already called for.
- **Observed, not fixed (Plan 005):** Edward's reply to the verification question said appointments "live in `appointments_tracker`", i.e. the memory corpus still references the deleted persistent database. Memories are untouched by decision.
- The in-app browser pane logs `[SW] Registration failed` on every load; `/sw.js` serves 200 from the dev server, so this is the pane's sandbox and unrelated to M5. Service-worker registration on a real phone is Plan 002's concern.

### M6 — Docs and verification
Status: pending
- `docs/ENGINEERING.md` architecture section rewritten against the real post-cleanup code. CLAUDE.md / AGENTS.md are pointers only.
- Browser verification on desktop and at 375px: login, chat with streaming, memory browser, events browser, WhatsApp send via tool, GitHub MCP query, web search.
- Commit. Merge `feat/prompt-caching` into `main`; delete the seven stale feature branches.

## Out of scope (own plans)

| Plan | Scope |
|---|---|
| 002 Push root cause | Live delivery test with logging to file, fix, iPhone verification. Move `webpush()` off the event loop. |
| 003 WhatsApp triage | Bridge forwards all inbound messages (not just @edward) with a per-chat allow-list; WhatsApp-first Haiku triage; digest + push; Edward can reply in-chat when asked. Bridge resilience (session expiry, reconnect, health push). |
| 004 UI redesign | Apply the design commitment. Chat-first layout, settings reduced to Memory, Documents, Events, WhatsApp, Skills. |
| 005 Memory redesign | Owner has said the memory system "might need redesign or enhancement". Scoped after 001–004 land. |
| 006 Detached turns | Each chat turn runs as a server-side task with a per-conversation event buffer; the SSE endpoint subscribes and can reconnect mid-turn. Client disconnect no longer cancels the work. On completion the reply is saved and a push is sent if no client is attached. Replaces the orchestrator's "background handoff" role with ~200 lines instead of ~2,200. Depends on 002 (push must work). |

## Task-planning tools: what they actually do

Asked by the owner: "do we need them for Edward to carry out tasks or handle a few requests simultaneously?" Verified from `graph/tools.py` (lines 1056–1311) and `graph/streaming.py` (lines 1720–1760, 2108–2135):

1. `create_plan` stores an in-memory checklist per conversation and emits `plan_*` SSE events that the frontend renders as a PlanBlock.
2. While a plan is active, the tool-loop iteration cap is raised from the default to `steps × 5 + 10` (max 100) and the consecutive-error breaker from 3 to 6.
3. When the model stops calling tools with steps still open, the loop injects a "you still have N incomplete steps, continue" user message.

There is **no concurrency**. Steps run one after another in the same loop; "a few requests at once" was the orchestrator's job, which is being deleted. The plan tools are a scaffold for long single-threaded tool chains (10+ calls), which only existed for self-coding and worker tasks. For companion chat and light ops (1–5 tool calls) the base loop already handles it, and the live activity feed (Plan 013) already shows tool progress.

Recommendation: **delete**. If a long multi-step use case appears later, re-add a smaller version as its own plan.

### "Can I close the app and come back to the answer?"

Verified from `routers/chat.py` lines 122–160: the whole chat turn (LLM calls, tool calls, saving the reply) runs *inside* the HTTP streaming response generator. When the phone closes the app, the SSE connection drops, Starlette cancels the generator, and the turn dies wherever it was. Nothing is saved and no notification is sent. Plan 011's answer to this was "delegate to `spawn_worker`", which is the orchestrator, which is being deleted for a 81% failure rate. The plan tools do not help here either.

So today the answer is **no**, and the fix is not the plan tools. The fix is Plan 006 below: run every turn as a server-side task that the SSE connection merely subscribes to, so a disconnect stops the *viewing*, not the *work*, and completion sends a push.

## Open questions for the owner

1. Plan tools: accept the deletion recommendation above, or keep them.

Resolved 2026-09-09: cut list approved except for the plan-tools row above; design commitment deferred to Plan 004 (D-001-6); no attribution trailers (D-001-7), today's commit amended accordingly.
