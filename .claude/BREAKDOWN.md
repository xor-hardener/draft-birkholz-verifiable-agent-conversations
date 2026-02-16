# Translation Layer Breakdown

Documents the exact transformations `scripts/validate-sessions.py` performs for each agent
format, mapping native fields to the CDDL spec (`agent-conversation.cddl`).

Last updated: 2026-02-16

## Claude Code

Native format: JSONL, one event per line. Each line carries session metadata redundantly.

### Direct matches (zero transformation)
- `type: "user"` → `type: "user"`
- `type: "assistant"` → `type: "assistant"`
- `timestamp` → `timestamp`

### Renames
- `uuid` → `id`
- `message.content` → `content` (un-nest from `message` wrapper)
- `message.model` → `model-id`

### Structural extraction
- One JSONL line with `message.content: [{type: "tool_use", ...}, {type: "text", ...}, {type: "thinking", ...}]`
  → parent entry with `content: <native array>` + `children` array of typed entries
- Each `tool_use` child: `id` → `call-id`, type `"tool_use"` → `"tool-call"`
- Each `tool_result` child (in user messages): `tool_use_id` → `call-id`, `content` → `output`,
  `is_error` → `status`, type `"tool_result"` → `"tool-result"`
- Each `thinking` child: `thinking` → `content`, type `"thinking"` → `"reasoning"`

### Dropped fields
`parentUuid`, `isSidechain`, `userType`, `cwd` (per-entry), `sessionId` (per-entry),
`version`, `gitBranch`, `permissionMode`, `requestId`, `message.role`, `message.usage`,
`message.stop_reason`

### Fabricated
- Provider inferred from model prefix ("claude" → "anthropic")
- `cli-name: "claude-code"` hardcoded
- Record wrapper (verifiable-agent-record envelope)

---

## Gemini CLI

Native format: single JSON object with `messages[]` array. Closest to CDDL of all agents.

### Direct matches
- `type: "user"` → `type: "user"`
- `timestamp` → `timestamp`
- `id` → `id`
- `content` → `content` (already a string)

### Renames
- `type: "gemini"` → `type: "assistant"`
- `model` → `model-id`

### Structural extraction
- `toolCalls[]` array on the message → children:
  - `name` → `name` (direct)
  - `args` → `input` (rename)
  - `id` → `call-id` (rename)
  - `result` → `output` (rename + different nesting: `result[].functionResponse.response.output`)
  - `status` → `status` (direct)
  - Each toolCall produces two children: `"tool-call"` + `"tool-result"`
- `thoughts[]` array → children:
  - `description` → `content` (rename)
  - `subject` → `subject` (direct)
  - Each thought produces child `"reasoning"`

### Dropped fields
`projectHash`, `lastUpdated`, `toolCalls[].resultDisplay`, `displayName`, `description`,
`renderOutputAsMarkdown`, `tokens`

### Fabricated
- Provider inferred from "gemini" prefix
- `cli-name: "gemini-cli"` hardcoded
- Record wrapper

---

## Codex CLI

Native format: JSONL with two-level envelope `{timestamp, type, payload}`.

### Direct matches
- `timestamp` → `timestamp` (from outer envelope)

### Renames
- `payload.arguments` → `input`
- `payload.call_id` → `call-id`
- `payload.name` → `name`
- `payload.output` → `output`

### Structural extraction
- Two-level envelope unwrap: `{timestamp, type: "response_item", payload: {type: "function_call", ...}}`
  → `{type: "tool-call", timestamp, ...}`
- Three-level type derivation for messages: outer `type` + `payload.type` + `payload.role` → single `type`
- Type mapping:
  - `"function_call"` → `"tool-call"`
  - `"function_call_output"` → `"tool-result"`
  - `"reasoning"` → `"reasoning"` (direct)
  - `"message"+"user"` → `"user"`
  - `"message"+"assistant"` → `"assistant"`
- `event_msg` entries duplicate `response_item` entries (~13% inflation, both emitted)

### Dropped fields
Outer `type`, `payload.type`, `payload.role`, `session_meta` fields (moved to meta),
`turn_context` fields, `event_msg` metadata

### Fabricated
- `cli-name: "codex-cli"` hardcoded
- Model extracted from `turn_context` (a different JSONL line than `session_meta`)
- Record wrapper

---

## OpenCode

Native format: concatenated pretty-printed JSON objects. First object is session header.

### Direct matches
- `id` → `id`

### Renames
- `text` → `content`
- `tool` → `name`
- `callID` → `call-id`
- `state.input` → `input` (un-nest)
- `state.output` → `output` (un-nest)
- `state.status` → `status` (un-nest)
- `state.time.start` → `timestamp` on tool-call (un-nest)
- `state.time.end` → `timestamp` on tool-result (un-nest)
- `role: "user"/"assistant"` → `type: "user"/"assistant"` (rename field)
- `time.created` → `timestamp` on role objects (un-nest)

### Structural extraction
- **SPLIT**: One `type: "tool"` object → TWO entries (`tool-call` + `tool-result`)
- Type mapping:
  - `"text"` → `"assistant"`
  - `"tool"` → `"tool-call"` + `"tool-result"`
  - `"step-start"` / `"step-finish"` → `"system-event"`
  - `"reasoning"` → `"reasoning"` (direct)

### Dropped fields
`sessionID` (per-entry), `messageID`, `state.title`, `state.metadata`, `metadata.openai`,
`parentID`, `modelID`/`providerID`/`cost`/`tokens`/`finish` (from role objects), `path`,
`mode`, `agent`

### Fabricated
- `cli-name: "opencode"` hardcoded
- Record wrapper

---

## Cursor

Native format: bare JSONL `{role, message}`. The most minimal format.

### Direct matches
- Nothing maps directly

### Renames
- `role: "user"` → `type: "user"` (rename field)
- `message.content` → `content` (un-nest)

### Structural extraction
- None

### Dropped fields
- None (there's nothing to drop)

### Fabricated
- `session-id`: generated UUID (Cursor has no session identity)
- `model-id`: "unknown" (no model info)
- `model-provider`: "unknown"
- `cli-name: "cursor"` hardcoded
- All timestamps absent
- Record wrapper

---

## Cross-Agent Summary

| Category | Claude | Gemini | Codex | OpenCode | Cursor |
|---|---|---|---|---|---|
| Direct matches | 3 fields | 4 fields | 1 field | 1 field | 0 fields |
| Renames | 3 | 2 | 4 | 10 | 2 |
| Un-nest | 2 | 0 | 5 (payload.\*) | 6 (state.\*) | 1 |
| Type value map | 4 values | 3 values | 5 values | 4 values | 1 value |
| Structural split/merge | content[] → children | toolCalls/thoughts → children | 2-level envelope unwrap | tool → call+result SPLIT | none |
| Fabricated | 3 | 3 | 2 | 2 | 5 |

## Heaviest Transformations

1. **Envelope unwrap** (Codex `payload.*`) — every field goes through one level of indirection
2. **Tool splitting** (OpenCode fused tool objects → separate call + result entries)
3. **Children extraction** (Claude/Gemini content blocks → typed children)
4. **Type value mapping** (every agent uses different type names for the same concepts)
