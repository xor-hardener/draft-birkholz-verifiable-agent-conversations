# Translation Layer Breakdown

Documents the exact transformations `scripts/validate-sessions.py` performs for each agent
format, mapping native fields to the CDDL spec (`agent-conversation.cddl`).

Last updated: 2026-02-17

## Per-Agent Breakdowns

Each file contains the transformation rules and a native JSON schema example.

- [Claude Code](breakdown/claude-code.md) — JSONL, one event per line with redundant session metadata
- [Gemini CLI](breakdown/gemini-cli.md) — Single JSON object with `messages[]` array (closest to CDDL)
- [Codex CLI](breakdown/codex-cli.md) — JSONL with two-level envelope `{timestamp, type, payload}`
- [OpenCode](breakdown/opencode.md) — Concatenated pretty-printed JSON objects
- [Cursor](breakdown/cursor.md) — Bare JSONL `{role, message}` (most minimal)

---

## Cross-Agent Summary

| Category | Claude | Gemini | Codex | OpenCode | Cursor |
|---|---|---|---|---|---|
| Direct matches | 1 field | 4 fields | 1 field | 1 field | 0 fields |
| Renames | 3 | 2 | 9 | 10 | 2 |
| Un-nest | 2 | 0 | 9 (payload.\*) | 6 (state.\*) | 1 |
| Type value map | 4 values | 4 values | 9 values | 6 values | 1 value |
| Structural split/merge | content[] → children | toolCalls/thoughts → children | 2-level envelope unwrap | tool → call+result SPLIT; text→user/assistant via messageID | none |
| Fabricated | 3 | 3 | 3 | 2 | 5 |

## Heaviest Transformations

1. **Envelope unwrap** (Codex `payload.*`) — every field goes through one level of indirection
2. **Tool splitting** (OpenCode fused tool objects → separate call + result entries)
3. **Children extraction** (Claude/Gemini content blocks → typed children)
4. **Type value mapping** (every agent uses different type names for the same concepts)
