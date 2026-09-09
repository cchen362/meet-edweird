# Edward — Claude Code

The authoritative engineering guide for this repository is `docs/ENGINEERING.md`, imported below. It is shared with every coding agent that works on Edward — **make all guidance edits there, not in this file**, so Claude Code and Codex can never drift apart.

@docs/ENGINEERING.md

## Claude Code specifics

- Settled cross-tool decisions live in `docs/DECISIONS.md`. Read it before proposing work on a paid provider or anything marked CLOSED, and append there — not only to memory — when a session settles something durable. Memory is private to this tool and this machine; Codex cannot see it.
- Implementation plans live in `docs/plans/`. Use the `implement-milestone`, `wrap-up`, and `handoff` skills when the request matches them.
- `IMPLEMENTATION_PLANS/` and `docs/superpowers/` are frozen archives (see the README in each). Never activate or extend them.
