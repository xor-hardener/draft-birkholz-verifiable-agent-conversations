# Schema Simplification Plan — Approach B

Date: 2026-02-18
Based on: [original-assessment.md](original-assessment.md)

## Decision Log

All decisions made during this planning session, with context for reviewers.

### Decision 1: Passthrough Strategy
- **Question:** Should parsers pass through native fields, keep dropping, or selectively normalize?
- **Options presented:**
  - **(A) Keep dropping** — Parsers unchanged. `* tstr => any` is just schema extensibility for
    future use. Token/cost data stays lost. Simplest option.
  - **(B) Full passthrough** — Copy ALL native fields into entries alongside canonical ones.
    Preserves everything including token usage, stop reasons, request IDs. But field names are
    inconsistent across agents (camelCase, snake_case mixed with kebab-case canonical).
  - **(C) Selective passthrough** — Pick 2-3 high-value fields to add to canonical schema (e.g.,
    token-usage, stop-reason). Normalize their names. Targeted data preservation without the mess.
  - **(D) Defer** — Ship schema with `* tstr => any`. Decide on passthrough later based on
    consumer feedback. Schema supports all three options.
- **Answer:** **C + B: Selective canonical for high-value fields + no dropping for everything else**
  - High-value fields (token usage) get canonical names in the schema
  - ALL other native fields are preserved (not dropped) — passed through as-is
  - Schema uses `* tstr => any` to accept the passthrough fields
- **Rationale:** Token usage is the highest-value data currently lost. Keeping all native fields
  means no data loss, which is the right default for an evidentiary format. The schema's
  `* tstr => any` (RFC 8610 Section 3.5.4 extensibility idiom, COSE precedent) accommodates this.
  User explicitly requested: "update implementation so we do NOT DROP ANYTHING."

### Decision 2: Native Field Placement
- **Question:** Where do non-canonical native fields appear in the produced entry?
- **Options presented:**
  - **(A) Flat merge** — Native fields at entry level alongside canonical fields. Simple but
    mixes naming conventions. Example: `{type: "assistant", content: [...], parentUuid: "...",
    stop_reason: null, usage: {input_tokens: 3}}`.
  - **(B) Nested under `native` key** — Canonical fields at top, everything else under a
    `native` sub-object. Clean separation but adds nesting. Consumers know exactly which
    fields are canonical vs agent-specific.
  - **(C) Nested under `vendor-data` key** — Same as B but using IETF-aligned naming.
    CDDL would define `? vendor-data: { * tstr => any }`.
- **Answer:** **A: Flat merge at entry level**
  - Canonical fields (type, content, timestamp, id, etc.) and native fields (parentUuid,
    stop_reason, usage, etc.) coexist at the same object level
  - No nesting under a `native` or `vendor-data` sub-key
- **Rationale:** Simplest approach. Consumers ignore fields they don't understand.
  Mixed naming (kebab-case canonical + camelCase/snake_case native) is acceptable
  because the canonical fields are well-defined and the rest is explicitly "extra."

### Decision 3: Canonical Token Usage
- **Question:** Which high-value fields should get canonical (normalized, renamed) treatment?
- **Options presented:**
  - **(A) Token usage only** — Add `? token-usage` to message-entry. 4/5 agents provide this.
    Single highest-value missing field.
  - **(B) Token usage + stop reason** — Also add `? stop-reason: tstr`. 3/5 agents provide it.
    Useful for understanding why the model stopped (end_turn, tool_use, max_tokens).
  - **(C) Token usage + stop reason + cost** — Also add `? cost: number`. Only OpenCode provides
    natively, but derivable from token counts. Useful for cost analytics.
  - **(D) Defer** — Don't add canonical fields now. Let `* tstr => any` capture everything.
    Add canonical fields later based on demand.
- **Answer:** **A: Token usage only**
  - Add `? token-usage: token-usage` to `message-entry`
  - Define `token-usage = { ? input: uint, ? output: uint, ? cached: uint, ? reasoning: uint, * tstr => any }`
  - Parsers extract and normalize token data from each agent's native format
- **Rationale:** Token usage is the one field that 4/5 agents provide, is universally
  useful for cost/performance analysis, and is currently completely lost by all parsers.
  Other candidates (stop-reason, cost) can be added later. Start minimal.

### Decision 4: File Attribution
- **Question:** Remove, extract, or keep file attribution (Sections 8, 12)?
- **Options presented:**
  - **(A) Remove entirely** — Drop Sections 8 and 12 from CDDL. Cleanest core schema. Can be
    added back later. Risk: Henk may object since it's his original contribution.
  - **(B) Separate companion file** — Move to `file-attribution.cddl`. Draft references it.
    Henk's work preserved, core schema stays lean. Moderate reorganization effort.
  - **(C) Keep in schema** — Leave as-is. ~100 lines isn't a big deal. Documents design intent.
    No political risk.
  - **(D) Ask Henk first** — Flag for discussion before deciding. Plan around either outcome.
- **Answer:** **C: Keep in schema with explicit TODO documentation**
  - Sections 8 and 12 remain in the CDDL
  - Add prominent comments marking them as unvalidated/unimplemented
  - Include file attribution investigation as a task in this plan
- **Rationale:** This is Henk Birkholz's original contribution. The ~100 extra CDDL lines are
  acceptable. User explicitly requested: "this stuff will definitely be on a todo list today —
  make sure looking into that is part of the spec." Investigation is Phase 4 of this plan.

### Decision 5: Session Types
- **Question:** Keep interactive/autonomous session split or merge into one type?
- **Options presented:**
  - **(A) Single session-trace with optional format** — One type, `? format: tstr` optional.
    Removes forced choice. Agents that want to declare format can. Simplifies CDDL.
  - **(B) Keep interactive/autonomous split** — Preserve current design. The autonomous-session
    has extra fields (`task-description`, `task-result`) that interactive doesn't. Explicit
    type discrimination.
- **Answer:** **A: Single `session-trace` with `? format: tstr`**
  - Remove `interactive-session` and `autonomous-session` named types
  - Remove `session-envelope` group composition
  - Inline all fields directly in `session-trace`
  - `format` becomes optional (not a discriminator)
- **Rationale:** In practice all 13 sessions use the same structure. The interactive/autonomous
  distinction adds CDDL complexity (group composition, choice types) without proven value.
  `task-description` / `task-result` fields can still exist via `* tstr => any` if needed.
  Agents can still declare format via the optional field.

### Decision 6: Event Entry Type
- **Question:** Should `event-entry` use `type: tstr` (catch-all) or explicit values?
- **Options presented:**
  - **(A) Explicit event types only** — `event-entry` has `type: "system-event"` only. No
    catch-all for vendor types — they go through `* tstr => any` on parent entry types.
    Cleanest CDDL, no ambiguity.
  - **(B) Keep catch-all with tstr** — `event-entry` keeps `type: tstr` as last union
    alternative. Relies on PEG ordering (specific types tried first, tstr catches rest).
    Matches current `vendor-entry` pattern.
  - **(C) Listed event types** — `event-entry` has `type: "system-event" / "lifecycle" /
    "token-count"`. Enumerate known events but no open catch-all.
- **Answer:** **A: Explicit `type: "system-event"` only**
  - No catch-all for vendor-specific entry types
  - Unknown vendor types handled by `* tstr => any` on existing entry types
  - Removes CDDL ambiguity from PEG-dependent union ordering
- **Rationale:** A `type: tstr` catch-all relies on PEG ordering (last union alternative tried
  last), which is implicit and confusing for implementers. Explicit types are clearer.
  Vendor-specific data goes in passthrough fields, not new entry types.

### Decision 7: Children Behavior
- **Question:** Currently only Claude and Gemini produce children (nested entries). Others
  produce flat entries. Keep this asymmetry or change?
- **Options presented:**
  - **(A) Keep current behavior** — Claude/Gemini produce children, others don't. Children
    are optional in schema. Asymmetric but accurate to each agent's native structure.
  - **(B) All agents produce children** — Restructure Codex/OpenCode parsers to also group
    tool-calls as children of parent messages. More consistent but adds parser complexity.
  - **(C) No children at all** — Flatten everything. Claude/Gemini entries split into separate
    top-level entries. Simpler schema but loses structural fidelity.
- **Answer:** **A: Keep current behavior**
  - Claude/Gemini produce children, Codex/OpenCode/Cursor produce flat entries
  - `? children: [* entry]` remains optional on all entry types
- **Rationale:** Accurate to each agent's native structure. Forcing children on agents that
  don't nest natively adds parser complexity for no data fidelity gain. Forcing flat entries
  on agents that DO nest loses structural information.

### Decision 8: Vendor Extension Type
- **Question:** The `vendor-extension` type (vendor + version + data) is redundant with
  `* tstr => any` on all maps. Keep it anywhere?
- **Options presented:**
  - **(A) Remove entirely** — Delete vendor-extension, extension-key, extension-data types.
    `* tstr => any` provides extensibility without ceremony. Saves ~20 CDDL lines.
  - **(B) Keep on session-trace only** — Remove from entries, keep for session-level vendor
    metadata that needs provenance tagging.
  - **(C) Keep everywhere** — Don't change. vendor-ext provides structured vendor ID (who
    added this field?). `* tstr => any` for passthrough; vendor-ext for intentional extensions.
- **Answer:** **A: Remove entirely**
  - Delete `vendor-extension`, `extension-key`, `extension-data` types
  - Remove all `? vendor-ext: vendor-extension` fields
  - `* tstr => any` on every map provides sufficient extensibility
- **Rationale:** The vendor-extension ceremony (vendor + version + data wrapper) adds CDDL
  complexity without proven value — no current parser or consumer uses it. If structured
  vendor identification is needed later, it can be re-introduced. The flat passthrough
  approach (Decision 1) makes vendor-ext redundant for our current use case.

---

## Implementation Plan

### Phase 1: Simplified CDDL Schema

**File:** `agent-conversation.cddl`

#### Changes from current schema:

| Current | Simplified | Section |
|---------|-----------|---------|
| 7 entry types | 4: message-entry, tool-entry, reasoning-entry, event-entry | 7 |
| `user-entry` + `assistant-entry` | Merged → `message-entry` with `type: "user" / "assistant"` | 7 |
| `tool-call-entry` + `tool-result-entry` | Merged → `tool-entry` with `type: "tool-call" / "tool-result"` | 7 |
| `system-event-entry` + `vendor-entry` | Merged → `event-entry` with `type: "system-event"` | 7 |
| No token-usage on entries | Add `? token-usage: token-usage` to `message-entry` | 7/9 |
| Closed entry maps | Add `* tstr => any` to all entry types | 7 |
| `vendor-extension` type | **Remove entirely** (Decision 8) | 10 |
| `interactive-session` / `autonomous-session` | Single `session-trace` with `? format: tstr` | 3 |
| `session-envelope` group | Inline fields in `session-trace` | 3 |
| File attribution (Sections 8, 12) | **Keep** — add TODO comments, investigate | 8, 12 |
| Signing envelope (Section 11) | **Keep as-is** — already implemented and tested | 11 |
| Vendor examples (Section 13) | Remove — subsumed by `* tstr => any` | 13 |

#### Entry type specifications:

**message-entry** (merges user-entry + assistant-entry):
```cddl
message-entry = {
    type: "user" / "assistant"
    ? content: any
    ? timestamp: abstract-timestamp
    ? id: entry-id
    ? model-id: tstr
    ? stop-reason: tstr
    ? parent-id: entry-id
    ? token-usage: token-usage
    ? children: [* entry]
    * tstr => any
}
```

**tool-entry** (merges tool-call-entry + tool-result-entry):
```cddl
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
```

**reasoning-entry** (unchanged except open map):
```cddl
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
```

**event-entry** (explicit type, no catch-all):
```cddl
event-entry = {
    type: "system-event"
    ? event-type: tstr
    ? timestamp: abstract-timestamp
    ? id: entry-id
    ? data: { * tstr => any }
    ? children: [* entry]
    * tstr => any
}
```

#### Types to remove entirely:
- `vendor-extension`, `extension-key`, `extension-data` (subsumed by `* tstr => any`)
- `interactive-session`, `autonomous-session` (merged into `session-trace`)
- `session-envelope` (inlined into `session-trace`)
- `contributor` (only used in file-attribution; stays there)
- Section 13 vendor composition examples (informative cruft, subsumed by open maps)

#### Types to keep:
- All Section 1 common types (abstract-timestamp, session-id, entry-id, regexps)
- Section 2 `verifiable-agent-record` (with `* tstr => any`)
- Section 3 `session-trace` (simplified, single type)
- Section 4 `agent-meta`, `recording-agent`
- Section 5 `environment`, `vcs-context`
- Section 8 `file-attribution-record` and sub-types (with TODO comments)
- Section 9 `token-usage` (with `* tstr => any`)
- Section 11 signing envelope (unchanged)
- Section 12 derivation algorithm (informative, with TODO comments)

### Phase 2: Parser Updates (`validate-sessions.py`)

#### 2a: No-drop policy

Update each parser to preserve ALL native fields. Implementation approach per agent:

**Claude parser:**
- After extracting canonical fields (type, content, timestamp, id, children), copy remaining
  line-level fields (`parentUuid`, `isSidechain`, `userType`, `requestId`, `permissionMode`,
  `slug`, `operation`) into the entry
- After extracting from `message`, copy remaining message-level fields (`stop_reason`,
  `stop_sequence`, `usage`, `id` as `message-id`) into the entry
- Skip fields already captured: `timestamp`, `sessionId`, `cwd`, `version`, `gitBranch`, `uuid`,
  `message.role`, `message.content`, `message.model` (these become canonical fields or metadata)

**Gemini parser:**
- After extracting canonical fields, copy remaining message-level fields (`tokens`,
  `projectHash`) into the entry
- For toolCall children: copy `resultDisplay`, `displayName`, `description`,
  `renderOutputAsMarkdown` into tool-call entries
- For thought children: copy `timestamp` into reasoning entries

**Codex parser:**
- After extracting canonical fields from payload, copy remaining payload fields into the entry
- For response_item entries: copy `status`, `rate_limits` where present
- For session_meta/turn_context: extract to metadata (already done), copy remaining into
  session-level passthrough

**OpenCode parser:**
- After extracting canonical fields, copy remaining object fields into the entry
- For tool objects: copy `state.title`, `state.metadata`, `state.time` into entries
- For role messages: copy `parentID`, `modelID`, `providerID`, `mode`, `agent`, `cost`,
  `tokens`, `finish` into entries
- For text objects: copy `metadata` into entries

**Cursor parser:**
- Already minimal — no fields to pass through

#### 2b: Token usage extraction (canonical)

Add token-usage normalization to each parser:

| Agent | Source | Mapping |
|-------|--------|---------|
| Claude | `message.usage` | `input_tokens` → `input`, `output_tokens` → `output`, `cache_read_input_tokens` → `cached` |
| Gemini | message-level `tokens` | `inputTokens` → `input`, `outputTokens` → `output` |
| Codex | `event_msg/token_count` payload | Parse `info` object → `input`, `output` |
| OpenCode | role-message `tokens` | Parse native structure → `input`, `output`, `cost` stays native |
| Cursor | N/A | No token data available |

Token usage goes on message-entry only (the assistant response that triggered the usage).

#### 2c: `wrap_record` updates

- Remove `vendor-ext` construction (no longer needed)
- `session-trace` now uses `? format: tstr` instead of `format: "autonomous"`
  - Decision: set `format: "interactive"` (these are human-agent conversations)
  - Or omit entirely (format is optional)

### Phase 3: Validation

1. Run `python3 scripts/validate-sessions.py` — all 13 sessions must pass with new schema
2. Run `python3 scripts/validate-sessions.py --report` — verify no data loss, check produced sizes
3. Run `python3 scripts/validate-sessions.py --dump-dir /tmp/vac-v2` — inspect produced records
4. Spot-check that native fields appear in produced entries
5. Spot-check that token-usage is correctly extracted
6. Run `ruff check` and `ruff format` on updated script
7. Run signing pipeline to verify compatibility (keygen → sign → verify)

### Phase 4: File Attribution Investigation

**Goal:** Assess what it would take to implement file attribution (Section 8) for at least one agent.

Tasks:
1. For Claude sessions: identify tool-call entries where `name` is "Edit", "Write", "Read",
   "Bash" (file-modifying). Extract `file_path` from `input`.
2. For OpenCode sessions: inspect `metadata.files[]` on tool-result entries (rich file attribution
   data: `relativePath`, `diff`, `additions`, `deletions`, `before`, `after`)
3. Prototype: generate `file-attribution-record` from one Claude session and one OpenCode session
4. Assess gaps: what data is NOT available from session traces alone?
5. Document findings in this review directory

### Phase 5: Documentation

- Update `docs/BREAKDOWN.md` — reflect parser changes (no-drop policy, token-usage canonical)
- Update `docs/CHANGELOG.md` — log all 6 decisions from this planning session
- Update `CLAUDE.md` — reflect simplified schema if needed
- Update CDDL file header comments — version, date, changelog entry

---

## Open Questions (not yet decided)

1. **`format` field value:** Should we set `format: "interactive"` on all produced records, or
   omit the field entirely since it's optional? (Low-impact; can decide during implementation.)
2. **`recording-agent` field:** Currently unused by parsers. Keep in schema or remove?
   (Leaning keep — it's small and may be useful for provenance.)
3. **Session-level passthrough:** Should session-level native data (Codex `turn_context` fields,
   OpenCode session header fields) be preserved in `session-trace` via `* tstr => any`?
   (Follows from Decision 1 — if entries don't drop, sessions shouldn't drop either.)
4. **Signing compatibility:** Does changing the schema affect the signing pipeline? (Likely no —
   signing operates on the JSON bytes, not the schema. Verify in Phase 3.)

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| CDDL validation breaks with `* tstr => any` + native fields | Low | High | Test all 13 sessions thoroughly |
| Native field passthrough bloats record size significantly | Medium | Low | Measure before/after; accept tradeoff |
| Mixed naming convention confuses consumers | Medium | Medium | Clear spec documentation distinguishing canonical vs native |
| Henk objects to file attribution changes | Low | Medium | We're keeping it, just adding TODO comments |
| Token-usage extraction is wrong for some agents | Medium | Medium | Manual verification against native data |
| Signing pipeline breaks with schema changes | Low | High | Re-run full sign/verify cycle |

---

## Estimated Scope

| Phase | Effort | Files Changed |
|-------|--------|--------------|
| 1: CDDL schema | Medium | `agent-conversation.cddl` |
| 2: Parser updates | Large | `scripts/validate-sessions.py` |
| 3: Validation | Small | (testing only) |
| 4: File attribution investigation | Medium | New files in `docs/reviews/2026-02-18/` |
| 5: Documentation | Small | `docs/BREAKDOWN.md`, `docs/CHANGELOG.md` |
