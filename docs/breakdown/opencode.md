# OpenCode — Translation Breakdown

Native format: concatenated pretty-printed JSON objects. First object is session header.

## Native Session Schema

```json
// Object 1: session header
{
  "id": "16a647c5082b1e9ae946a35977ada01660f5668b",
  "worktree": "/mnt/github/simdutf-XOR-simdutf",
  "vcs": "git",
  "sandboxes": ["/tmp/CRs5SvG4"],
  "time": {
    "created": 1770847186989,
    "updated": 1770847186990
  }
}

// Object 2: share info (optional)
{
  "id": "aGeSaH5Z",
  "secret": "<REDACTED>",
  "url": "https://opncd.ai/share/aGeSaH5Z"
}

// Object: text part (role determined by parent message via messageID lookup)
// This example belongs to a user message (messageID → role: "user")
{
  "id": "prt_c4eb7b51a001nNlQuDojGF6KXs",
  "sessionID": "ses_3b1484cbcffeuvlIbiaGeSaH5Z",
  "messageID": "msg_c4eb7b519001eei876ChGRp6aL",
  "type": "text",
  "text": "Fix the heap-buffer-overflow in the UTF-8 converter"
}

// Object: step-start (marks beginning of an assistant turn)
{
  "id": "prt_c4eb7b799001dviwglkkdeDi4B",
  "sessionID": "ses_3b1484cbcffeuvlIbiaGeSaH5Z",
  "messageID": "msg_c4eb7b543001KTLZ8jxM3yfkEt",
  "type": "step-start",
  "snapshot": "dccfdca0f2ce00791e1c3ca2a482baaf4fee18ed"
}

// Object: reasoning
{
  "id": "prt_c4eb7b7dd001gFdMTQGiiUKFPS",
  "sessionID": "ses_3b1484cbcffeuvlIbiaGeSaH5Z",
  "messageID": "msg_c4eb7b543001KTLZ8jxM3yfkEt",
  "type": "reasoning",
  "text": "Planning tool usage...",
  "metadata": {
    "openai": {
      "itemId": "rs_09653cae5528a06b...",
      "reasoningEncryptedContent": "gAAAAABpjPvdJYo4umZl..."
    }
  },
  "time": {
    "start": 1770847188957,
    "end": 1770847197623
  }
}

// Object: tool (fused call + result)
{
  "id": "prt_c4eb7d9fa0010rV16Xk7aOkVsF",
  "sessionID": "ses_3b1484cbcffeuvlIbiaGeSaH5Z",
  "messageID": "msg_c4eb7b543001KTLZ8jxM3yfkEt",
  "type": "tool",
  "callID": "call_KEXdpGvQrjEw0wSnSxTCZUoj",
  "tool": "grep",
  "state": {
    "status": "completed",
    "input": {
      "pattern": "westmere::implementation",
      "include": "*.{h,hpp,cc,cpp,cxx,ipp,inl}"
    },
    "output": "Found 2 matches\n/tmp/CRs5SvG4/src/implementation.cpp:...",
    "title": "westmere::implementation",
    "metadata": {
      "matches": 2,
      "truncated": false
    },
    "time": {
      "start": 1770847197690,
      "end": 1770847197693
    }
  },
  "metadata": {
    "openai": {
      "itemId": "fc_09653cae5528a06b..."
    }
  }
}

// Object: step-finish (marks end of an assistant turn)
{
  "id": "prt_c4eb7da08001FQKGxKBjSINkVm",
  "sessionID": "ses_3b1484cbcffeuvlIbiaGeSaH5Z",
  "messageID": "msg_c4eb7b543001KTLZ8jxM3yfkEt",
  "type": "step-finish",
  "reason": "tool-calls",
  "snapshot": "dccfdca0f2ce00791e1c3ca2a482baaf4fee18ed",
  "cost": 0.03233125,
  "tokens": {
    "input": 10803,
    "output": 538,
    "reasoning": 421,
    "cache": { "read": 0, "write": 0 }
  }
}

// Object: role message (assistant summary for a turn)
{
  "id": "msg_c4eb7b543001KTLZ8jxM3yfkEt",
  "sessionID": "ses_3b1484cbcffeuvlIbiaGeSaH5Z",
  "role": "assistant",
  "time": {
    "created": 1770847188291,
    "completed": 1770847197750
  },
  "parentID": "msg_c4eb7b519001eei876ChGRp6aL",
  "modelID": "gpt-5.2",
  "providerID": "openai",
  "mode": "build",
  "agent": "build",
  "path": {
    "cwd": "/tmp/CRs5SvG4",
    "root": "/tmp/CRs5SvG4"
  },
  "cost": 0.03233125,
  "tokens": {
    "input": 10803,
    "output": 538,
    "reasoning": 421,
    "cache": { "read": 0, "write": 0 }
  },
  "finish": "tool-calls"
}
```

## Direct matches

- `id` → `id`

## Renames

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

## Structural extraction

- **SPLIT**: One `type: "tool"` object → TWO entries (`tool-call` + `tool-result`)
- Type mapping:
  - `"text"` → `"user"` or `"assistant"` (determined by looking up `messageID` against
    role-message objects; text parts under `role: "user"` messages map to `"user"`)
  - `"tool"` → `"tool-call"` + `"tool-result"`
  - `"patch"` → `"tool-result"` (`diff` → `output`, `status` hardcoded to `"success"`)
  - `"step-start"` / `"step-finish"` → `"system-event"`
  - `"reasoning"` → `"reasoning"` (direct)

## Dropped fields

Session header: `id` (worktree hash), `vcs`, `sandboxes`, `time.updated` (extracted: `worktree` → cwd,
`time.created` → start). Share-info object (optional; `id`, `secret`, `url`) dropped entirely.
Session summary object (optional; `id`, `slug`, `version`, `projectID`, `directory`, `title`,
`permission`, `share`, `summary`, `time`) dropped entirely.

Per-entry: `sessionID`, `messageID`, `state.title`, `state.metadata`, `metadata.openai`,
`id`/`snapshot`/`reason`/`cost`/`tokens` (from step-start/step-finish), `time.start`/`time.end`
(from reasoning and text objects), `id`/`modelID`/`providerID`/`cost`/`tokens`/`finish`
(from role objects; `parentID` renamed to `parent-id`), nested `model` object on user role messages (contains `providerID`,
`modelID` — extracted to metadata), `summary` (with diffs), `time.completed`, `path`,
`mode`, `agent`.
On patch objects: `hash`, `files` (parser reads `diff` which is absent → `output` is `""`).

## Fabricated

- `cli-name: "opencode"` hardcoded
- Record wrapper
