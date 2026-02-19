# Schema Simplification Assessment — Approach B

Date: 2026-02-18
Context: Assessing how to simplify the translation layer and spec definition while keeping it meaningful and working with all 13 example session files across 5 agent formats.

## Current Complexity (Quantified)

| Metric | Value |
|--------|-------|
| CDDL schema | 630 lines, 12 sections, 7 entry types, 20+ named types |
| Parser code | ~530 lines across 5 parsers (lines 140-658 of validate-sessions.py) |
| Total renames | 26 across all agents |
| Total un-nestings | 18 across all agents |
| Type value mappings | 24 distinct values → 7 canonical types |
| Structural transforms | 5 (children extraction, tool splitting, envelope unwrap) |
| Fabricated fields | 16 across all agents |

## Root Causes of Complexity

**1. Seven distinct entry types with rigid field sets.** Each entry type (`user-entry`, `assistant-entry`, `tool-call-entry`, `tool-result-entry`, `reasoning-entry`, `system-event-entry`, `vendor-entry`) has its own required/optional field combinations. This means the parser must classify every native object into exactly one type and provide the right fields — even when the native format doesn't make the same distinctions.

**2. Required fields that agents don't provide.** `tool-call-entry` requires `name` and `input`. `system-event-entry` requires `event-type`. This forces fabrication or extraction where the native format doesn't naturally provide these.

**3. Canonical kebab-case field names.** Every agent uses different conventions (camelCase, snake_case, nested paths). Every field must be renamed: `call_id` → `call-id`, `tool_use_id` → `call-id`, `callID` → `call-id`, etc.

**4. Forced structural transformations.** OpenCode fuses tool call+result into one object → must be split into two entries. Codex wraps everything in a `{timestamp, type, payload}` envelope → must be unwrapped. Claude/Gemini nest sub-entries inside messages → must be extracted into children.

**5. The wrapper envelope.** `verifiable-agent-record > session-trace > interactive/autonomous-session > session-envelope > entries[]` is 4 levels deep. Every parser must construct this from scattered metadata.

## Approaches Considered

### Approach A: "Open Entry" (Maximum Simplicity)

Replace all 7 entry types with one open map. `type` is the only required field. Everything else passes through.

- CDDL: ~630 → ~150 lines
- Parsers: ~530 → ~200 lines (still need envelope unwrap + metadata extraction)
- **Tradeoff:** Loses schema-enforced structure. The schema validates almost any JSON object with a `type` field. Not very IETF-like.

### Approach B: "Fewer Types + Open Maps" (Pragmatic Middle) — RECOMMENDED

Collapse 7 entry types to 4 with `* tstr => any` on each.

- CDDL: ~630 → ~120 lines (excluding signing envelope)
- Parsers: ~530 → ~525 lines (~1% reduction)
- **Tradeoff:** Good spec simplification. Schema still has meaningful structure. Parsers barely change.

### Approach C: "Dual Mode — Native Passthrough + Canonical"

Keep typed schema for canonicalized records, add a "raw entry" mode that accepts native format objects wrapped in minimal metadata.

- Parsers: Dramatically simpler for passthrough mode (~100 lines)
- **Tradeoff:** Two validation paths. Schema complexity increases. Pushes complexity to consumers.

## Approach B: The Concrete Schema

```cddl
; ROOT
start = verifiable-agent-record

; COMMON TYPES (unchanged)
abstract-timestamp = tstr .regexp date-time-regexp / number
session-id = tstr
entry-id = tstr
date-time-regexp = "([0-9]{4})-(0[1-9]|1[0-2])..."

; ROOT RECORD — flattened, open map
verifiable-agent-record = {
    version: tstr
    id: tstr
    ? created: abstract-timestamp
    ? session: session-trace
    ? vcs: vcs-context
    * tstr => any                          ; record-level extensions
}
;; REMOVED: file-attribution, recording-agent, metadata/vendor-extension

; SESSION — no interactive/autonomous split, inline envelope, open map
session-trace = {
    ? format: tstr                         ; "interactive" / "autonomous" / vendor string
    session-id: session-id
    ? session-start: abstract-timestamp
    ? session-end: abstract-timestamp
    agent-meta: agent-meta
    ? environment: environment
    entries: [* entry]
    * tstr => any                          ; session-level extensions
}
;; REMOVED: interactive-session / autonomous-session distinction
;; REMOVED: session-envelope group composition (inlined)
;; REMOVED: vendor-ext field (subsumed by * tstr => any)

; AGENT META — open map
agent-meta = {
    model-id: tstr
    model-provider: tstr
    ? models: [* tstr]
    ? cli-name: tstr
    ? cli-version: tstr
    * tstr => any
}

; ENVIRONMENT — open map
environment = {
    ? working-dir: tstr
    * tstr => any
}

; VCS — open map
vcs-context = {
    ? type: tstr
    ? revision: tstr
    ? branch: tstr
    ? repository: tstr
    * tstr => any
}

; ENTRIES — 4 types instead of 7
entry = message-entry / tool-entry / reasoning-entry / event-entry

message-entry = {
    type: "user" / "assistant"
    ? content: any
    ? timestamp: abstract-timestamp
    ? id: entry-id
    ? model-id: tstr
    ? stop-reason: tstr
    ? parent-id: entry-id
    ? children: [* entry]
    * tstr => any
}
;; MERGED: user-entry + assistant-entry (identical field sets)
;; REMOVED: token-usage named type (passthrough or * tstr => any)

tool-entry = {
    type: "tool-call" / "tool-result"
    ? call-id: tstr
    ? name: tstr
    ? input: any
    ? output: any
    ? status: tstr
    ? is-error: bool
    ? timestamp: abstract-timestamp
    ? id: entry-id
    ? children: [* entry]
    * tstr => any
}
;; MERGED: tool-call-entry + tool-result-entry
;; NOTE: name/input only relevant for tool-call, output/status for tool-result
;;       but schema doesn't enforce this — both are optional

reasoning-entry = {
    type: "reasoning"
    ? content: any
    ? encrypted: tstr
    ? subject: tstr
    ? timestamp: abstract-timestamp
    ? id: entry-id
    ? children: [* entry]
    * tstr => any
}

event-entry = {
    type: tstr                              ; catch-all: "system-event", vendor types
    ? event-type: tstr
    ? timestamp: abstract-timestamp
    ? id: entry-id
    ? children: [* entry]
    * tstr => any
}
;; MERGED: system-event-entry + vendor-entry
;; NOTE: event-entry is LAST in union — PEG semantics try specific types first
```

**Removed entirely:** `vendor-extension`, `extension-key`, `extension-data`, `token-usage`, `contributor`, `file-attribution-record`, `file`, `conversation`, `range`, `resource`, `recording-agent`, `uri-regexp`, `interactive-session`, `autonomous-session`, `session-envelope`. Also Sections 8, 10, 12, 13.

**Line count:** ~630 → ~120 (excluding signing envelope, which stays).

## CDDL Open Map Semantics

### How `* tstr => any` Works

RFC 8610 Section 3.5.4 defines this as the standard extensibility idiom. Key behaviors:

- **Cut semantics with colon syntax:** The current schema uses `:` for all field definitions (e.g., `type: "user"`). Colon syntax includes implicit "cut" semantics — once a key matches a defined entry, it is locked in and won't fall through to the wildcard. So `type: 42` fails validation even with `* tstr => any` present.
- **Wildcard catches extras:** After all defined keys are matched/skipped, remaining key-value pairs validate against `* tstr => any`.
- **No conflict:** Defined keys and the wildcard coexist without ambiguity thanks to cuts.

### IETF Precedent

| RFC | Pattern | Key Type | Notes |
|-----|---------|----------|-------|
| RFC 8610 | `* tstr => any` | Text only | Canonical extensibility idiom |
| RFC 9052 (COSE) | `* label => values` | `int / tstr` | CBOR-optimized with integer keys |
| RFC 9711 (EAT) | `$$socket //=` | Via socket | Most structured, type-safe |
| CoRIM | `$$socket //=` + negative int | Via socket | Vendor scope via negative ints |

COSE (RFC 9052) is the strongest precedent — it uses `* label => values` on COSE_Key and header maps. Since this draft already references COSE for signing, following the same extensibility pattern is defensible.

## What "Passthrough" Actually Means Per Agent

### The Nesting Problem

True passthrough only works cleanly for **flat formats**. Of the 5 agents:

- **Claude:** Content nested in `message.content`, role in `message.role`. Must un-nest. Passthrough can capture line-level fields (`parentUuid`, `isSidechain`, `userType`, `requestId`) and message-level fields (`stop_reason`, `usage`), but this requires flattening two levels.
- **Codex:** Everything nested in `payload.*`. Must unwrap envelope. Passthrough captures nothing extra — all payload fields are already extracted or structurally transformed.
- **OpenCode:** Tool data nested in `state.*`. Must un-nest. Passthrough could capture `state.title`, `state.metadata`, `state.time`, but requires flattening.
- **Gemini:** Relatively flat. Passthrough captures `tokens`, `projectHash` at message level. Cleanest case.
- **Cursor:** Nothing to pass through. Already minimal.

**Concrete example — Claude assistant line passthrough:**

```json
{
  "type": "assistant",
  "content": [...],                    // canonical (un-nested from message.content)
  "timestamp": "2026-02-10T...",       // canonical
  "id": "c2680663-...",               // canonical (renamed from uuid)
  "children": [...],                   // canonical (extracted from content blocks)
  "parentUuid": "ad554ee9-...",        // passthrough (line-level, camelCase)
  "isSidechain": false,                // passthrough (line-level, camelCase)
  "userType": "external",              // passthrough (line-level, camelCase)
  "requestId": "req_011CX...",         // passthrough (line-level, camelCase)
  "stop_reason": null,                 // passthrough (message-level, snake_case)
  "usage": { "input_tokens": 3, ... } // passthrough (message-level, nested)
}
```

Result: a mix of canonical kebab-case fields and native camelCase/snake_case passthrough. Functional but ugly.

## Parser Simplification: Honest Numbers

| Parser | Current lines | Lines eliminated | Remaining | Savings |
|--------|-------------|-----------------|-----------|---------|
| Claude | ~100 | ~0 (structural: un-nesting, children) | ~100 | **0%** |
| Gemini | ~75 | ~0 (structural: toolCall/thought → children) | ~75 | **0%** |
| Codex | ~145 | ~0 (structural: envelope unwrap + type dispatch) | ~145 | **0%** |
| OpenCode | ~145 | ~0 (structural: two-pass role attribution + tool split) | ~145 | **0%** |
| Cursor | ~30 | ~0 (already trivial) | ~30 | **0%** |
| wrap_record | ~30 | ~5 (no vendor-ext construction) | ~25 | **17%** |
| **Total** | **~530** | **~5** | **~525** | **~1%** |

Parser complexity comes from structural transforms, not field dropping. `* tstr => any` eliminates the need to explicitly ignore fields, but that was already implicit in the parsers (they simply don't reference unused fields).

## Documenting Passthrough Fields

| Approach | Pros | Cons |
|----------|------|------|
| **Don't document** — "additional fields MAY be present" | Honest, simple | Useless to consumers |
| **Per-agent appendix in the I-D** | Comprehensive | Becomes stale when agents update; bloats draft |
| **Companion registry** (informal) | Extensible, separate from spec | Maintenance burden; no enforcement |
| **Informative table** listing common fields with agent origin | Middle ground | Still becomes stale |

COSE uses IANA registration for header parameters. Agent passthrough fields change with every CLI release — registration doesn't scale. The practical answer: passthrough fields cannot be meaningfully documented in the spec.

## Three Consumer Use Cases

### Use Case A: SCITT Transparency Log Submission

**Scenario:** Enterprise submits signed session records to a SCITT transparency log for regulatory compliance.

**What the consumer needs:**
- Record boundary → `verifiable-agent-record` envelope
- Signing envelope → `signed-agent-record` (COSE_Sign1)
- Identity → `id`, `version`, `session-id`

**Assessment:** Works perfectly. SCITT consumers don't inspect individual entries — they store the signed blob. The record envelope, signing format, and identity fields all remain. `* tstr => any` on entries is irrelevant.

**Schema value: HIGH** — envelope structure and signing format are genuinely necessary.

### Use Case B: Cross-Agent Behavior Diff Tool

**Scenario:** Benchmark runner compares how 5 agents approach the same CVE fix — tool call count, iteration count, files edited, reasoning patterns.

**What the consumer needs:**
- Filter entries by type (`tool-call`, `reasoning`, etc.)
- Extract tool names and inputs
- Count entries and children
- Compare content across agents

**Assessment:** Type discriminator works — consumer can filter by canonical type values. Canonical fields (`name`, `input`, `output`) are still defined and type-safe. But for anything beyond basic counting (token usage, cost, detailed metadata), consumers need agent-specific knowledge because passthrough fields have different names per agent.

Currently, token data is dropped by ALL parsers — both schemas fail equally here. With passthrough, the data would at least be PRESERVED (e.g., Claude's `usage` object), even if not normalized. Consumers have data to work with, even if they need agent-specific logic.

**Schema value: LOW-MEDIUM** — type discrimination and canonical tool fields help with basic comparison. Anything deeper requires agent-specific adapters regardless of schema precision.

### Use Case C: Conversation Replay Viewer

**Scenario:** Developer reviews an agent's session in a web UI — user prompts, agent responses, tool calls, reasoning in chronological order.

**What the consumer needs:**
- Ordered entries → `entries: [* entry]`
- Type discrimination → `type` field
- Content → `content: any`
- Tool visualization → `name`, `input`, `output`
- Timeline → `timestamp`
- Hierarchy → `children: [* entry]`

**Assessment:** Basic structure works — entries are ordered, typed, and may have children. But `content: any` means the viewer must handle: plain strings, arrays of `{type, text}` blocks, arrays mixing text + tool_use + thinking, null/missing content, and native structured content. The viewer needs ~5 content-rendering paths regardless of schema.

The simplified schema is functionally equivalent to the current one here — `content: any` is already the current definition. Extra passthrough fields are simply ignored by the viewer.

**Schema value: MEDIUM** — entry ordering, type discrimination, and children structure are genuinely useful. Content rendering requires format-specific logic regardless.

## Honest Overall Assessment

| Dimension | Improvement | Notes |
|-----------|------------|-------|
| Schema size | **Large** (630 → 120 lines) | Real reduction in spec complexity |
| Schema readability | **Large** | 4 entry types vs 7; no vendor-extension ceremony |
| CDDL named types | **Large** (20+ → ~10) | Fewer concepts for implementers |
| Parser complexity | **Near zero** (~1% reduction) | Structural transforms dominate; field dropping is trivial |
| Consumer experience | **Neutral to slightly worse** | Passthrough fields create naming inconsistency |
| IETF reviewability | **Improved** | Less spec to review; COSE precedent for open maps |
| Field normalization | **Worse** | Mixed canonical + native field names in entries |

### The Uncomfortable Truth

Approach B is primarily a **spec simplification**, not a **translation layer simplification**. The parsers barely change because their complexity comes from structural transforms (un-nesting, children extraction, envelope unwrapping, tool splitting) — not from field dropping or vendor-extension construction.

The heavy transforms that remain unchanged:
1. Content un-nesting (Claude `message.content`, Codex `payload.content`)
2. Type mapping (every agent's roles → canonical types)
3. Children extraction (Claude tool_use/thinking blocks, Gemini toolCalls/thoughts)
4. Tool splitting (OpenCode fused objects → call + result)
5. Envelope unwrapping (Codex `{type, payload}`)
6. Metadata extraction (session-level fields scattered across lines)

To actually simplify parsers, you'd need to change the data model itself — accepting flat entries without children, fused tool objects, native nesting, or native type names. Each pushes complexity to consumers and undermines the canonical interchange format.

**Conclusion:** Approach B is worth doing for the spec simplification alone — 630 lines of over-specified CDDL becomes 120 lines of practical schema. But it should be sold honestly as a spec cleanup, not as parser simplification. The parsers will look almost identical afterward.

## Open Questions for Planning

1. **Passthrough: actually do it or not?** The parser barely benefits. Is the mixed naming (canonical + native) worth the data preservation?
2. **File attribution (Section 8):** Remove entirely, or move to a separate companion schema?
3. **Signing envelope (Section 11):** Keep as-is (it's already implemented and working)?
4. **Token usage:** Currently dropped by all parsers. Should the simplified schema define token fields, or leave to passthrough?
5. **Children:** Keep as optional on all entries, or rethink the hierarchical model?
6. **`event-entry` catch-all:** The `type: tstr` wildcard works via PEG ordering, but is it confusing for implementers?
7. **`format` field on session-trace:** `"interactive"` / `"autonomous"` distinction — keep or drop?
