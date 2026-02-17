# Claude Code — Translation Breakdown

Native format: JSONL, one event per line. Each line carries session metadata redundantly.

## Native Session Schema

```json
// Line type: queue-operation (session lifecycle)
{
  "type": "queue-operation",
  "operation": "dequeue",
  "timestamp": "2026-02-10T17:27:10.484Z",
  "sessionId": "0574c517-2408-4a20-8808-7626fd961640"
}

// Line type: user message
{
  "parentUuid": null,
  "isSidechain": false,
  "userType": "external",
  "cwd": "/tmp/v9azOZts",
  "sessionId": "0574c517-2408-4a20-8808-7626fd961640",
  "version": "2.1.34",
  "gitBranch": "main",
  "type": "user",
  "message": {
    "role": "user",
    "content": "Fix the bug in main.py"
  },
  "uuid": "7e6c5e25-5eb4-4a75-99e3-6b8498f5ee0a",
  "timestamp": "2026-02-10T17:27:10.587Z",
  "permissionMode": "bypassPermissions"
}

// Line type: assistant message (text + tool_use content blocks)
{
  "parentUuid": "7e6c5e25-5eb4-4a75-99e3-6b8498f5ee0a",
  "isSidechain": false,
  "userType": "external",
  "cwd": "/tmp/v9azOZts",
  "sessionId": "0574c517-2408-4a20-8808-7626fd961640",
  "version": "2.1.34",
  "gitBranch": "main",
  "message": {
    "model": "claude-opus-4-6",
    "id": "msg_01K9HuWngewdT879ZLkzYDkf",
    "type": "message",
    "role": "assistant",
    "content": [
      {
        "type": "text",
        "text": "I'll analyze this crash and find the root cause."
      },
      {
        "type": "tool_use",
        "id": "toolu_01D3fj28UAco6kEdZJSNnKf7",
        "name": "Bash",
        "input": {
          "command": "git log --oneline -20"
        }
      },
      {
        "type": "thinking",
        "thinking": "Let me examine the code..."
      }
    ],
    "stop_reason": null,
    "stop_sequence": null,
    "usage": {
      "input_tokens": 3,
      "cache_creation_input_tokens": 5559,
      "cache_read_input_tokens": 15360,
      "output_tokens": 2
    }
  },
  "requestId": "req_011CXznGJUhydqGc2YJRagGV",
  "type": "assistant",
  "uuid": "ad554ee9-4bf4-4373-95a3-1cef1ac70b76",
  "timestamp": "2026-02-10T17:27:14.496Z"
}

// Line type: tool_result (in a user-type line)
{
  "parentUuid": "a8f08f4d-a49e-4264-aea3-109f4b4b8b5d",
  "isSidechain": false,
  "userType": "external",
  "cwd": "/tmp/v9azOZts",
  "sessionId": "0574c517-2408-4a20-8808-7626fd961640",
  "version": "2.1.34",
  "gitBranch": "main",
  "type": "user",
  "message": {
    "role": "user",
    "content": [
      {
        "tool_use_id": "toolu_01P3KW6HyP6xLEw62Ajzx3No",
        "type": "tool_result",
        "content": "README.md\nsrc/\ntests/\n",
        "is_error": false
      }
    ]
  },
  "uuid": "d6ac1129-0c22-402e-aebb-6ed1b74747ab",
  "timestamp": "2026-02-10T17:27:24.950Z",
  "toolUseResult": {
    "stdout": "README.md\nsrc/\ntests/\n",
    "stderr": "",
    "interrupted": false,
    "isImage": false
  },
  "sourceToolAssistantUUID": "d2601b99-ef44-4c96-bc47-ffab9fcf1afc"
}
```

## Direct matches (zero transformation)

- `timestamp` → `timestamp`

## Renames

- `uuid` → `id`
- `message.content` → `content` (un-nest from `message` wrapper)
- `message.role` → `type` (rename field + un-nest; parser reads `message.role`, not line-level `type`)

## Structural extraction

- `type: "queue-operation"` → entry type `"system-event"` with `event-type: "queue-operation"`
- One JSONL line with `message.content: [{type: "tool_use", ...}, {type: "text", ...}, {type: "thinking", ...}]`
  → parent entry with `content: <native array>` + `children` array of typed entries
- Each `tool_use` child: `id` → `call-id`, `name` → `name`, `input` → `input`, type `"tool_use"` → `"tool-call"`
- Each `tool_result` child (in user messages): `tool_use_id` → `call-id`, `content` → `output`,
  `is_error` → `status`, type `"tool_result"` → `"tool-result"`
- Each `thinking` child: `thinking` → `content`, type `"thinking"` → `"reasoning"`

## Dropped fields

Metadata-extracted (per-entry → record wrapper): `sessionId` → `session.session-id`,
`cwd` → `session.environment.working-dir`, `version` → `agent-meta.cli-version`,
`message.model` → `agent-meta.model-id`. Also extracted but not emitted:
`gitBranch` → `meta["branch"]` (collected by parser but `wrap_record` has no output mapping).

Per-entry dropped: line-level `type` (e.g., `"user"`, `"assistant"` — ignored; parser uses
`message.role` instead), `parentUuid`, `isSidechain`, `userType`, `slug`, `permissionMode`,
`requestId`, `message.id`, `message.type`, `message.usage`, `message.stop_reason`,
`message.stop_sequence`, `toolUseResult`, `sourceToolAssistantUUID`.
On queue-operation lines: `operation` (e.g., `"dequeue"`) is not emitted.

## Fabricated

- Provider inferred from model prefix ("claude" → "anthropic")
- `cli-name: "claude-code"` hardcoded
- Record wrapper (verifiable-agent-record envelope; includes conditional `agent-meta.models`
  list when multiple models observed)
