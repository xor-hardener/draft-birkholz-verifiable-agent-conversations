# Agent-Specific to Abstract Type Mapping

## Overview

This table documents how each agent implementation's message types map to the abstract CDDL types defined in `agent-conversation.cddl`. The mapping was derived from empirical analysis of 221 CVE-fixing sessions.

## Message Type Mapping Matrix

| Abstract Type | Claude Code (JSONL) | Gemini CLI (JSON) | Codex CLI (JSONL) | OpenCode (JSON) |
|:--------------|:--------------------|:------------------|:------------------|:----------------|
| **user-entry** | `type: "user"` | `role: "user"` | `role: "user"` | `role: "user"` |
| **assistant-entry** | `type: "assistant"` | `role: "model"` | `role: "assistant"` | `role: "assistant"` |
| **tool-call-entry** | `content[].type: "tool_use"` | `parts[].function_call` | `content[].type: "function_call"` | `tool_calls[]` |
| **tool-result-entry** | `type: "user"` + `tool_use_id` | `parts[].function_response` | `content[].type: "function_result"` | `tool_responses[]` |
| **reasoning-entry** | `content[].type: "thinking"` | *(not present)* | `content[].type: "reasoning"` | `metadata.thinking` |
| **system-event-entry** | `type: "queue-operation"` | *(not present)* | `type: "session_meta"` | `meta.agent` |
| **vendor-entry** | *(use vendor-ext)* | *(use vendor-ext)* | *(use vendor-ext)* | *(use vendor-ext)* |

---

## Detailed Field Mappings

### user-entry

**Abstract CDDL**:
```cddl
user-entry = {
    & base-entry
    type: "user"
    content: tstr
    ? parent-id: entry-id
    ? vendor-ext: vendor-extension
}
```

**Vendor Implementations**:

#### Claude Code
```json
{
  "type": "user",
  "parentUuid": "842a3c63-...",
  "isSidechain": false,
  "userType": "external",
  "cwd": "/tmp/workspace",
  "sessionId": "bb822f3c-...",
  "version": "2.0.76",
  "gitBranch": "main",
  "message": {
    "role": "user",
    "content": "Fix the buffer overflow bug"
  },
  "uuid": "b2d9983f-...",
  "timestamp": "2026-02-07T11:22:22.649Z"
}
```

**Mapping**:
- `type: "user"` → `type: "user"` ✓
- `message.content` → `content` ✓
- `uuid` → `id` ✓
- `timestamp` → `timestamp` (RFC 3339 string) ✓
- `parentUuid` → `parent-id` ✓
- `{cwd, version, gitBranch, ...}` → `vendor-ext.data`

#### Gemini CLI
```json
{
  "sessionId": "0498cf95-...",
  "role": "user",
  "parts": [
    {"text": "Fix the buffer overflow bug"}
  ],
  "timestamp": "2026-02-07T11:22:16.345Z"
}
```

**Mapping**:
- `role: "user"` → `type: "user"` (semantic mapping)
- `parts[0].text` → `content` ✓
- `sessionId` → context from session envelope
- `timestamp` → `timestamp` (RFC 3339 string) ✓

#### Codex CLI
```json
{
  "timestamp": "2026-02-07T11:22:16.344Z",
  "type": "response_item",
  "payload": {
    "type": "message",
    "role": "user",
    "content": [
      {"type": "input_text", "text": "Fix the buffer overflow bug"}
    ]
  }
}
```

**Mapping**:
- `payload.role: "user"` → `type: "user"` ✓
- `payload.content[0].text` → `content` ✓
- `timestamp` → `timestamp` (RFC 3339 string) ✓
- Wrapper `type: "response_item"` discarded (Codex-specific)

#### OpenCode
```json
{
  "role": "user",
  "content": "Fix the buffer overflow bug",
  "timestamp": 1707307336344
}
```

**Mapping**:
- `role: "user"` → `type: "user"` ✓
- `content` → `content` ✓
- `timestamp` → `timestamp` (epoch ms → number) ✓

---

### assistant-entry

**Abstract CDDL**:
```cddl
assistant-entry = {
    & base-entry
    type: "assistant"
    content: tstr
    ? model-id: tstr
    ? stop-reason: tstr
    ? token-usage: token-usage
    ? parent-id: entry-id
    ? vendor-ext: vendor-extension
}
```

**Vendor Implementations**:

#### Claude Code
```json
{
  "type": "assistant",
  "message": {
    "model": "claude-opus-4-5-20251101",
    "role": "assistant",
    "content": [
      {"type": "text", "text": "I'll search for the vulnerable function."}
    ],
    "stop_reason": "tool_use",
    "usage": {
      "input_tokens": 7295,
      "output_tokens": 42,
      "cache_read_input_tokens": 15359
    }
  },
  "timestamp": "2026-02-07T11:22:25.609Z",
  "uuid": "29bed8aa-..."
}
```

**Mapping**:
- `type: "assistant"` → `type: "assistant"` ✓
- `message.content[0].text` → `content` (concatenate if multiple text blocks)
- `message.model` → `model-id` ✓
- `message.stop_reason` → `stop-reason` ✓
- `message.usage` → `token-usage` ✓
- `timestamp` → `timestamp` ✓

#### Gemini CLI
```json
{
  "role": "model",
  "parts": [
    {"text": "I'll search for the vulnerable function."}
  ],
  "finishReason": "STOP"
}
```

**Mapping**:
- `role: "model"` → `type: "assistant"` (semantic mapping)
- `parts[0].text` → `content` ✓
- `finishReason` → `stop-reason` (value mapping: "STOP" → "end_turn")

#### Codex CLI
```json
{
  "type": "response_item",
  "payload": {
    "type": "message",
    "role": "assistant",
    "content": [
      {"type": "text", "text": "I'll search for the vulnerable function."}
    ]
  }
}
```

**Mapping**:
- `payload.role: "assistant"` → `type: "assistant"` ✓
- `payload.content[0].text` → `content` ✓

#### OpenCode
```json
{
  "role": "assistant",
  "content": "I'll search for the vulnerable function.",
  "metadata": {
    "model": "gpt-5.2",
    "finish_reason": "stop"
  }
}
```

**Mapping**:
- `role: "assistant"` → `type: "assistant"` ✓
- `content` → `content` ✓
- `metadata.model` → `model-id` ✓
- `metadata.finish_reason` → `stop-reason` ✓

---

### tool-call-entry

**Abstract CDDL**:
```cddl
tool-call-entry = {
    & base-entry
    type: "tool-call"
    name: tstr
    tool-id: tstr
    input: vendor-extension
    ? contributor: contributor
    ? parent-id: entry-id
    ? vendor-ext: vendor-extension
}
```

**Vendor Implementations**:

#### Claude Code
```json
{
  "type": "assistant",
  "message": {
    "content": [
      {
        "type": "tool_use",
        "id": "toolu_01Fu9Rdh2qExW8yw9oAGFaYL",
        "name": "Grep",
        "input": {
          "pattern": "KerxSubTableFormat2::sanitize",
          "path": "/tmp/workspace"
        }
      }
    ]
  }
}
```

**Mapping**:
- `content[].type: "tool_use"` → `type: "tool-call"` ✓
- `content[].name` → `name` ✓
- `content[].id` → `tool-id` ✓
- `content[].input` → `input` ✓

#### Gemini CLI
```json
{
  "parts": [
    {
      "function_call": {
        "name": "code_execution",
        "args": {
          "code": "grep -r 'KerxSubTableFormat2' ."
        }
      }
    }
  ]
}
```

**Mapping**:
- `parts[].function_call` → `type: "tool-call"` ✓
- `function_call.name` → `name` ✓
- `function_call` (object) → `tool-id` (generate synthetic ID if missing)
- `function_call.args` → `input` ✓

#### Codex CLI
```json
{
  "content": [
    {
      "type": "function_call",
      "name": "shell",
      "arguments": {"command": ["grep", "-r", "KerxSubTableFormat2", "."]}
    }
  ]
}
```

**Mapping**:
- `content[].type: "function_call"` → `type: "tool-call"` ✓
- `content[].name` → `name` ✓
- `content[]` (hash of object) → `tool-id` (generate if missing)
- `content[].arguments` → `input` ✓

#### OpenCode
```json
{
  "tool_calls": [
    {
      "id": "call-001",
      "type": "function",
      "function": {
        "name": "apply_patch",
        "arguments": "{\"patch\": \"...\"}"
      }
    }
  ]
}
```

**Mapping**:
- `tool_calls[]` → `type: "tool-call"` ✓
- `tool_calls[].function.name` → `name` ✓
- `tool_calls[].id` → `tool-id` ✓
- `tool_calls[].function.arguments` (JSON string) → `input` (parse JSON) ✓

---

### tool-result-entry

**Abstract CDDL**:
```cddl
tool-result-entry = {
    & base-entry
    type: "tool-result"
    call-id: tstr
    status: tstr
    ? output: tstr
    ? error: tstr
    ? vendor-ext: vendor-extension
}
```

**Vendor Implementations**:

#### Claude Code
```json
{
  "type": "user",
  "message": {
    "role": "user",
    "content": [
      {
        "tool_use_id": "toolu_01Fu9Rdh2qExW8yw9oAGFaYL",
        "type": "tool_result",
        "content": "No files found"
      }
    ]
  },
  "toolUseResult": {
    "mode": "files_with_matches",
    "filenames": [],
    "numFiles": 0
  }
}
```

**Mapping**:
- `content[].type: "tool_result"` → `type: "tool-result"` ✓
- `content[].tool_use_id` → `call-id` ✓
- `content[].content` → `output` ✓
- Status inferred from presence of error vs success content

#### Gemini CLI
```json
{
  "parts": [
    {
      "function_response": {
        "name": "code_execution",
        "response": {
          "output": "No files found",
          "outcome": "success"
        }
      }
    }
  ]
}
```

**Mapping**:
- `parts[].function_response` → `type: "tool-result"` ✓
- `function_response.name` → link to prior `function_call` to get `call-id`
- `response.output` → `output` ✓
- `response.outcome` → `status` ✓

#### Codex CLI
```json
{
  "content": [
    {
      "type": "function_result",
      "call_id": "call-001",
      "result": "No files found"
    }
  ]
}
```

**Mapping**:
- `content[].type: "function_result"` → `type: "tool-result"` ✓
- `content[].call_id` → `call-id` ✓
- `content[].result` → `output` ✓

#### OpenCode
```json
{
  "tool_responses": [
    {
      "tool_call_id": "call-001",
      "output": "No files found",
      "status": "success"
    }
  ]
}
```

**Mapping**:
- `tool_responses[]` → `type: "tool-result"` ✓
- `tool_responses[].tool_call_id` → `call-id` ✓
- `tool_responses[].output` → `output` ✓
- `tool_responses[].status` → `status` ✓

---

### reasoning-entry

**Abstract CDDL**:
```cddl
reasoning-entry = {
    & base-entry
    type: "reasoning"
    content: tstr
    ? encrypted: bool
    ? parent-id: entry-id
    ? vendor-ext: vendor-extension
}
```

**Vendor Implementations**:

#### Claude Code
```json
{
  "message": {
    "content": [
      {
        "type": "thinking",
        "thinking": "I need to find the file containing KerxSubTableFormat2..."
      }
    ]
  }
}
```

**Mapping**:
- `content[].type: "thinking"` → `type: "reasoning"` ✓
- `content[].thinking` → `content` ✓

#### Gemini CLI
**Not present** - Gemini does not expose reasoning traces

#### Codex CLI
```json
{
  "content": [
    {
      "type": "reasoning",
      "text": "I need to find the file containing KerxSubTableFormat2..."
    }
  ]
}
```

**Mapping**:
- `content[].type: "reasoning"` → `type: "reasoning"` ✓
- `content[].text` → `content` ✓

#### OpenCode
```json
{
  "metadata": {
    "thinking": "I need to find the file containing KerxSubTableFormat2..."
  }
}
```

**Mapping**:
- `metadata.thinking` → extract as separate `reasoning-entry` ✓
- `metadata.thinking` → `content` ✓

---

### system-event-entry

**Abstract CDDL**:
```cddl
system-event-entry = {
    & base-entry
    type: "system-event"
    event-type: tstr
    ? description: tstr
    ? vendor-ext: vendor-extension
}
```

**Vendor Implementations**:

#### Claude Code
```json
{
  "type": "queue-operation",
  "operation": "dequeue",
  "timestamp": "2026-02-07T11:22:22.551Z",
  "sessionId": "3c3b4e88-..."
}
```

**Mapping**:
- `type: "queue-operation"` → `type: "system-event"` ✓
- `operation` → `event-type` ✓
- `{operation, sessionId}` → `vendor-ext.data`

#### Gemini CLI
**Not present** - Gemini has no system event records

#### Codex CLI
```json
{
  "type": "session_meta",
  "payload": {
    "id": "019c37d6-...",
    "originator": "codex_exec",
    "cli_version": "0.91.0",
    "model_provider": "openai"
  }
}
```

**Mapping**:
- `type: "session_meta"` → `type: "system-event"` ✓
- `"session_meta"` → `event-type: "session-start"` (semantic mapping)
- `payload` → `vendor-ext.data` ✓

#### OpenCode
```json
{
  "meta": {
    "agent": "opencode",
    "date": "2026-02-07"
  }
}
```

**Mapping**:
- `meta` → `type: "system-event"` ✓
- `"agent"` → `event-type: "agent-identification"` ✓
- `meta` → `vendor-ext.data` ✓

---

## Conversion Statistics

| Metric | Claude Code | Gemini CLI | Codex CLI | OpenCode |
|:-------|:------------|:-----------|:----------|:---------|
| **Entry types supported** | 6/7 | 4/7 | 6/7 | 6/7 |
| **Native tool calls** | ✓ | ✓ | ✓ | ✓ |
| **Native tool results** | ✓ | ✓ | ✓ | ✓ |
| **Reasoning traces** | ✓ (thinking) | ✗ | ✓ (reasoning) | ✓ (metadata) |
| **System events** | ✓ (queue ops) | ✗ | ✓ (session_meta) | ✓ (meta) |
| **Timestamp format** | RFC 3339 | RFC 3339 | RFC 3339 | Epoch ms |
| **Session ID** | UUID v4 | UUID | UUID v7 | SHA-256 |
| **Parent tracking** | ✓ (parentUuid) | ✗ | ✗ | ✗ |

---

## Coverage Analysis

### Field Coverage Across Agents

| Field | Claude | Gemini | Codex | OpenCode | CDDL Status |
|:------|:-------|:-------|:------|:---------|:------------|
| `timestamp` | ✓ | ✓ | ✓ | ✓ | **REQUIRED** (4/4) |
| `type`/`role` | ✓ | ✓ | ✓ | ✓ | **REQUIRED** (4/4) |
| `content` | ✓ | ✓ | ✓ | ✓ | **REQUIRED** (4/4) |
| `model-id` | ✓ | ✓ | ✓ | ✓ | **OPTIONAL** (4/4 present) |
| `tool-id` | ✓ | ✗* | ✗* | ✓ | **REQUIRED** (2/4 explicit) |
| `parent-id` | ✓ | ✗ | ✗ | ✗ | **OPTIONAL** (1/4) |
| `reasoning` | ✓ | ✗ | ✓ | ✓ | **OPTIONAL** (3/4) |
| `system-events` | ✓ | ✗ | ✓ | ✓ | **OPTIONAL** (3/4) |

\* Gemini and Codex lack explicit tool IDs but can generate synthetic ones from call order

---

## Derivation Algorithm

For each trace file:

1. **Parse JSON/JSONL**: Load vendor format
2. **Identify entry type**: Map vendor `type`/`role` to abstract type
3. **Extract common fields**: `timestamp`, `content`, `model-id`
4. **Map tool calls**: Extract `name`, `tool-id`, `input`
5. **Link tool results**: Match `call-id` to prior `tool-id`
6. **Extract reasoning**: Detect `thinking`/`reasoning`/`metadata.thinking`
7. **Preserve vendor data**: Store unmapped fields in `vendor-ext`

**Output**: Abstract `verifiable-agent-record` conformant to CDDL

---

## References

- CDDL Schema: `vendor/specs/draft-birkholz-verifiable-agent-conversations/agent-conversation.cddl`
- Evidence: `bench/runs/arvo-250iq/run-2026-02-07/` (221 traces)
- RLM Extraction: `.quint/rlm-extractions/cddl-unification.md`
- Quint DRR: `.quint/decisions/DRR-cddl-unification.md`
