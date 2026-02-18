# Gemini CLI — Translation Breakdown

Native format: single JSON object with `messages[]` array. Closest to CDDL of all agents.

## Native Session Schema

```json
// Top-level session wrapper
{
  "sessionId": "08c1f87b-ff3b-48ff-9d6f-524e2bbf89b9",
  "projectHash": "79b1946573b55334fbdb6d41866f54789477fe12ecee2ed364ceea086a02ef82",
  "startTime": "2026-02-10T17:27:58.644Z",
  "lastUpdated": "2026-02-10T17:35:55.624Z",
  "messages": [ /* ... */ ]
}

// User message
{
  "id": "48341a07-47c1-4340-b4c4-088399a45aba",
  "timestamp": "2026-02-10T17:27:58.644Z",
  "type": "user",
  "content": "Fix the bug in frame.c"
}

// Assistant message with tool calls + thoughts
{
  "id": "89bea036-72ba-40d8-bb49-7b47b8aba537",
  "timestamp": "2026-02-10T17:28:05.832Z",
  "type": "gemini",
  "content": "",
  "toolCalls": [
    {
      "id": "search_file_content-1770744484519-a47bac6cd4faf",
      "name": "search_file_content",
      "args": {
        "pattern": "blosc_getitem"
      },
      "result": [
        {
          "functionResponse": {
            "id": "search_file_content-1770744484519-a47bac6cd4faf",
            "name": "search_file_content",
            "response": {
              "output": "Found 22 matches for pattern \"blosc_getitem\"..."
            }
          }
        }
      ],
      "status": "success",
      "timestamp": "2026-02-10T17:28:05.832Z",
      "resultDisplay": "Found 22 matches",
      "displayName": "SearchText",
      "description": "FAST, optimized search powered by `ripgrep`...",
      "renderOutputAsMarkdown": true
    }
  ],
  "thoughts": [
    {
      "subject": "Investigating the Blosc2 Bug",
      "description": "I'm currently focusing on the `blosc_getitem` function...",
      "timestamp": "2026-02-10T17:28:03.479Z"
    }
  ],
  "model": "gemini-3-pro-preview",
  "tokens": {
    "input": 13283,
    "output": 21,
    "cached": 8147,
    "thoughts": 248,
    "tool": 0,
    "total": 13552
  }
}

// Assistant message with text content + thoughts
{
  "id": "b88730f3-b4f7-4652-99dd-dff5a1140d69",
  "timestamp": "2026-02-10T17:35:55.621Z",
  "type": "gemini",
  "content": "I have fixed the issue where `get_coffset` in `blosc/frame.c` was...",
  "thoughts": [
    {
      "subject": "Concluding the Problem",
      "description": "I've finalized the fix for `get_coffset`...",
      "timestamp": "2026-02-10T17:35:40.269Z"
    },
    {
      "subject": "Assessing the Performance Impact",
      "description": "I've reproduced the issue and verified...",
      "timestamp": "2026-02-10T17:35:43.427Z"
    }
  ],
  "model": "gemini-3-pro-preview",
  "tokens": {
    "input": 154032,
    "output": 1282,
    "cached": 142880,
    "thoughts": 10978,
    "tool": 0,
    "total": 166292
  }
}
```

## Direct matches

- `type: "user"` → `type: "user"`
- `timestamp` → `timestamp`
- `id` → `id`
- `content` → `content` (already a string)

## Renames

- `type: "gemini"` → `type: "assistant"` (also `type: "human"` → `type: "user"`)
- `model` → `model-id`

## Metadata extraction (top-level → record wrapper)

- `sessionId` → `session.session-id`
- `startTime` → `session.session-start` / `record.created`

## Structural extraction

- `toolCalls[]` array on the message → children:
  - `name` → `name` (direct)
  - `args` → `input` (rename)
  - `id` → `call-id` (rename)
  - `timestamp` → `timestamp` (direct, with fallback to parent message timestamp)
  - `result` → `output` (raw `result` array passed through as-is, no deep extraction)
  - `status` → `status` (direct)
  - Each toolCall produces a `"tool-call"` child, and a `"tool-result"` child when `result` is not null
- `thoughts[]` array → children:
  - `description` → `content` (rename)
  - `subject` → `subject` (direct)
  - Each thought produces child `"reasoning"`

## Dropped fields

`projectHash`, `lastUpdated`, `toolCalls[].resultDisplay`, `toolCalls[].displayName`,
`toolCalls[].description`, `toolCalls[].renderOutputAsMarkdown`, `tokens`,
`thoughts[].timestamp`

## Fabricated

- Provider inferred from "gemini" prefix
- `cli-name: "gemini-cli"` hardcoded
- Record wrapper
