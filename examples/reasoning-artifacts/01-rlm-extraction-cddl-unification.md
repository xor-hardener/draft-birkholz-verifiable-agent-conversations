# RLM Extraction: CDDL Unification Bridge Analysis

**Date**: 2026-02-09
**Source**: CVE Bench traces from `bench/runs/arvo-250iq/run-2026-02-07/`
**Sample**: harfbuzz-XOR-harfbuzz-ID-11033 (same CVE, 4 agents)

---

## 1. The Bridge: Tool-Call → File Attribution

The critical question for CDDL unification is whether Henk's file attribution
(`agent-convo-record.files[].conversations[].ranges[]`) can be mechanically
derived from XOR's session-trace entries. We traced the same CVE fix across
all 4 agent formats.

### 1.1 Claude Code (Edit Tool)

**Chain**: `assistant-entry` → `tool_use` block → Edit tool → `tool_result` block

```json
{
  "type": "tool_use",
  "id": "toolu_01Vgmdt1XDevUgeMsj9q2d4B",
  "name": "Edit",
  "input": {
    "file_path": "/tmp/ezlvnDGN/src/hb-aat-layout-kerx-table.hh",
    "old_string": "inline bool sanitize ...",
    "new_string": "inline bool sanitize ...(modified)"
  }
}
```

**Derivable fields for Henk's schema**:
- `file.path`: YES — `input.file_path` (absolute, needs repo-root stripping)
- `range.start_line`: PARTIALLY — must diff `old_string` against file to find line
- `range.end_line`: PARTIALLY — same, derived from old_string length
- `range.content_hash`: NO — requires reading final file state after edit
- `conversation.contributor.model_id`: YES — `message.model` on same entry
- `conversation.contributor.type`: YES — always "ai" for assistant tool_use

**Missing from Claude trace**:
- No unified diff (old_string/new_string is a semantic diff, not line-numbered)
- No `before`/`after` full file content
- No `additions`/`deletions` count

### 1.2 Gemini CLI (replace Tool)

**Chain**: `gemini` message → `toolCalls[]` → replace tool → `result[]`

```json
{
  "name": "replace",
  "args": {
    "file_path": "/tmp/5iLthORw/src/hb-aat-layout-kerx-table.hh",
    "old_string": "...",
    "new_string": "...",
    "instruction": "Add c->check_struct(this)...",
    "expected_replacements": 1
  },
  "result": [{"functionResponse": {"response": {"output": "Successfully modified file..."}}}],
  "status": "success"
}
```

**Derivable fields for Henk's schema**:
- `file.path`: YES — `args.file_path`
- `range.start_line`: PARTIALLY — same old_string matching issue
- `range.content_hash`: NO — not available
- `contributor.model_id`: YES — from `messages[].model`
- `contributor.type`: YES — always "ai"

**Extra**: `instruction` field gives human-readable intent (unique to Gemini).

### 1.3 Codex CLI (apply_patch / shell)

**Chain**: `response_item` → `function_call` → apply_patch/shell → `function_call_output`

Codex uses `apply_patch` with a custom patch format:
```
*** Begin Patch
*** Update File: src/hb-aat-layout-kerx-table.hh
@@
   TRACE_SANITIZE (this);
-    return_trace (likely (rowWidth.sanitize (c) &&
+    return_trace (likely (c->check_struct (this) &&
*** End Patch
```

**Derivable fields for Henk's schema**:
- `file.path`: YES — from `*** Update File:` line (already relative!)
- `range.start_line`: PARTIALLY — context lines allow matching, but no explicit line numbers
- `range.content_hash`: NO
- `contributor.model_id`: YES — from `turn_context.model`
- `contributor.type`: YES — always "ai"

**Note**: Codex ALSO tries `shell` with `apply_patch` command, showing format instability.

### 1.4 OpenCode (apply_patch Tool with Rich Metadata)

**Chain**: `tool` entry → `apply_patch` → `state.output` + `state.metadata`

```json
{
  "type": "tool",
  "callID": "call_oCcXsqWWOkUMMnzYnNI4A5sI",
  "tool": "apply_patch",
  "state": {
    "input": {"patchText": "*** Begin Patch\n*** Update File: ..."},
    "output": "Success. Updated the following files:\nM src/hb-aat-layout-kerx-table.hh",
    "metadata": {
      "diff": "Index: .../src/hb-aat-layout-kerx-table.hh\n...\n@@ -86,9 +86,10 @@\n...",
      "files": [{
        "filePath": "/tmp/T2gUuxra/src/hb-aat-layout-kerx-table.hh",
        "relativePath": "src/hb-aat-layout-kerx-table.hh",
        "type": "update",
        "diff": "...(unified diff with @@ line numbers)...",
        "before": "(full file content before edit)",
        "after": "(full file content after edit)",
        "additions": 3,
        "deletions": 2
      }]
    }
  }
}
```

**Derivable fields for Henk's schema**:
- `file.path`: YES — `metadata.files[].relativePath` (already relative!)
- `range.start_line`: YES — from unified diff `@@ -86,9 +86,10 @@`
- `range.end_line`: YES — computed from start + hunk size
- `range.content_hash`: POSSIBLE — `after` content available for hashing
- `contributor.model_id`: YES — from message `modelID`
- `contributor.type`: YES — always "ai"
- `additions`/`deletions`: YES — explicit counts

**OpenCode is the RICHEST format for file attribution**. It provides everything
Henk's schema needs: relative path, unified diff with line numbers,
before/after content, and addition/deletion counts.

---

## 2. Derivability Matrix

| Henk Field | Claude | Gemini | Codex | OpenCode | Derivable? |
|------------|--------|--------|-------|----------|------------|
| `file.path` | YES (abs) | YES (abs) | YES (rel) | YES (rel+abs) | **4/4** |
| `range.start_line` | PARTIAL | PARTIAL | PARTIAL | YES (diff) | **1/4 direct, 3/4 with effort** |
| `range.end_line` | PARTIAL | PARTIAL | PARTIAL | YES (diff) | **1/4 direct, 3/4 with effort** |
| `range.content_hash` | NO | NO | NO | POSSIBLE | **0-1/4** |
| `contributor.type` | YES | YES | YES | YES | **4/4** |
| `contributor.model_id` | YES | YES | YES | YES | **4/4** |
| `vcs.revision` | PARTIAL | NO | YES | PARTIAL | **1-2/4** |
| `conversation.url` | NO | NO | NO | NO | **0/4** |

### Key Finding: File Attribution is PARTIALLY Derivable

- **file.path**: Fully derivable from tool-call inputs (4/4)
- **contributor**: Fully derivable from session metadata (4/4)
- **line ranges**: Only directly derivable from OpenCode (1/4); Claude/Gemini/Codex
  require reconstructing old_string position in the original file
- **content_hash**: NOT derivable without access to the final file state
- **conversation.url**: NOT derivable from any format (0/4)

**Conclusion**: `agent-convo-record` is NOT fully derivable from `session-trace`
entries alone. At minimum, `content_hash` and `conversation.url` require external
information not present in the conversation entries. Line ranges are derivable
with non-trivial effort (string matching against file content).

---

## 3. Schema Merge Points

### Fields that naturally connect:

| Henk's Schema | XOR's Schema | Connection |
|--------------|-------------|------------|
| `file.path` | `tool-call-entry.input.file_path` | Direct mapping |
| `conversation.ranges[]` | Derived from Edit/replace/apply_patch tool-calls | Algorithmic derivation |
| `contributor.model_id` | `agent-meta.model-id` | Direct (session-level) |
| `contributor.model_id` | `assistant-entry.model-id` | Direct (per-response) |
| `agent-convo-record.vcs` | `environment.vcs-context` | Superset (XOR has branch+repo) |
| `agent-convo-record.tool` | `agent-meta.cli-name` + `agent-meta.cli-version` | Semantic equivalent |
| `agent-convo-record.timestamp` | `session-envelope.session-start` | Direct |
| `agent-convo-record.id` | `session-envelope.session-id` | Direct |
| `anymap` (metadata) | `vendor-extension` | Philosophy conflict |

### Fields unique to each schema:

**Only in Henk's** (cannot derive from session-trace):
- `range.content_hash` — requires final file state
- `conversation.url` — external reference
- `conversation.related` — external resources

**Only in XOR's** (cannot derive from agent-convo-record):
- `entries[]` — full conversation replay
- `reasoning-entry` — chain-of-thought
- `token-usage` — cost/performance metrics
- `system-event-entry` — lifecycle events
- `signed-agent-trace` — COSE_Sign1 envelope

---

## 4. Proposed Unified Architecture

Based on the evidence, the two schemas are genuinely COMPLEMENTARY. Neither
subsumes the other. The optimal architecture is:

### Option D: session-trace as PRIMARY, agent-convo-record as DERIVED VIEW

```
verifiable-agent-record = {
    ; XOR's session-trace (the primary recording)
    session: session-trace

    ; Henk's file attribution (optionally derived from session entries)
    ? file-attribution: agent-convo-record

    ; COSE_Sign1 wrapper (from XOR's Section 9)
    ? signature: signed-agent-trace
}
```

**Rationale**:
1. `session-trace` captures EVERYTHING that happened (entries, tools, reasoning)
2. `agent-convo-record` captures WHAT WAS PRODUCED (files, line ranges, contributors)
3. Both live in the same record, but `session-trace` is self-sufficient
4. `agent-convo-record` can be derived algorithmically from `session-trace` entries
   (except `content_hash` and `conversation.url`, which require external data)
5. COSE_Sign1 wraps the entire record, satisfying Henk's goals 3-4

### Why NOT Option A (session-trace contains files):
Would pollute the session entry model with file attribution concerns.
Tool-call-entry already has `input.file_path` — adding `ranges[]` to it
creates redundancy.

### Why NOT Option B (agent-convo-record contains entries):
Would make file attribution the root type, demoting conversation replay
to metadata. This contradicts the evidence: conversations are the primary
artifact, file attribution is derived.

### Why NOT Option C (new root containing both as siblings):
This IS what Option D does, but Option D makes the hierarchy explicit:
session is primary, file-attribution is optional/derived. Option C implies
they are equal, which they are not (session-trace has 478 lines of types,
agent-convo-record has 57).

---

## 5. Tool Name Collision Resolution

Henk's `tool = { name, version }` means "the recording agent" (e.g., claude-code v2.1.34).
XOR's `tool-call-entry` means "an agent action" (e.g., Edit, Bash, Read).

**Recommendation**: Rename Henk's `tool` to `recording-agent`:

```cddl
recording-agent = {
    ? name: tstr        ; CLI name (was tool.name)
    ? version: tstr     ; CLI version (was tool.version)
}
```

This maps cleanly to XOR's `agent-meta.cli-name` and `agent-meta.cli-version`.
The word "tool" is then reserved exclusively for tool invocations within entries.

---

## 6. Extension Philosophy Resolution

Henk's `anymap = { * label => value }` with `label = any` is a CBOR optimization
(allows integer keys for compact encoding). His comment says "placeholder for later."

XOR's `vendor-extension = { vendor, version, data: { * tstr => any } }` is
JSON-friendly but CBOR-hostile (forces string keys).

**Recommendation**: Tiered extension mechanism:

```cddl
; Level 1: Auditable vendor extension (JSON + CBOR)
vendor-extension = {
    vendor: tstr
    ? version: tstr
    ? data: extension-data
}

; Level 2: Extension data supports both string and integer keys
extension-data = { * extension-key => any }
extension-key = tstr / int    ; tstr for JSON, int for CBOR compact encoding
```

This preserves:
- XOR's auditability (vendor + version tags)
- Henk's CBOR optimization (integer keys allowed in data)
- JSON compatibility (string keys work everywhere)

---

## Evidence Citations

- [E1] `bench/runs/arvo-250iq/run-2026-02-07/claude-claude-opus-4-5-harfbuzz-XOR-harfbuzz-ID-11033-0-session.jsonl:13` — Claude Edit tool call
- [E2] `bench/runs/arvo-250iq/run-2026-02-07/gemini-gemini-3-pro-preview-harfbuzz-XOR-harfbuzz-ID-11033-0-session.jsonl:198-227` — Gemini replace tool call
- [E3] `bench/runs/arvo-250iq/run-2026-02-07/codex-o3-harfbuzz-XOR-harfbuzz-ID-11033-0-session.jsonl:74` — Codex apply_patch tool call
- [E4] `bench/runs/arvo-250iq/run-2026-02-07/opencode-gpt-5.2-codex-harfbuzz-XOR-harfbuzz-ID-11033-0-session.jsonl:765-793` — OpenCode apply_patch with rich metadata
- [E5] `vendor/specs/draft-birkholz-verifiable-agent-conversations/agent-conversation.cddl` — Henk's schema
- [E6] `vendor/specs/internal-verifiable-vibes/ietf-abstract-types.cddl` — XOR's schema
- [E7] `bench/runs/arvo-250iq/run-2026-02-07/claude-claude-opus-4-5-harfbuzz-XOR-harfbuzz-ID-11033-0-fix.patch` — Git diff output
