# Design Decision Log

Tracks all interview questions asked and decisions made during schema and tooling development.

## 2026-02-20: End-to-End Signing Validation & SCITT Conformance

PR #16 (`scitt-ready` branch) restructured the CDDL signing envelope (Section 9) for SCITT
interoperability. The new `protected-header` requires `CWT_Claims` (label 15) with `iss` and
`sub`, but `scripts/sign-record.py` didn't populate these fields. This session fixes the
structural mismatch and adds CI-integrated end-to-end signing validation.

### Decisions

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| 1 | How to populate CWT_Claims? | **CLI args `--issuer`/`--subject` with auto-defaults** | `iss` defaults to `model-provider` (e.g. "anthropic"), `sub` defaults to `session-id`. Sensible defaults for automation; overridable for custom deployments. |
| 2 | SCITT-imported COSE_Sign1 uses `nil` instead of `null` | **Fix `nil` → `null`** | RFC 8610 uses `null`, not `nil`. The `signed-agent-record` at line 246 correctly uses `null`; the imported `COSE_Sign1` type (for Receipt validation) had a typo. |
| 3 | Signing validation approach? | **New `validate-signing.py` end-to-end script** | Self-contained pipeline: parse → sign → CDDL-validate → verify. Ephemeral keypair per run (no secrets). Covers all 5 agent formats. |
| 4 | CI integration? | **Add to existing `validate-cddl.yml`** | Extends the CDDL validation workflow with a pip install step and signing validation step. Path triggers widened to `scripts/**`. |

### CDDL Changes

- `agent-conversation.cddl` line 310: `nil` → `null` (SCITT-imported `COSE_Sign1` type)

### Signing Changes (`scripts/sign-record.py`)

- Added `CWT_CLAIMS_LABEL = 15`, `CWT_ISS_LABEL = 1`, `CWT_SUB_LABEL = 2` constants
- Added `_extract_cwt_claims()` helper: derives `iss` from `model-provider`, `sub` from `session-id`
- `cmd_sign()`: CWT_Claims map now included in protected header alongside Algorithm and ContentType
- `cmd_verify()`: extracts and displays CWT Issuer/Subject from protected header
- New CLI args: `--issuer`, `--subject` on the `sign` subcommand

### New Script (`scripts/validate-signing.py`)

End-to-end signing validation pipeline:
1. Imports `PARSERS` and `wrap_record` from `validate-sessions.py` via `importlib`
2. Picks one session per agent (first alphabetically)
3. Parses + wraps into `verifiable-agent-record`
4. Generates ephemeral Ed25519 keypair (in-memory, no secrets)
5. Signs with COSE_Sign1 including CWT_Claims
6. CDDL-validates the signed CBOR via `cddl` gem
7. Verifies signature with detached payload reattachment
8. Reports PASS/FAIL per agent, exits non-zero on any failure

### CI Changes (`.github/workflows/validate-cddl.yml`)

- Path triggers: `scripts/validate-sessions.py` → `scripts/**`
- Added: `pip install -r requirements.txt` step (pycose, cbor2)
- Renamed: existing step to "Validate unsigned records against CDDL"
- Added: "Validate signed records (end-to-end)" step

### Bug Fix: Timestamp Fallback

`_extract_trace_metadata()` in both `sign-record.py` and `validate-signing.py` previously
fell back to `"unknown"` when no session-start or record-created timestamp was available.
The `trace-metadata` CDDL type requires `timestamp-start: abstract-timestamp` (RFC 3339 or
epoch number), so `"unknown"` caused CDDL validation failures for Cursor sessions (which
lack timestamps entirely). Fixed to fall back to current UTC time at signing.

### Other Fixes

- `sign-record.py`: Updated stale "Section 11" references to "Section 9" (signing envelope
  was renumbered in the SCITT restructure)

### Validation

All 13 unsigned sessions pass. All 5 agents pass end-to-end signing validation
(sign + CDDL-validate + verify). CWT Issuer and CWT Subject displayed in verify output.

## 2026-02-19: Data Quality Review & Cleanup

Second review pass focused on produced record quality, null noise, dead fields, and consumer
experience. Inspected all 13 produced records for naming convention mixing, null pollution,
content shape diversity, and token-usage consistency.

### Decisions

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| 1 | Filter None from `_passthrough()`? | **Yes** | Fixes Claude `stop_sequence: null` noise (446 entries) and Codex `content: null` bug where native null overwrites canonical content (176 reasoning entries). No consumer benefits from null passthrough. |
| 2 | Dead `stop-reason` field in CDDL? | **Remove** | `msg.get("stop_reason")` always returns None in Claude data (streaming API only sets on final chunk). Zero real-world data across 13 sessions. Schema field had no backing. |

### Schema Changes

- Removed `stop-reason` from `message-entry` in `agent-conversation.cddl`

### Parser Changes

- `_passthrough()`: Added `and v is not None` filter — eliminates null noise from all agents
- Claude: Removed `stop_reason` from `_MSG_CONSUMED` set (no longer consumed for canonical
  mapping — passes through but filtered as null)
- Claude: Removed `stop-reason` from assistant entry construction

### Documentation Changes

- `docs/type-descriptions.md`: Added "Field Naming Convention" section documenting canonical
  kebab-case vs native passthrough naming; updated `content` field description with per-agent
  shapes; removed `stop-reason` from message-entry; added token-usage native extras note
- `docs/BREAKDOWN.md`: Updated date to 2026-02-19; updated no-drop policy to note null
  filtering; updated Claude passthrough details (renames 5→4, stop_reason removed)
- `docs/breakdown/claude-code.md`: Updated renamed/dropped/passthrough field lists
- `.claude/CLAUDE.md`: Fixed "Four entry types" → "Five", "optional session-trace" → "required"

### Validation

All 13 sessions pass. Zero null-valued fields in produced records. Codex reasoning entries
now correctly retain content (181/181, was 102/181 before fix).

## 2026-02-19: Critical Review & Schema Tightening

Comprehensive review of spec quality, usability, and IETF CDDL conventions. Multiple issues
fixed: stale documentation, dead canonical fields, overly-permissive root type, unreachable
signing type.

### Decisions

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| 1 | Make `session` required on root? | **Yes** | A `{version, id}` record is useless. The spec is about conversations; every record must have a session. |
| 2 | Dead canonical fields (stop-reason, parent-id)? | **Rename in parsers** | Populate canonical fields: `stop_reason`→`stop-reason`, `parentUuid`/`parentID`→`parent-id`. Makes canonical schema real, not aspirational. |
| 3 | Native passthrough namespace? | **Document convention** | Canonical fields use kebab-case; native fields retain original naming (camelCase, snake_case). Already ~95% true. |
| 4 | `content: any` consumer burden? | **Keep as-is** | The schema can't fix this — agents genuinely produce different shapes. Constraining the CDDL wouldn't help consumers. Document known shapes in prose. |
| 5 | `signed-agent-record` reachable from start? | **Add both + TODO** | `start = verifiable-agent-record / signed-agent-record`. Open question whether signed should be the sole start rule. |
| 6 | Rename `verifiable-agent-record`? | **Keep** | Established in codebase and docs. Rename is churn. |
| 7 | File attribution stay in schema? | **Keep with NOTE** | Henk's original contribution. TODO/NOTE comments sufficient for -00. |
| 8 | Draft `abbrev: "RATS CMW"`? | **Keep** | Set by Henk from first commit. Positioning within RATS ecosystem is intentional. |

### Schema Changes

- `session` field on `verifiable-agent-record`: optional → **required**
- `start` rule: `verifiable-agent-record` → `verifiable-agent-record / signed-agent-record`
  (with TODO comment re: signed-only start)

### Parser Changes

- Claude: `parentUuid` → `parent-id` (canonical rename, added to consumed set)
- Claude: `stop_reason` → `stop-reason` (canonical rename, added to consumed set)
- OpenCode: `parentID` → `parent-id` (canonical rename, added to consumed set)

### Documentation Updates

- `docs/CHANGELOG.md`: Added this section; fixed stale "4 entry types" → "5 entry types";
  removed `tool-call-entry`/`tool-result-entry` from "Removed" list; removed wrong `abbrev`
  open question; renumbered open questions.
- `docs/BREAKDOWN.md`: Fixed "4" → "5" entry types; updated Claude renames 3→5, OpenCode
  renames 10→11; updated passthrough/consumed details.
- `docs/breakdown/claude-code.md`: Moved `parentUuid`, `stop_reason` from dropped to renamed.
- `docs/breakdown/opencode.md`: Moved `parentID` from dropped to renamed.
- `docs/type-descriptions.md`: `session` field marked required.

### Validation

All 13 sessions pass. Canonical fields verified: `parent-id` present on Claude (349/376)
and OpenCode (123-199) entries. `stop-reason` not present (all Claude `stop_reason` values
are null in current session data — correctly skipped by `_make_entry`).

## 2026-02-19: Required Fields & Tool Entry Split

Post-review fixes to reduce schema looseness. Two changes: making empirically-required fields
mandatory, and splitting the merged `tool-entry` back into `tool-call-entry` + `tool-result-entry`.

### Required Field Changes

Analyzed field presence across all 13 sessions (6,409 entries). Five fields changed from
optional to required based on 96-100% presence in real data:

| Type | Field | Presence | Rationale |
|------|-------|----------|-----------|
| `recording-agent` | `name` | 100% (fabricated) | Every record has a recording agent name. The type is pointless without it. |
| `environment` | `working-dir` | 100% (when env present) | The environment type exists to capture working directory. |
| `vcs-context` | `type` | 100% (when vcs present) | VCS context without knowing the VCS type is useless. |
| `reasoning-entry` | `content` | 100% (may be null/empty) | Reasoning entries must carry content (even if empty string for encrypted-only). |
| `event-entry` | `event-type` | 100% | Events must have a classifier. An untyped event is meaningless. |

Unchanged: `token-usage` (stats bag — all fields optional by design), `message-entry.content`
(OpenCode message-level envelopes legitimately lack content).

### Tool Entry Split

Reversed the v3 merge of `tool-call-entry` + `tool-result-entry` into a single `tool-entry`.
The merge forced all direction-specific fields to be optional (calls need `name`+`input`,
results need `output`), making `{type: "tool-call"}` valid without any tool information.

Split back into two types with proper required fields:
- `tool-call-entry`: `name` (required), `input` (required)
- `tool-result-entry`: `output` (required)

Entry union now has 5 types: `message-entry`, `tool-call-entry`, `tool-result-entry`,
`reasoning-entry`, `event-entry`.

### Validation

All 13 sessions pass with updated schema. No parser changes needed.

## 2026-02-18: Spec Review — Fixes & Open Questions

Critical review of the full spec (CDDL, type descriptions, draft, tooling). 7 issues fixed,
5 noted as open questions for the -00 submission.

### Decisions

| # | Issue | Decision | Rationale |
|---|-------|----------|-----------|
| 3 | File attribution uses snake_case (start_line, etc.) while rest uses kebab-case | **Rename to kebab-case** | No consumers exist yet. Internal consistency. Changed: start-line, end-line, content-hash, content-hash-alg, model-id. |
| 4 | trace-metadata-key = 100 is unregistered private-use COSE label | **Add IANA comment** | Note label 100 as provisional. IANA registration required before RFC. Appropriate for -00. |
| 5 | trace-format-id hardcodes vendor strings in CDDL | **Simplify to tstr** | Vendor strings documented in comments only. CDDL stays clean; values are informational. |
| 8 | recording-agent type unused by parsers | **Implement in parsers** | Set to `{name: "vac-validate", version: "3.0.0-draft"}` in wrap_record(). Quick fix. |
| 9 | File attribution (Section 8) completely unvalidated | **Add TODO comments** | Mark as specified-but-unvalidated. Implementation is separate task. |
| 10 | No CBOR serialization despite CBOR positioning | **Implement --cbor flag** | Added `--cbor` to validate-sessions.py producing `.spec.cbor` alongside JSON via cbor2. |
| 12 | No Security Considerations section | **Note as open question** | Required for IETF but scope is for draft prose, not schema/tooling. |

### Open Questions for -00 Submission

These issues were identified during review but deferred. They need resolution before or
during the -00 submission process.

1. **Empty draft body** (#1): `draft-birkholz-verifiable-agent-conversations.md` has stub
   abstract/body with just the CDDL include. Needs substantial prose for IETF editorial review.
   The `docs/type-descriptions.md` content is ready for insertion.

2. **Entry union discrimination** (#2): The `entry` CDDL union relies on PEG-ordered choice
   with overlapping open maps (`* tstr => any`). Validators may match the wrong branch. The
   spec should acknowledge this and recommend `type`-first validation.

3. **`content: any` is maximally permissive** (#6): Zero validation on the most important
   field. Consumers can't know the shape of content. Deliberate tradeoff (Decision 10 in
   simplification plan) — draft should discuss.

4. **No version negotiation** (#7): `version: tstr` is informal. No registry, no mechanism
   for consumers to handle unknown versions or graceful degradation.

5. **Security Considerations missing** (#12): Required for all IETF documents. Should cover:
   signing threat model, key management, detached payload risks, content-hash integrity,
   no confidentiality guarantee, trust anchor bootstrapping.

## 2026-02-18: IETF CDDL Comparative Review

Compared VAC schema against established IETF CDDL schemas: RFC 9052 (COSE), draft-ietf-rats-eat
(EAT), draft-ietf-rats-corim (CoRIM), and draft-ietf-scitt-architecture (SCITT).

### Critique: String map keys vs integer keys (MAJOR)

Every IETF CBOR schema uses integer map keys for compactness. COSE uses `1 => tstr / int`,
SCITT uses `&(CWT_Claims: 15) => CWT_Claims`, CoRIM uses `&(id: 0) => $corim-id-type-choice`.
Our schema uses string keys everywhere (`version: tstr`, `id: tstr`, etc.).

This is a deliberate JSON-first design, but produces unnecessarily large CBOR encodings.
IETF convention is `&(name: int)` with an IANA registry for key assignments.

**Action**: Acknowledge JSON-primary approach in draft prose. Consider an integer key assignment
table (with IANA registry) for CBOR-optimized encoding in a future revision.

### Critique: No CDDL sockets for extensibility (MODERATE)

EAT uses group sockets (`$$Claims-Set-Claims //= (label => type)`), CoRIM uses
`* $$corim-map-extension`, allowing downstream specs to formally extend the schema and
compose with CDDL validation. Our `* tstr => any` is closest to COSE's `* label => values`
but less typed — it accepts anything, and profiles can't add fields that validators will check.

**Action**: Acceptable for -00. Plan socket-based extensibility (`$$record-extension`,
`$$entry-extension`) for -01 or later.

### Critique: No CBOR tag for root type (MODERATE)

CoRIM registers CBOR tags for type identification (`#6.501(unsigned-corim-map)`). EAT uses
tags for nesting. SCITT types are `#6.18(COSE_Sign1)`. Our `verifiable-agent-record` has no
CBOR tag, making it impossible to distinguish from arbitrary CBOR maps. A registered tag would
also solve the union discrimination problem (open question #2) if applied to entry types.

**Action**: Register a CBOR tag for `verifiable-agent-record` in IANA Considerations section.

### Critique: `content: any` has no IETF precedent (MODERATE)

No reference schema uses `any` for a primary data field. COSE uses `bstr / nil` for payload.
EAT has typed claims with size constraints (`bstr .size (8..64)`). CoRIM uses `non-empty<{}>`.
Our `content: any` means validators accept literally anything — IETF reviewers will flag this.

**Action**: Draft prose MUST justify this choice (fidelity tradeoff). Consider minimal typing
like `content: tstr / [* any] / { * tstr => any }` (string, array of blocks, or map) to
provide some shape while preserving flexibility.

### Critique: No IANA registries for entry types (MINOR)

CoRIM defines IANA registries for every extensible value. EAT registers claims. Our entry
type values (`"user"`, `"assistant"`, `"tool-call"`, etc.) are hardcoded string literals
with no extension mechanism or registry.

**Action**: Flag for future revision. An IANA registry for entry type values would enable
formal extension without schema changes.

### Critique: Missing `.cbor` constraints on signing envelope (COSMETIC)

SCITT uses `protected: bstr .cbor Protected_Header` to type the protected header bytes.
CoRIM does the same. Our `signed-agent-record` declares `protected: bstr` without the
`.cbor` constraint, losing the ability to validate header structure in CDDL alone.

**Action**: Change `protected: bstr` to `protected: bstr .cbor protected-header-map` and
define `protected-header-map = { 1 => int, 3 => tstr }` (alg + content-type).

### What matches IETF practice (confirmed correct)

- **kebab-case naming** — matches CoRIM, EAT, COSE identifier conventions
- **COSE_Sign1 envelope structure** — matches SCITT's Signed_Statement pattern exactly
- **Detached payload mode** — standard COSE pattern (`payload: bstr / null`)
- **Open map extensibility** — similar to COSE's `* label => values`
- **`?` optional field syntax** — standard CDDL throughout
- **trace-metadata in unprotected header** — analogous to SCITT's receipts placement
- **Ed25519 algorithm choice** — used across RATS/SCITT examples

### Reference schemas consulted

- RFC 9052 §§3-5: COSE_Sign1, Headers, COSE_Key (integer keys, `* label => values`)
- draft-ietf-rats-eat-31 §§4-9: EAT claims (`$$` sockets, `JC<>` dual-encoding, `.size`)
- draft-ietf-rats-corim-09 §§3-7: CoRIM maps (`&(name: N)`, `$$extension`, `$type-choice`)
- draft-ietf-scitt-architecture-10 §4.2: Signed_Statement (`* int => any`, CWT binding)

### Changes

- `agent-conversation.cddl`: Renamed file-attribution fields to kebab-case (5 fields),
  simplified `trace-format-id` to `tstr`, added IANA comment on label 100, added TODO to
  Section 8.
- `scripts/validate-sessions.py`: Added `recording-agent` to `wrap_record()`, added `--cbor`
  flag producing CBOR records via `cbor2`.
- `docs/type-descriptions.md`: Updated field names, trace-format-id description,
  recording-agent description, added JSON/CBOR note, added Section 8 unvalidated note.
- All 13 sessions pass CDDL validation. CBOR output verified.

## 2026-02-18: CDDL Comment Debloat & Type Descriptions

Moved verbose CDDL comments to a separate markdown document for the Internet-Draft body.

### Changes

- **Created `docs/type-descriptions.md`**: Detailed descriptions for every complex map type
  in the schema. 3-4 sentences per type purpose, 1-2 sentences per member. Written as raw
  markdown ready for insertion into the I-D body text.
- **Debloated `agent-conversation.cddl`**: Removed multi-paragraph rationale blocks,
  cross-references, empirical basis, specification references, JSON/CBOR explanation,
  extensibility explanation, passthrough examples (Section 11), derivation algorithm
  (Section 10), changelog, and limitations. Kept terse 1-line descriptions and inline
  member comments.
- CDDL line count: 569 → 250 total (162 code unchanged, 399 → 51 comments).
- All 13 sessions still validate. No code changes.

### Context

Coworker (Henk) requested: debloat CDDL comments, create separate .md with 3-4 sentence
type descriptions for each complex type, 1-2 sentences per member. Needed as raw markdown
for the Internet-Draft -00 submission.

## 2026-02-18: Schema Simplification v3.0.0-draft (Approach B)

Major schema rewrite: 7 entry types → 5, all maps extensible via `* tstr => any`,
no-drop policy on parsers, canonical token-usage extraction.

Full decision log with options and reasoning: [`docs/reviews/2026-02-18/simplification-plan.md`](reviews/2026-02-18/simplification-plan.md)

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

- 7 entry types → 5: `message-entry`, `tool-call-entry`, `tool-result-entry`, `reasoning-entry`, `event-entry`
- All maps: added `* tstr => any` (RFC 8610 §3.5.4 extensibility, COSE precedent)
- Removed: `vendor-extension`, `extension-key`, `extension-data`, `interactive-session`,
  `autonomous-session`, `session-envelope`, `base-entry`, `user-entry`, `assistant-entry`,
  `system-event-entry`, `vendor-entry`
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

See [`docs/reviews/2026-02-18/file-attribution-investigation.md`](reviews/2026-02-18/file-attribution-investigation.md).
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

Second review of per-agent breakdown files (`docs/breakdown/*.md`) against session data and parser code.

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
