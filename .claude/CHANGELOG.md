# Design Decision Log

Tracks all interview questions asked and decisions made during schema and tooling development.

## 2026-02-18: Schema Simplification v3.0.0-draft (Approach B)

Major schema rewrite: 7 entry types → 4, all maps extensible via `* tstr => any`,
no-drop policy on parsers, canonical token-usage extraction.

Full decision log with options and reasoning: [`.claude/reviews/2026-02-18/simplification-plan.md`](reviews/2026-02-18/simplification-plan.md)

### Decisions

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| 1 | Passthrough strategy | **Selective canonical + full native preservation** | Token usage gets canonical names; all other native fields preserved via `* tstr => any`. User: "do NOT DROP ANYTHING." |
| 2 | Native field placement | **Flat merge at entry level** | Simplest. Canonical kebab-case + native camelCase/snake_case coexist. Consumers ignore unknown fields. |
| 3 | Canonical fields to add | **Token usage only** | 4/5 agents provide tokens. Single highest-value missing data. `? token-usage: token-usage` on message-entry. |
| 4 | File attribution | **Keep in schema with TODO comments** | Henk's original contribution. ~100 extra CDDL lines acceptable. Investigation shows derivability (see Phase 4). |
| 5 | Session types | **Single `session-trace` with `? format: tstr`** | All 13 sessions use same structure. interactive/autonomous distinction adds CDDL complexity without value. |
| 6 | Event entry type | **Explicit `type: "system-event"` only** | No `type: tstr` catch-all. Avoids PEG ordering ambiguity. |
| 7 | Children behavior | **Keep current asymmetry** | Claude/Gemini nest children; Codex/OpenCode/Cursor flat. Accurate to native structures. |
| 8 | Vendor extension type | **Remove entirely** | `* tstr => any` provides extensibility. vendor-extension ceremony adds complexity with no proven use. |

### Schema Changes

- 7 entry types → 4: `message-entry`, `tool-entry`, `reasoning-entry`, `event-entry`
- All maps: added `* tstr => any` (RFC 8610 §3.5.4 extensibility, COSE precedent)
- Removed: `vendor-extension`, `extension-key`, `extension-data`, `interactive-session`,
  `autonomous-session`, `session-envelope`, `base-entry`, `user-entry`, `assistant-entry`,
  `tool-call-entry`, `tool-result-entry`, `system-event-entry`, `vendor-entry`
- Added: `token-usage` type with `? input/output/cached/reasoning: uint` + `* tstr => any`
- Kept: file attribution (Sections 8, 10), signing envelope (Section 9)
- Version: `2.0.0-draft` → `3.0.0-draft`
- Trace format: `ietf-vac-v2.0` → `ietf-vac-v3.0`

### Parser Changes

- **No-drop policy:** All 5 parsers updated. Native fields not consumed for canonical mapping
  are flat-merged into entries. No data is silently dropped.
- **Token-usage extraction:** Claude (`message.usage`), Gemini (`messages[].tokens`),
  Codex (`event_msg/token_count`), OpenCode (`role-message.tokens`). Cursor has no token data.
- **Bug fix:** Claude `msg.type` ("message") and `msg.id` (API message ID) were overwriting
  canonical `type` and `id` via passthrough. Fixed by adding to `_MSG_CONSUMED` set.

### Validation

- All 13 sessions pass CDDL validation with v3 schema
- All 13 records signed and verified with COSE_Sign1 (trace-format: `ietf-vac-v3.0`)
- Token-usage present: Claude 230/378, Gemini 23/24, Codex 203/568, OpenCode 199/1264, Cursor 0/79

### File Attribution Investigation

See [`.claude/reviews/2026-02-18/file-attribution-investigation.md`](reviews/2026-02-18/file-attribution-investigation.md).
OpenCode provides the richest file attribution data (full before/after content, diffs, relative paths).
Claude Edit tool provides `old_string`/`new_string` requiring string matching for line positions.
All CDDL Section 8 fields derivable except `conversation.url` and `conversation.related`.

## 2026-02-17: Breakdown Review — Round 10

Tenth review using 5 parallel verification agents. All existing claims verified correct;
found 1 precision gap in `gemini-cli.md`.

### Fixes Applied

| # | File | Issue | Fix |
|---|------|-------|-----|
| 1 | `gemini-cli.md` | "Each toolCall produces two children" stated unconditionally but parser code is conditional (`if result is not None`, line 306); tool-result child only emitted when result field exists | Qualified to "produces a `tool-call` child, and a `tool-result` child when `result` is not null" |

### Context

Round 10 deployed 5 parallel agents (same methodology as Rounds 3-9). No fabrications found.
The single issue is a precision gap: the Gemini parser conditionally emits tool-result children
(only when `tc.get("result") is not None`), but the breakdown stated unconditionally that each
toolCall produces two children. In practice all toolCalls in the current session data have
non-null results, so this is always true for observed data — but the breakdown documents parser
behavior, which is explicitly conditional.

False alarms triaged: OpenCode text objects lacking `time` fields (agent checked one of the
23/190 text objects without `time`; 167/190 DO have them — Round 7 fix confirmed valid);
native schema examples missing minor subfields in dropped objects (cosmetic, covered by
existing dropped-field documentation).

## 2026-02-17: Breakdown Review — Round 9

Ninth review using 5 parallel verification agents. All existing claims verified correct;
found 1 completeness gap in `opencode.md`.

### Fixes Applied

| # | File | Issue | Fix |
|---|------|-------|-----|
| 1 | `opencode.md` | `id` field silently dropped from role-message and step-start/step-finish entries but not listed in dropped fields (parser lines 566, 614 don't pass `id`; content-bearing entries at lines 575, 589, 610, 612 do) | Added `id` to both dropped-field lists: step-start/step-finish and role objects |

### Context

Round 9 deployed 5 parallel agents (same methodology as Rounds 3-8). No fabrications found.
The single issue is a completeness gap: role-message objects (`msg_...` IDs) and
step-start/step-finish objects (`prt_...` IDs) have `id` fields in the native data that the
parser drops, but the dropped fields section only listed other fields from these entry types
(`snapshot`/`reason`/`cost`/`tokens` for step-start/step-finish; `parentID`/`modelID`/etc. for
role objects). The "Direct matches" section's `id` → `id` claim remains correct for
content-bearing entries (text, tool-call, patch, reasoning).

## 2026-02-17: Breakdown Review — Round 8

Eighth review using 5 parallel verification agents. All existing claims verified correct;
found 2 issues in `codex-cli.md` and updated `BREAKDOWN.md` summary table.

### Fixes Applied

| # | File | Issue | Fix |
|---|------|-------|-----|
| 1 | `codex-cli.md` | `token_count` grouped under "duplicates `response_item`" heading, but it is unique data with no `response_item` equivalent | Restructured: 3 of 4 event_msg subtypes labeled as duplicates; `token_count` labeled as unique |
| 2 | `codex-cli.md` | Missing `payload.content` → `content` un-nest for `response_item` message entries (same pattern as `payload.output` → `output`) | Added to Renames section |
| 3 | `BREAKDOWN.md` | Codex renames 8→9, un-nest 8→9 (reflects new `payload.content` rename) | Updated summary table |

### Context

Round 8 deployed 5 parallel agents (same methodology as Rounds 3-7). No fabrications
found. Both Codex issues are completeness/accuracy gaps: one incorrectly grouped unique
data under a "duplicates" heading, and one missing un-nest rename that follows the same
pattern as other documented renames in the same file.

## 2026-02-17: Breakdown Review — Round 7

Seventh review using 5 parallel verification agents. All existing claims verified correct;
found 1 completeness gap in `opencode.md`.

### Fixes Applied

| # | File | Issue | Fix |
|---|------|-------|-----|
| 1 | `opencode.md` | `time.start`/`time.end` on text objects (167/190 text objects across 4 files) silently dropped but only documented as dropped on reasoning objects | Changed "(from reasoning objects)" to "(from reasoning and text objects)" |

### Context

Round 7 deployed 5 parallel agents (same methodology as Rounds 3-6). No fabrications
found. The single issue is a completeness gap: text-type objects in OpenCode sessions
carry `time.start`/`time.end` fields that the parser drops, but the dropped fields
documentation only mentioned these fields on reasoning objects.

## 2026-02-17: Breakdown Review — Round 6

Sixth review using 5 parallel verification agents. All existing claims verified correct;
found 2 factual errors in `codex-cli.md`.

### Fixes Applied

| # | File | Issue | Fix |
|---|------|-------|-----|
| 1 | `codex-cli.md` | Native schema example shows `collaboration_mode` as string `"none"` and `truncation_policy` as string `"auto"`, but real data has objects (`{"mode": "default", "settings": {...}}` and `{"mode": "bytes", "limit": 10000}`) | Updated example to match real session data |
| 2 | `codex-cli.md` | `payload.content` on reasoning described as "raw encrypted reasoning" — it is actually always `null`; encrypted reasoning lives in `encrypted_content` | Changed to "always `null`; would contain unencrypted reasoning if available, but models with encrypted reasoning never populate it" |

### Context

Round 6 deployed 5 parallel agents (same methodology as Rounds 3-5). No fabrications
found. Both issues are in `codex-cli.md`: one factual error in the native schema example
(wrong data types for two `turn_context` fields) and one misleading description of
`payload.content` on reasoning entries.

## 2026-02-17: Breakdown Review — Round 5

Fifth review using 5 parallel verification agents. All existing claims verified correct;
found 4 completeness gaps.

### Fixes Applied

| # | File | Issue | Fix |
|---|------|-------|-----|
| 1 | `claude-code.md` | Line-level `type` field (e.g., `"user"`, `"assistant"`) silently ignored by parser (uses `message.role` instead) but not listed as dropped | Added to per-entry dropped with explanation |
| 2 | `codex-cli.md` | `turn_context.model` described as "primary source" but code checks `session_meta.model` first; `turn_context` is structurally a fallback | Changed to "fallback source, but always used because `session_meta` lacks `model` field" |
| 3 | `opencode.md` | Session summary dropped field list missing `id` field | Added `id` to session summary field list |
| 4 | `opencode.md` | Nested `model` object on user role messages (containing `providerID`, `modelID`) undocumented | Added to per-entry dropped with note about metadata extraction |

### Context

Round 5 deployed 5 parallel agents (same methodology as Rounds 3-4). No fabrications
found. The 4 issues are all completeness gaps: one undocumented ignored field (Claude
line-level `type`), one misleading characterization (Codex "primary" vs "fallback"), and
two missing dropped fields (OpenCode). The Codex "9 values" type count in BREAKDOWN.md
was investigated and confirmed correct (counts `developer` and `user` as separate source
values; excludes event_msg duplicates).

## 2026-02-17: Breakdown Review — Round 4

Fourth review using 5 parallel verification agents. All existing claims verified correct;
found 13 completeness gaps (missing fields, undocumented mappings).

### Fixes Applied

| # | File | Issue | Fix |
|---|------|-------|-----|
| 1 | `claude-code.md` | `tool_use` child structural extraction missing `name` → `name` and `input` → `input` pass-throughs | Added to tool_use child mapping |
| 2 | `claude-code.md` | `gitBranch` listed as "per-entry dropped" but parser extracts it into `meta["branch"]` (then discarded by `wrap_record`) | Moved to metadata-extracted with "not emitted" note |
| 3 | `claude-code.md` | `operation` on queue-operation lines undocumented as dropped | Added to per-entry dropped |
| 4 | `claude-code.md` | `slug` field undocumented as dropped | Added to per-entry dropped |
| 5 | `claude-code.md` | Conditional `agent-meta.models` list in record wrapper undocumented | Added note to record wrapper fabrication |
| 6 | `gemini-cli.md` | `toolCalls[].timestamp` → `timestamp` on children undocumented | Added to toolCalls structural extraction |
| 7 | `codex-cli.md` | `payload.git.branch` listed as "Metadata-extracted" but `wrap_record` never emits it | Moved to "extracted but not emitted" note |
| 8 | `codex-cli.md` | `session_meta` lacks `model` field; `turn_context` is primary (not fallback) source | Corrected description |
| 9 | `codex-cli.md` | "Silently dropped from `turn_context`" missing 4 fields: `cwd`, `collaboration_mode`, `user_instructions`, `truncation_policy` | Added all 4 |
| 10 | `codex-cli.md` | Missing `payload.rate_limits` and `payload.status` from dropped fields | Added to event_msg and response_item dropped |
| 11 | `codex-cli.md` | Native schema examples for `turn_context` and `token_count` incomplete | Added missing fields |
| 12 | `opencode.md` | Patch objects' `hash` and `files` fields not listed as dropped | Added to per-entry dropped |
| 13 | `opencode.md` | Session summary objects (slug, projectID, etc.) undocumented | Added as silently dropped |

### Context

Round 4 deployed 5 parallel agents (same methodology as Round 3). No outright fabrications
were found — all existing claims in the breakdowns are correct. The 13 issues are all
completeness gaps: missing dropped fields, undocumented field mappings, and miscategorized
metadata fields that are extracted but never emitted to the output record.

## 2026-02-17: Breakdown Review — Round 3

Third review using 5 parallel verification agents, each cross-referencing one breakdown file
against parser code and actual session data.

### Fixes Applied

| # | File | Issue | Fix |
|---|------|-------|-----|
| 1 | `claude-code.md` | Direct matches listed `type: "user"/"assistant"` but entry type actually comes from `message.role`, not line-level `type` | Changed to 1 direct match (`timestamp`); moved `message.role` → `type` to renames |
| 2 | `claude-code.md` | `message.model` → `model-id` listed as per-entry rename but is record-level metadata extraction | Moved to new "Metadata-extracted" paragraph in dropped fields |
| 3 | `claude-code.md` | `cwd`, `sessionId`, `version` listed as "dropped" but are metadata-extracted to record wrapper | Split dropped fields into metadata-extracted vs per-entry dropped |
| 4 | `claude-code.md` | `queue-operation` → `system-event` type mapping undocumented | Added to structural extraction |
| 5 | `gemini-cli.md` | Claimed `result[].functionResponse.response.output` deep nesting extraction — fabricated; parser passes raw `result` as-is | Corrected to "raw result array passed through" |
| 6 | `gemini-cli.md` | Bare `description` in dropped list ambiguous (could mean `thoughts[].description` which IS used) | Qualified all dropped fields with parent path: `toolCalls[].description`, etc. |
| 7 | `gemini-cli.md` | Missing `"human"` → `"user"` type mapping | Added alongside `"gemini"` → `"assistant"` |
| 8 | `gemini-cli.md` | Top-level `sessionId`/`startTime` metadata extraction undocumented | Added "Metadata extraction" section |
| 9 | `opencode.md` | `"patch"` → `"tool-result"` type mapping missing | Added to type mapping |
| 10 | `opencode.md` | Missing dropped fields: reasoning `time.start`/`time.end`, role `summary`/`time.completed`, step-finish `cost`/`tokens` | Added to per-entry dropped list |
| 11 | `codex-cli.md` | Only 4 renames listed; missing reasoning, event_msg, and input-variant renames | Added 4 more renames (summary→content, encrypted_content→encrypted, message→content, text→content) |
| 12 | `codex-cli.md` | "session_meta fields (moved to meta)" overstatement — several fields silently dropped | Split into metadata-extracted, per-entry dropped, and silently-dropped-from paragraphs |
| 13 | `cursor.md` | Catch-all role mapping undocumented (all non-"user" → "assistant") | Added to rename description |
| 14 | `BREAKDOWN.md` | Summary table: Claude direct matches 3→1, Codex renames 4→8, un-nest 5→8, type map 5→9, fabricated 2→3; Gemini type map 3→4; OpenCode type map 5→6 | Updated all cells |

### Context

Round 3 deployed 5 parallel agents (one per breakdown file) plus a summary-table checker.
Most critical finding was Gemini's fabricated `result` nesting path — the parser passes the raw
`result` array through as `output`, no deep extraction occurs. Claude's entry type was being
misattributed to line-level `type` when it actually comes from `message.role`.

## 2026-02-17: Breakdown Review — Round 2

Second review of per-agent breakdown files (`.claude/breakdown/*.md`) against session data and parser code.

### Fixes Applied

| # | File | Issue | Fix |
|---|------|-------|-----|
| 1 | `opencode.md` | Dropped fields omitted session header (`id`, `vcs`, `sandboxes`, `time.updated`), share-info object, and step-start/step-finish fields (`snapshot`, `reason`) | Added session-header and share-info paragraphs; added `snapshot`/`reason` to per-entry list |
| 2 | `gemini-cli.md` | `thoughts[].timestamp` silently dropped but not listed | Added to dropped fields list |

### Context

Round 1 (same day, earlier session) fixed 5 issues: OpenCode text→role mapping, Claude dropped
fields, Codex type mappings, Cursor fabricated ambiguity, and BREAKDOWN.md summary table.
Round 2 caught these two remaining omissions by cross-referencing native schema examples
against the dropped-fields lists.

## 2026-02-16: COSE_Sign1 Signing Implementation

Implemented `scripts/sign-record.py` — a standalone tool that produces cryptographically
signed agent session records using COSE_Sign1 (RFC 9052), matching the `signed-agent-record`
type defined in CDDL Section 11.

### Decisions

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| 1 | New script or extend validate-sessions.py? | **New standalone `scripts/sign-record.py`** | Separation of concerns: validation ≠ signing. Different dependencies (pycose, cbor2). |
| 2 | Algorithm? | **Ed25519 (EdDSA)** | Fast, small 64-byte signatures, deterministic. Used by RATS/SCITT examples. COSE algorithm ID: -8. |
| 3 | Payload mode? | **Detached only** | COSE_Sign1 with `payload=null`. JSON record file stays separate, can be inspected/diffed. Signature file is small (~300 bytes). |
| 4 | Key format? | **PEM files (PKCS8/SubjectPublicKeyInfo)** | Standard, interoperable. Private key unencrypted for dev use. |
| 5 | Dependencies? | **`requirements.txt` with pycose, cbor2** | No flake.nix changes. Nix dev shell already installs `requirements*.txt`. |
| 6 | Trace-metadata source? | **Extracted from record JSON** | session-id, agent-vendor, timestamps from the verifiable-agent-record structure. Content hash (SHA-256) computed over canonical JSON bytes. |

### Implementation

- **`keygen`**: Generates Ed25519 keypair via `cryptography` library, writes PEM files.
- **`sign`**: Canonicalizes JSON (compact, sorted keys), builds COSE_Sign1 with detached payload,
  stores trace-metadata in unprotected header at label 100 (per CDDL `trace-metadata-key`).
- **`verify`**: Decodes COSE_Sign1, reattaches detached payload, verifies Ed25519 signature,
  checks content-hash integrity.

### Verification

- All 13 session records signed and verified successfully
- CBOR output inspected: Tag 18, 4-element array, protected header `{1: -8, 3: "application/json"}`,
  unprotected header `{100: trace-metadata}`, payload `null`, 64-byte signature
- Structure matches `signed-agent-record` in CDDL Section 11 exactly

## 2026-02-16: Schema Simplification (content: any + children)

Goal: Minimize the translation layer in `validate-sessions.py` by making the CDDL spec
accept native agent formats more directly.

### Round 1: Core Schema Decisions

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| 1 | Should `content` change from `tstr` to `any`? | **content: any** | Eliminates `_content_to_str()` entirely. Preserves native structured content (arrays of parts, multimodal blocks). Matches existing `input: any` / `output: any` precedent. |
| 2 | Should entries support inline children? | **Yes, add `? children: [* entry]`** | Lets Claude/Gemini keep their hierarchical message structure (tool blocks inside assistant messages) instead of forcing flat entry arrays. |
| 3 | Should the spec accept `role` as alternative to `type`? | **type only** | Keep `type` as sole discriminator. Parsers rename `role` to `type`. |
| 4 | How should the verifiable-agent-record wrapper work? | **Keep as-is** | The multi-level wrapper (verifiable-agent-record > session > entries) stays. Translation must construct it. |

### Round 2: Naming and Structure

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| 5 | Accept native type values (function_call, tool_use) alongside canonical? | **Canonical only** | Pick one name and rename everything. Keeps CDDL clean. |
| 6 | Accept native field names as alternatives (call-id / call_id / callID)? | **Canonical kebab-case only** | CDDL convention is kebab-case. Parsers rename from native conventions. |
| 7 | How should children work for Claude's tool_use/tool_result blocks? | **Children as typed entries** | Children must be valid entry types (tool-call-entry, etc.). Parser maps type values but doesn't need to flatten into separate top-level entries. |
| 8 | Support combined tool-round-trip entry (fused call+result)? | **Keep separate call/result** | Require splitting into tool-call + tool-result. OpenCode/Gemini parsers split fused objects. |

### Round 3: Content and Mapping

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| 9 | Tool entry type names? | **tool-call / tool-result** | Current names. Hyphenated, explicit direction. |
| 10 | Should parsers pass through native content structures as-is? | **Pass-through** | No `_content_to_str()`. Maximum fidelity. Native arrays stay as arrays. |
| 11 | Claude mapping: 1 entry + children vs N flat entries? | **1 entry + children** | One assistant entry per JSONL line. Tool-use, text, thinking blocks become typed children. |

### Changes Made

**CDDL (`agent-conversation.cddl`):**
- `content: tstr` → `content: any` on user-entry, assistant-entry, reasoning-entry
- Added `? children: [* entry]` to base-entry

**Script (`scripts/validate-sessions.py`):**
- Claude parser: 1 entry per JSONL line with children for tool-call/tool-result/reasoning
- Gemini parser: 1 entry per message with children (140 flat entries → 24 entries + 138 children)
- Removed all `_content_to_str()` calls from parsers (kept for report utility)
- Content/output passed through as native structures
- Report updated to count children

### Impact
- Gemini entry count: 140 → 24 (+ 138 children)
- Claude: same entry count, but tool/reasoning blocks now in children
- Total produced size: 4.68 MB → 5.79 MB (native arrays slightly larger than flattened strings)
- All 13 sessions pass validation with zero data loss

## 2026-02-16: Secrets Scrub (pre-push audit)

GitHub Push Protection blocked the initial push. Full audit of all 13 session files revealed
two categories of embedded secrets.

### Findings

| Severity | Type | Count | Files | Replacement |
|---|---|---|---|---|
| HIGH | GitHub App Installation Tokens (`ghs_`) in `repository_url` | 2 tokens | `codex-gpt-5-2.jsonl`, `codex-gpt-5-2-codex.jsonl` | `x-access-token:<REDACTED>@` |
| MEDIUM | OpenCode session share secrets (UUIDs) | 31 secrets | All 4 `opencode-*.jsonl` files | `"secret": "<REDACTED>"` |

### Details

**Codex `ghs_` tokens:** The Codex CLI records the full git clone URL in `session_meta.payload.git.repository_url`,
including the `x-access-token:ghs_XXXX@github.com` credential used by the benchmark runner. Both Codex session
files had this on line 1. Tokens are likely expired (short-lived installation tokens) but must not be in public repos.

**OpenCode share secrets:** OpenCode emits `{"id": "...", "secret": "uuid", "url": "https://opncd.ai/share/..."}` objects
throughout sessions (on step boundaries). The `secret` field grants access to the shared session URL. 31 distinct UUIDs
found across the 4 OpenCode files.

### Non-findings (verified false positives)
- `secret_manager_`, `Secret::SecretManagerImpl` in Claude sessions → Envoy C++ source code
- `password`, `Authorization`, `credential` in OpenCode sessions → Mongoose HTTP library source code
- `authorization` in Codex sessions → HPACK static table entries (HTTP/2)
- `credential` in OpenCode sessions → GDAL git commit messages
- `AKIA`-like strings → base64-encoded COSE/CBOR content, not AWS keys
- `tokens` fields → token usage metadata (input_tokens, output_tokens), not auth tokens
