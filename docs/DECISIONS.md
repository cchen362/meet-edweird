# Edward — Settled Decisions

Owner decisions that any coding agent (Claude Code, Codex, or otherwise) must respect and must not re-litigate.

**Why this file exists.** Agent memory stores are per-tool and per-machine. When one agent settles something and records it only in its own memory, the next agent — a different tool, or the same tool on a different machine — cannot see it and will re-propose work that is already done or already declined. This file is in git, so every agent reads the same truth.

**How this file relates to code markers.** Decisions attached to specific behaviour are marked `D-<plan>-<n>` in the code they govern (see "Settled Decisions" in `docs/ENGINEERING.md`). Those get **one line here plus a pointer** — the reasoning stays next to the code, where it cannot drift. Decisions with **no single code home** keep their full reasoning here, because this file is their only home.

**How to use it.** Read before proposing changes to a paid provider, an external-service tier, or anything marked CLOSED. Append when a session settles something durable. **Never delete an entry** — supersede it, and mark the old one SUPERSEDED with the reason.

---

## Decisions anchored in code

One line each. The code marker is authoritative; follow the pointer for the reasoning. Markers for D-001-1 through D-001-4 are stamped during the Plan 001 milestone that touches the governing code; until then the reasoning is in `docs/plans/001_REVIVAL_CLEANUP.md`.

| ID | Ruling | Reasoning lives in |
|---|---|---|
| D-001-1 | Windows is the only supported platform; no `sys.platform` branches. | `backend/main.py` (stamped in M2) |
| D-001-2 | Chat provider is GPT via Codex OAuth only; the Anthropic SDK is used solely for Haiku background calls. | `backend/services/graph/streaming.py` (stamped in M4) |
| D-001-3 | Background jobs stay on Claude Haiku 4.5. | `backend/services/llm_client.py` (stamped in M4) |
| D-001-4 | Edward does not spawn workers, self-code, or execute code. | `backend/services/tool_registry.py` (stamped in M3) |
| D-001-6 | No design commitment exists; chosen visually from mockups in Plan 004. No restyling before then. | `frontend/app/globals.css` (stamped in M6) |

## Superseded or hollowed-out — do not re-stamp

Decisions whose premise has changed. Recorded so a future triage does not rediscover them in the plan docs, see no marker, and re-stamp a ruling that no longer holds.

| Decision | Status |
|---|---|
| Plan 000 "Cross-platform, not Windows-only" (macOS + Windows) | SUPERSEDED by D-001-1, 2026-09-09. Owner has no Mac. |
| Plan 000 "NotebookLM for deep knowledge" | SUPERSEDED, 2026-09-09. No usage signal; deleted in Plan 001 M3. |
| Plan 009 "Dual provider (Anthropic + OpenAI) for chat" | SUPERSEDED by D-001-2, 2026-09-09. Owner will not pay for Claude API chat. |
| Plan 011 "Long-running work is backgrounded via `spawn_worker`" | SUPERSEDED, 2026-09-09. Orchestrator deleted (21 of 26 tasks failed); replaced by Plan 006 detached turns. |
| Plan 014 CASCE governance (Phases 0–3) | SUPERSEDED, 2026-09-09. Deleted in Plan 001 M3; not re-proposed without a measured need. |
| Plan 000 "Telegram deferred; PWA covers it" | Still stands, but PWA push is broken (Plan 002). Revisit only if Plan 002 fails. |

## Decisions with no code home

External-service facts, corpus-level policy, and ops details that no single file governs.

**This section is complete by design, not a backlog.** Prose here does not mean "not yet given a code marker"; it means a code marker would have nowhere honest to sit.

**D-001-5 — Plan docs live in `docs/plans/`.** `IMPLEMENTATION_PLANS/` and `docs/superpowers/` are frozen archives with a README saying so. Numbering restarts at 001. Neither archive is moved or renamed, so old links keep resolving.

**D-001-7 — No attribution trailers in commits.** No `Co-Authored-By`, no "Generated with" footers, from any agent or harness. The owner wants clean git history. A harness default that says otherwise is overridden by this rule.

**Deleted features are not re-proposed without a usage case.** The 2026-09-09 review measured actual use from the database (145 user conversations, 21/26 orchestrator failures, 65 self-audit documents, 0 Twilio contacts, no heartbeat events since March). Anything on the Plan 001 cut list comes back only when the owner names a concrete use.

**Backups live outside the repo** at `C:\Users\cchen362\edward-backups\`. Pre-revival dump: `edward-pre-revival-2026-09-09.sql` (36 tables, taken from the `edward-pg` Docker container). Take a fresh dump before any table drop.

**PostgreSQL runs in Docker Desktop** as container `edward-pg` (image `pgvector/pgvector:pg16`, port 5432). `pg_dump` is not installed on the host; run it inside the container.

**Chat model is chosen by probing the Codex endpoint**, not from a hardcoded list. The owner keeps the "brain" on the newest GPT line the endpoint serves; the picker must reflect what is actually available.

**Twilio is closed.** Paid number, zero contacts ever, and WhatsApp-via-Twilio requires a business tier the owner declines. WhatsApp goes through the Baileys bridge only.
