# Translation Layer Breakdown

Documents the exact transformations `scripts/validate-sessions.py` performs for each agent
format, mapping native fields to the CDDL spec (`agent-conversation.cddl`).

Last updated: 2026-02-18

## v3.0.0-draft Changes

**Schema simplification** (2026-02-18): 7 entry types → 4. All maps extensible via `* tstr => any`.
See [`.claude/reviews/2026-02-18/simplification-plan.md`](reviews/2026-02-18/simplification-plan.md).

**No-drop policy**: Parsers now preserve ALL native fields. Fields not consumed for canonical
mapping are flat-merged into entries alongside canonical kebab-case fields. This means entries
contain a mix of canonical names (e.g., `type`, `content`, `timestamp`) and native names
(e.g., `parentUuid`, `stop_reason`, `isSidechain`).

**Token-usage extraction**: 4/5 agents now have canonical `token-usage` on assistant entries.

> **Note:** The per-agent breakdown files below document the v2 transformation rules. The v3
> changes add passthrough fields and token-usage extraction on top of the existing transforms.
> The structural transformations (envelope unwrap, children extraction, tool splitting, type
> mapping) are unchanged from v2.

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
| **Passthrough** (v3) | line + msg fields | msg + toolCall fields | payload remnants | role + state fields | none |
| **Token-usage** (v3) | `message.usage` | `messages[].tokens` | `event_msg/token_count` | `role-message.tokens` | N/A |

## Heaviest Transformations

1. **Envelope unwrap** (Codex `payload.*`) — every field goes through one level of indirection
2. **Tool splitting** (OpenCode fused tool objects → separate call + result entries)
3. **Children extraction** (Claude/Gemini content blocks → typed children)
4. **Type value mapping** (every agent uses different type names for the same concepts)

## v3 Passthrough Details

### Claude Code
- **Line-level passthrough**: `parentUuid`, `isSidechain`, `userType`, `requestId`,
  `permissionMode`, `slug`, `sourceToolAssistantUUID`, `toolUseResult`
- **Message-level passthrough**: `stop_reason`, `stop_sequence` (after `type`, `id`, `usage`
  consumed for canonical mapping)
- **Token-usage source**: `message.usage` → `{input, output, cached}` + native extras
  (`cache_creation_input_tokens`, `service_tier`, `inference_geo`)
- **Consumed (not passed through)**: Line: `timestamp`, `sessionId`, `version`, `cwd`,
  `gitBranch`, `uuid`, `type`, `message`. Msg: `role`, `content`, `model`, `type`, `id`, `usage`.

### Gemini CLI
- **Message-level passthrough**: native fields not in consumed set
- **Token-usage source**: `messages[].tokens` dict → `{input, output}` (from `inputTokens`,
  `outputTokens`); scalar `tokens` values passed through as native
- **toolCall child passthrough**: fields not in `{name, args, result, timestamp}`
- **thought child passthrough**: fields not in `{text, subject, timestamp}`

### Codex CLI
- **Per-payload-type passthrough**: Remaining payload fields after canonical extraction
- **Token-usage source**: `event_msg` with `subtype=token_count`, `info` object →
  `{input, output, total}` on system-event entries

### OpenCode
- **Role-message passthrough**: fields not in `{role, content, id}`
- **Text/tool passthrough**: remaining metadata and state fields
- **Token-usage source**: `role-message.tokens` + `role-message.cost` →
  `{input, output, cost}` on user/assistant entries
- **Skipped**: `share-info` objects (contain secrets)

### Cursor
- No passthrough fields (already minimal)
- No token data available
