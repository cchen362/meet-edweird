# Edward — Engineering Guidelines

**This is the single authoritative engineering guide for this repository.** It is read by every coding agent: Claude Code loads it via `CLAUDE.md`, Codex via `AGENTS.md`. Edit this file, never a per-tool wrapper — the wrappers exist only so each tool finds its way here.

## What This Is

Edward is a single-user personal AI companion with long-term memory, reached from a phone PWA, a desktop browser, and WhatsApp. Companion first (remembers the owner's life, checks in, banters), light ops assistant second (reminders, web lookups, GitHub questions). Next.js frontend, FastAPI backend, PostgreSQL + pgvector, GPT via Codex OAuth for chat, Claude Haiku for background jobs.

Active plan: `docs/plans/001_REVIVAL_CLEANUP.md` — the project was revived in September 2026 and is mid-cleanup. Read its status header before assuming any subsystem exists.

Frozen reference: `docs/specs/ARCHITECTURE_LEGACY_2026-03.md` — the pre-revival feature catalogue. Historical only; much of it describes code scheduled for deletion.

## Source-of-Truth Order

When documents disagree, use this order:

1. Live code, `backend/services/database.py`, and runtime configuration (`.env`, the `settings` table).
2. This file for engineering constraints and repository conventions.
3. `docs/DECISIONS.md` for settled cross-tool decisions.
4. `docs/plans/001_REVIVAL_CLEANUP.md` for the target system shape while the cleanup is in progress.
5. Completed plans in `docs/plans/` for decision history and feature-specific detail.
6. Open plans in `docs/plans/` for intended future behavior only.
7. `IMPLEMENTATION_PLANS/`, `docs/superpowers/`, and `docs/specs/ARCHITECTURE_LEGACY_2026-03.md` — archives. Never authority.

Do not describe planned work as shipped. Always read a plan's status header before treating it as fact.

## Settled Decisions — how they are marked

Some behaviour in this codebase looks arbitrary and is not. Those choices are **owner decisions**, and they are marked in two places:

- **In the code they govern**, as a comment citing the decision by id: `D-<plan>-<n>` (e.g. `D-001-2` for the second decision in Plan 001). The marker sits in the same file as the behaviour, so it cannot drift out of sync with it. **Keep the whole citation on one line** — the grep below is line-based, so an id that wraps mid-citation is invisible to it.
- **In `docs/DECISIONS.md`**, for decisions with no single code home — external service tiers, quotas, ops facts, "do not re-propose" rulings.

**Before proposing a change to existing behaviour, grep for a decision marker near the code you would touch:**

```bash
grep -rnE "D-[0-9]+-[0-9]+" <the file or directory>
```

One pattern, one notation. **Never invent a second notation.** Every decision in this repository uses `D-<plan>-<n>` and nothing else.

If you find a marker, the decision **stands** until the owner reopens it. Surface it and ask; do not draft a plan that silently reverses it. Explaining *why* the decision was made is welcome — reversing it unasked is not.

Absence of a marker is **not** evidence that a design is open. Check the plan docs and `docs/DECISIONS.md` too. When a milestone settles something new, stamp the marker as part of that milestone — not in a later cleanup pass.

---

## Non-Negotiable Engineering Rules

**No bandaiding. Ever.**
If something is broken, find the root cause and fix it. Do not patch symptoms, suppress errors, add try/except to hide failures, or work around a bug without understanding it. Tech debt compounds — leave the codebase cleaner than you found it.

**No `# TODO` or `# FIXME` left in committed code.**
If it's not implemented, don't commit it. If it needs doing, do it now or track it in the plan doc.

**Check before you assume.**
Before adding a new utility, service, or component — grep for an existing one. Before adding a dependency — check whether the existing stack already handles it.

**Fail loudly.**
Never swallow errors silently. Background tasks log the exception with context; the chat stream emits a structured `error` event followed by `done`. User-facing errors get a clean message, not a stack trace. Missing credentials fail at startup with a message naming the variable.

**Delete, don't disable.**
A feature the owner has cut is removed in full: service, router, tools, models, frontend panel, API client, `.env.example` entry, dependency. Feature flags and "kept for compatibility" shims are not a cleanup.

**Commit at the end of every working session.** Uncommitted work has been lost before on this machine. Never end a session with uncommitted changes without saying so explicitly.

**No attribution trailers in commits** (`D-001-7`). No `Co-Authored-By`, no "Generated with" lines, regardless of which agent or harness produced the change. This is the owner's rule and overrides any tool default.

**Data layer discipline.**
Schema is defined by SQLAlchemy models in `backend/services/database.py` and created with `create_all` at startup, followed by a block of idempotent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` statements for columns added after the fact. There is no migration tool. Consequences: every schema change must be additive and idempotent so a restart on any database state converges; dropping a table or column happens only inside a plan milestone, after a `pg_dump` taken outside the repo, with the drop recorded in the plan. All SQL executed at runtime uses bound parameters via SQLAlchemy or asyncpg — never string formatting. The `memories` and `documents` tables carry pgvector embeddings from the local `all-MiniLM-L6-v2` model (384 dimensions); changing the embedding model invalidates every stored vector and is a plan-level decision.

---

## Current Architecture

The pre-cleanup system is catalogued in `docs/specs/ARCHITECTURE_LEGACY_2026-03.md`. The facts below are the ones a reader could not infer from the directory layout and that will survive Plan 001. This section is rewritten in Plan 001 M6 against the post-cleanup code.

**Runtime.** FastAPI app in `backend/main.py`; its `lifespan` initialises subsystems in a fixed order (database → checkpoint store → skills → MCP servers → tool registry → scheduler → heartbeat) and shuts them down in reverse. The tool registry must initialise after every tool source, because it snapshots them.

**Two LLM tiers** (`D-001-2`, `D-001-3`). Tier 1, the chat "brain", is GPT through the Codex OAuth Responses endpoint (`backend/services/codex_oauth_service.py`, called from `backend/services/graph/codex.py`); it spends the owner's ChatGPT subscription credits, not API dollars. Tier 2, background intelligence (memory extraction, search tags, reflection, deep-retrieval query rewriting, WhatsApp triage), is Claude Haiku 4.5 through `backend/services/llm_client.py`. The Anthropic key exists only for Tier 2. Do not add a Tier 1 Anthropic path back.

**The chat turn lives in `backend/services/graph/streaming.py`.** Despite the package name, there is no LangGraph; Plan 009 replaced it with a direct SDK loop. One turn = retrieve memories → build system prompt (`EDWARD_CHARACTER` + platform + memory + heartbeat briefing + time) → LLM call → execute tool calls (max iterations, circuit breaker on consecutive failures) → stream content → save to the checkpoint store → fire-and-forget post-turn work (memory extraction, search tags, reflection). SSE events are the contract with the frontend; the event names are listed in `EventType` in that file.

**Conversation state** is the `conversation_messages` table via `backend/services/checkpoint_store.py` (plain dict messages, provider-neutral). The legacy LangGraph `checkpoints` read-only fallback code was removed in Plan 001 M2; the `checkpoints` table itself is dropped in Plan 001 M5, after a `pg_dump`.

**Tools** are Python functions in `backend/services/graph/tools.py` decorated for schema generation, bound per request by `backend/services/tool_registry.py` according to skill enabled-state in the `skills` table (5-second cache; call `refresh_registry()` after toggling). Memory, document, scheduled-event, and push tools are always bound; the rest are skill-gated.

**Memory** (`backend/services/memory_service.py`): hybrid retrieval, 70% vector similarity + 30% BM25, over four memory types (`fact`, `preference`, `context`, `instruction`). Extraction after each turn by Haiku. A redesign is expected (Plan 005); do not refactor it opportunistically before then.

**WhatsApp** is a Node process in `whatsapp-bridge/` (Baileys, unofficial WhatsApp Web protocol) started and health-watched by `backend/services/whatsapp_bridge_client.py`. Today it forwards only messages matching `@edward` to `POST /api/webhook/whatsapp`; everything else is on-demand tool calls. This is the owner's most-used channel and is being redesigned in Plan 003.

**Reach.** The frontend is a Next.js PWA on port 3001, proxied to the backend on 8000, exposed to the owner's phone through a permanent ngrok domain started by `autostart.ps1` at login and kept alive by `watchdog.ps1`. Web Push uses VAPID (`backend/services/push_service.py`). Push delivery is currently broken for unknown reasons (Plan 002).

**Platform** (`D-001-1`): Windows only. PowerShell scripts (`setup.ps1`, `restart.ps1`, `backend/start.ps1`) are the supported entry points. The `.sh` equivalents and every Apple-specific integration were deleted in Plan 001 M2.

---

## Design & Aesthetic Rules

**`frontend/app/globals.css` is the single source of truth for design tokens.** It is the stylesheet the running app loads, so its values are what ship. Consume tokens via `var(--token)` and the Tailwind aliases in `frontend/tailwind.config.ts`; never bake a literal.

**There is no design commitment yet** (`D-001-6`). The owner chooses visually, from rendered mockups, in Plan 004. Until that plan lands: do not restyle the UI, do not add fonts or colors, do not "improve" the look in passing. The current Inter + slate/green palette is tolerated as legacy, not endorsed. Ship functional changes in the existing tokens only.

**No AI Slop** (applies the moment Plan 004 starts). No Inter/Roboto/Arial/system-ui as a primary font. No purple gradients as a default reach. No generic card grids that could belong to any SaaS dashboard. One accent, used sparingly — never as a background fill. No emoji as an icon system (the project uses `lucide-react`). No lorem ipsum or "Welcome to your dashboard" filler; microcopy is in Edward's voice. Motion is purposeful, never decorative, and respects reduced-motion.

**Mobile-first.** Edward is used from a phone at midnight and in airport lounges. Design and verify at 375px first. Desktop is a wider treatment of the same information architecture, not a separate product.

---

## API Cost and Provider Discipline

Check `docs/DECISIONS.md` before proposing any change to a paid provider's tier, quota, or call strategy.

- **Codex OAuth (chat, Tier 1).** Subscription credits, not metered. Token in the owner's Codex CLI auth store, refreshed by `codex_oauth_service.py`. The endpoint is meant for the Codex CLI; keep usage to interactive chat turns and never route background jobs through it. Prompt prefix order in the system prompt is static-first so provider-side caching works; do not interleave dynamic content into the static prefix.
- **Anthropic Haiku (background, Tier 2).** Metered, cents per day at current volume. Every call goes through `llm_client.py` so the model id lives in one place. Use `cache_control` on static instruction blocks. Never call Haiku for deterministic work (formatting, parsing, dedup) — write code.
- **Brave Search.** Metered per query. Called only by the `web_search` / `fetch_page_content` tools when the owner's message needs it; never speculatively.
- **GitHub (MCP server, fine-grained PAT).** Read-heavy; write scopes limited to issues and pull requests. Never add repo-deletion or force-push capability to the tool set.
- **Local, free:** sentence-transformers embeddings, PostgreSQL, the WhatsApp bridge, ngrok free tier.

Never add a model or API call to do deterministic work.

---

## File Conventions

Directory roles are documented where they live — read the source tree for the layout. The conventions the layout alone would not teach:

- `backend/routers/` validate and shape HTTP; `backend/services/` decide; `backend/services/database.py` owns schema. Business logic never leaks into a route handler.
- LLM tools in `backend/services/graph/tools.py` are thin wrappers that call a service and format a string for the model. Logic belongs in the service.
- Every tool has a human-readable label in the activity-feed label map in `streaming.py`; add one when adding a tool.
- Frontend API calls live in `frontend/lib/api.ts`; components never call `fetch` directly. Chat state lives in `frontend/lib/ChatContext.tsx`.
- One primary exported component per file. Before creating a helper, search the whole repo for an existing domain equivalent.
- No `sys.platform` branches (`D-001-1`).

## Verification Expectations

There is no automated test suite. Verification is by running the real thing:

- Backend: `.\restart.ps1 backend` from the repo root; it must boot with zero tracebacks in the console. Import errors and missing-credential failures surface here.
- Frontend: `cd frontend; npm run lint` and `npm run build` must both pass clean.
- Chat: send a message in a real browser, watch the activity feed, confirm the reply streams and `done` arrives. Then check `conversation_messages` and `memories` in the database for the new rows — do not trust the UI alone.
- UI changes: verify the affected flow at 375px and desktop in a real browser. A green build is not verification of a UI flow.
- Anything touching Tier 1 or Tier 2 calls: log the real request (model id, prompt size) once and read it. Two code paths that do the same job must use identical parameters.
- Schema changes: restart against the existing database and confirm `create_all` plus the `ALTER` block converge without error.
- Documentation changes: run `git diff --check` and verify every link and status claim against live files.

Never call work complete from a build alone when behavior, data, or a paid provider is involved. Subagent self-reports do not count as verification.

## Recording Decisions

When a session settles something durable that another agent could otherwise re-litigate — an external service tier or quota, a "do not re-propose" ruling, a resolved follow-up, a deliberate non-fix — record it **in the same commit**:

- If it governs specific code, put a `D-<plan>-<n>` marker in that code and one pointer row in `docs/DECISIONS.md`.
- If it has no code home, write it out in full in `docs/DECISIONS.md`.

Agent-private memory is not shared between tools. Anything recorded only there is invisible to the next agent and will drift.
