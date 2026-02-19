# Cursor — Translation Breakdown

Native format: bare JSONL `{role, message}`. The most minimal format.

## Native Session Schema

```json
// Line: user message
{
  "role": "user",
  "message": {
    "content": [
      {
        "type": "text",
        "text": "Fix the heap-buffer-overflow in the OGR filesystem fuzzer"
      }
    ]
  }
}

// Line: assistant message (text only)
{
  "role": "assistant",
  "message": {
    "content": [
      {
        "type": "text",
        "text": "I'll analyze the crash report and find the root cause..."
      }
    ]
  }
}
```

## Direct matches

- Nothing maps directly

## Renames

- `role` → `type` (rename field; catch-all: `"user"` stays `"user"`, all other roles map to `"assistant"`)
- `message.content` → `content` (un-nest)

## Structural extraction

- None

## Dropped fields

- None (there's nothing to drop)

## Fabricated

- `session-id`: generated UUID (Cursor has no session identity)
- `model-id`: "unknown" (no model info in export)
- `model-provider`: "unknown" (no provider info in export)
- `cli-name: "cursor"` hardcoded
- Record wrapper

**Note:** Cursor exports also lack all timestamps and entry IDs — these fields
are simply absent rather than fabricated.
