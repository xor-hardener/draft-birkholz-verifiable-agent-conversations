# Codex CLI — Translation Breakdown

Native format: JSONL with two-level envelope `{timestamp, type, payload}`.

## Native Session Schema

```json
// Line type: session_meta (session header)
{
  "timestamp": "2026-02-10T17:24:23.778Z",
  "type": "session_meta",
  "payload": {
    "id": "019c4895-344c-79b1-83b2-00413ff7f9a9",
    "timestamp": "2026-02-10T17:24:23.756Z",
    "cwd": "/tmp/pBuH0CoJ",
    "originator": "codex_exec",
    "cli_version": "0.98.0",
    "source": "exec",
    "model_provider": "openai",
    "base_instructions": {
      "text": "You are GPT-5.2 running in the Codex CLI..."
    },
    "git": {
      "commit_hash": "6be7aee18c5b8e639103df951d0d277f4b46f902",
      "branch": "main",
      "repository_url": "https://github.com/user/repo.git"
    }
  }
}

// Line type: response_item — developer/user message
{
  "timestamp": "2026-02-10T17:24:23.778Z",
  "type": "response_item",
  "payload": {
    "type": "message",
    "role": "user",
    "content": [
      {
        "type": "input_text",
        "text": "Fix the heap-buffer-overflow in the tokenizer"
      }
    ]
  }
}

// Line type: event_msg — user message echo
{
  "timestamp": "2026-02-10T17:24:23.781Z",
  "type": "event_msg",
  "payload": {
    "type": "user_message",
    "message": "Fix the heap-buffer-overflow in the tokenizer",
    "images": [],
    "local_images": [],
    "text_elements": []
  }
}

// Line type: response_item — reasoning
{
  "timestamp": "2026-02-10T17:24:37.736Z",
  "type": "response_item",
  "payload": {
    "type": "reasoning",
    "summary": [
      {
        "type": "summary_text",
        "text": "Investigating a buffer overflow..."
      }
    ],
    "content": null,
    "encrypted_content": "gAAAAABpi2nV6m8B..."
  }
}

// Line type: response_item — function_call (tool invocation)
{
  "timestamp": "2026-02-10T17:24:37.946Z",
  "type": "response_item",
  "payload": {
    "type": "function_call",
    "name": "exec_command",
    "arguments": "{\"cmd\":\"cd /tmp/pBuH0CoJ && ls\"}",
    "call_id": "call_HDE6oo4p5xCNAAmI0YHKxq2Y"
  }
}

// Line type: response_item — function_call_output (tool result)
{
  "timestamp": "2026-02-10T17:24:38.048Z",
  "type": "response_item",
  "payload": {
    "type": "function_call_output",
    "call_id": "call_HDE6oo4p5xCNAAmI0YHKxq2Y",
    "output": "Chunk ID: a739b0\nWall time: 0.0512 seconds\nProcess exited with code 0\nOutput:\nDoc\nGrammar\nInclude\n"
  }
}

// Line type: event_msg — reasoning echo
{
  "timestamp": "2026-02-10T17:24:37.736Z",
  "type": "event_msg",
  "payload": {
    "type": "agent_reasoning",
    "text": "Investigating a buffer overflow..."
  }
}

// Line type: event_msg — token_count
{
  "timestamp": "2026-02-10T17:24:37.960Z",
  "type": "event_msg",
  "payload": {
    "type": "token_count",
    "info": {
      "total_token_usage": {
        "input_tokens": 13410,
        "cached_input_tokens": 10368,
        "output_tokens": 670,
        "reasoning_output_tokens": 640,
        "total_tokens": 14080
      },
      "model_context_window": 258400
    },
    "rate_limits": { /* per-model rate limit info */ }
  }
}

// Line type: turn_context (per-turn metadata, repeated)
{
  "timestamp": "2026-02-10T17:24:23.804Z",
  "type": "turn_context",
  "payload": {
    "cwd": "/tmp/pBuH0CoJ",
    "approval_policy": "never",
    "sandbox_policy": { "type": "danger-full-access" },
    "model": "gpt-5.2",
    "personality": "pragmatic",
    "effort": "xhigh",
    "summary": "auto",
    "collaboration_mode": { "mode": "default", "settings": { "model": "gpt-5.2", "reasoning_effort": "xhigh", "developer_instructions": null } },
    "user_instructions": "",
    "truncation_policy": { "mode": "bytes", "limit": 10000 }
  }
}
```

## Direct matches

- `timestamp` → `timestamp` (from outer envelope)

## Renames

- `payload.arguments` → `input` (function_call); `payload.input` → `input` (custom_tool_call);
  `payload.action` → `input` (web_search_call)
- `payload.call_id` → `call-id`
- `payload.name` → `name`
- `payload.output` → `output`
- `payload.summary` → `content` (reasoning; list of `summary_text` joined to string)
- `payload.encrypted_content` → `encrypted` (reasoning)
- `payload.content` → `content` (response_item message; un-nest from payload)
- `payload.message` → `content` (event_msg user_message/agent_message)
- `payload.text` → `content` (event_msg agent_reasoning)

## Structural extraction

- Two-level envelope unwrap: `{timestamp, type: "response_item", payload: {type: "function_call", ...}}`
  → `{type: "tool-call", timestamp, ...}`
- Three-level type derivation for messages: outer `type` + `payload.type` + `payload.role` → single `type`
- Type mapping:
  - `"function_call"` → `"tool-call"`
  - `"function_call_output"` → `"tool-result"`
  - `"web_search_call"` → `"tool-call"` (name="web_search")
  - `"custom_tool_call"` → `"tool-call"`
  - `"custom_tool_call_output"` → `"tool-result"`
  - `"reasoning"` → `"reasoning"` (direct)
  - `"message"+"user"`/`"developer"` → `"user"`
  - `"message"+"assistant"` → `"assistant"`
- `event_msg` subtypes also emitted (3 of 4 duplicate `response_item` entries):
  - `"agent_reasoning"` → `"reasoning"` (duplicates `response_item` reasoning)
  - `"user_message"` → `"user"` (duplicates `response_item` message+user)
  - `"agent_message"` → `"assistant"` (duplicates `response_item` message+assistant)
  - `"token_count"` → `"system-event"` (unique; no `response_item` equivalent)

## Dropped fields

Metadata-extracted (→ record wrapper): `session_meta` → `payload.id` (session-id),
`payload.cwd` (working-dir), `payload.cli_version`, `payload.model_provider`;
`turn_context` → `payload.model` (fallback source, but always used because `session_meta` lacks `model` field).
Also extracted but not emitted: `payload.git.branch` → `meta["branch"]` (collected by
parser but `wrap_record` has no output mapping).

Per-entry dropped: outer `type`, `payload.type`, `payload.role`, `payload.content` (on
reasoning — always `null`; would contain unencrypted reasoning if available, but models
with encrypted reasoning never populate it).

Silently dropped from `session_meta`: `payload.originator`, `payload.source`,
`payload.timestamp`, `payload.base_instructions`, `payload.git.commit_hash`,
`payload.git.repository_url`.

Silently dropped from `turn_context`: `cwd`, `approval_policy`, `sandbox_policy`,
`personality`, `effort`, `summary`, `collaboration_mode`, `user_instructions`,
`truncation_policy`.

Silently dropped from `event_msg`: `payload.images`, `payload.local_images`,
`payload.text_elements`, `payload.info` (token_count details), `payload.rate_limits`
(token_count).

Silently dropped from `response_item`: `payload.status` on `web_search_call` and
`custom_tool_call` entries.

## Fabricated

- `cli-name: "codex-cli"` hardcoded
- Model extracted from `turn_context` (a different JSONL line than `session_meta`)
- Record wrapper
