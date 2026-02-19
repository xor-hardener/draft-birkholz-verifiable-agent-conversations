# File Attribution Investigation — Phase 4

Date: 2026-02-18
Context: Assess feasibility of implementing CDDL Section 8 (`file-attribution-record`) by
deriving file attribution data from session traces. Analyzed two agents: Claude Code and OpenCode.

## Summary

| Dimension | Claude Code | OpenCode |
|-----------|------------|----------|
| File-modifying tools | Edit (3 calls, 1 file) | apply_patch (6), edit (6) — 9 files |
| `file.path` | YES — `input.file_path`, strip working-dir | YES — `metadata.files[].relativePath` (apply_patch) |
| `range.start_line/end_line` | INDIRECT — match `old_string` vs file, or parse git diff | YES — unified diff `@@` hunk headers |
| `range.content_hash` | HARD — reconstruct file from Read + sequential Edit replays | YES — `metadata.filediff.after` provides full post-edit content |
| `contributor.type` | YES — `"ai"` for all tool edits | YES — `"ai"` for all tool edits |
| `contributor.model_id` | YES — `session.agent-meta.model-id` or per-entry `model-id` | YES — same, but multi-model sessions need per-entry correlation |
| `conversation.url` | NO — not in native data | NO — not in native data |
| Overall feasibility | Medium (requires string matching or diff parsing) | High (rich metadata natively available) |

## Claude Code: Tool-Call Analysis

### Inventory (claude-opus-4-6 session, 378 entries)

| Tool | Count | Category |
|------|-------|----------|
| Bash | 56 | Shell commands (git, find, etc.) |
| Grep | 40 | Code search (read-only) |
| Read | 26 | File read (read-only) |
| WebFetch | 13 | Web fetch |
| WebSearch | 4 | Web search |
| TodoWrite | 3 | Task management |
| **Edit** | **3** | **File modification** |
| Write | 0 | Not used in this session |

### File Modifications

**1 unique file modified:** `source/server/config_validation/server.cc`
(Working dir: `/tmp/v9azOZts/`, relative path after strip)

3 sequential edits:
1. Added null-pointer guard (+4 lines net)
2. Added `#include` directive (+1 line net)
3. Changed fallback address (0 net change)

### Edit Tool Input Structure

```json
{
  "type": "tool-call",
  "name": "Edit",
  "input": {
    "replace_all": false,
    "file_path": "/tmp/v9azOZts/source/server/config_validation/server.cc",
    "old_string": "#include \"common/common/utility.h\"\n#include \"common/config/utility.h\"",
    "new_string": "#include \"common/common/utility.h\"\n#include \"common/config/utility.h\"\n#include \"common/network/address_impl.h\""
  },
  "call-id": "toolu_01FQPFn2hRG5cEJXL2XCZTbB"
}
```

### Line Range Derivation Challenge

Claude's Edit tool uses `old_string`/`new_string` (string matching), NOT line numbers. To derive
`start_line`/`end_line`, the algorithm must:

1. **Option A: Match against Read output.** The session includes Read tool-results for the same file
   with `cat -n` formatted output showing line numbers. Match `old_string` against Read output to
   find starting position, then count `new_string` lines for end position.

2. **Option B: Parse git diff output.** The session includes `git diff` Bash outputs with unified
   diff hunk headers (`@@ -26,7 +27,11 @@`) that give exact line positions.

3. **Option C: Replay edits.** Apply edits sequentially to the original file content (from Read
   output) and track line positions. Most accurate but most complex.

**Recommendation:** Option B (git diff parsing) when available; Option A (string matching) as
fallback. Option C only for `content_hash` computation.

## OpenCode: Tool-Result Analysis

### Inventory (opencode-claude-opus-4-6 session, 1264 entries)

12 file-modifying operations across two tool types:
- `apply_patch` (6): OpenAI-style patch application
- `edit` (6): String-replacement edits (like Claude's Edit)

Modifying files across 7 different repositories (multi-project session).

### Rich Metadata (apply_patch)

OpenCode's `apply_patch` tool-results include `metadata.files[]` with:

```json
{
  "filePath": "/tmp/CRs5SvG4/src/westmere/sse_convert_utf8_to_utf32.cpp",
  "relativePath": "src/westmere/sse_convert_utf8_to_utf32.cpp",
  "type": "update",
  "diff": "Index: ...\n@@ -80,9 +80,9 @@\n...",
  "before": "<full file content before edit>",
  "after": "<full file content after edit>",
  "additions": 4,
  "deletions": 3
}
```

**All 8 fields present on all 6 `apply_patch` results.** This is the richest file attribution
data of any agent format. Every CDDL field is directly derivable.

### edit Tool Metadata

OpenCode's `edit` tool-results include `metadata.filediff`:

```json
{
  "file": "/tmp/zMMrAobM/src/hb-aat-layout-kerx-table.hh",
  "before": "<full file content>",
  "after": "<full file content>",
  "additions": 20,
  "deletions": 2
}
```

Plus `metadata.diff` (separate key) with unified diff. Similar richness, slightly different
structure. No `relativePath` (must strip prefix).

## Field-by-Field Derivability

| CDDL Field | Claude | OpenCode | Notes |
|-------------|--------|----------|-------|
| `file.path` | YES | YES | Claude: `input.file_path` - working-dir. OpenCode: `metadata.files[].relativePath` |
| `range.start_line` | MEDIUM | YES | Claude: string match or git diff. OpenCode: diff `@@` headers |
| `range.end_line` | MEDIUM | YES | Same as start_line |
| `range.content_hash` | HARD | YES | Claude: reconstruct file. OpenCode: `after` content available |
| `range.content_hash_alg` | YES | YES | Fixed `"sha-256"` |
| `contributor.type` | YES | YES | `"ai"` for tool-generated edits |
| `contributor.model_id` | YES | YES | Session-level or per-entry model ID |
| `conversation.url` | NO | NO | External input required (not in any native data) |
| `conversation.related` | NO | NO | External input required |

## Gaps: What Cannot Be Derived

1. **`conversation.url`** — No agent stores a URL to the conversation source. This must be
   supplied by the recording system (e.g., a CI pipeline or web UI that knows the conversation
   permalink).

2. **`conversation.related`** — External resources (issues, PRs, docs) are not tracked in any
   native format. Could potentially be extracted from user message content (URLs mentioned in
   prompts), but this is heuristic, not reliable.

3. **Human-authored ranges** — If the user edits code directly (outside the agent), the session
   trace won't record it. Session traces only capture agent-initiated tool calls. Mixed
   human/AI attribution requires VCS integration (comparing agent edits against full commit diff).

4. **Cross-edit line drift** — When an agent makes multiple edits to the same file, earlier
   edits shift line numbers for later edits. The derivation algorithm must apply edits
   sequentially and track position shifts.

## Implementation Recommendation

### Phase 1: OpenCode prototype (lowest effort, highest data quality)
- Parse `metadata.files[]` from `apply_patch` results and `metadata.filediff` from `edit` results
- Extract `relativePath`, parse `@@` hunk headers for line ranges
- Compute `content_hash` from `after` content
- Produces complete `file-attribution-record` with minimal effort

### Phase 2: Claude prototype (medium effort)
- Parse Edit tool-call `input` for `file_path`, `old_string`, `new_string`
- Use Read tool-result output or git diff output (if present) for line range derivation
- For `content_hash`: reconstruct file by replaying edits (complex but feasible)

### Phase 3: Generalized derivation
- Implement the algorithm described in CDDL Section 10
- Handle all 5 agent formats
- Codex: similar to Claude (Edit-like tools)
- Gemini: similar to Claude (file operations in tool calls)
- Cursor: minimal file attribution data (lacks metadata)

### Not Recommended: Removing file-attribution from schema
The investigation confirms that file attribution IS derivable from session data (at least
partially) for 4/5 agents. OpenCode provides near-complete data natively. The schema section
should be retained and implementation prioritized.
