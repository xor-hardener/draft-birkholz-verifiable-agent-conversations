# DRR: CDDL Schema Unification (Henk + XOR)

**Date**: 2026-02-09
**Analysis Method**: Quint evidence-backed reasoning across 8 input documents: 2 CDDL schemas (57 + 478 lines), Henk's Internet-Draft, Agent0 blocking questions (12 questions), prior DRR (Q1-Q4), prior Council deliberation (consensus 0.62), RLM trace format extraction (4 agents, 221 sessions), IETF abstract types architecture document
**Confidence Level**: HIGH (0.80 weighted average across 4 decisions)
**Status**: READY FOR REVIEW

---

## Decision Summary

This DRR resolves the 4 blocking questions that prevent merging Henk Birkholz's `agent-convo-record` (file attribution schema, 57 lines) with XOR's `session-trace` (conversation recording schema, 478 lines) into a single IETF Internet-Draft.

The core finding is that **file attribution is a derived view of session trace data**, not an independent root type. A `session-trace` that records tool-call entries with file-modifying operations (Edit, Write, apply_patch) contains sufficient information to mechanically reconstruct most -- but not all -- of Henk's `agent-convo-record` fields. The non-derivable fields (`content_hash` over final file state, `contributor.type` human/ai/mixed classification) require a post-hoc derivation algorithm that inspects final file contents and applies attribution heuristics. The recommended architecture is **Option D**: `session-trace` is PRIMARY, with a normative derivation algorithm for `agent-convo-record` as a COMPUTED VIEW.

For extension philosophy, the evidence shows Henk's `anymap` is an acknowledged placeholder [E1:15], not a deliberate CBOR optimization. XOR's `vendor-extension` is adopted as the normative mechanism, with `anymap` retained as a CBOR-optimized alternative representation profile. The `tool` type collision is resolved by renaming Henk's `tool` to `recording-agent`, preserving XOR's `tool-call-entry` / `tool-result-entry` terminology unchanged.

---

## Q1: Root Type Architecture

### Evidence

#### Schema A: Henk's `agent-convo-record` (file-centric)

The root type [E1:1-9] defines a hierarchy:

```
agent-convo-record
  +-- version: text
  +-- id: text (UUID v4)
  +-- timestamp: text (RFC 3339)
  +-- ? vcs: { type, revision }
  +-- ? tool: { name, version }          ; the RECORDING agent
  +-- files: [* file]
  +-- ? metadata: anymap
```

Each `file` [E1:29-32] contains `path` and `conversations[]`. Each `conversation` [E1:44-49] contains `? url`, `? contributor`, `ranges[]`, and `? related`. Each `range` [E1:51-56] contains `start_line`, `end_line`, `? content_hash`, and `? contributor`.

**Information flow**: `agent-convo-record` answers the question: "For file X, which conversations produced which line ranges, and who (human/ai/mixed) contributed each range?"

#### Schema B: XOR's `session-trace` (event-centric)

The root type [E2:77-102] defines:

```
session-trace = interactive-session / autonomous-session
  +-- session-id: session-id
  +-- session-start: abstract-timestamp
  +-- ? session-end: abstract-timestamp
  +-- agent-meta: agent-meta
  +-- ? environment: environment
  +-- entries: [* entry]
  +-- ? vendor-ext: vendor-extension
```

Where `entry` [E2:175-181] is a union of user-entry, assistant-entry, tool-call-entry, tool-result-entry, reasoning-entry, system-event-entry, and vendor-entry.

**Information flow**: `session-trace` answers the question: "What happened during this coding session, step by step, with full tool invocation records?"

#### Derivability Analysis: Can `agent-convo-record` be mechanically derived from `session-trace`?

**Step-by-step derivation chain:**

1. **Identify file-modifying tool calls**: Walk `entries[]` and filter for `tool-call-entry` where `name` is one of: `Edit`, `Write`, `NotebookEdit`, `edit_file`, `write_file`, `apply_patch`, `bash` (with file-writing commands). These are identifiable by the `name` field [E2:226].

2. **Extract file path**: From `tool-call-entry.input`, extract the `file_path` field. This is present in Claude's Edit/Write tools [E4:41-43], Gemini's `edit_file` [E4:94-96], Codex's `apply_patch` (path embedded in unified diff string) [E4:186], and OpenCode's `tool` entries with `diffs[].file` [E4:253].

3. **Extract line ranges**: From `tool-call-entry.input`:
   - Claude Edit: `old_string` + `new_string` define the changed region. Line numbers require resolving against file content at that point in the session. **Not directly available** -- Edit tool uses string matching, not line numbers [E4:42].
   - Claude Write: Full file replacement, so range = entire file. Line numbers = 1 to EOF.
   - Gemini `edit_file`: Has `old_string` / `new_string` (same issue as Claude) [E4:94-96].
   - Codex `apply_patch`: Unified diff format includes `@@ -start,count +start,count @@` headers. Line numbers ARE directly available.
   - OpenCode: `diffs[].additions`, `diffs[].deletions` provide aggregate counts but NOT specific line numbers [E4:253-254]. Structured diffs with `before`/`after` provide content but line mapping requires reconstruction.

4. **Derive `file.conversations[]`**: Group tool-call entries by file path. Each session represents one "conversation" in Henk's model. The `conversation.url` can be set to a sharing URL if available (only Claude Code provides these [E5:131]).

5. **Derive `range.contributor`**: The `assistant-entry.model-id` [E2:201] preceding a tool-call identifies the model. `contributor.type` requires interpretation:
   - If model-id is present -> `"ai"`
   - If the file was also edited by a user-entry containing manual edits -> `"mixed"`
   - If no model attribution -> `"unknown"`
   This classification is HEURISTIC, not mechanical [E5:50-51].

6. **Derive `range.content_hash`**: This field [E1:54] is defined as "Hash of attributed content for position-independent tracking." Computing this requires the FINAL content of the attributed range, which is the file content AFTER all edits in the session are applied. This is NOT present in the session trace -- the trace records the edit operations, not the resulting file state. Computing `content_hash` requires replaying all edits against the original file.

**Fields NOT derivable from session-trace alone:**

| Field | Why Not Derivable | Workaround |
|-------|-------------------|------------|
| `range.start_line` / `range.end_line` | Claude/Gemini Edit tools use string matching, not line numbers. Line numbers require resolving `old_string` against file content at that point. | Derivation algorithm must replay edits sequentially, tracking file state. |
| `range.content_hash` | Requires final file content after all edits. Session trace records operations, not states. | Derivation algorithm must reconstruct final file state, then hash attributed ranges. |
| `contributor.type` = `"mixed"` | Requires determining whether BOTH human and AI edited the same range. Session trace records who requested each edit but not whether a human also typed in the file outside the agent session. | Heuristic: if session has both user-initiated edits and AI tool-calls on the same range, classify as "mixed". |
| `vcs.revision` | Henk's `vcs.revision` [E1:21] records the commit SHA at recording time. XOR's `vcs-context.commit` [E2:136] records the commit at session START. These may differ if the agent commits during the session. | Derivation algorithm uses the VCS commit at session end, or the most recent commit observable in the trace. |

**Conclusion on derivability**: File attribution is MOSTLY derivable but requires a non-trivial derivation algorithm that:
1. Replays tool-call edits sequentially to track file state
2. Resolves string-match edits to line numbers
3. Computes content hashes over final attributed ranges
4. Applies contributor classification heuristics

This derivation is deterministic given the session trace + original file contents. It is NOT derivable from the session trace ALONE without access to the original files (needed for string-match resolution).

#### Option Analysis

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A**: `session-trace` wraps `agent-convo-record` | XOR's model contains Henk's as a nested field | Preserves both. Henk's file attribution data is pre-computed. | Forces every session trace to include file attribution even when not needed. Increases envelope size. |
| **B**: `agent-convo-record` wraps `session-trace` | Henk's model contains XOR's as nested entries | Respects Henk's authorship hierarchy. | Demotes real-time conversation to metadata. Loses session-level fields (agent-meta, environment) as top-level concepts. |
| **C**: New root `verifiable-agent-record` with both as siblings | Neutral container for both types | No hierarchy -- both are equal. | Doubles spec surface area. Two root types to validate. No clear primary for implementations to target. |
| **D**: `session-trace` is PRIMARY, `agent-convo-record` is COMPUTED VIEW | Session trace is the recording format. A normative derivation algorithm produces file attribution on demand. | Clean separation of concerns. Recording (session-trace) is complete. Analysis (file attribution) is derived. Minimizes mandatory schema surface. Allows file attribution to evolve independently. | Requires a derivation algorithm spec (adds complexity). Non-trivial edge cases in string-match-to-line-number resolution. Henk may perceive his contribution as "secondary." |

#### Evidence from Henk's I-D Goals

Henk's introduction [E7:68-72] states 4 goals:

1. **Recording fidelity**: "assure that the recording of an agent conversation being proffered is the same as the agent conversation that actually occurred" -- This is a property of the SESSION TRACE, not file attribution. The session trace IS the conversation record.

2. **Extensible conversation structure**: "a general structure of agent conversations that can represent most common types of agent conversation frames, is extensible" -- Both schemas serve this. XOR's entry-level composition with vendor-extension is more extensible than Henk's `anymap`.

3. **RATS evidence generation**: "present believable evidence about how an agent conversation is recorded utilizing Evidence generation as laid out in the Remote ATtestation ProcedureS architecture" -- This requires signing. XOR's COSE_Sign1 envelope [E2:343-350] directly serves this goal. Henk's schema has NO signing mechanism.

4. **SCITT auditability**: "render conversation records auditable after the fact and enable non-repudiation" -- This requires both signing AND structured records. The session trace provides the structured record; COSE_Sign1 provides non-repudiation; file attribution provides the audit output.

**Key insight**: Goals 1-2 are served by the session trace as the recording format. Goals 3-4 are served by the signing envelope wrapping the session trace. File attribution (Henk's `agent-convo-record`) is a CONSUMPTION artifact -- it answers audit questions about file provenance AFTER the session is recorded and signed. It is an output of analysis, not an input to recording.

### Decision

**Option D: `session-trace` is PRIMARY, with a normative derivation algorithm for `agent-convo-record` as a COMPUTED VIEW.**

Rationale:
1. Session-trace contains ALL the information needed to derive file attribution (with the caveat that original file access is needed for string-match resolution and content hashing).
2. File attribution is a consumption/analysis artifact, not a recording artifact. Recording happens once (during the session). Analysis happens many times (each time someone asks "who wrote this code?").
3. Henk's 4 goals are ALL served by session-trace + COSE_Sign1. File attribution is a specific VIEW that serves the audit use case (goal 4).
4. The derivation algorithm makes the relationship between the two schemas explicit and verifiable -- a conformance test can check that a derived `agent-convo-record` is consistent with its source `session-trace`.
5. This respects Henk's contribution: file attribution is a NAMED type in the spec with normative derivation rules, not an afterthought. The I-D section structure would be: (1) Session Trace format, (2) File Attribution format, (3) Derivation algorithm, (4) Signing envelope.

**Mitigation for Henk's authorship concern** [E5:Q2]: Frame the I-D abstract as: "This document defines (1) a format for recording agent conversations, and (2) an algorithm for deriving file attribution records from conversation recordings, enabling (3) verifiable provenance for AI-generated code." This gives equal billing to conversation recording and file attribution.

### Confidence: 0.82

High confidence because the derivability analysis is grounded in concrete field-by-field mapping. The main uncertainty is in edge cases of the derivation algorithm (overlapping edits, reverts, multi-agent attribution).

---

## Q3: Tool-Call to File Attribution Bridge

### Evidence

#### The Derivation Chain (Concrete)

Given a `session-trace` with entries, the chain to file attribution is:

```
STEP 1: User sends a request
  user-entry { type: "user", content: "Fix the buffer overflow in parser.c" }

STEP 2: Assistant reasons and decides to edit
  assistant-entry { type: "assistant", model-id: "claude-opus-4-5-20251101", content: "I'll fix..." }

STEP 3: Assistant invokes Edit tool
  tool-call-entry {
    type: "tool-call",
    call-id: "toolu_abc123",
    name: "Edit",
    input: {
      "file_path": "/src/parser.c",
      "old_string": "memcpy(buf, src, len);",
      "new_string": "if (len > sizeof(buf)) return -1;\nmemcpy(buf, src, len);"
    }
  }

STEP 4: Tool result confirms success
  tool-result-entry {
    type: "tool-result",
    call-id: "toolu_abc123",
    output: "File edited successfully",
    status: "success"
  }

STEP 5: DERIVATION -> file attribution
  file {
    path: "src/parser.c",
    conversations: [{
      contributor: { type: "ai", model_id: "anthropic/claude-opus-4-5-20251101" },
      ranges: [{
        start_line: <requires resolving old_string position in file>,
        end_line: <start_line + count(new_string lines)>,
        content_hash: <SHA-256 of new_string content>,
        contributor: { type: "ai", model_id: "anthropic/claude-opus-4-5-20251101" }
      }]
    }]
  }
```

#### Field-by-Field Bridge

| `agent-convo-record` Field | Source in `session-trace` | Derivation Method | Confidence |
|---|---|---|---|
| `version` | Hardcoded by derivation tool | Static (e.g., "1.0") | N/A |
| `id` | `session-trace.session-id` or new UUID | Direct copy or generate | HIGH |
| `timestamp` | `session-trace.session-end` or max(entry timestamps) | Direct computation | HIGH |
| `vcs.type` | `environment.vcs-context.type` [E2:134] | Direct copy | HIGH |
| `vcs.revision` | `environment.vcs-context.commit` [E2:136] | Direct copy (caveat: records session START commit, not end) | MEDIUM |
| `tool.name` | `agent-meta.cli-name` [E2:113] | Direct copy | HIGH |
| `tool.version` | `agent-meta.cli-version` [E2:114] | Direct copy | HIGH |
| `files[].path` | `tool-call-entry.input.file_path` | Extract from all file-modifying tool calls | HIGH |
| `files[].conversations[].url` | No standard field; vendor-specific | Only available if sharing URL in vendor-ext | LOW |
| `files[].conversations[].contributor.type` | Inferred from session structure | Heuristic: "ai" if tool-call preceded by assistant-entry | MEDIUM |
| `files[].conversations[].contributor.model_id` | `assistant-entry.model-id` [E2:201] | Copy from the assistant entry that preceded the tool call | HIGH |
| `files[].conversations[].ranges[].start_line` | Requires file state reconstruction | Resolve `old_string` position in file at time of edit | LOW-MEDIUM |
| `files[].conversations[].ranges[].end_line` | `start_line` + line count of `new_string` | Computation | MEDIUM |
| `files[].conversations[].ranges[].content_hash` | Requires final file content | Hash `new_string` content (or final attributed region after all edits) | LOW |

#### What CANNOT Be Reconstructed from Session Trace Alone

1. **Precise line numbers for string-match edits**: Claude Code and Gemini CLI use `old_string`/`new_string` replacement semantics. The line number depends on the file state at the time of the edit, which changes with each preceding edit. The derivation algorithm must maintain a running file state model. If the original file is not available (e.g., the session trace was shared without the repository), line numbers cannot be resolved.

2. **Content hash over final file state**: The `content_hash` in Henk's schema [E1:54] is described as "Hash of attributed content for position-independent tracking." If this means hashing the final content of the attributed range (after all edits), it requires replaying all edits to determine the final state. The session trace records the operations, not the resulting state.

3. **Human contributions outside the session**: If a developer edits the same file in their text editor during an agent session, those edits are NOT in the session trace. The `contributor.type: "mixed"` classification cannot account for out-of-band edits.

4. **VCS revision at recording time vs. session time**: Henk's `vcs.revision` [E1:21] is described as the revision "when the convo was recorded." If the agent commits during the session, the revision at recording time (post-session) differs from the revision at session start. The session trace captures the starting commit [E2:136]; the recording-time commit is a post-hoc value.

#### Proposed Bridge Type

To enable derivation, the merged schema should include a NORMATIVE bridge definition:

```cddl
; Informative derivation bridge (normative algorithm in I-D Section N)
; A session-trace entry that describes a file modification
file-modification-context = (
    ; Extracted from tool-call-entry with file-modifying name
    file-path: tstr             ; from tool-call-entry.input.file_path
    ? old-content: tstr         ; from tool-call-entry.input.old_string (Edit)
    ? new-content: tstr         ; from tool-call-entry.input.new_string (Edit)
    ? full-content: tstr        ; from tool-call-entry.input.content (Write)
    ? contributor-model: tstr   ; from preceding assistant-entry.model-id
    call-id: tstr               ; from tool-call-entry.call-id (links to result)
)
```

This bridge type is NOT a new entry type -- it is a derivation TEMPLATE that the algorithm applies when interpreting `tool-call-entry` inputs. The actual tool-call-entry remains opaque (`input: any`), but the derivation algorithm knows how to interpret inputs from known tool names.

### Decision

File attribution IS derivable from session-trace entries, but the derivation requires:
1. A known mapping of tool names to file-modification semantics (Edit -> string replacement, Write -> full file replacement, apply_patch -> unified diff)
2. Access to original file contents (for string-match line number resolution) OR acceptance of content-based ranges (hash-based) instead of line-based ranges
3. A sequential replay model to track file state across multiple edits

The bridge is a DERIVATION ALGORITHM (specified normatively in the I-D), not a bridge type in CDDL. The algorithm inputs a `session-trace` and produces an `agent-convo-record`. The I-D MUST specify:
- Which tool names are recognized for file attribution (extensible registry)
- How `old_string`/`new_string` maps to line ranges
- How `content_hash` is computed (SHA-256 over the UTF-8 encoded new content)
- How `contributor.type` is classified (ai/human/mixed heuristics)

### Confidence: 0.72

Medium-high confidence. The derivation chain is well-understood for the common case (single tool-call, known tool name). Confidence is lower for edge cases: overlapping edits, reverts, bash commands that modify files indirectly, and multi-agent sessions where sub-agents use different tool names.

---

## Q6: Extension Philosophy -- `anymap` vs `vendor-extension`

### Evidence

#### Henk's `anymap` [E1:15-17]

```cddl
anymap = { * label => value }    ; placeholder for later
label = any
value = any
```

The comment "placeholder for later" [E1:15] is critical evidence. This was NOT a deliberate CBOR optimization -- it was an acknowledged temporary design that Henk intended to refine. The `label = any` choice allows CBOR integer keys (which is standard CBOR practice for compact encoding per RFC 8949 Section 3.1), but the "placeholder" comment suggests this was a convenience, not a design commitment.

Henk's I-D references CBOR [E7:76] as "the primary representation next to the established representation that is JSON." This suggests CBOR compatibility is important but not at the expense of JSON interoperability.

Usage in the schema: `anymap` appears ONCE, as `? metadata: anymap` on the root type [E1:8]. It is an optional top-level escape hatch for implementation-specific data.

#### XOR's `vendor-extension` [E2:318-323]

```cddl
vendor-extension = {
    vendor: tstr                    ; Vendor identifier
    ? version: tstr                 ; Schema version
    ? data: { * tstr => any }       ; Vendor-specific payload
}
```

Design rationale documented in Council Correction 4 [E6:381-393]:
- `any` is unfalsifiable -- it validates everything and guarantees nothing
- Wrapping in `vendor-extension` tags data with provenance (vendor) and version
- Enables future validation via schema registry lookup
- Uses `tstr` keys (JSON-compatible) instead of `any` keys (CBOR-only for integers)

Usage in the schema: `vendor-extension` appears 12 times -- on session-envelope, agent-meta, environment, vcs-context, user-entry, assistant-entry, tool-call-entry, tool-result-entry, reasoning-entry, system-event-entry, token-usage, and as the required field on vendor-entry. It is a pervasive, structured extension mechanism.

#### JSON vs CBOR Analysis

| Property | `anymap` (Henk) | `vendor-extension` (XOR) |
|----------|:---:|:---:|
| JSON compatible | PARTIAL (integer keys invalid in JSON) | YES (tstr keys = string keys) |
| CBOR compatible | YES (any key type valid) | YES (tstr keys valid in CBOR) |
| CBOR compact encoding | YES (integer keys = 1-2 bytes vs string keys = N+1 bytes) | NO (string keys only) |
| Auditable (who produced the data?) | NO (no provenance tag) | YES (vendor field required) |
| Versionable (which schema?) | NO (no version tag) | YES (version field optional) |
| Validatable against schema registry | NO (no schema identifier) | FUTURE (vendor + version -> schema lookup) |
| IETF precedent | Common in CDDL specs (CBOR-first) | Less common but aligns with SCITT transparency goals |

#### Agent0 Q6 Evidence [E5:75-81]

The Agent0 question correctly identifies the core tension:

> "Henk's approach: maximally extensible (CBOR integer keys valid), minimally verifiable. XOR's approach: tagged, auditable, JSON-compatible, CBOR-hostile for integer keys. The merge must work for BOTH JSON and CBOR representations."

However, the Agent0 question also notes [E5:81]:

> "If [anymap is a] placeholder, XOR's tagged approach is the stronger design."

The evidence confirms: `anymap` IS a placeholder [E1:15].

#### CBOR Integer Key Consideration

IETF CBOR conventions use integer keys for compact encoding (e.g., COSE headers use integer labels). If the merged schema aims to produce compact CBOR representations, integer keys in extension data would reduce payload size. However:

1. The schema is described as "JSON-first" [E2:34], and the I-D references JSON as the "established representation" [E7:76].
2. The signing envelope (COSE_Sign1) already uses CBOR with integer keys for the protected header [E2:343-350]. The TRACE PAYLOAD can be JSON (the envelope wraps opaque bytes).
3. Extension data is inherently vendor-specific and unpredictable. Assigning integer keys requires a registry, which is premature for an experimental draft.
4. Henk's `anymap` is used ONCE (root metadata). XOR's `vendor-extension` is used 12 times throughout the type hierarchy. The pervasive pattern is XOR's.

### Decision

**HYBRID: Adopt XOR's `vendor-extension` as the NORMATIVE extension mechanism. Retain Henk's `anymap` concept as an OPTIONAL CBOR-optimized alternative representation profile.**

Concrete proposal for the merged CDDL:

```cddl
; NORMATIVE extension mechanism (JSON-compatible, auditable)
vendor-extension = {
    vendor: tstr                    ; Vendor identifier (REQUIRED)
    ? version: tstr                 ; Schema version for this vendor's extensions
    ? data: extension-data          ; Vendor-specific payload
}

; Extension data: string keys for JSON compatibility
extension-data = { * tstr => any }

; INFORMATIVE: CBOR-optimized profile
; When using CBOR encoding with integer key optimization,
; implementations MAY use the following alternative:
; cbor-extension-data = { * (tstr / uint) => any }
; This profile requires a key registry (out of scope for this draft).
```

Rationale:
1. `anymap` is a self-acknowledged placeholder [E1:15]. Replacing it with a structured type is an improvement, not a contradiction.
2. `vendor-extension` serves Henk's goal 4 (auditability) by tagging extension data with provenance.
3. JSON compatibility is essential for practical adoption (all 4 agent formats are currently JSON-based [E4:340]).
4. The CBOR-optimized profile acknowledges Henk's CBOR alignment strategy without mandating integer keys in the experimental draft.
5. The integer key registry can be defined in a future draft once the extension points stabilize.

### Confidence: 0.85

High confidence. The "placeholder for later" comment [E1:15] is dispositive evidence that `anymap` was not a deliberate design. The vendor-extension pattern has been validated through the full CDDL specification exercise (478 lines, 12 usage sites) and Council review (Correction 4) [E6:381-393].

---

## Q10: Tool Type Collision

### Evidence

#### Usage Analysis in Both Schemas

**Schema A (Henk) -- `tool` type [E1:24-27]:**

```cddl
tool = {
    ? name: text
    ? version: text
}
```

This type appears at [E1:6]: `? tool: tool` on the root `agent-convo-record`. It identifies the SOFTWARE THAT GENERATED the conversation record. Example: `{ name: "claude-code", version: "2.1.34" }`. This is a METADATA field about the recording tool, not an action within the conversation.

Henk's I-D introduction [E7:68] uses the phrase "recording of an agent conversation." The `tool` type records the recording tool -- the agent that produced the trace file.

**Schema B (XOR) -- `tool-call-entry` and `tool-result-entry` [E2:222-244]:**

```cddl
tool-call-entry = {
    & base-entry
    type: "tool-call"
    call-id: tstr
    name: tstr
    input: any
}

tool-result-entry = {
    & base-entry
    type: "tool-result"
    call-id: tstr
    output: any
    ? status: tstr
    ? is-error: bool
}
```

These are ENTRY TYPES representing agent ACTIONS during the conversation. Example: the agent calls the Edit tool to modify a file. "Tool" here means "a capability the agent can invoke" (Read, Write, Edit, Bash, WebSearch, etc.).

#### Semantic Analysis

| Aspect | Henk's `tool` | XOR's `tool-call-entry` |
|--------|---------------|------------------------|
| **Refers to** | The agent software that recorded the trace | A capability the agent invoked during the session |
| **Cardinality** | One per record (top-level metadata) | Many per session (one per tool invocation) |
| **Example** | `{ name: "claude-code", version: "2.1.34" }` | `{ name: "Edit", input: { file_path: "..." } }` |
| **Level** | Session-level metadata | Entry-level action |
| **Semantic class** | Producer identification | Action log |

These are clearly distinct concepts. Using "tool" for both in a single specification would violate BCP 14 terminology precision requirements. IETF reviewers WILL flag this as ambiguous.

#### XOR's Existing Analog

XOR's `agent-meta` [E2:110-116] already captures the information that Henk's `tool` captures:

```cddl
agent-meta = {
    model-id: tstr
    model-provider: tstr
    ? cli-name: tstr               ; "claude-code", "gemini-cli", etc.
    ? cli-version: tstr            ; Semver string
    ? vendor-ext: vendor-extension
}
```

Specifically, `cli-name` + `cli-version` is semantically equivalent to Henk's `tool.name` + `tool.version`. The merge should unify these.

#### Naming Options

| Option | Henk's `tool` becomes | XOR's entries remain | Pros | Cons |
|--------|----------------------|---------------------|------|------|
| A: `recording-agent` | `recording-agent: { name, version }` | `tool-call-entry`, `tool-result-entry` | Descriptive, unambiguous. "Recording agent" = the agent that recorded | Slightly verbose. "Agent" may confuse with "AI agent" (the model). |
| B: `generator` | `generator: { name, version }` | `tool-call-entry`, `tool-result-entry` | Short, clear. "Generator" = what generated this record | Less specific than "recording-agent." |
| C: Keep `tool`, rename XOR | `tool: { name, version }` | `action-call-entry`, `action-result-entry` | Preserves Henk's term. | Requires renaming XOR's well-established types. "Action" is less standard than "tool" in LLM agent literature. |
| D: `recorder` | `recorder: { name, version }` | `tool-call-entry`, `tool-result-entry` | Short, descriptive | New term not in either schema |

#### Cross-reference with `agent-meta` Unification

Since XOR's `agent-meta` already captures `cli-name` and `cli-version`, Henk's `tool` can be MERGED INTO `agent-meta` rather than renamed as a standalone type. This eliminates the collision entirely:

```cddl
; Unified: Henk's tool.name/version -> agent-meta.cli-name/cli-version
agent-meta = {
    model-id: tstr
    model-provider: tstr
    ? cli-name: tstr          ; WAS Henk's tool.name
    ? cli-version: tstr       ; WAS Henk's tool.version
    ? vendor-ext: vendor-extension
}
```

This is the cleanest resolution because:
1. No naming collision (the `tool` type disappears entirely)
2. `agent-meta` already exists and serves the same purpose
3. Henk's `tool` fields are preserved as `cli-name` and `cli-version`
4. The root type no longer needs a separate `? tool: tool` field

### Decision

**Merge Henk's `tool` INTO XOR's `agent-meta`. Rename the concept from `tool` to `recording-agent` in normative prose for disambiguation.**

Concrete CDDL:

```cddl
; agent-meta replaces Henk's top-level "tool" field
; The recording agent is identified by cli-name + cli-version
; within the agent-meta structure
agent-meta = {
    model-id: tstr                  ; Primary model identifier
    model-provider: tstr            ; Model provider
    ? cli-name: tstr                ; Recording agent name (Henk's tool.name)
    ? cli-version: tstr             ; Recording agent version (Henk's tool.version)
    ? vendor-ext: vendor-extension
}
```

In the I-D prose, use "recording agent" when referring to the software that produced the trace, and "tool invocation" or "tool call" when referring to actions within the conversation. The terminology section (BCP 14) MUST define:

- **Recording Agent**: The software that captures and serializes agent conversations. Identified by `agent-meta.cli-name` and `agent-meta.cli-version`.
- **Tool Call**: An invocation of a capability by the agent during a conversation session. Represented by `tool-call-entry`.

### Confidence: 0.90

Very high confidence. The semantic distinction is clear, the merge into `agent-meta` is clean (both schemas already have the concept), and the terminology disambiguation is straightforward. No information is lost.

---

## Unified Root Type Proposal

Based on the 4 decisions above, the merged root type is:

```cddl
; =============================================================================
; UNIFIED ROOT TYPE: Verifiable Agent Conversation
; =============================================================================
;
; Merges:
;   - Henk Birkholz's agent-convo-record (file attribution, 57 lines)
;   - XOR's session-trace (conversation recording, 478 lines)
;
; Architecture: session-trace is PRIMARY, agent-convo-record is DERIVED
; Extension: vendor-extension (tagged, auditable, JSON-compatible)
; Signing: COSE_Sign1 envelope (independent of trace format)
;
; Terminology:
;   "recording agent" = software that produced this trace (agent-meta)
;   "tool call" = capability invocation during conversation (tool-call-entry)
; =============================================================================

; --- COMMON TYPES ---

abstract-timestamp = tstr / number
; tstr: RFC 3339 timestamp (RECOMMENDED for new implementations)
; number: epoch milliseconds (MUST accept for OpenCode compatibility)

session-id = tstr
; UUID v4, UUID v7, SHA-256 hash, or opaque string
; Implementations SHOULD use UUID v7 (RFC 9562) for new implementations

entry-id = tstr

; --- ROOT TYPE ---

; Session trace: the PRIMARY recording format
; Derivation algorithm (I-D Section N) produces agent-convo-record from this
session-trace = interactive-session / autonomous-session

interactive-session = {
    format: "interactive"
    & session-envelope
}

autonomous-session = {
    format: "autonomous"
    & session-envelope
    ? task-description: tstr
    ? task-result: tstr
}

session-envelope = (
    session-id: session-id
    session-start: abstract-timestamp
    ? session-end: abstract-timestamp
    agent-meta: agent-meta            ; Replaces Henk's top-level "tool" field
    ? environment: environment
    entries: [* entry]
    ? file-attribution: [* file]      ; OPTIONAL pre-computed file attribution
                                      ; (Henk's agent-convo-record.files)
                                      ; Implementations MAY include this OR
                                      ; derive it from entries[] post-hoc
    ? vendor-ext: vendor-extension
)

; --- AGENT METADATA (unified with Henk's "tool") ---

agent-meta = {
    model-id: tstr
    model-provider: tstr
    ? cli-name: tstr                  ; Recording agent name (was Henk's tool.name)
    ? cli-version: tstr               ; Recording agent version (was Henk's tool.version)
    ? vendor-ext: vendor-extension
}

; --- ENVIRONMENT ---

environment = {
    ? working-dir: tstr
    ? vcs: vcs-context                ; Superset of Henk's vcs type
    ? sandboxes: [* tstr]
    ? vendor-ext: vendor-extension
}

vcs-context = {
    ? type: tstr                      ; "git", "jj", "hg", "svn" (Henk's vcs.type)
    ? branch: tstr                    ; XOR addition (2/4 vendor support)
    ? commit: tstr                    ; Henk's vcs.revision + XOR's vcs-context.commit
    ? repository: tstr                ; XOR addition (1/4 vendor support)
    ? vendor-ext: vendor-extension
}

; --- ENTRY TYPES ---

entry = user-entry
      / assistant-entry
      / tool-call-entry               ; "tool" = capability invocation (NOT recording agent)
      / tool-result-entry
      / reasoning-entry
      / system-event-entry
      / vendor-entry

base-entry = (
    type: tstr
    timestamp: abstract-timestamp
    ? id: entry-id
    ? session-id: session-id
)

user-entry = {
    & base-entry
    type: "user"
    content: tstr
    ? parent-id: entry-id
    ? vendor-ext: vendor-extension
}

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

tool-call-entry = {
    & base-entry
    type: "tool-call"
    call-id: tstr
    name: tstr                        ; Tool name (Edit, Write, Bash, etc.)
    input: any
    ? vendor-ext: vendor-extension
}

tool-result-entry = {
    & base-entry
    type: "tool-result"
    call-id: tstr
    output: any
    ? status: tstr
    ? is-error: bool
    ? vendor-ext: vendor-extension
}

reasoning-entry = {
    & base-entry
    type: "reasoning"
    ? content: tstr
    ? encrypted: tstr
    ? subject: tstr
    ? vendor-ext: vendor-extension
}

system-event-entry = {
    & base-entry
    type: "system-event"
    event-type: tstr
    ? data: vendor-extension
    ? vendor-ext: vendor-extension
}

vendor-entry = {
    & base-entry
    type: tstr
    vendor-ext: vendor-extension
}

; --- TOKEN USAGE ---

token-usage = {
    ? input: uint
    ? output: uint
    ? cached: uint
    ? reasoning: uint
    ? total: uint
    ? cost: number
    ? vendor-ext: vendor-extension
}

; --- EXTENSION MECHANISM ---

; Normative: tagged, auditable, JSON-compatible
vendor-extension = {
    vendor: tstr
    ? version: tstr
    ? data: { * tstr => any }
}

; --- FILE ATTRIBUTION (Henk's types, embedded as OPTIONAL computed view) ---

; These types are derived from Henk's agent-convo-record
; They can be:
;   (a) pre-computed and embedded in session-envelope.file-attribution
;   (b) derived post-hoc by the normative derivation algorithm (I-D Section N)

file = {
    path: tstr                        ; Relative file path from repository root
    conversations: [* conversation]   ; Conversations that contributed to this file
}

contributor = {
    type: "human" / "ai" / "mixed" / "unknown"
    ? model-id: tstr                  ; models.dev convention identifier
}

conversation = {
    ? url: tstr                       ; URL to the conversation (if available)
    ? contributor: contributor        ; Default contributor for ranges
    ranges: [* range]
    ? related: [* resource]
}

resource = {
    type: tstr
    url: tstr
}

range = {
    start-line: uint
    end-line: uint
    ? content-hash: tstr              ; Hash of attributed content
    ? content-hash-alg: tstr          ; Hash algorithm (default: "sha-256")
    ? contributor: contributor        ; Override for this specific range
}

; --- SIGNING ENVELOPE (independent of trace format) ---

signed-agent-trace = #6.18([         ; COSE_Sign1 tag
    protected: bstr,
    unprotected: {
        ? trace-metadata-key => trace-metadata
    },
    payload: bstr / null,
    signature: bstr
])

trace-metadata-key = 100

trace-metadata = {
    session-id: session-id
    agent-vendor: tstr
    trace-format: trace-format-id
    timestamp-start: abstract-timestamp
    ? timestamp-end: abstract-timestamp
    ? content-hash: tstr
    ? content-hash-alg: tstr
}

trace-format-id = "ietf-unified-v0.1"
               / "ietf-abstract-v0.1"
               / "claude-jsonl"
               / "gemini-json"
               / "codex-jsonl"
               / "opencode-json"
               / tstr
```

---

## Field-by-Field Mapping

### Henk's `agent-convo-record` -> Unified Schema

| Henk Field | Henk Location | Unified Field | Unified Location | Notes |
|---|---|---|---|---|
| `version` | root:2 | `trace-format` | `trace-metadata` | Format version moves to signing envelope metadata |
| `id` | root:3 | `session-id` | `session-envelope` | Direct mapping |
| `timestamp` | root:4 | `session-start` | `session-envelope` | Recording timestamp = session start |
| `vcs.type` | vcs:20 | `vcs-context.type` | `environment` | Direct mapping; XOR adds "jj" to Henk's enum |
| `vcs.revision` | vcs:21 | `vcs-context.commit` | `environment` | Renamed: "revision" -> "commit" for clarity |
| `tool.name` | tool:25 | `agent-meta.cli-name` | `session-envelope` | **Merged into agent-meta** (resolves Q10 collision) |
| `tool.version` | tool:26 | `agent-meta.cli-version` | `session-envelope` | **Merged into agent-meta** |
| `files[]` | root:7 | `file-attribution[]` | `session-envelope` | Optional pre-computed view OR derived |
| `metadata` | root:8 | `vendor-ext` | `session-envelope` | **Replaces anymap** (resolves Q6) |
| `file.path` | file:30 | `file.path` | `file-attribution[]` | Direct mapping |
| `file.conversations[]` | file:31 | `conversation[]` | `file-attribution[]` | Direct mapping |
| `conversation.url` | conv:45 | `conversation.url` | `file-attribution[]` | Direct mapping |
| `conversation.contributor` | conv:46 | `conversation.contributor` | `file-attribution[]` | Direct mapping |
| `conversation.ranges[]` | conv:47 | `range[]` | `file-attribution[]` | Direct mapping |
| `conversation.related[]` | conv:48 | `conversation.related[]` | `file-attribution[]` | Direct mapping |
| `range.start_line` | range:52 | `range.start-line` | `file-attribution[]` | Snake_case -> kebab-case (CDDL convention) |
| `range.end_line` | range:53 | `range.end-line` | `file-attribution[]` | Snake_case -> kebab-case |
| `range.content_hash` | range:54 | `range.content-hash` | `file-attribution[]` | Snake_case -> kebab-case; added `content-hash-alg` |
| `range.contributor` | range:55 | `range.contributor` | `file-attribution[]` | Direct mapping |
| `contributor.type` | contrib:35 | `contributor.type` | Same enum values | Direct mapping |
| `contributor.model_id` | contrib:36 | `contributor.model-id` | Kebab-case | Snake_case -> kebab-case |
| `resource.type` | resource:40 | `resource.type` | Direct | Direct mapping |
| `resource.url` | resource:41 | `resource.url` | Direct | Direct mapping; regex retained informatively |
| `anymap` | line:15 | `vendor-extension` | Pervasive | **Replaced** (Q6 decision) |
| `label = any` | line:16 | `tstr` keys only | `vendor-extension.data` | **Restricted to tstr** for JSON compat |

### XOR's `session-trace` -> Unified Schema

| XOR Field | XOR Location | Unified Field | Change? |
|---|---|---|---|
| `session-trace` | line:77 | `session-trace` | NO CHANGE |
| `interactive-session` | line:80 | `interactive-session` | NO CHANGE |
| `autonomous-session` | line:85 | `autonomous-session` | NO CHANGE |
| `session-envelope` | line:94 | `session-envelope` | ADDED: `? file-attribution: [* file]` |
| `session-id` | line:95 | `session-id` | NO CHANGE |
| `session-start` | line:96 | `session-start` | NO CHANGE |
| `session-end` | line:97 | `session-end` | NO CHANGE |
| `agent-meta` | line:98 | `agent-meta` | NO CHANGE (Henk's tool merged in) |
| `environment` | line:99 | `environment` | NO CHANGE |
| `entries` | line:100 | `entries` | NO CHANGE |
| `vendor-ext` | line:101 | `vendor-ext` | NO CHANGE |
| All entry types | lines:175-281 | All entry types | NO CHANGE |
| `base-entry` | line:161 | `base-entry` | NO CHANGE |
| `vendor-extension` | line:318 | `vendor-extension` | NO CHANGE |
| `signed-agent-trace` | line:343 | `signed-agent-trace` | ADDED: `"ietf-unified-v0.1"` to format IDs |
| `trace-metadata` | line:356 | `trace-metadata` | NO CHANGE |

**Summary of changes to XOR's schema**: 2 additions, 0 modifications, 0 deletions. XOR's schema is the base, with Henk's file attribution types added as optional components.

---

## Evidence Citations

| ID | Source | Line(s) | Description |
|----|--------|---------|-------------|
| [E1] | `vendor/specs/draft-birkholz-verifiable-agent-conversations/agent-conversation.cddl` | 1-57 | Henk's complete CDDL schema (file attribution) |
| [E2] | `vendor/specs/internal-verifiable-vibes/ietf-abstract-types.cddl` | 1-478 | XOR's complete CDDL schema (session trace) |
| [E3] | `.quint/decisions/DRR-2026-02-09-ietf-abstract-types.md` | 1-492 | Prior DRR: base-entry reduction, tool abstraction, composition vs union |
| [E4] | `.quint/rlm-extractions/ietf-trace-formats.md` | 1-540 | RLM extraction: 4 agent format analysis with field mappings |
| [E5] | `.quint/agent0-questions/cddl-merge.md` | 1-200 | Agent0 blocking questions Q1-Q12 with priority ordering |
| [E6] | `.quint/council-deliberations/ietf-cddl-architecture.md` | 1-447 | Council deliberation: 3 personas, consensus 0.62, 5 mandatory corrections |
| [E7] | `vendor/specs/draft-birkholz-verifiable-agent-conversations/draft-birkholz-verifiable-agent-conversations.md` | 1-97 | Henk's Internet-Draft: 4 goals, RATS/SCITT references |
| [E8] | `vendor/specs/internal-verifiable-vibes/IETF-ABSTRACT-TYPES-ARCHITECTURE.md` | 1-145 | Architecture document: 3-layer design, coverage matrix |

### Cross-References Within This DRR

| Decision | Cites | Cited By |
|----------|-------|----------|
| Q1 (Root Type) | [E1], [E2], [E4], [E5], [E7] | Q3 (derivation depends on Q1) |
| Q3 (Tool-Call Bridge) | [E1], [E2], [E4], [E5] | Q1 (bridge feasibility confirms Option D) |
| Q6 (Extension Philosophy) | [E1]:15, [E2]:318-323, [E5]:75-81, [E6]:381-393 | Unified Root Type |
| Q10 (Tool Collision) | [E1]:24-27, [E2]:222-244, [E7]:68 | Unified Root Type, Field-by-Field Mapping |

---

## Shortcuts Not Applied

- Did NOT run CDDL validation of the unified root type proposal (no `cddl` CLI tool invocation). The proposal is based on analysis of RFC 8610 semantics and composition rules from the prior DRR [E3].
- Did NOT validate the derivation algorithm against real CVE-fixing session traces. The derivation chain in Q3 is based on the RLM trace format analysis [E4] field mappings, not empirical testing.
- Did NOT consult Henk Birkholz on the `tool` -> `agent-meta` merge decision. The analysis is based on schema semantics and the I-D prose, not author discussion.
- Did NOT implement the CBOR-optimized extension profile mentioned in Q6. This is deferred to a future draft per the decision rationale.
- All evidence citations reference specific file paths and line numbers in the working tree at `/Users/iznogood/code/xor/.worktrees/feat/ray-1-strategy/`.
