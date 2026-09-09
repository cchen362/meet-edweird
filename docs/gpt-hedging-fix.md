# Fixing GPT-5.4's Hedging Habit

## The Problem

GPT-5.4 ends responses with "If you want, I can..." or "Would you like me to..." even when the system prompt explicitly says not to. This isn't a reasoning failure — it's a reflexive habit from RLHF training, where human raters consistently rewarded deferential closings. The model generates them almost automatically, regardless of instructions.

---

## How the Prompt Is Structured

Every request to GPT-5.4 sends three separate fields:

```
instructions  (system prompt — assembled blob)
input         (conversation history)
tools         (tool schemas — separate, not inside instructions)
```

The `instructions` blob is assembled in this order:

```
settings.system_prompt      "You are Edward, a personal AI assistant..."
EDWARD_CHARACTER            identity + behavioral principles
platform_context            "Running on Windows..."
─────────────────────────── static (same every turn)
memory_context              retrieved memories from pgvector
briefing_context            heartbeat briefing (if any)
time_context                "Current date and time: ..."
─────────────────────────── dynamic (changes per turn)
## Response Rule            ← appended last
```

The model reads `instructions` first, then `input` (conversation), then generates. By the time it's writing its closing words, the freshest thing in its attention window is the **tail of `instructions`** and the latest user message.

---

## Why the First Fix Wasn't Enough

The behavioral principle was already in `EDWARD_CHARACTER` mid-blob — but surrounded by hundreds of tokens of other context, it's attention-stale by the time the model reaches its closing tokens. Stronger wording in the wrong position doesn't help much.

---

## The Fix

Two layers:

**1. `EDWARD_CHARACTER` (principle level, all providers)**
The ownership rule is isolated into its own paragraph so it reads as a standalone directive, not one clause among many:
> *"Own your decisions. Act or decline — never hedge. Saying 'If you want, I can...' means you chose not to act; say that plainly instead."*

**2. `## Response Rule` (enforcement, Codex/GPT only)**
Appended at the tail of `instructions`, right before the conversation:
> *"Never end a response with a hedging offer like 'If you want, I can...', 'Would you like me to...', or any variant. End responses with your answer or action — not an invitation to ask you to act."*

Recency bias does the work — it's the last system-level directive the model reads before generating.

---

## Why Not More Rules?

The temptation is to keep adding "never say X" phrases. That's the wrong direction. A growing blocklist trains the model to pattern-match against a list rather than exercise judgment — technically compliant but mechanical. That's pseudo-agentic behavior.

The right structure is: one principle at the character level (shapes reasoning), one concrete anchor at the tail (handles the reflexive habit). Two layers. Everything else is left to the model's judgment.
